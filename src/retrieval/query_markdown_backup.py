
from pathlib import Path
import sys

import chromadb
import torch

from sentence_transformers import (
    SentenceTransformer,
    CrossEncoder,
)


# ============================================================
# CONFIGURACIÓN DEL PROYECTO
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.query_expansion import expandir_consulta


# ============================================================
# CONFIGURACIÓN DEL RECUPERADOR
# ============================================================

CHROMA_DIR = PROJECT_ROOT / "chroma_db"

COLLECTION_NAME = "ipc_markdown_v3"

EMBEDDING_MODEL_NAME = (
    "jinaai/jina-embeddings-v5-omni-nano-retrieval"
)

RERANKER_MODEL_NAME = "BAAI/bge-reranker-v2-m3"

# Candidatos recuperados inicialmente desde ChromaDB
RETRIEVAL_TOP_K = 10

# Fragmentos finales entregados al LLM
FINAL_TOP_K = 3

# Filtro provisional por fabricante.
# Cambiar a None para buscar en todos los fabricantes.
FABRICANTE_FILTRO = "Beckhoff"

# Umbrales desactivados provisionalmente.
# Se calibrarán mediante evaluación de relevancia.
MAX_DISTANCE = None
MIN_RERANKER_SCORE = None

# Dispositivos de ejecución
EMBEDDING_DEVICE = (
    "cuda" if torch.cuda.is_available() else "cpu"
)

RERANKER_DEVICE = "cpu"


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def prioridad_fuente(metadata):
    """
    Criterio secundario de desempate.

    Cuando dos candidatos obtienen el mismo score,
    prioriza la documentación oficial.
    """

    if metadata.get("tipo_fuente") == "documentacion_oficial":
        return 1

    return 0


# ============================================================
# CLASE RECUPERADOR DOCUMENTAL
# ============================================================

class RecuperadorDocumental:

    def __init__(self):
        """
        Inicializa la conexión documental y carga
        los modelos una sola vez por instancia.
        """

        print("\nInicializando recuperador documental...")

        # ----------------------------------------------------
        # 1. CARGAR JINA EMBEDDINGS
        # ----------------------------------------------------

        print("\nCargando modelo Jina...")

        self.embedding_model = SentenceTransformer(
            EMBEDDING_MODEL_NAME,
            trust_remote_code=True,
            device=EMBEDDING_DEVICE,
        )

        print(
            "Modelo Jina cargado en:",
            self.embedding_model.device,
        )

        # ----------------------------------------------------
        # 2. CONECTAR A CHROMADB
        # ----------------------------------------------------

        print("\nConectando con ChromaDB...")

        if not CHROMA_DIR.exists():
            raise FileNotFoundError(
                f"No existe el directorio: {CHROMA_DIR}"
            )

        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR)
        )

        self.collection = self.client.get_collection(
            name=COLLECTION_NAME
        )

        self.total_documentos = self.collection.count()

        print("Colección:", COLLECTION_NAME)

        print(
            "Registros disponibles:",
            self.total_documentos,
        )

        # ----------------------------------------------------
        # 3. CARGAR BGE RERANKER
        # ----------------------------------------------------

        print("\nCargando BGE Reranker...")

        self.reranker = CrossEncoder(
            RERANKER_MODEL_NAME,
            device=RERANKER_DEVICE,
        )

        print(
            "Reranker cargado:",
            RERANKER_MODEL_NAME,
        )

        print("\nRecuperador documental listo.")

    # ========================================================
    # RECUPERACIÓN DOCUMENTAL
    # ========================================================

    def recuperar_documentos(
        self,
        consulta: str,
        top_final: int = FINAL_TOP_K,
    ) -> list[dict]:
        """
        Recupera los fragmentos documentales más relevantes.

        Flujo:
        1. Validar la consulta.
        2. Expandir siglas técnicas.
        3. Generar embedding con Jina.
        4. Recuperar candidatos desde ChromaDB.
        5. Reordenar con BGE Reranker.
        6. Seleccionar los mejores resultados.

        La pregunta original se conserva para BGE
        y para el modelo generativo Qwen.

        No modifica ChromaDB.
        """

        # ----------------------------------------------------
        # VALIDACIÓN DE LA CONSULTA
        # ----------------------------------------------------

        if not isinstance(consulta, str):
            raise TypeError(
                "La consulta debe ser una cadena de texto."
            )

        consulta = consulta.strip()

        if not consulta:
            raise ValueError(
                "La consulta no puede estar vacía."
            )

        if not isinstance(top_final, int) or isinstance(
            top_final, bool
        ):
            raise TypeError(
                "top_final debe ser un número entero."
            )

        if top_final < 1:
            raise ValueError(
                "top_final debe ser mayor o igual a 1."
            )

        if self.total_documentos == 0:
            return []

        # ----------------------------------------------------
        # 1. EXPANDIR LA CONSULTA
        # ----------------------------------------------------

        consulta_busqueda = expandir_consulta(consulta)

        # ----------------------------------------------------
        # 2. GENERAR EMBEDDING CON JINA
        # ----------------------------------------------------

        query_embedding = self.embedding_model.encode_query(
            consulta_busqueda
        ).tolist()

        # ----------------------------------------------------
        # 3. RECUPERACIÓN VECTORIAL
        # ----------------------------------------------------

        top_k = min(
            RETRIEVAL_TOP_K,
            self.total_documentos,
        )

        filtro = (
            {"fabricante": FABRICANTE_FILTRO}
            if FABRICANTE_FILTRO is not None
            else None
        )

        resultados = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filtro,
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        ids = resultados["ids"][0]
        documentos = resultados["documents"][0]
        metadatos = resultados["metadatas"][0]
        distancias = resultados["distances"][0]

        # ----------------------------------------------------
        # 4. CONSTRUIR LISTA DE CANDIDATOS
        # ----------------------------------------------------

        candidatos = []

        for doc_id, documento, metadata, distancia in zip(
            ids,
            documentos,
            metadatos,
            distancias,
        ):

            if not documento or not documento.strip():
                continue

            distancia = float(distancia)

            # Filtro opcional por distancia.
            if (
                MAX_DISTANCE is not None
                and distancia > MAX_DISTANCE
            ):
                continue

            candidatos.append(
                {
                    "id": doc_id,
                    "documento": documento,
                    "metadata": metadata or {},
                    "distancia": distancia,
                }
            )

        if not candidatos:
            return []

        # ----------------------------------------------------
        # 5. PREPARAR PARES PARA EL RERANKER
        # ----------------------------------------------------

        # Se conserva la consulta original.
        pares = [
            (
                consulta,
                candidato["documento"],
            )
            for candidato in candidatos
        ]

        # ----------------------------------------------------
        # 6. CALCULAR SCORES CON BGE
        # ----------------------------------------------------

        scores = self.reranker.predict(
            pares,
            show_progress_bar=False,
        )

        for candidato, score in zip(
            candidatos,
            scores,
        ):
            candidato["reranker_score"] = float(score)

        # ----------------------------------------------------
        # 7. FILTRAR POR SCORE (OPCIONAL)
        # ----------------------------------------------------

        if MIN_RERANKER_SCORE is not None:
            candidatos = [
                candidato
                for candidato in candidatos
                if candidato["reranker_score"]
                >= MIN_RERANKER_SCORE
            ]

        if not candidatos:
            return []

        # ----------------------------------------------------
        # 8. ORDENAR POR RELEVANCIA
        # ----------------------------------------------------

        candidatos.sort(
            key=lambda candidato: (
                candidato["reranker_score"],
                prioridad_fuente(
                    candidato["metadata"]
                ),
            ),
            reverse=True,
        )

        # ----------------------------------------------------
        # 9. SELECCIONAR RESULTADOS FINALES
        # ----------------------------------------------------

        resultados_finales = candidatos[:top_final]

        for posicion, candidato in enumerate(
            resultados_finales,
            start=1,
        ):
            candidato["posicion"] = posicion

        return resultados_finales


