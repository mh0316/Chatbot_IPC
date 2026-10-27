
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import chromadb
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder


# ============================================================
# CONFIGURACIÓN
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CHROMA_DIR = PROJECT_ROOT / "chroma_db"

PILOT_PATH = (
    PROJECT_ROOT
    / "data/evaluation/retrieval_pilot_15.json"
)

RESULTS_DIR = PROJECT_ROOT / "results/retrieval"

EMBEDDING_MODEL_NAME = (
    "jinaai/jina-embeddings-v5-omni-nano-retrieval"
)

RERANKER_MODEL_NAME = "BAAI/bge-reranker-v2-m3"

COLLECTION_NAME = "ipc_markdown_v3"

RETRIEVAL_TOP_K = 30
FINAL_TOP_K = 3

EMBEDDING_DEVICE = "cuda"
RERANKER_DEVICE = "cpu"


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def guardar_json(datos, ruta):
    ruta.parent.mkdir(parents=True, exist_ok=True)

    with ruta.open("w", encoding="utf-8") as archivo:
        json.dump(
            datos,
            archivo,
            ensure_ascii=False,
            indent=2
        )


def cargar_preguntas():
    with PILOT_PATH.open("r", encoding="utf-8") as archivo:
        preguntas = json.load(archivo)

    if not isinstance(preguntas, list):
        raise ValueError("El conjunto piloto debe ser una lista.")

    if len(preguntas) != 15:
        raise ValueError(
            f"Se esperaban 15 preguntas, se encontraron {len(preguntas)}."
        )

    ids = set()

    for pregunta in preguntas:
        if not all(
            clave in pregunta
            for clave in ("id", "question", "category", "difficulty")
        ):
            raise ValueError(f"Pregunta incompleta: {pregunta}")

        if pregunta["id"] in ids:
            raise ValueError(f"ID duplicado: {pregunta['id']}")

        ids.add(pregunta["id"])

    return preguntas


def extraer_candidatos(resultados):
    candidatos = []

    ids = resultados["ids"][0]
    documentos = resultados["documents"][0]
    metadatos = resultados["metadatas"][0]
    distancias = resultados["distances"][0]

    for posicion, (doc_id, documento, metadata, distancia) in enumerate(
        zip(ids, documentos, metadatos, distancias),
        start=1
    ):
        candidatos.append({
            "id": doc_id,
            "documento": documento,
            "metadata": metadata or {},
            "distancia": float(distancia),
            "vector_rank": posicion,
        })

    return candidatos


def datos_resultado(candidato, posicion_final):
    metadata = candidato["metadata"]

    return {
        "rank": posicion_final,
        "id": candidato["id"],
        "vector_rank": candidato["vector_rank"],
        "distancia": candidato["distancia"],
        "reranker_score": candidato.get("reranker_score"),
        "fabricante": metadata.get("fabricante"),
        "tipo_fuente": metadata.get("tipo_fuente"),
        "archivo": metadata.get("archivo"),
        "ruta": metadata.get("ruta"),
        "seccion": metadata.get("seccion"),
        "chunk_index": metadata.get("chunk_index"),
        "metadata": metadata,
        "documento": candidato["documento"],
    }


# ============================================================
# EVALUAR UNA CONSULTA
# ============================================================

