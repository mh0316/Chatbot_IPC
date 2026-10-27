
import sys
import time

from pathlib import Path

import chromadb

from sentence_transformers import (
    SentenceTransformer,
    CrossEncoder,
)


# ============================================================
# RUTAS DEL PROYECTO
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

EMBEDDING_MODEL = (
    "jinaai/jina-embeddings-v5-omni-nano-retrieval"
)

RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

RETRIEVAL_TOP_K = 10
FINAL_TOP_K = 3

FABRICANTE_FILTRO = "Beckhoff"

MAX_DISTANCE = None
MIN_RERANKER_SCORE = None

# Recuperación con pregunta original y expandida.
MULTI_QUERY_ENABLED = True

# Experimento:
# False = BGE utiliza pregunta original.
# True  = BGE utiliza pregunta expandida.
RERANKER_EXPANSION_ENABLED = True


# ============================================================
# RECUPERADOR DOCUMENTAL
# ============================================================

class RecuperadorDocumental:

    def __init__(self):

        print("\nInicializando recuperador documental...")

        # --------------------------------------------
        # JINA EMBEDDINGS
        # --------------------------------------------

        print("\nCargando Jina Embeddings...")

        self.embedding_model = SentenceTransformer(
            EMBEDDING_MODEL,
            trust_remote_code=True,
            device="cuda",
        )

        print(
            "Jina cargado en:",
            self.embedding_model.device,
        )

        # --------------------------------------------
        # CHROMADB
        # --------------------------------------------

        print("\nConectando con ChromaDB...")

        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR)
        )

        self.collection = self.client.get_collection(
            name=COLLECTION_NAME
        )

        print("Colección:", COLLECTION_NAME)
        print(
            "Registros disponibles:",
            self.collection.count(),
        )

        # --------------------------------------------
        # BGE RERANKER
        # --------------------------------------------

        print("\nCargando BGE Reranker...")

        self.reranker = CrossEncoder(
            RERANKER_MODEL,
            device="cpu",
            trust_remote_code=True,
        )

        print("BGE Reranker cargado.")
        print("\nRecuperador documental listo.")

    # ========================================================
    # PREPARAR CONSULTAS
    # ========================================================

    def preparar_consultas(
        self,
        consulta,
        multi_query=None,
        modo_st=False,
    ):
        if multi_query is None:
            multi_query = MULTI_QUERY_ENABLED

        consulta_original = consulta.strip()
        consultas = [consulta_original]

        # Configuración C: comportamiento original.
        if multi_query:
            expandida = expandir_consulta(
                consulta_original
            )

            if (
                expandida
                and expandida != consulta_original
            ):
                consultas.append(expandida)

        # Configuración E: consultas adicionales para ST.
        if modo_st:
            texto = consulta_original.lower()

            marcadores_st = (
                "structured text",
                "en st ",
                "codigo st",
                "código st",
                "programa st",
                "programa en st",
                "function block",
                "bloque de función",
                "bloque de funcion",
            )

            solicita_st = any(
                termino in texto
                for termino in marcadores_st
            )

            if solicita_st:
                # Caso: dos motores con exclusión mutua.
                if (
                    "motor" in texto
                    and any(
                        termino in texto
                        for termino in (
                            "simultán",
                            "simultan",
                            "enclavamiento",
                            "interbloqueo",
                        )
                    )
                ):
                    consultas.extend([
                        (
                            "TwinCAT Structured Text "
                            "motor interlock mutual exclusion"
                        ),
                        (
                            "PLC Structured Text two motors "
                            "interlocking AND NOT"
                        ),
                    ])

                # Caso: cinta transportadora.
                elif (
                    "cinta" in texto
                    or "transportador" in texto
                ):
                    consultas.extend([
                        (
                            "TwinCAT Structured Text "
                            "conveyor start stop sensor "
                            "function block"
                        ),
                        (
                            "PLC motor start stop latch "
                            "rising edge restart prevention"
                        ),
                    ])

                # Otras consultas que solicitan ST.
                else:
                    consultas.append(
                        "TwinCAT 3 IEC 61131-3 "
                        "Structured Text programming "
                        + consulta_original
                    )

        # Desduplicación de consultas.
        unicas = []
        vistas = set()

        for pregunta in consultas:
            clave = " ".join(
                pregunta.lower().split()
            )

            if clave not in vistas:
                vistas.add(clave)
                unicas.append(pregunta)

        return unicas

    # ========================================================
    # BÚSQUEDA INICIAL: JINA + CHROMADB
    # ========================================================

    def buscar_en_chroma(self, consulta_busqueda):

        embedding = self.embedding_model.encode_query(
            consulta_busqueda,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        filtro = None

        if FABRICANTE_FILTRO:
            filtro = {
                "fabricante": FABRICANTE_FILTRO
            }

        resultados = self.collection.query(
            query_embeddings=[
                embedding.tolist()
            ],
            n_results=RETRIEVAL_TOP_K,
            where=filtro,
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        candidatos = []

        ids = resultados["ids"][0]
        documentos = resultados["documents"][0]
        metadatas = resultados["metadatas"][0]
        distancias = resultados["distances"][0]

        for doc_id, documento, metadata, distancia in zip(
            ids,
            documentos,
            metadatas,
            distancias,
        ):

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
                    "consultas_origen": [
                        consulta_busqueda
                    ],
                }
            )

        return candidatos

    # ========================================================
    # FUSIONAR CANDIDATOS
    # ========================================================

    def fusionar_candidatos(self, grupos):

        documentos_unicos = {}

        for grupo in grupos:

            for candidato in grupo:

                doc_id = candidato["id"]

                if doc_id not in documentos_unicos:

                    documentos_unicos[doc_id] = {
                        **candidato,
                        "consultas_origen": list(
                            candidato.get(
                                "consultas_origen",
                                [],
                            )
                        ),
                    }

                else:

                    existente = documentos_unicos[doc_id]

                    existente["distancia"] = min(
                        existente["distancia"],
                        candidato["distancia"],
                    )

                    for origen in candidato.get(
                        "consultas_origen",
                        [],
                    ):
                        if origen not in existente[
                            "consultas_origen"
                        ]:
                            existente[
                                "consultas_origen"
                            ].append(origen)

        return list(documentos_unicos.values())

    # ========================================================
    # CONSULTA PARA BGE
    # ========================================================

    def preparar_consulta_reranker(
        self,
        consulta_original,
        usar_expansion=None,
    ):

        if usar_expansion is None:
            usar_expansion = (
                RERANKER_EXPANSION_ENABLED
            )

        if not usar_expansion:
            return consulta_original.strip()

        consulta_expandida = expandir_consulta(
            consulta_original.strip()
        )

        return (
            consulta_expandida
            if consulta_expandida
            else consulta_original.strip()
        )

    # ========================================================
    # RERANKING BGE
    # ========================================================

    def rerankear_candidatos(
        self,
        consulta_original,
        candidatos,
        usar_expansion=None,
    ):

        if not candidatos:
            return []

        consulta_reranker = (
            self.preparar_consulta_reranker(
                consulta_original,
                usar_expansion=usar_expansion,
            )
        )

        pares = [
            (
                consulta_reranker,
                candidato["documento"],
            )
            for candidato in candidatos
        ]

        scores = self.reranker.predict(
            pares,
            show_progress_bar=False,
        )

        resultados = []

        for candidato, score in zip(
            candidatos,
            scores,
        ):

            score = float(score)

            if (
                MIN_RERANKER_SCORE is not None
                and score < MIN_RERANKER_SCORE
            ):
                continue

            resultados.append(
                {
                    **candidato,
                    "score_reranker": score,
                    "consulta_reranker": consulta_reranker,
                }
            )

        # BGE determina la prioridad principal.
        # La fuente oficial se utiliza solo como
        # criterio de desempate.
        resultados.sort(
            key=lambda doc: (
                doc["score_reranker"],
                doc["metadata"].get("tipo_fuente")
                == "documentacion_oficial",
            ),
            reverse=True,
        )

        return resultados

    # ========================================================
    # RECUPERACIÓN COMPLETA
    # ========================================================

    def recuperar_documentos(
        self,
        consulta,
        top_final=FINAL_TOP_K,
        multi_query=None,
        reranker_expansion=None,
        modo_st=False,
    ):

        consulta = consulta.strip()

        if not consulta:
            return []

        consultas = self.preparar_consultas(
            consulta,
            multi_query=multi_query,
            modo_st=modo_st,
        )

        grupos = []

        for consulta_busqueda in consultas:

            candidatos = self.buscar_en_chroma(
                consulta_busqueda
            )

            grupos.append(candidatos)

        candidatos_unicos = self.fusionar_candidatos(
            grupos
        )

        if not candidatos_unicos:
            return []

        documentos_ordenados = (
            self.rerankear_candidatos(
                consulta,
                candidatos_unicos,
                usar_expansion=reranker_expansion,
            )
        )

        documentos_finales = documentos_ordenados[
            :top_final
        ]

        for posicion, documento in enumerate(
            documentos_finales,
            start=1,
        ):
            documento["posicion"] = posicion

        return documentos_finales


