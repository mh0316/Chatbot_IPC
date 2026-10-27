from pathlib import Path
import hashlib
import re

import chromadb
from sentence_transformers import SentenceTransformer


# ============================================================
# CONFIGURACIÓN
# ============================================================

PROJECT_ROOT = Path.home() / "chatbot_ipc"

RAW_DIR = PROJECT_ROOT / "documents" / "raw"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"

MODEL_NAME = "jinaai/jina-embeddings-v5-omni-nano-retrieval"

# Nueva colección para no conservar chunks malos de la v1
COLLECTION_NAME = "ipc_markdown_v2"

CORPUS = {
    "Beckhoff": RAW_DIR / "Corpus documental Beckhoff",
    "CODESYS": RAW_DIR / "Corpus documental CODESYS",
}

# Tamaño aproximado de los chunks
CHUNK_SIZE = 1800

# Solapamiento entre chunks largos
CHUNK_OVERLAP = 250

# Tamaño de lote para embeddings
BATCH_SIZE = 32

# Un chunk debe tener al menos esta cantidad de palabras útiles
MIN_CONTENT_WORDS = 15

# Evita chunks extremadamente pequeños aunque tengan palabras
MIN_CONTENT_CHARS = 80


# ============================================================
# GENERACIÓN DE IDs
# ============================================================

def generar_id(
    fabricante: str,
    ruta: str,
    seccion: str,
    indice: int
) -> str:
    """
    Genera un ID estable para cada chunk.
    """

    texto = (
        f"{fabricante}|"
        f"{ruta}|"
        f"{seccion}|"
        f"{indice}"
    )

    return hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest()


# ============================================================
# LIMPIEZA DE MARKDOWN
# ============================================================

def limpiar_texto(texto: str) -> str:
    """
    Aplica una limpieza conservadora al Markdown.

    Se intenta conservar:
    - código;
    - listas;
    - tablas;
    - encabezados;
    - contenido técnico.

    Se elimina principalmente ruido de navegación.
    """

    texto = texto.replace("\r\n", "\n")
    texto = texto.replace("\r", "\n")

    lineas_limpias = []

    for linea in texto.splitlines():

        linea_strip = linea.strip()

        # ----------------------------------------------------
        # Ignorar navegación típica de documentación web
        # ----------------------------------------------------

        if re.match(
            r"^-?\s*\[(Prev|Previous|Next)\]\(",
            linea_strip,
            flags=re.IGNORECASE
        ):
            continue

        if re.match(
            r"^\[(Skip to main content)\]",
            linea_strip,
            flags=re.IGNORECASE
        ):
            continue

        if linea_strip.lower() in {
            "[english](#)",
            "toggle navigation",
            "search",
            "info",
            "*?*",
        }:
            continue

        # Encabezados vacíos / poco útiles
        if re.match(
            r"^#{1,6}\s+In this section:\s*$",
            linea_strip,
            flags=re.IGNORECASE
        ):
            continue

        lineas_limpias.append(linea)

    texto = "\n".join(lineas_limpias)

    # Reducir exceso de líneas vacías
    texto = re.sub(
        r"\n{4,}",
        "\n\n\n",
        texto
    )

    return texto.strip()


# ============================================================
# DETECTAR CONTENIDO ÚTIL
# ============================================================

def contar_palabras_utiles(texto: str) -> int:
    """
    Cuenta palabras ignorando buena parte de la sintaxis Markdown.
    """

    texto_limpio = texto

    # Eliminar URLs
    texto_limpio = re.sub(
        r"https?://\S+",
        " ",
        texto_limpio
    )

    # Eliminar símbolos Markdown frecuentes
    texto_limpio = re.sub(
        r"[#>*_\-\[\]\(\)`|=]+",
        " ",
        texto_limpio
    )

    palabras = re.findall(
        r"\b[\wÀ-ÿ]+\b",
        texto_limpio,
        flags=re.UNICODE
    )

    return len(palabras)


def tiene_contenido_suficiente(texto: str) -> bool:
    """
    Descarta chunks demasiado pobres.

    Ejemplos que queremos descartar:

        # EtherCAT
        ---

        ## Description of the function block
        ---

    """

    texto = texto.strip()

    if not texto:
        return False

    if len(texto) < MIN_CONTENT_CHARS:
        return False

    cantidad_palabras = contar_palabras_utiles(
        texto
    )

    if cantidad_palabras < MIN_CONTENT_WORDS:
        return False

    return True