def evaluar_consulta(
    pregunta,
    collection,
    embedding_model,
    reranker,
    retrieval_top_k,
    final_top_k
):
    consulta = pregunta["question"]

    # --------------------------------------------------------
    # 1. EMBEDDING DE CONSULTA
    # --------------------------------------------------------

    inicio_embedding = time.perf_counter()

    query_embedding = embedding_model.encode_query(
        consulta
    )

    tiempo_embedding = time.perf_counter() - inicio_embedding

    query_embedding = np.asarray(
        query_embedding,
        dtype=np.float32
    ).tolist()

    # --------------------------------------------------------
    # 2. RECUPERACIÓN VECTORIAL
    # --------------------------------------------------------

    inicio_retrieval = time.perf_counter()

    resultados = collection.query(
        query_embeddings=[query_embedding],
        n_results=retrieval_top_k,
        include=[
            "documents",
            "metadatas",
            "distances"
        ]
    )

    tiempo_retrieval = time.perf_counter() - inicio_retrieval

    candidatos = extraer_candidatos(resultados)

    # --------------------------------------------------------
    # 3. RESULTADOS SIN RERANKING
    # --------------------------------------------------------

    resultados_vectoriales = [
        datos_resultado(candidato, posicion)
        for posicion, candidato in enumerate(
            candidatos[:final_top_k],
            start=1
        )
    ]

    # --------------------------------------------------------
    # 4. RERANKING
    # --------------------------------------------------------

    tiempo_reranking = 0.0
    resultados_reranking = []

    if candidatos:
        pares = [
            (consulta, candidato["documento"])
            for candidato in candidatos
        ]

        inicio_reranking = time.perf_counter()

        scores = reranker.predict(
            pares,
            batch_size=8,
            show_progress_bar=False,
            apply_softmax=False
        )

        tiempo_reranking = (
            time.perf_counter() - inicio_reranking
        )

        scores = np.asarray(scores).reshape(-1)

        for candidato, score in zip(candidatos, scores):
            candidato["reranker_score"] = float(score)

        candidatos_ordenados = sorted(
            candidatos,
            key=lambda item: (
                -item["reranker_score"],
                item["vector_rank"]
            )
        )

        resultados_reranking = [
            datos_resultado(candidato, posicion)
            for posicion, candidato in enumerate(
                candidatos_ordenados[:final_top_k],
                start=1
            )
        ]

    # --------------------------------------------------------
    # 5. RESULTADOS COMPLETOS
    # --------------------------------------------------------

    todos_candidatos = [
        datos_resultado(candidato, posicion)
        for posicion, candidato in enumerate(
            candidatos,
            start=1
        )
    ]

    return {
        "id": pregunta["id"],
        "category": pregunta["category"],
        "type": pregunta.get("type"),
        "difficulty": pregunta["difficulty"],
        "question": consulta,
        "candidatos_recuperados": len(candidatos),
        "tiempos_ms": {
            "embedding": round(tiempo_embedding * 1000, 3),
            "retrieval": round(tiempo_retrieval * 1000, 3),
            "reranking": round(tiempo_reranking * 1000, 3),
            "total": round(
                (
                    tiempo_embedding
                    + tiempo_retrieval
                    + tiempo_reranking
                ) * 1000,
                3
            ),
        },
        "resultados_vectoriales": resultados_vectoriales,
        "resultados_reranking": resultados_reranking,
        "todos_candidatos": todos_candidatos,
    }


