import sys
from pathlib import Path

import chromadb
import torch

from sentence_transformers import (
    SentenceTransformer,
    CrossEncoder,
)


# ============================================================
# RUTAS E IMPORTACIONES
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.query_expansion import expandir_consulta


# ============================================================
# CONFIGURACIÓN
# ============================================================

CHROMA_DIR = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "ipc_markdown_v3"

EMBEDDING_MODEL_NAME = (
    "jinaai/jina-embeddings-v5-omni-nano-retrieval"
)

RERANKER_MODEL_NAME = "BAAI/bge-reranker-v2-m3"

# Número de candidatos por búsqueda.
RETRIEVAL_TOP_K = 10

# Número de documentos que recibe Qwen.
FINAL_TOP_K = 3

# Activar o desactivar Multi-Query Retrieval.
MULTI_QUERY_ENABLED = True

# Filtro provisional de documentación.
FABRICANTE_FILTRO = "Beckhoff"

# Filtros pendientes de calibración.
MAX_DISTANCE = None
MIN_RERANKER_SCORE = None

EMBEDDING_DEVICE = (
    "cuda" if torch.cuda.is_available() else "cpu"
)

RERANKER_DEVICE = "cpu"


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def prioridad_fuente(metadata):
    """
    Prioridad secundaria para desempatar resultados.
    """

    if metadata.get("tipo_fuente") == "documentacion_oficial":
        return 1

    return 0


# ============================================================
# RECUPERADOR DOCUMENTAL
# ============================================================

class RecuperadorDocumental:

    def __init__(self):
        """
        Carga modelos y conecta ChromaDB una vez
        por instancia.
        """

        print("\nInicializando recuperador documental...")

        print("\nCargando Jina Embeddings...")

        self.embedding_model = SentenceTransformer(
            EMBEDDING_MODEL_NAME,
            trust_remote_code=True,
            device=EMBEDDING_DEVICE,
        )

        print(
            "Jina cargado en:",
            self.embedding_model.device,
        )

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
        print("Registros disponibles:", self.total_documentos)

        print("\nCargando BGE Reranker...")

        self.reranker = CrossEncoder(
            RERANKER_MODEL_NAME,
            device=RERANKER_DEVICE,
        )

        print("BGE Reranker cargado.")
        print("\nRecuperador documental listo.")

    # ========================================================
    # CONSULTAS DE BÚSQUEDA
    # ========================================================

    def preparar_consultas(
        self,
        consulta: str,
        multi_query: bool,
    ) -> list[str]:
        """
        Prepara consultas originales y expandidas.

        Si la expansión no cambia la pregunta,
        evita realizar la misma búsqueda dos veces.
        """

        consultas = [consulta]

        if multi_query:
            consulta_expandida = expandir_consulta(consulta)

            if (
                consulta_expandida.strip()
                and consulta_expandida.strip() != consulta
            ):
                consultas.append(
                    consulta_expandida.strip()
                )

        return consultas

    # ========================================================
    # BÚSQUEDA VECTORIAL
    # ========================================================

    def buscar_en_chroma(
        self,
        consulta_busqueda: str,
    ) -> list[dict]:
        """
        Ejecuta una búsqueda vectorial individual.

        Retorna candidatos con sus documentos,
        metadatos y distancias.
        """

        query_embedding = self.embedding_model.encode_query(
            consulta_busqueda
        ).tolist()

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

        candidatos = []

        for doc_id, documento, metadata, distancia in zip(
            resultados["ids"][0],
            resultados["documents"][0],
            resultados["metadatas"][0],
            resultados["distances"][0],
        ):
            if not documento or not documento.strip():
                continue

            distancia = float(distancia)

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
                    "consulta_origen": consulta_busqueda,
                }
            )

        return candidatos

    # ========================================================
    # UNIFICAR CANDIDATOS
    # ========================================================

    def fusionar_candidatos(
        self,
        grupos: list[list[dict]],
    ) -> list[dict]:
        """
        Elimina documentos duplicados por ID.

        Cuando un documento aparece en ambas
        búsquedas, conserva su menor distancia
        observada y registra ambas consultas.
        """

        candidatos_unicos = {}

        for grupo in grupos:
            for candidato in grupo:
                doc_id = candidato["id"]

                if doc_id not in candidatos_unicos:
                    nuevo = candidato.copy()

                    nuevo["consultas_origen"] = [
                        candidato["consulta_origen"]
                    ]

                    candidatos_unicos[doc_id] = nuevo

                else:
                    existente = candidatos_unicos[doc_id]

                    existente["consultas_origen"].append(
                        candidato["consulta_origen"]
                    )

                    if (
                        candidato["distancia"]
                        < existente["distancia"]
                    ):
                        existente["distancia"] = (
                            candidato["distancia"]
                        )

                        existente["consulta_origen"] = (
                            candidato["consulta_origen"]
                        )

        return list(candidatos_unicos.values())

    # ========================================================
    # RECUPERACIÓN DOCUMENTAL COMPLETA
    # ========================================================

    def recuperar_documentos(
        self,
        consulta: str,
        top_final: int = FINAL_TOP_K,
        multi_query: bool = None,
    ) -> list[dict]:
        """
        Recuperación RAG con Multi-Query opcional.

        1. Valida la pregunta.
        2. Prepara pregunta original y expandida.
        3. Recupera hasta 10 candidatos por búsqueda.
        4. Fusiona los resultados por ID.
        5. Reordena con BGE usando la pregunta original.
        6. Devuelve los mejores documentos.

        No modifica la colección ChromaDB.
        """

        if not isinstance(consulta, str):
            raise TypeError(
                "La consulta debe ser una cadena de texto."
            )

        consulta = consulta.strip()

        if not consulta:
            raise ValueError(
                "La consulta no puede estar vacía."
            )

        if (
            isinstance(top_final, bool)
            or not isinstance(top_final, int)
            or top_final < 1
        ):
            raise ValueError(
                "top_final debe ser un entero positivo."
            )

        if multi_query is None:
            multi_query = MULTI_QUERY_ENABLED

        if not isinstance(multi_query, bool):
            raise TypeError(
                "multi_query debe ser True o False."
            )

        if self.total_documentos == 0:
            return []

        # ----------------------------------------------------
        # 1. PREPARAR CONSULTAS
        # ----------------------------------------------------

        consultas = self.preparar_consultas(
            consulta,
            multi_query,
        )

        # ----------------------------------------------------
        # 2. RECUPERAR CANDIDATOS
        # ----------------------------------------------------

        grupos_resultados = []

        for consulta_busqueda in consultas:
            candidatos = self.buscar_en_chroma(
                consulta_busqueda
            )

            grupos_resultados.append(candidatos)

        # ----------------------------------------------------
        # 3. FUSIONAR Y ELIMINAR DUPLICADOS
        # ----------------------------------------------------

        candidatos = self.fusionar_candidatos(
            grupos_resultados
        )

        if not candidatos:
            return []

        # ----------------------------------------------------
        # 4. PREPARAR PARES PARA BGE
        # ----------------------------------------------------

        # El reranker utiliza la pregunta original.
        pares = [
            (consulta, candidato["documento"])
            for candidato in candidatos
        ]

        # ----------------------------------------------------
        # 5. APLICAR RERANKER
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
        # 6. FILTRO OPCIONAL
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
        # 7. ORDENAR RESULTADOS
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
        # 8. SELECCIONAR RESULTADOS FINALES
        # ----------------------------------------------------

        resultados_finales = candidatos[:top_final]

        for posicion, candidato in enumerate(
            resultados_finales,
            start=1,
        ):
            candidato["posicion"] = posicion

        return resultados_finales