# ============================================================
# INSTANCIA REUTILIZABLE
# ============================================================

_RECUPERADOR = None


def obtener_recuperador():

    global _RECUPERADOR

    if _RECUPERADOR is None:
        _RECUPERADOR = RecuperadorDocumental()

    return _RECUPERADOR


# ============================================================
# FUNCIÓN COMPATIBLE CON CHATBOT CLI
# ============================================================

def recuperar_documentos(
    consulta,
    top_final=FINAL_TOP_K,
    multi_query=None,
    reranker_expansion=None,
    modo_st=False,
):

    recuperador = obtener_recuperador()

    return recuperador.recuperar_documentos(
        consulta=consulta,
        top_final=top_final,
        multi_query=multi_query,
        reranker_expansion=reranker_expansion,
        modo_st=modo_st,
    )


# ============================================================
# MOSTRAR DOCUMENTOS
# ============================================================

def mostrar_documentos(documentos):

    if not documentos:
        print("\nNo se recuperaron documentos.")
        return

    print("\n" + "=" * 65)
    print("RESULTADOS DESPUÉS DEL RERANKING")
    print("=" * 65)

    for posicion, documento in enumerate(
        documentos,
        start=1,
    ):

        metadata = documento["metadata"]

        print(f"\nRESULTADO {posicion}")
        print("-" * 65)

        print(
            "Distancia Chroma:",
            round(documento["distancia"], 4),
        )

        print(
            "Score BGE:",
            round(documento["score_reranker"], 4),
        )

        print(
            "Fabricante:",
            metadata.get("fabricante", "No definido"),
        )

        print(
            "Tipo de fuente:",
            metadata.get("tipo_fuente", "No definido"),
        )

        print(
            "Archivo:",
            metadata.get("archivo", "No definido"),
        )

        print(
            "Sección:",
            metadata.get("seccion", "Sin sección"),
        )

        print(
            "Chunk:",
            metadata.get("chunk_index", "No definido"),
        )

        print(
            "Ruta:",
            metadata.get("ruta", "No definida"),
        )

        print(
            "Consultas de origen:",
            len(documento.get("consultas_origen", [])),
        )

        print("\nContenido:\n")
        print(documento["documento"])

        print("-" * 65)