# ============================================================
# DIVISIÓN POR SECCIONES MARKDOWN
# ============================================================

def dividir_por_secciones_markdown(texto: str):
    """
    Divide un Markdown por encabezados.

    Conserva el encabezado dentro del contenido.
    """

    lineas = texto.splitlines()

    secciones = []

    titulo_actual = "Sin sección"
    buffer = []

    for linea in lineas:

        if re.match(
            r"^#{1,6}\s+",
            linea
        ):

            if buffer:

                contenido = "\n".join(
                    buffer
                ).strip()

                if contenido:

                    secciones.append(
                        {
                            "titulo": titulo_actual,
                            "contenido": contenido,
                        }
                    )

            titulo_actual = (
                linea.lstrip("#").strip()
            )

            buffer = [linea]

        else:

            buffer.append(linea)

    if buffer:

        contenido = "\n".join(
            buffer
        ).strip()

        if contenido:

            secciones.append(
                {
                    "titulo": titulo_actual,
                    "contenido": contenido,
                }
            )

    return secciones


# ============================================================
# FUSIÓN DE SECCIONES DEMASIADO PEQUEÑAS
# ============================================================

def fusionar_secciones_pequenas(secciones):
    """
    Fusiona una sección pobre con la siguiente sección.

    Esto evita conservar títulos aislados como:

        # EtherCAT

    si inmediatamente después viene contenido útil.
    """

    resultado = []

    i = 0

    while i < len(secciones):

        actual = secciones[i]

        titulo = actual["titulo"]
        contenido = actual["contenido"]

        if (
            not tiene_contenido_suficiente(contenido)
            and i + 1 < len(secciones)
        ):

            siguiente = secciones[i + 1]

            contenido_fusionado = (
                contenido
                + "\n\n"
                + siguiente["contenido"]
            )

            resultado.append(
                {
                    "titulo": titulo,
                    "contenido": contenido_fusionado,
                }
            )

            i += 2
            continue

        resultado.append(actual)

        i += 1

    return resultado


# ============================================================
# DIVISIÓN DE SECCIONES LARGAS
# ============================================================

def dividir_chunk_largo(
    texto: str,
    chunk_size: int,
    overlap: int
):
    """
    Divide una sección demasiado grande.

    Intenta cortar por párrafos antes que por
    posición arbitraria.
    """

    if len(texto) <= chunk_size:
        return [texto]

    chunks = []

    inicio = 0

    while inicio < len(texto):

        fin = min(
            inicio + chunk_size,
            len(texto)
        )

        if fin < len(texto):

            # Primero intentar corte por párrafo
            corte = texto.rfind(
                "\n\n",
                inicio,
                fin
            )

            # Si no hay párrafo razonable,
            # intentar corte por línea
            if corte <= inicio + int(
                chunk_size * 0.5
            ):

                corte = texto.rfind(
                    "\n",
                    inicio,
                    fin
                )

            if corte > inicio + int(
                chunk_size * 0.5
            ):
                fin = corte

        chunk = texto[
            inicio:fin
        ].strip()

        if chunk:
            chunks.append(chunk)

        if fin >= len(texto):
            break

        nuevo_inicio = fin - overlap

        # Evita bucle infinito
        if nuevo_inicio <= inicio:
            nuevo_inicio = fin

        inicio = nuevo_inicio

    return chunks


# ============================================================
# PROCESAMIENTO DE UN MARKDOWN
# ============================================================

def procesar_markdown(
    ruta_archivo: Path
):
    """
    Lee un Markdown y devuelve chunks útiles
    con su sección correspondiente.
    """

    try:

        texto = ruta_archivo.read_text(
            encoding="utf-8"
        )

    except UnicodeDecodeError:

        texto = ruta_archivo.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    texto = limpiar_texto(texto)

    if not texto:
        return []

    secciones = dividir_por_secciones_markdown(
        texto
    )

    secciones = fusionar_secciones_pequenas(
        secciones
    )

    resultados = []

    for seccion in secciones:

        titulo = seccion["titulo"]
        contenido = seccion["contenido"]

        chunks = dividir_chunk_largo(
            contenido,
            CHUNK_SIZE,
            CHUNK_OVERLAP
        )

        for chunk in chunks:

            chunk = chunk.strip()

            if not tiene_contenido_suficiente(
                chunk
            ):
                continue

            resultados.append(
                {
                    "seccion": titulo,
                    "texto": chunk,
                }
            )

    return resultados


