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

# Nueva colección
COLLECTION_NAME = "ipc_markdown_v3"

CORPUS = {
    "Beckhoff": RAW_DIR / "Corpus documental Beckhoff",
    "CODESYS": RAW_DIR / "Corpus documental CODESYS",
}

CHUNK_SIZE = 1800
CHUNK_OVERLAP = 250

BATCH_SIZE = 32

MIN_CONTENT_WORDS = 15
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
# EXTRAER FRONT MATTER YAML
# ============================================================

def extraer_front_matter(texto: str):
    """
    Extrae front matter delimitado por:

    ---
    clave: valor
    ...
    ---

    Devuelve:
        texto_sin_yaml
        metadata_yaml

    No necesita PyYAML.
    Extrae únicamente campos simples útiles.
    """

    metadata = {}

    texto = texto.lstrip()

    patron = re.compile(
        r"^---\s*\n(.*?)\n---\s*\n?",
        flags=re.DOTALL
    )

    coincidencia = patron.match(texto)

    if not coincidencia:
        return texto, metadata

    bloque_yaml = coincidencia.group(1)

    # Campos simples que queremos conservar
    campos_permitidos = {
        "source",
        "platform",
        "domain",
        "document_key",
        "document_id",
        "title",
        "collection",
        "language",
        "selection_status",
        "collection_relevance",
        "collection_type",
        "document_type",
        "category",
        "source_relative_path",
        "score_ipc",
        "score_collection",
    }

    for linea in bloque_yaml.splitlines():

        linea = linea.strip()

        if not linea:
            continue

        if ":" not in linea:
            continue

        clave, valor = linea.split(":", 1)

        clave = clave.strip()
        valor = valor.strip()

        if clave not in campos_permitidos:
            continue

        # Quitar comillas simples o dobles
        valor = valor.strip("\"'")

        if valor:
            metadata[clave] = valor

    texto_sin_yaml = texto[
        coincidencia.end():
    ]

    return texto_sin_yaml, metadata


# ============================================================
# ELIMINAR TIMESTAMPS
# ============================================================

def eliminar_timestamps(texto: str) -> str:
    """
    Elimina timestamps habituales de transcripciones.

    Ejemplos:

    00:00:43.620 hola...
    00:01:03,540 texto...
    01:22 texto...
    [00:01:32] texto...

    Mantiene el contenido hablado.
    """

    nuevas_lineas = []

    for linea in texto.splitlines():

        # Ejemplo:
        # 00:00:43.620 hola
        linea = re.sub(
            r"^\s*\[?"
            r"\d{1,2}:\d{2}(?::\d{2})?"
            r"(?:[.,]\d{1,3})?"
            r"\]?\s*",
            "",
            linea
        )

        nuevas_lineas.append(linea)

    return "\n".join(nuevas_lineas)


# ============================================================
# DETECTAR TIPO DE FUENTE
# ============================================================

def detectar_tipo_fuente(
    ruta_archivo: Path,
    metadata_yaml: dict
) -> str:
    """
    Clasifica aproximadamente el origen documental.
    """

    ruta = str(ruta_archivo).lower()

    source = str(
        metadata_yaml.get(
            "source",
            ""
        )
    ).lower()

    # Transcripciones
    if (
        "transcrip" in ruta
        or "videos transcritos" in ruta
        or "youtube" in ruta
        or "youtube" in source
    ):
        return "transcripcion_video"

    # Documentación oficial conocida
    if (
        "beckhoff information system" in source
        or "codesys offline help" in source
        or "documentación beckhoff" in ruta
        or "documentos procesados codesys" in ruta
        or "offline help" in ruta
    ):
        return "documentacion_oficial"

    return "documentacion_tecnica"


# ============================================================
# LIMPIEZA GENERAL
# ============================================================

def limpiar_texto(texto: str) -> str:
    """
    Limpieza conservadora.

    Mantiene:
    - código
    - tablas
    - listas
    - encabezados
    - sintaxis técnica

    Elimina:
    - navegación web
    - elementos vacíos
    - ruido frecuente
    """

    texto = texto.replace("\r\n", "\n")
    texto = texto.replace("\r", "\n")

    lineas_limpias = []

    for linea in texto.splitlines():

        linea_strip = linea.strip()

        # ----------------------------------------------------
        # Navegación Prev / Next
        # ----------------------------------------------------

        if re.match(
            r"^-?\s*\[(Prev|Previous|Next)\]\(",
            linea_strip,
            flags=re.IGNORECASE
        ):
            continue

        # ----------------------------------------------------
        # Navegación web
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Encabezados sin información
        # ----------------------------------------------------

        if re.match(
            r"^#{1,6}\s+In this section:\s*$",
            linea_strip,
            flags=re.IGNORECASE
        ):
            continue

        # ----------------------------------------------------
        # Separadores aislados repetidos
        # ----------------------------------------------------

        if re.match(
            r"^\s*-{3,}\s*$",
            linea_strip
        ):
            # Lo dejamos fuera porque ya no aporta semántica
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
# CONTAR PALABRAS ÚTILES
# ============================================================

def contar_palabras_utiles(texto: str) -> int:

    texto_limpio = texto

    # Eliminar URLs
    texto_limpio = re.sub(
        r"https?://\S+",
        " ",
        texto_limpio
    )

    # Reducir sintaxis Markdown
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