# ============================================================
# EJECUCIÓN PRINCIPAL
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Evaluación piloto de recuperación RAG"
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=RETRIEVAL_TOP_K
    )

    parser.add_argument(
        "--final-k",
        type=int,
        default=FINAL_TOP_K
    )

    args = parser.parse_args()

    if args.top_k < 1 or args.final_k < 1:
        parser.error("Los valores de K deben ser mayores que cero.")

    if args.final_k > args.top_k:
        parser.error("--final-k no puede superar --top-k.")

    print("\n==========================================")
    print("EVALUACIÓN PILOTO DEL RETRIEVER RAG")
    print("==========================================")

    preguntas = cargar_preguntas()

    print(f"\nPreguntas cargadas: {len(preguntas)}")

    # --------------------------------------------------------
    # INICIALIZAR CHROMADB
    # --------------------------------------------------------

    print("\nConectando con ChromaDB...")

    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR)
    )

    # get_collection evita crear una colección nueva
    collection = client.get_collection(
        name=COLLECTION_NAME
    )

    cantidad_registros = collection.count()

    print(f"Colección: {COLLECTION_NAME}")
    print(f"Registros: {cantidad_registros}")

    if cantidad_registros == 0:
        raise RuntimeError("La colección está vacía.")

    top_k = min(args.top_k, cantidad_registros)

    # --------------------------------------------------------
    # CARGAR MODELOS UNA SOLA VEZ
    # --------------------------------------------------------

    print("\nCargando modelo Jina...")

    embedding_model = SentenceTransformer(
        EMBEDDING_MODEL_NAME,
        trust_remote_code=True,
        device=EMBEDDING_DEVICE
    )

    print(f"Embedding device: {embedding_model.device}")

    print("\nCargando BGE Reranker...")

    reranker = CrossEncoder(
        RERANKER_MODEL_NAME,
        device=RERANKER_DEVICE
    )

    print(f"Reranker device: {RERANKER_DEVICE}")

    # --------------------------------------------------------
    # EJECUTAR PREGUNTAS
    # --------------------------------------------------------

    resultados_evaluacion = []

    for numero, pregunta in enumerate(preguntas, start=1):
        print(
            f"\n[{numero}/{len(preguntas)}] "
            f"{pregunta['id']}"
        )

        resultado = evaluar_consulta(
            pregunta=pregunta,
            collection=collection,
            embedding_model=embedding_model,
            reranker=reranker,
            retrieval_top_k=top_k,
            final_top_k=args.final_k
        )

        resultados_evaluacion.append(resultado)

        tiempos = resultado["tiempos_ms"]

        print(
            f"  Candidatos: {resultado['candidatos_recuperados']}"
        )
        print(f"  Retrieval: {tiempos['retrieval']:.2f} ms")
        print(f"  Reranking: {tiempos['reranking']:.2f} ms")
        print(f"  Total: {tiempos['total']:.2f} ms")

        for candidato in resultado["resultados_reranking"]:
            print(
                f"    Rank {candidato['rank']}: "
                f"{candidato['fabricante']} | "
                f"{candidato['seccion']} | "
                f"score={candidato['reranker_score']:.4f}"
            )

    # --------------------------------------------------------
    # RESUMEN DE LATENCIAS
    # --------------------------------------------------------

    def promedio_tiempo(campo):
        return round(
            sum(
                resultado["tiempos_ms"][campo]
                for resultado in resultados_evaluacion
            ) / len(resultados_evaluacion),
            3
        )

    resumen = {
        "preguntas_evaluadas": len(resultados_evaluacion),
        "promedio_embedding_ms": promedio_tiempo("embedding"),
        "promedio_retrieval_ms": promedio_tiempo("retrieval"),
        "promedio_reranking_ms": promedio_tiempo("reranking"),
        "promedio_total_ms": promedio_tiempo("total"),
    }

    # --------------------------------------------------------
    # GUARDAR RESULTADOS
    # --------------------------------------------------------

    fecha = datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S"
    )

    OUTPUT_PATH = (
        RESULTS_DIR
        / f"retrieval_pilot_k{top_k}_{fecha}.json"
    )

    salida = {
        "configuracion": {
            "collection": COLLECTION_NAME,
            "embedding_model": EMBEDDING_MODEL_NAME,
            "reranker_model": RERANKER_MODEL_NAME,
            "retrieval_top_k": top_k,
            "final_top_k": args.final_k,
            "max_distance": None,
            "min_reranker_score": None,
            "reranker_scores": "raw",
            "evaluado_en_utc": datetime.now(
                timezone.utc
            ).isoformat(),
        },
        "resumen": resumen,
        "resultados": resultados_evaluacion,
    }

    guardar_json(salida, OUTPUT_PATH)

    print("\n==========================================")
    print("EVALUACIÓN FINALIZADA")
    print("==========================================")

    print(f"\nPreguntas evaluadas: {resumen['preguntas_evaluadas']}")
    print(f"Embedding promedio: {resumen['promedio_embedding_ms']} ms")
    print(f"Retrieval promedio: {resumen['promedio_retrieval_ms']} ms")
    print(f"Reranking promedio: {resumen['promedio_reranking_ms']} ms")
    print(f"Tiempo total promedio: {resumen['promedio_total_ms']} ms")

    print(f"\nResultados guardados en:\n{OUTPUT_PATH}")


if __name__ == "__main__":
    main()
