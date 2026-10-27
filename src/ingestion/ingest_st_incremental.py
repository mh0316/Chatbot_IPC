
from pathlib import Path
import hashlib
import re

import chromadb
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ARCHIVO = (
    PROJECT_ROOT
    / "documents"
    / "raw"
    / "Corpus documental Beckhoff"
    / "Material Didáctico ST"
    / "guia_structured_text_twincat3.md"
)

CHROMA_DIR = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "ipc_markdown_v3"
MODEL_NAME = "jinaai/jina-embeddings-v5-omni-nano-retrieval"

MAX_CHUNK_CHARS = 1800
MAX_EXCEPTIONAL_CHARS = 4000
BATCH_SIZE = 32



def dividir_secciones(texto):
    import re

    chunks = []
    titulo = "Introducción"
    bloque = []
    dentro_codigo = False

    def guardar():
        if not bloque:
            return

        contenido = "\n".join(bloque).strip()

        if len(contenido) < 80:
            return

        if len(contenido) > MAX_EXCEPTIONAL_CHARS:
            raise ValueError(
                f"Sección demasiado larga: {titulo} "
                f"({len(contenido)} caracteres). "
                "Debes dividirla en subsecciones."
            )

        if len(contenido) > MAX_CHUNK_CHARS:
            print(
                f"AVISO: '{titulo}' tiene "
                f"{len(contenido)} caracteres. "
                "Se conservará completo para "
                "no separar el código ST."
            )

        chunks.append({
            "seccion": titulo,
            "documento": contenido,
        })

    for linea in texto.splitlines():

        # Reconocer encabezados solo fuera
        # de bloques de código Markdown.
        es_encabezado = (
            not dentro_codigo
            and re.match(r"^#{2,3}\s+", linea)
        )

        if es_encabezado:
            guardar()
            titulo = linea.lstrip("#").strip()
            bloque = [linea]
        else:
            bloque.append(linea)

        if linea.strip().startswith("```"):
            dentro_codigo = not dentro_codigo

    if dentro_codigo:
        raise ValueError(
            "El Markdown contiene un bloque "
            "de código sin cerrar."
        )

    guardar()
    return chunks


def main():
    if not ARCHIVO.exists():
        raise FileNotFoundError(ARCHIVO)

    texto = ARCHIVO.read_text(encoding="utf-8")
    chunks = dividir_secciones(texto)

    if not chunks:
        raise RuntimeError("No se generaron chunks.")

    print("Chunks preparados:", len(chunks))

    cliente = chromadb.PersistentClient(
        path=str(CHROMA_DIR)
    )

    coleccion = cliente.get_collection(
        name=COLLECTION_NAME
    )

    cantidad_antes = coleccion.count()
    print("Registros antes:", cantidad_antes)

    ruta_relativa = ARCHIVO.relative_to(PROJECT_ROOT)

    ids = []
    documentos = []
    metadatas = []

    for indice, item in enumerate(chunks):
        contenido = item["documento"]

        # ID estable para este archivo y sección.
        clave = (
            f"{ruta_relativa}|"
            f"{item['seccion']}|"
            f"{indice}"
        )

        identificador = hashlib.sha256(
            clave.encode("utf-8")
        ).hexdigest()

        ids.append(identificador)
        documentos.append(contenido)

        metadatas.append({
            "fabricante": "Beckhoff",
            "archivo": ARCHIVO.name,
            "ruta": str(ruta_relativa),
            "seccion": item["seccion"],
            "tipo": "markdown",
            "tipo_fuente": "material_didactico_no_validado",
            "chunk_index": indice,
            "longitud_caracteres": len(contenido),
            "cantidad_palabras": len(contenido.split()),
            "plataforma": "TwinCAT 3",
            "lenguaje": "Structured Text",
        })

    print("Cargando Jina...")
    modelo = SentenceTransformer(
        MODEL_NAME,
        trust_remote_code=True,
        device="cuda",
    )

    for inicio in range(0, len(ids), BATCH_SIZE):
        fin = inicio + BATCH_SIZE

        lote_textos = documentos[inicio:fin]

        vectores = modelo.encode_document(
            lote_textos,
            batch_size=BATCH_SIZE,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        coleccion.upsert(
            ids=ids[inicio:fin],
            documents=lote_textos,
            embeddings=vectores.tolist(),
            metadatas=metadatas[inicio:fin],
        )

    print("Registros después:", coleccion.count())
    print("Ingesta finalizada.")


if __name__ == "__main__":
    main()