# ============================================================
# DETECTAR CHUNKS POBRES
# ============================================================

def tiene_contenido_suficiente(
    texto: str
) -> bool:

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
# DIVIDIR POR SECCIONES MARKDOWN
# ============================================================

def dividir_por_secciones_markdown(
    texto: str
):

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
# FUSIONAR SECCIONES PEQUEÑAS
# ============================================================

def fusionar_secciones_pequenas(
    secciones
):
    """
    Fusiona secciones pobres con la siguiente
    cuando sea posible.
    """

    resultado = []

    i = 0

    while i < len(secciones):

        actual = secciones[i]

        titulo = actual["titulo"]
        contenido = actual["contenido"]

        if (
            not tiene_contenido_suficiente(
                contenido
            )
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
                    "contenido":
                        contenido_fusionado,
                }
            )

            i += 2
            continue

        resultado.append(actual)

        i += 1

    return resultado


# ============================================================
# DIVIDIR CHUNKS GRANDES
# ============================================================

def dividir_chunk_largo(
    texto: str,
    chunk_size: int,
    overlap: int
):

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

            # Intentar cortar por párrafo
            corte = texto.rfind(
                "\n\n",
                inicio,
                fin
            )

            # Si está demasiado atrás,
            # intentar por salto de línea
            if corte <= (
                inicio
                + int(chunk_size * 0.5)
            ):

                corte = texto.rfind(
                    "\n",
                    inicio,
                    fin
                )

            if corte > (
                inicio
                + int(chunk_size * 0.5)
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

        if nuevo_inicio <= inicio:
            nuevo_inicio = fin

        inicio = nuevo_inicio

    return chunks


# ============================================================
# PROCESAR MARKDOWN
# ============================================================

def procesar_markdown(
    ruta_archivo: Path
):
    """
    Devuelve:

    chunks
    metadata_documento
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

    # --------------------------------------------------------
    # Extraer YAML antes de limpiar
    # --------------------------------------------------------

    texto, metadata_yaml = (
        extraer_front_matter(texto)
    )

    # --------------------------------------------------------
    # Eliminar timestamps
    # --------------------------------------------------------

    texto = eliminar_timestamps(
        texto
    )

    # --------------------------------------------------------
    # Limpieza general
    # --------------------------------------------------------

    texto = limpiar_texto(
        texto
    )

    if not texto:
        return [], metadata_yaml

    # --------------------------------------------------------
    # Separación por Markdown
    # --------------------------------------------------------

    secciones = (
        dividir_por_secciones_markdown(
            texto
        )
    )

    # --------------------------------------------------------
    # Fusionar encabezados aislados
    # --------------------------------------------------------

    secciones = (
        fusionar_secciones_pequenas(
            secciones
        )
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

    return resultados, metadata_yaml


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

total_documentacion_oficial = 0
total_transcripciones = 0
total_documentacion_tecnica = 0


# ============================================================
# PROCESAR CORPUS
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

            chunks, metadata_yaml = (
                procesar_markdown(
                    archivo
                )
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

        tipo_fuente = detectar_tipo_fuente(
            archivo,
            metadata_yaml
        )

        if tipo_fuente == "documentacion_oficial":
            total_documentacion_oficial += 1

        elif tipo_fuente == "transcripcion_video":
            total_transcripciones += 1

        else:
            total_documentacion_tecnica += 1

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

                # --------------------------------------------
                # Metadata base
                # --------------------------------------------

                metadata = {
                    "fabricante":
                        fabricante,

                    "archivo":
                        archivo.name,

                    "ruta":
                        str(ruta_relativa),

                    "seccion":
                        item["seccion"],

                    "tipo":
                        "markdown",

                    "tipo_fuente":
                        tipo_fuente,

                    "chunk_index":
                        indice_global,

                    "longitud_caracteres":
                        len(item["texto"]),

                    "cantidad_palabras":
                        contar_palabras_utiles(
                            item["texto"]
                        ),
                }

                # --------------------------------------------
                # Añadir metadata YAML útil
                # --------------------------------------------

                for clave in [
                    "source",
                    "platform",
                    "domain",
                    "document_key",
                    "document_id",
                    "title",
                    "collection",
                    "language",
                    "selection_status",
                    "collection_relevance",
                    "collection_type",
                    "document_type",
                    "category",
                    "source_relative_path",
                    "score_ipc",
                    "score_collection",
                ]:

                    valor = metadata_yaml.get(
                        clave
                    )

                    if valor not in (
                        None,
                        ""
                    ):
                        metadata[
                            f"doc_{clave}"
                        ] = str(valor)

                metadatas.append(
                    metadata
                )

            collection.upsert(
                ids=ids,
                documents=textos,
                embeddings=embeddings.tolist(),
                metadatas=metadatas
            )

            total_chunks += len(batch)

        total_archivos += 1

        # ----------------------------------------------------
        # Mostrar progreso
        # ----------------------------------------------------

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
    "Documentación oficial:",
    total_documentacion_oficial
)

print(
    "Transcripciones de video:",
    total_transcripciones
)

print(
    "Otra documentación técnica:",
    total_documentacion_tecnica
)

print(
    "Colección:",
    COLLECTION_NAME
)

print(
    "Base ChromaDB:",
    CHROMA_DIR
)