# ============================================================
# CARGAR MODELO JINA
# ============================================================

print("\nCargando modelo Jina...")

model = SentenceTransformer(
    MODEL_NAME,
    trust_remote_code=True,
    device="cuda"
)

print(
    "Modelo cargado en:",
    model.device
)


# ============================================================
# INICIALIZAR CHROMADB
# ============================================================

print("\nInicializando ChromaDB...")

client = chromadb.PersistentClient(
    path=str(CHROMA_DIR)
)

collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    metadata={
        "hnsw:space": "cosine"
    }
)

print(
    "Registros existentes:",
    collection.count()
)


# ============================================================
# ESTADÍSTICAS
# ============================================================

total_archivos = 0
total_chunks = 0
total_descartados = 0


# ============================================================
# PROCESAR AMBOS CORPUS
# ============================================================

for fabricante, corpus_dir in CORPUS.items():

    print("\n======================================")
    print(
        f"Procesando corpus: {fabricante}"
    )
    print("======================================")

    if not corpus_dir.exists():

        print(
            f"ADVERTENCIA: no existe "
            f"{corpus_dir}"
        )

        continue

    archivos_md = sorted(
        corpus_dir.rglob("*.md")
    )

    print(
        "Archivos Markdown encontrados:",
        len(archivos_md)
    )

    for numero_archivo, archivo in enumerate(
        archivos_md,
        start=1
    ):

        ruta_relativa = archivo.relative_to(
            RAW_DIR
        )

        try:

            chunks = procesar_markdown(
                archivo
            )

        except Exception as error:

            print(
                f"\nERROR procesando "
                f"{ruta_relativa}: {error}"
            )

            continue

        if not chunks:

            total_descartados += 1
            continue

        # ----------------------------------------------------
        # Procesamiento por lotes
        # ----------------------------------------------------

        for batch_inicio in range(
            0,
            len(chunks),
            BATCH_SIZE
        ):

            batch = chunks[
                batch_inicio:
                batch_inicio + BATCH_SIZE
            ]

            textos = [
                item["texto"]
                for item in batch
            ]

            # Embeddings de documentos
            embeddings = (
                model.encode_document(
                    textos,
                    batch_size=BATCH_SIZE,
                    show_progress_bar=False
                )
            )

            ids = []
            metadatas = []

            for i, item in enumerate(batch):

                indice_global = (
                    batch_inicio + i
                )

                chunk_id = generar_id(
                    fabricante=fabricante,
                    ruta=str(
                        ruta_relativa
                    ),
                    seccion=item["seccion"],
                    indice=indice_global
                )

                ids.append(
                    chunk_id
                )

                metadatas.append(
                    {
                        "fabricante": fabricante,

                        "archivo": archivo.name,

                        "ruta": str(
                            ruta_relativa
                        ),

                        "seccion":
                            item["seccion"],

                        "tipo": "markdown",

                        "chunk_index":
                            indice_global,

                        "longitud_caracteres":
                            len(item["texto"]),

                        "cantidad_palabras":
                            contar_palabras_utiles(
                                item["texto"]
                            ),
                    }
                )

            collection.upsert(
                ids=ids,
                documents=textos,
                embeddings=embeddings.tolist(),
                metadatas=metadatas
            )

            total_chunks += len(batch)

        total_archivos += 1

        # Mostrar progreso
        if numero_archivo % 25 == 0:

            print(
                f"{numero_archivo}/"
                f"{len(archivos_md)} "
                f"archivos revisados "
                f"- {total_chunks} chunks"
            )


# ============================================================
# RESULTADO FINAL
# ============================================================

print("\n======================================")
print("INGESTA FINALIZADA")
print("======================================")

print(
    "Archivos con contenido indexado:",
    total_archivos
)

print(
    "Archivos sin chunks útiles:",
    total_descartados
)

print(
    "Chunks procesados:",
    total_chunks
)

print(
    "Registros en ChromaDB:",
    collection.count()
)

print(
    "Colección:",
    COLLECTION_NAME
)

print(
    "Base ChromaDB:",
    CHROMA_DIR
)
