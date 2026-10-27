
import argparse
import ast
import hashlib
import json
import re

from pathlib import Path

import chromadb


# ============================================================
# CONFIGURACIÓN
# ============================================================

ROOT = Path.home() / "chatbot_ipc"

INGEST_SCRIPT = (
    ROOT / "src/ingestion/ingest_markdown_v3.py"
)

MARKDOWN = (
    ROOT
    / "documents/processed/twincat_tutorial"
    / "Tutorial TwinCAT 3_normalizado.md"
)

PDF_RELATIVO = (
    "documents/raw/Corpus documental Beckhoff/"
    "TwinCAT 3/Tutorial TwinCAT 3.pdf"
)

PDF_ORIGINAL = ROOT / PDF_RELATIVO

MANIFEST = (
    ROOT
    / "documents/processed/twincat_tutorial"
    / "imagenes_manifest.json"
)

CHROMA_DIR = ROOT / "chroma_db"
COLLECTION_NAME = "ipc_markdown_v3"

MODEL_NAME = "jinaai/jina-embeddings-v5-omni-nano-retrieval"

FABRICANTE = "Beckhoff"
BATCH_SIZE = 32

# Identificador estable que distingue este tutorial
# de otros documentos del corpus.
RUTA_LOGICA = (
    "Corpus documental Beckhoff/TwinCAT 3/"
    "Tutorial TwinCAT 3.pdf"
)


# ============================================================
# REUTILIZAR CHUNKING ORIGINAL SIN EJECUTAR INGESTA
# ============================================================

def cargar_funciones_chunking():
    """
    Carga únicamente las funciones del script original.

    No ejecuta su código de carga de Jina ni su
    procesamiento completo de documentos.
    """

    codigo = INGEST_SCRIPT.read_text(
        encoding="utf-8"
    )

    arbol = ast.parse(codigo)

    funciones = [
        nodo
        for nodo in arbol.body
        if isinstance(nodo, ast.FunctionDef)
    ]

    modulo = ast.Module(
        body=funciones,
        type_ignores=[],
    )

    espacio = {
        "Path": Path,
        "re": re,
        "hashlib": hashlib,
        "CHUNK_SIZE": 1800,
        "CHUNK_OVERLAP": 250,
        "MIN_CONTENT_WORDS": 15,
        "MIN_CONTENT_CHARS": 80,
    }

    exec(
        compile(
            modulo,
            str(INGEST_SCRIPT),
            "exec",
        ),
        espacio,
    )

    return espacio


# ============================================================
# PREPARAR DOCUMENTOS
# ============================================================

def preparar_registros(funciones):
    chunks, _ = funciones["procesar_markdown"](
        MARKDOWN
    )

    generar_id = funciones["generar_id"]
    contar_palabras = funciones["contar_palabras_utiles"]

    registros = []

    for indice, chunk in enumerate(chunks):

        texto = chunk["texto"]
        seccion = chunk["seccion"]

        chunk_id = generar_id(
            fabricante=FABRICANTE,
            ruta=RUTA_LOGICA,
            seccion=seccion,
            indice=indice,
        )

        # Las imágenes se conservan como referencias.
        # No se interpretan automáticamente.
        imagenes = re.findall(
            r"!\[[^\]]*\]\((assets_v2/[^)]+)\)",
            texto,
        )

        metadata = {
            "fabricante": FABRICANTE,
            "archivo": MARKDOWN.name,
            "ruta": RUTA_LOGICA,
            "seccion": seccion,
            "tipo": "markdown",
            "tipo_fuente": "material_didactico",
            "chunk_index": indice,
            "longitud_caracteres": len(texto),
            "cantidad_palabras": contar_palabras(texto),
            "documento_original": PDF_ORIGINAL.name,
            "ruta_pdf_original": PDF_RELATIVO,
            "tiene_imagenes": bool(imagenes),
            "imagenes_json": json.dumps(
                imagenes,
                ensure_ascii=False,
            ),
            "origen_ingesta": "tutorial_incremental_v1",
        }

        registros.append({
            "id": chunk_id,
            "texto": texto,
            "metadata": metadata,
        })

    return registros


# ============================================================
# COMPROBAR IDENTIFICADORES EXISTENTES
# ============================================================