# ============================================================
# FUNCIÓN REUTILIZABLE PARA EL RAG
# ============================================================

_recuperador = None


def recuperar_documentos(
    consulta: str,
    top_final: int = FINAL_TOP_K,
) -> list[dict]:
    """
    Función pública utilizada por generate_answer.py
    y chatbot_cli.py.

    Inicializa el recuperador solo en la primera
    llamada dentro del proceso Python.
    """

    global _recuperador

    if _recuperador is None:
        _recuperador = RecuperadorDocumental()

    return _recuperador.recuperar_documentos(
        consulta,
        top_final=top_final,
    )


# ============================================================
# PRESENTACIÓN DE RESULTADOS EN TERMINAL
# ============================================================

def mostrar_resultados(resultados):
    """
    Presenta los fragmentos recuperados.

    Esta función se utiliza únicamente cuando
    ejecutamos query_markdown.py directamente.
    """

    print("\n" + "=" * 65)
    print("RESULTADOS DESPUÉS DEL RERANKING")
    print("=" * 65)

    if not resultados:
        print("\nNo se encontraron fragmentos.")
        return

    for candidato in resultados:

        metadata = candidato["metadata"]

        print(
            f"\nRESULTADO {candidato['posicion']}"
        )

        print("-" * 65)

        print(
            "Distancia Chroma:",
            round(candidato["distancia"], 4),
        )

        print(
            "Score reranker:",
            round(candidato["reranker_score"], 4),
        )

        print(
            "Fabricante:",
            metadata.get(
                "fabricante",
                "Desconocido",
            ),
        )

        print(
            "Tipo de fuente:",
            metadata.get(
                "tipo_fuente",
                "Desconocido",
            ),
        )

        print(
            "Archivo:",
            metadata.get(
                "archivo",
                "Desconocido",
            ),
        )

        print(
            "Sección:",
            metadata.get(
                "seccion",
                "Sin sección",
            ),
        )

        print(
            "Chunk:",
            metadata.get(
                "chunk_index",
                "?",
            ),
        )

        print(
            "Ruta:",
            metadata.get(
                "ruta",
                "Desconocida",
            ),
        )

        print("\nContenido documental:\n")

        documento = candidato["documento"]

        print(documento[:1500])

        if len(documento) > 1500:
            print("\n[...]")

        print("-" * 65)


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    recuperador = RecuperadorDocumental()

    print("\n" + "=" * 65)
    print("CONSULTA DOCUMENTAL RAG")
    print("=" * 65)

    try:
        while True:

            consulta = input(
                "\nEscribe tu consulta "
                "(o 'salir' para terminar): "
            ).strip()

            if consulta.lower() == "salir":
                print("\nConsulta finalizada.")
                break

            if not consulta:
                print(
                    "\nLa consulta no puede estar vacía."
                )
                continue

            print(
                f"\nRecuperando Top {RETRIEVAL_TOP_K} "
                "y aplicando reranking..."
            )

            resultados = recuperador.recuperar_documentos(
                consulta
            )

            mostrar_resultados(resultados)

    except (KeyboardInterrupt, EOFError):
        print("\n\nEjecución interrumpida.")


if __name__ == "__main__":
    main()
