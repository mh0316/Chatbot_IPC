
import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path

from src.generation.generate_answer import GeneradorQwen
from src.retrieval.query_markdown import recuperar_documentos


def leer_preguntas(ruta):
    ruta = Path(ruta)

    if ruta.suffix.lower() == ".csv":
        with ruta.open(encoding="utf-8-sig", newline="") as f:
            preguntas = list(csv.DictReader(f))
    elif ruta.suffix.lower() == ".jsonl":
        with ruta.open(encoding="utf-8") as f:
            preguntas = [
                json.loads(linea)
                for linea in f
                if linea.strip()
            ]
    else:
        raise ValueError("Utiliza un archivo CSV o JSONL.")

    for numero, pregunta in enumerate(preguntas, start=1):
        pregunta.setdefault("id", str(numero))
        if not pregunta.get("pregunta", "").strip():
            raise ValueError(
                f"Pregunta sin contenido en posición {numero}"
            )

    ids = [str(p["id"]) for p in preguntas]
    if len(ids) != len(set(ids)):
        raise ValueError("Hay identificadores duplicados.")

    return preguntas


def ids_completados(ruta):
    completados = set()

    if not ruta.exists():
        return completados

    with ruta.open(encoding="utf-8") as f:
        for linea in f:
            if not linea.strip():
                continue
            registro = json.loads(linea)
            if registro.get("estado") == "ok":
                completados.add(str(registro["id"]))

    return completados


def convertir_json(valor):
    """Convierte datos no serializables a texto."""
    if isinstance(valor, dict):
        return {
            str(k): convertir_json(v)
            for k, v in valor.items()
        }
    if isinstance(valor, (list, tuple)):
        return [convertir_json(v) for v in valor]
    if isinstance(valor, (str, int, float, bool)) or valor is None:
        return valor
    return str(valor)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preguntas", required=True)
    parser.add_argument(
        "--salida",
        default="results/evaluation/qwen_rag_76.jsonl"
    )
    args = parser.parse_args()

    preguntas = leer_preguntas(args.preguntas)
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)

    completados = ids_completados(salida)
    pendientes = [
        p for p in preguntas
        if str(p["id"]) not in completados
    ]

    print(f"Total de preguntas: {len(preguntas)}")
    print(f"Ya completadas: {len(completados)}")
    print(f"Pendientes: {len(pendientes)}")

    if not pendientes:
        print("No hay preguntas pendientes.")
        return

    # Qwen se carga una sola vez.
    print("Cargando Qwen...")
    generador = GeneradorQwen()

    with salida.open("a", encoding="utf-8") as archivo:
        for indice, item in enumerate(pendientes, start=1):
            pregunta = item["pregunta"]
            identificador = str(item["id"])

            print(
                f"\n[{indice}/{len(pendientes)}] "
                f"Pregunta {identificador}",
                flush=True
            )

            registro = {
                "id": identificador,
                "pregunta": pregunta,
                "configuracion": "QWEN_RAG",
                "fecha": datetime.now().isoformat()
            }

            try:
                inicio = time.perf_counter()

                documentos = recuperar_documentos(
                    pregunta,
                    top_final=3,
                    multi_query=True,
                    reranker_expansion=False
                )

                tiempo_recuperacion = (
                    time.perf_counter() - inicio
                )

                resultado = generador.generar_respuesta(
                    pregunta,
                    documentos
                )

                registro.update({
                    "estado": "ok",
                    "respuesta": resultado.get("respuesta", ""),
                    "documentos": convertir_json(documentos),
                    "metricas_generacion": convertir_json(resultado),
                    "tiempo_recuperacion": tiempo_recuperacion
                })

                print(
                    f"Completada en recuperación: "
                    f"{tiempo_recuperacion:.2f}s",
                    flush=True
                )

            except Exception as error:
                registro.update({
                    "estado": "error",
                    "error": repr(error)
                })
                print(f"Error: {error}", flush=True)

            archivo.write(
                json.dumps(registro, ensure_ascii=False) + "\n"
            )
            archivo.flush()

    print("\nEvaluación terminada.")
    print(f"Resultados: {salida}")


if __name__ == "__main__":
    main()