def separar_registros(collection, registros):
    ids = [registro["id"] for registro in registros]

    # Evitar IDs duplicados dentro del propio tutorial.
    if len(ids) != len(set(ids)):
        raise RuntimeError(
            "Se detectaron identificadores duplicados."
        )

    existentes = collection.get(
        ids=ids,
        include=["documents", "metadatas"],
    )

    datos_existentes = {
        doc_id: (texto, metadata)
        for doc_id, texto, metadata in zip(
            existentes["ids"],
            existentes["documents"],
            existentes["metadatas"],
        )
    }

    nuevos = []
    ya_existentes = []

    for registro in registros:
        anterior = datos_existentes.get(
            registro["id"]
        )

        if anterior is None:
            nuevos.append(registro)
            continue

        texto_anterior, metadata_anterior = anterior

        if (
            texto_anterior != registro["texto"]
            or metadata_anterior != registro["metadata"]
        ):
            raise RuntimeError(
                "Existe un ID con contenido o metadatos "
                "diferentes. No se modificará la colección. "
                f"ID: {registro['id']}"
            )

        ya_existentes.append(registro)

    return nuevos, ya_existentes


# ============================================================
# VALIDAR ARCHIVOS DE ENTRADA
# ============================================================

def validar_archivos():
    for archivo in [
        INGEST_SCRIPT,
        MARKDOWN,
        PDF_ORIGINAL,
        MANIFEST,
    ]:
        if not archivo.is_file():
            raise FileNotFoundError(archivo)


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--commit",
        action="store_true",
        help="Insertar los registros faltantes en ChromaDB",
    )

    args = parser.parse_args()

    validar_archivos()

    print("\nPreparando tutorial...")

    funciones = cargar_funciones_chunking()
    registros = preparar_registros(funciones)

    cliente = chromadb.PersistentClient(
        path=str(CHROMA_DIR)
    )

    # Se exige que la colección exista.
    # No crear una nueva por accidente.
    collection = cliente.get_collection(
        name=COLLECTION_NAME
    )

    conteo_antes = collection.count()

    nuevos, existentes = separar_registros(
        collection,
        registros,
    )

    print("\n" + "=" * 60)
    print("RESUMEN DE INGESTA INCREMENTAL")
    print("=" * 60)

    print("Colección:", COLLECTION_NAME)
    print("Registros actuales:", conteo_antes)
    print("Chunks preparados:", len(registros))
    print("Chunks ya existentes:", len(existentes))
    print("Chunks nuevos:", len(nuevos))
    print("PDF original:", PDF_RELATIVO)

    print("\nMuestra de los primeros chunks:")

    for registro in registros[:5]:
        print(
            "-",
            registro["metadata"]["chunk_index"],
            "|",
            registro["metadata"]["seccion"],
            "|",
            len(registro["texto"]),
            "caracteres",
        )

    if not args.commit:
        print("\nMODO VISTA PREVIA")
        print("No se ha modificado ChromaDB.")
        print(
            "Para insertar, ejecutar nuevamente "
            "con --commit."
        )
        return

    if not nuevos:
        print("\nNo hay registros nuevos para insertar.")
        return

    # --------------------------------------------
    # Confirmar durante la ejecución
    # --------------------------------------------

    confirmacion = input(
        "\nEscribe INSERTAR para confirmar: "
    ).strip()

    if confirmacion != "INSERTAR":
        print("Operación cancelada.")
        return

    # --------------------------------------------
    # Generar embeddings
    # --------------------------------------------

    from sentence_transformers import SentenceTransformer

    print("\nCargando modelo Jina...")

    model = SentenceTransformer(
        MODEL_NAME,
        trust_remote_code=True,
        device="cuda",
    )

    print("Generando embeddings e insertando...")

    insertados = 0

    for inicio in range(0, len(nuevos), BATCH_SIZE):
        lote = nuevos[inicio:inicio + BATCH_SIZE]

        textos = [item["texto"] for item in lote]

        embeddings = model.encode_document(
            textos,
            batch_size=BATCH_SIZE,
            show_progress_bar=False,
        )

        # Comprobación adicional inmediatamente
        # antes de insertar cada lote.
        ids_lote = [item["id"] for item in lote]

        comprobacion = collection.get(
            ids=ids_lote
        )

        if comprobacion["ids"]:
            raise RuntimeError(
                "Algunos IDs aparecieron antes de la "
                "inserción. Operación detenida."
            )

        collection.add(
            ids=ids_lote,
            documents=textos,
            embeddings=embeddings.tolist(),
            metadatas=[
                item["metadata"]
                for item in lote
            ],
        )

        insertados += len(lote)

        print(
            f"Insertados: {insertados}/{len(nuevos)}"
        )

    conteo_despues = collection.count()

    print("\n" + "=" * 60)
    print("RESULTADO FINAL")
    print("=" * 60)
    print("Registros antes:", conteo_antes)
    print("Nuevos insertados:", insertados)
    print("Registros después:", conteo_despues)

    if conteo_despues != conteo_antes + insertados:
        print(
            "ADVERTENCIA: el conteo final no coincide "
            "con la suma esperada. Revisar la colección."
        )
    else:
        print("Conteo de inserción verificado.")


if __name__ == "__main__":
    main()