# ============================================================
# COMPARAR RERANKING SOBRE LOS MISMOS CANDIDATOS
# ============================================================

def comparar_reranking(recuperador, consulta):

    consultas = recuperador.preparar_consultas(
        consulta,
        multi_query=True,
    )

    grupos = [
        recuperador.buscar_en_chroma(pregunta)
        for pregunta in consultas
    ]

    candidatos = recuperador.fusionar_candidatos(
        grupos
    )

    original = recuperador.rerankear_candidatos(
        consulta,
        candidatos,
        usar_expansion=False,
    )

    expandido = recuperador.rerankear_candidatos(
        consulta,
        candidatos,
        usar_expansion=True,
    )

    print("\n" + "=" * 65)
    print("COMPARACIÓN BGE")
    print("=" * 65)

    print("Candidatos únicos:", len(candidatos))

    for titulo, resultados in [
        ("A. PREGUNTA ORIGINAL", original),
        ("B. PREGUNTA EXPANDIDA", expandido),
    ]:

        print("\n" + titulo)
        print("-" * 65)

        for posicion, documento in enumerate(
            resultados[:FINAL_TOP_K],
            start=1,
        ):

            metadata = documento["metadata"]

            print(
                f"{posicion}. "
                f"{metadata.get('archivo')} | "
                f"{metadata.get('seccion')} | "
                f"BGE: {documento['score_reranker']:.4f}"
            )


# ============================================================
# INTERFAZ DE PRUEBAS
# ============================================================

def main():

    recuperador = RecuperadorDocumental()

    print("\n" + "=" * 65)
    print("CONSULTA DOCUMENTAL RAG")
    print("=" * 65)

    print(
        "Multi-Query Retrieval:",
        "ACTIVADO"
        if MULTI_QUERY_ENABLED
        else "DESACTIVADO",
    )

    print(
        "Expansión en BGE:",
        "ACTIVADA"
        if RERANKER_EXPANSION_ENABLED
        else "DESACTIVADA",
    )

    print(
        "\nEscribe 'comparar' para comparar ambos "
        "métodos de reranking."
    )

    while True:

        consulta = input(
            "\nEscribe tu consulta "
            "(o 'salir' para terminar): "
        ).strip()

        if consulta.lower() in {
            "salir",
            "exit",
            "quit",
        }:
            break

        if not consulta:
            continue

        if consulta.lower() == "comparar":

            pregunta = input(
                "\nPregunta para comparar: "
            ).strip()

            if pregunta:
                comparar_reranking(
                    recuperador,
                    pregunta,
                )

            continue

        inicio = time.perf_counter()

        documentos = recuperador.recuperar_documentos(
            consulta,
            top_final=FINAL_TOP_K,
        )

        tiempo = time.perf_counter() - inicio

        mostrar_documentos(documentos)

        print(
            f"\nTiempo de recuperación: "
            f"{tiempo:.2f} segundos"
        )


if __name__ == "__main__":
    main()
