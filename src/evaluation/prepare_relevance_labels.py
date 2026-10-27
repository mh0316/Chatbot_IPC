
import argparse
import json
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RESULTS_DIR = PROJECT_ROOT / "results/retrieval"

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data/evaluation/relevance_labels_pilot.json"
)

PREGUNTAS_INICIALES = [
    "FUND_001",
    "ST_CODE_001",
    "FB_007",
    "RT_006",
    "SAFE_001",
]


# ============================================================
# CARGAR RESULTADOS
# ============================================================

def cargar_json(ruta):
    with ruta.open("r", encoding="utf-8") as archivo:
        return json.load(archivo)


def buscar_resultado(top_k):
    patron = f"retrieval_pilot_k{top_k}_*.json"

    archivos = sorted(
        RESULTS_DIR.glob(patron),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not archivos:
        raise FileNotFoundError(
            f"No se encontraron archivos: {patron}"
        )

    ruta = archivos[0]

    print(f"Top {top_k}: {ruta.name}")

    datos = cargar_json(ruta)

    config = datos.get("configuracion", {})

    if config.get("retrieval_top_k") != top_k:
        raise ValueError(
            f"Configuración incorrecta en {ruta.name}"
        )

    return datos, ruta


# ============================================================
# ORDEN DE RERANKING
# ============================================================

def construir_ranking_reranker(candidatos):
    ordenados = sorted(
        candidatos,
        key=lambda x: (
            -(x.get("reranker_score") or 0.0),
            x["vector_rank"]
        )
    )

    return {
        candidato["id"]: posicion
        for posicion, candidato in enumerate(
            ordenados,
            start=1
        )
    }


# ============================================================
# UNIFICAR CANDIDATOS
# ============================================================

def combinar_resultados(datos_10, datos_30, ids):
    preguntas_10 = {
        item["id"]: item
        for item in datos_10["resultados"]
    }

    preguntas_30 = {
        item["id"]: item
        for item in datos_30["resultados"]
    }

    preguntas_finales = []

    for question_id in ids:
        if question_id not in preguntas_10:
            raise ValueError(
                f"{question_id} no existe en Top 10"
            )

        if question_id not in preguntas_30:
            raise ValueError(
                f"{question_id} no existe en Top 30"
            )

        pregunta_10 = preguntas_10[question_id]
        pregunta_30 = preguntas_30[question_id]

        if (
            pregunta_10["question"]
            != pregunta_30["question"]
        ):
            raise ValueError(
                f"La pregunta {question_id} cambió "
                "entre evaluaciones."
            )

        rankings_10 = construir_ranking_reranker(
            pregunta_10["todos_candidatos"]
        )

        rankings_30 = construir_ranking_reranker(
            pregunta_30["todos_candidatos"]
        )

        candidatos = {}

        # Recopilar fragmentos de ambas ejecuciones
        for top_k, pregunta in [
            (10, pregunta_10),
            (30, pregunta_30)
        ]:
            for candidato in pregunta["todos_candidatos"]:
                chunk_id = candidato["id"]

                if chunk_id not in candidatos:
                    metadata = candidato.get(
                        "metadata", {}
                    )

                    candidatos[chunk_id] = {
                        "chunk_id": chunk_id,
                        "fabricante": candidato.get(
                            "fabricante"
                        ),
                        "tipo_fuente": candidato.get(
                            "tipo_fuente"
                        ),
                        "archivo": candidato.get(
                            "archivo"
                        ),
                        "ruta": candidato.get(
                            "ruta"
                        ),
                        "seccion": candidato.get(
                            "seccion"
                        ),
                        "chunk_index": candidato.get(
                            "chunk_index"
                        ),
                        "titulo_documento": metadata.get(
                            "doc_title"
                        ),
                        "contenido": candidato.get(
                            "documento", ""
                        ),
                        "rankings": {},
                        "relevance": None,
                        "notes": "",
                    }

                candidatos[chunk_id]["rankings"][
                    f"top_{top_k}"
                ] = {
                    "vector_rank": candidato[
                        "vector_rank"
                    ],
                    "reranker_rank": (
                        rankings_10.get(chunk_id)
                        if top_k == 10
                        else rankings_30.get(chunk_id)
                    ),
                    "distancia": candidato.get(
                        "distancia"
                    ),
                    "reranker_score": candidato.get(
                        "reranker_score"
                    ),
                }

        # Orden reproducible: primero ranking vectorial Top 30
        candidatos_ordenados = sorted(
            candidatos.values(),
            key=lambda x: (
                x["rankings"]
                .get("top_30", {})
                .get("vector_rank", 999999),
                x["chunk_id"]
            )
        )

        preguntas_finales.append({
            "id": question_id,
            "category": pregunta_30["category"],
            "difficulty": pregunta_30["difficulty"],
            "question": pregunta_30["question"],
            "judgment_status": "pending",
            "chunks": candidatos_ordenados,
        })

    return preguntas_finales


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Preparar etiquetas de relevancia RAG"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Preparar las 15 preguntas"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescribir plantilla existente"
    )

    args = parser.parse_args()

    if OUTPUT_PATH.exists() and not args.force:
        raise FileExistsError(
            f"La plantilla ya existe: {OUTPUT_PATH}\n"
            "No se sobrescribirá para evitar perder "
            "etiquetas manuales."
        )

    print("\n======================================")
    print("PREPARACIÓN DE ETIQUETAS DE RELEVANCIA")
    print("======================================")

    datos_10, ruta_10 = buscar_resultado(10)
    datos_30, ruta_30 = buscar_resultado(30)

    config_10 = datos_10["configuracion"]
    config_30 = datos_30["configuracion"]

    for clave in (
        "collection",
        "embedding_model",
        "reranker_model"
    ):
        if config_10.get(clave) != config_30.get(clave):
            raise ValueError(
                f"Las ejecuciones difieren en {clave}"
            )

    if args.all:
        ids = [
            item["id"]
            for item in datos_30["resultados"]
        ]
    else:
        ids = PREGUNTAS_INICIALES

    preguntas = combinar_resultados(
        datos_10,
        datos_30,
        ids
    )

    total_chunks = sum(
        len(p["chunks"])
        for p in preguntas
    )

    plantilla = {
        "description": (
            "Evaluación manual de relevancia documental "
            "para recuperación RAG."
        ),
        "collection": config_30["collection"],
        "source_files": [
            ruta_10.name,
            ruta_30.name
        ],
        "relevance_scale": {
            "0": "Irrelevante",
            "1": "Parcialmente relevante",
            "2": "Directamente relevante"
        },
        "questions": preguntas
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_PATH.open("w", encoding="utf-8") as archivo:
        json.dump(
            plantilla,
            archivo,
            ensure_ascii=False,
            indent=2
        )

    print("\nPlantilla generada correctamente")
    print(f"Preguntas: {len(preguntas)}")
    print(f"Fragmentos para etiquetar: {total_chunks}")

    for pregunta in preguntas:
        print(
            f"  {pregunta['id']}: "
            f"{len(pregunta['chunks'])} chunks"
        )

    print(f"\nArchivo: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
