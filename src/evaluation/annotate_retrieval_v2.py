
import argparse
import json
import math
import os

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

RESULTS_DIR = ROOT / "results/retrieval"

LABELS_DIR = ROOT / "data/evaluation"

CONFIGURACIONES = ("A", "B", "C", "D")


def cargar_json(ruta):
    with ruta.open("r", encoding="utf-8") as f:
        return json.load(f)


def guardar_json(datos, ruta):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")

    with temporal.open("w", encoding="utf-8") as f:
        json.dump(
            datos, f,
            ensure_ascii=False, indent=2
        )

    os.replace(temporal, ruta)


def archivo_evaluacion(ruta=None):
    if ruta:
        p = Path(ruta).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(p)
        return p

    archivos = sorted(
        RESULTS_DIR.glob("retrieval_v2_76_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not archivos:
        raise FileNotFoundError(
            "No existe una evaluación V2 de 76 preguntas."
        )

    return archivos[0]


def preparar_etiquetas(evaluacion, nombre_archivo):
    preguntas = []

    for resultado in evaluacion["resultados"]:
        chunks = {}

        # Reunir los Top 3 de las cuatro configuraciones.
        # Cada documento se etiqueta una sola vez por pregunta.
        for config in CONFIGURACIONES:
            for doc in resultado["rankings"][config]:
                chunk_id = doc["id"]

                if chunk_id not in chunks:
                    chunks[chunk_id] = {
                        "chunk_id": chunk_id,
                        "archivo": doc.get("archivo"),
                        "seccion": doc.get("seccion"),
                        "ruta": doc.get("ruta"),
                        "tipo_fuente": doc.get("tipo_fuente"),
                        "formato_origen": doc.get("formato_origen"),
                        "elementos": doc.get("elementos", {}),
                        "contenido": doc.get("documento", ""),
                        "relevance": None,
                        "notes": "",
                    }

        preguntas.append({
            "id": resultado["id"],
            "question": resultado["question"],
            "category": resultado["category"],
            "type": resultado.get("type"),
            "difficulty": resultado["difficulty"],
            "chunks": list(chunks.values()),
        })

    return {
        "archivo_origen": nombre_archivo,
        "escala": {
            "0": "Irrelevante",
            "1": "Parcialmente relevante",
            "2": "Directamente relevante",
        },
        "preguntas": preguntas,
    }


def pendiente(pregunta):
    return [
        doc for doc in pregunta["chunks"]
        if doc["relevance"] is None
    ]


def anotar(etiquetas, ruta_salida, limite=None):
    preguntas = etiquetas["preguntas"]
    anotadas_sesion = 0

    for numero, pregunta in enumerate(preguntas, start=1):
        if not pendiente(pregunta):
            continue

        if limite is not None and anotadas_sesion >= limite:
            break

        print("\n" + "=" * 75)
        print(f"PREGUNTA {numero}/{len(preguntas)}")
        print("ID:", pregunta["id"])
        print("Categoría:", pregunta["category"])
        print("Dificultad:", pregunta["difficulty"])
        print("\n", pregunta["question"])
        print("=" * 75)

        for i, doc in enumerate(pregunta["chunks"], start=1):
            if doc["relevance"] is not None:
                continue

            print("\n" + "-" * 75)
            print(f"FRAGMENTO {i}/{len(pregunta['chunks'])}")
            print("Chunk ID:", doc["chunk_id"])
            print("Formato:", doc["formato_origen"])
            print("Tipo de fuente:", doc["tipo_fuente"])
            print("Archivo:", doc["archivo"])
            print("Sección:", doc["seccion"])
            print("Ruta:", doc["ruta"])
            print("Elementos:", doc["elementos"])
            print("\nCONTENIDO:\n")
            print(doc["contenido"])
            print("\n" + "-" * 75)

            print("0 = Irrelevante")
            print("1 = Parcialmente relevante")
            print("2 = Directamente relevante")
            print("s = Guardar y salir")

            while True:
                try:
                    respuesta = input(
                        "\nRelevancia [0/1/2/s]: "
                    ).strip().lower()
                except (EOFError, KeyboardInterrupt):
                    respuesta = "s"
                    print()

                if respuesta in ("0", "1", "2"):
                    doc["relevance"] = int(respuesta)
                    guardar_json(etiquetas, ruta_salida)
                    break

                if respuesta == "s":
                    guardar_json(etiquetas, ruta_salida)
                    print("\nProgreso guardado:", ruta_salida)
                    return

                print("Introduce 0, 1, 2 o s.")

        anotadas_sesion += 1
        guardar_json(etiquetas, ruta_salida)

        print(
            f"\nPregunta {pregunta['id']} completada."
        )

    print("\nSesión terminada.")
    print("Etiquetas guardadas en:", ruta_salida)


def dcg(relevancias):
    return sum(
        (2 ** rel - 1) / math.log2(i + 2)
        for i, rel in enumerate(relevancias)
    )


def ndcg_at_3(relevancias):
    ideal = sorted(relevancias, reverse=True)
    maximo = dcg(ideal)

    if maximo == 0:
        return 0.0

    return dcg(relevancias) / maximo


def generar_reporte(evaluacion, etiquetas):
    mapa = {
        pregunta["id"]: {
            doc["chunk_id"]: doc["relevance"]
            for doc in pregunta["chunks"]
        }
        for pregunta in etiquetas["preguntas"]
    }

    preguntas_completas = 0
    fragmentos_totales = 0
    fragmentos_anotados = 0

    acumulados = {
        config: {
            "precision3": [],
            "ndcg3": [],
            "hit3": [],
            "formatos": Counter(),
        }
        for config in CONFIGURACIONES
    }

    por_categoria = {
        config: {}
        for config in CONFIGURACIONES
    }

    for resultado in evaluacion["resultados"]:
        qid = resultado["id"]
        labels = mapa[qid]

        fragmentos_totales += len(labels)
        fragmentos_anotados += sum(
            valor is not None
            for valor in labels.values()
        )

        rankings = resultado["rankings"]

        # No calcular métricas de una pregunta si algún
        # documento de cualquiera de los Top 3
        # sigue sin etiqueta.
        ids_top = {
            doc["id"]
            for config in CONFIGURACIONES
            for doc in rankings[config]
        }

        if any(labels.get(cid) is None for cid in ids_top):
            continue

        if any(
            len(rankings[config]) != 3
            for config in CONFIGURACIONES
        ):
            continue

        preguntas_completas += 1
        categoria = resultado["category"]

        for config in CONFIGURACIONES:
            documentos = rankings[config]
            rel = [labels[d["id"]] for d in documentos]

            # Solo etiqueta 2 cuenta como directamente
            # relevante en Precision@3.
            precision = sum(r == 2 for r in rel) / 3
            hit = float(any(r == 2 for r in rel))
            ndcg = ndcg_at_3(rel)

            acumulados[config]["precision3"].append(
                precision
            )
            acumulados[config]["hit3"].append(hit)
            acumulados[config]["ndcg3"].append(ndcg)

            for doc in documentos:
                acumulados[config]["formatos"][
                    doc.get("formato_origen")
                    or "sin_clasificar"
                ] += 1

            por_categoria[config].setdefault(
                categoria, []
            ).append(precision)

    def promedio(valores):
        return (
            sum(valores) / len(valores)
            if valores else None
        )

    resumen = {
        "fecha_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "total_preguntas": len(evaluacion["resultados"]),
        "preguntas_completamente_anotadas": preguntas_completas,
        "fragmentos_unicos_por_pregunta": fragmentos_totales,
        "fragmentos_anotados": fragmentos_anotados,
        "configuraciones": {},
    }

    print("\n" + "=" * 75)
    print("REPORTE DE RELEVANCIA")
    print("=" * 75)
    print(
        "Preguntas completas:",
        preguntas_completas,
        "/",
        len(evaluacion["resultados"]),
    )
    print(
        "Fragmentos etiquetados:",
        fragmentos_anotados,
        "/",
        fragmentos_totales,
    )

    for config in CONFIGURACIONES:
        datos = acumulados[config]
        p3 = promedio(datos["precision3"])
        n3 = promedio(datos["ndcg3"])
        h3 = promedio(datos["hit3"])

        resumen["configuraciones"][config] = {
            "precision_at_3": p3,
            "ndcg_at_3": n3,
            "hit_at_3": h3,
            "precision_por_categoria": {
                categoria: promedio(valores)
                for categoria, valores in sorted(
                    por_categoria[config].items()
                )
            },
            "formatos_en_preguntas_anotadas": dict(
                datos["formatos"]
            ),
        }

        print(f"\nConfiguración {config}")

        if p3 is None:
            print("Aún no hay preguntas completas.")
        else:
            print(f"Precision@3: {p3:.2%}")
            print(f"nDCG@3:      {n3:.4f}")
            print(f"Hit@3:       {h3:.2%}")

    if preguntas_completas < len(
        evaluacion["resultados"]
    ):
        print(
            "\nATENCIÓN: Son resultados parciales. "
            "No representan aún las 76 preguntas."
        )

    return resumen


def main():
    parser = argparse.ArgumentParser(
        description="Etiquetado humano de recuperación RAG V2"
    )

    parser.add_argument(
        "--input",
        help="JSON retrieval_v2_76_*.json",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Número máximo de preguntas a anotar en esta sesión",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Mostrar métricas de las preguntas anotadas",
    )
    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        parser.error("--limit debe ser mayor que cero")

    ruta_entrada = archivo_evaluacion(args.input)
    evaluacion = cargar_json(ruta_entrada)

    ruta_etiquetas = (
        LABELS_DIR
        / f"relevance_labels_{ruta_entrada.stem}.json"
    )

    if ruta_etiquetas.exists():
        etiquetas = cargar_json(ruta_etiquetas)

        if etiquetas["archivo_origen"] != ruta_entrada.name:
            raise ValueError(
                "Las etiquetas pertenecen a otro experimento."
            )
    else:
        etiquetas = preparar_etiquetas(
            evaluacion, ruta_entrada.name
        )
        guardar_json(etiquetas, ruta_etiquetas)

    print("Evaluación:", ruta_entrada)
    print("Etiquetas:", ruta_etiquetas)

    if not args.report:
        anotar(
            etiquetas,
            ruta_etiquetas,
            limite=args.limit,
        )

    reporte = generar_reporte(
        evaluacion, etiquetas
    )

    ruta_reporte = (
        RESULTS_DIR
        / f"relevance_report_{ruta_entrada.stem}.json"
    )

    guardar_json(reporte, ruta_reporte)
    print("\nReporte guardado:", ruta_reporte)


if __name__ == "__main__":
    main()