# ============================================================
# FUNCIÓN PÚBLICA PARA EL CHATBOT
# ============================================================

_recuperador = None


def recuperar_documentos(
    consulta: str,
    top_final: int = FINAL_TOP_K,
    multi_query: bool = None,
) -> list[dict]:
    """
    Función utilizada por generate_answer.py
    y chatbot_cli.py.

    Reutiliza los modelos dentro del mismo proceso.
    """

    global _recuperador

    if _recuperador is None:
        _recuperador = RecuperadorDocumental()

    return _recuperador.recuperar_documentos(
        consulta,
        top_final=top_final,
        multi_query=multi_query,
    )


# ============================================================
# MOSTRAR RESULTADOS EN TERMINAL
# ============================================================

def mostrar_resultados(resultados):

    print("\n" + "=" * 65)
    print("RESULTADOS DESPUÉS DEL RERANKING")
    print("=" * 65)

    if not resultados:
        print("No se encontraron documentos.")
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
            "Score BGE:",
            round(candidato["reranker_score"], 4),
        )

        print(
            "Fabricante:",
            metadata.get("fabricante", "Desconocido"),
        )

        print(
            "Tipo de fuente:",
            metadata.get("tipo_fuente", "Desconocido"),
        )

        print(
            "Archivo:",
            metadata.get("archivo", "Desconocido"),
        )

        print(
            "Sección:",
            metadata.get("seccion", "Sin sección"),
        )

        print(
            "Chunk:",
            metadata.get("chunk_index", "?"),
        )

        print(
            "Ruta:",
            metadata.get("ruta", "Desconocida"),
        )

        print(
            "Consultas de origen:",
            len(candidato["consultas_origen"]),
        )

        print("\nContenido:\n")

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

    print(
        "Multi-Query Retrieval:",
        "ACTIVADO" if MULTI_QUERY_ENABLED else "DESACTIVADO",
    )

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
                print("La consulta no puede estar vacía.")
                continue

            resultados = recuperador.recuperar_documentos(
                consulta
            )

            mostrar_resultados(resultados)

    except (KeyboardInterrupt, EOFError):
        print("\nEjecución interrumpida.")


if __name__ == "__main__":
    main()
