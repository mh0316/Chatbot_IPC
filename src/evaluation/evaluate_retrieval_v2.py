
import argparse
import csv
import json
import sys
import time

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# RUTAS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.query_markdown import RecuperadorDocumental


DATASET_PATH = (
    PROJECT_ROOT / "data/evaluation/baseline_text.json"
)

RESULTS_DIR = PROJECT_ROOT / "results/retrieval"

TOP_FINAL = 3

CONFIGURACIONES = {
    "A": "Jina, consulta original",
    "B": "Jina + BGE original",
    "C": "Jina Multi-Query + BGE original",
    "D": "Jina Multi-Query + BGE expandido",
}


# ============================================================
# CARGAR Y VALIDAR DATASET
# ============================================================

def cargar_preguntas(limite=None):

    with DATASET_PATH.open(
        "r", encoding="utf-8"
    ) as archivo:
        preguntas = json.load(archivo)

    if not isinstance(preguntas, list):
        raise ValueError(
            "baseline_text.json debe contener una lista."
        )

    ids = set()

    for pregunta in preguntas:

        for campo in (
            "id",
            "question",
            "category",
            "type",
            "difficulty",
        ):
            if campo not in pregunta:
                raise ValueError(
                    f"Falta el campo {campo}: {pregunta}"
                )

        identificador = pregunta["id"]

        if identificador in ids:
            raise ValueError(
                f"ID de pregunta duplicado: {identificador}"
            )

        ids.add(identificador)

        if not str(pregunta["question"]).strip():
            raise ValueError(
                f"Pregunta vacía: {identificador}"
            )

    if limite is not None:
        preguntas = preguntas[:limite]

    return preguntas


# ============================================================
# CLASIFICACIÓN DE FUENTES
# ============================================================

def identificar_formato(metadata):

    metadata = metadata or {}

    archivo = str(
        metadata.get("archivo") or ""
    ).lower()

    ruta = str(
        metadata.get("ruta") or ""
    ).lower()

    tipo = str(
        metadata.get("tipo_fuente") or ""
    ).lower()

    if metadata.get("ruta_pdf_original"):
        return "pdf_convertido_markdown"

    if (
        "tutorial twincat 3_normalizado.md" in archivo
        or "tutorial twincat 3.pdf" in ruta
    ):
        return "pdf_convertido_markdown"

    if "transcripcion" in tipo or "video" in tipo:
        return "transcripcion_video"

    if "video" in ruta or "transcrito" in ruta:
        return "transcripcion_video"

    if archivo.endswith(".md"):
        return "markdown_documental"

    return "origen_no_determinado"


def detectar_elementos(contenido):

    contenido = contenido or ""
    lineas = contenido.splitlines()

    contiene_imagen = "![" in contenido

    contiene_codigo = (
        "```" in contenido
        or any(
            palabra in contenido.upper()
            for palabra in (
                "PROGRAM ",
                "FUNCTION_BLOCK ",
                "VAR_INPUT",
                "VAR_OUTPUT",
                "END_VAR",
            )
        )
    )

    contiene_tabla_markdown = any(
        linea.count("|") >= 2
        for linea in lineas
    )

    return {
        "referencias_imagen": contiene_imagen,
        "indicios_codigo": contiene_codigo,
        "tablas_markdown": contiene_tabla_markdown,
    }


# ============================================================
# SERIALIZAR CANDIDATOS
# ============================================================

def serializar_candidato(candidato, rank):

    metadata = candidato.get("metadata") or {}

    contenido = candidato.get(
        "documento", ""
    )

    score = candidato.get(
        "score_reranker"
    )

    if score is not None:
        score = float(score)

    return {
        "rank": rank,
        "id": candidato["id"],
        "distancia": float(
            candidato["distancia"]
        ),
        "score_bge": score,
        "consultas_origen": candidato.get(
            "consultas_origen", []
        ),
        "fabricante": metadata.get(
            "fabricante"
        ),
        "tipo_fuente": metadata.get(
            "tipo_fuente"
        ),
        "formato_origen": identificar_formato(
            metadata
        ),
        "archivo": metadata.get("archivo"),
        "ruta": metadata.get("ruta"),
        "seccion": metadata.get("seccion"),
        "chunk_index": metadata.get(
            "chunk_index"
        ),
        "ruta_pdf_original": metadata.get(
            "ruta_pdf_original"
        ),
        "elementos": detectar_elementos(
            contenido
        ),
        "documento": contenido,
    }


def preparar_ranking(candidatos):

    return [
        serializar_candidato(
            candidato, posicion
        )
        for posicion, candidato in enumerate(
            candidatos[:TOP_FINAL],
            start=1,
        )
    ]


# ============================================================
# MEDIR UNA PREGUNTA
# ============================================================

def evaluar_pregunta(
    recuperador,
    pregunta,
):

    consulta = pregunta["question"].strip()

    inicio_total = time.perf_counter()

    # --------------------------------------------------------
    # 1. Preparar consulta original y expandida
    # --------------------------------------------------------

    consultas = recuperador.preparar_consultas(
        consulta,
        multi_query=True,
    )

    consulta_original = consultas[0]

    consulta_expandida = (
        consultas[1]
        if len(consultas) > 1
        else consulta_original
    )

    # --------------------------------------------------------
    # 2. Jina + ChromaDB
    # --------------------------------------------------------

    inicio = time.perf_counter()

    candidatos_originales = (
        recuperador.buscar_en_chroma(
            consulta_original
        )
    )

    tiempo_original = (
        time.perf_counter() - inicio
    )

    candidatos_expandidos = []

    tiempo_expandida = 0.0

    if consulta_expandida != consulta_original:

        inicio = time.perf_counter()

        candidatos_expandidos = (
            recuperador.buscar_en_chroma(
                consulta_expandida
            )
        )

        tiempo_expandida = (
            time.perf_counter() - inicio
        )

    # --------------------------------------------------------
    # 3. Unificar los candidatos
    # --------------------------------------------------------

    candidatos_multiquery = (
        recuperador.fusionar_candidatos(
            [
                candidatos_originales,
                candidatos_expandidos,
            ]
        )
    )

    # --------------------------------------------------------
    # A: Jina solamente
    # --------------------------------------------------------

    ranking_a = sorted(
        candidatos_originales,
        key=lambda documento: documento["distancia"],
    )

    # --------------------------------------------------------
    # B: Jina + BGE original
    # --------------------------------------------------------

    inicio = time.perf_counter()

    ranking_b = recuperador.rerankear_candidatos(
        consulta,
        candidatos_originales,
        usar_expansion=False,
    )

    tiempo_bge_b = (
        time.perf_counter() - inicio
    )

    # --------------------------------------------------------
    # C: Multi-Query + BGE original
    # --------------------------------------------------------

    inicio = time.perf_counter()

    ranking_c = recuperador.rerankear_candidatos(
        consulta,
        candidatos_multiquery,
        usar_expansion=False,
    )

    tiempo_bge_c = (
        time.perf_counter() - inicio
    )

    # --------------------------------------------------------
    # D: Multi-Query + BGE expandido
    # --------------------------------------------------------

    inicio = time.perf_counter()

    ranking_d = recuperador.rerankear_candidatos(
        consulta,
        candidatos_multiquery,
        usar_expansion=True,
    )

    tiempo_bge_d = (
        time.perf_counter() - inicio
    )

    tiempo_total = (
        time.perf_counter() - inicio_total
    )

    # Conservar el conjunto evaluado para crear
    # posteriormente etiquetas de relevancia.
    pool = []

    ranking_c_por_id = {
        item["id"]: posicion
        for posicion, item in enumerate(
            ranking_c, start=1
        )
    }

    ranking_d_por_id = {
        item["id"]: posicion
        for posicion, item in enumerate(
            ranking_d, start=1
        )
    }

    for posicion, candidato in enumerate(
        candidatos_multiquery,
        start=1,
    ):

        registro = serializar_candidato(
            candidato, posicion
        )

        registro["rank_bge_original"] = (
            ranking_c_por_id.get(
                candidato["id"]
            )
        )

        registro["rank_bge_expandido"] = (
            ranking_d_por_id.get(
                candidato["id"]
            )
        )

        pool.append(registro)

    return {
        "id": pregunta["id"],
        "category": pregunta["category"],
        "type": pregunta["type"],
        "difficulty": pregunta["difficulty"],
        "question": consulta,
        "consulta_expandida": consulta_expandida,
        "cantidad_candidatos": {
            "original": len(
                candidatos_originales
            ),
            "expandida": len(
                candidatos_expandidos
            ),
            "unicos_multiquery": len(
                candidatos_multiquery
            ),
        },
        "rankings": {
            "A": preparar_ranking(ranking_a),
            "B": preparar_ranking(ranking_b),
            "C": preparar_ranking(ranking_c),
            "D": preparar_ranking(ranking_d),
        },
        "pool_candidatos": pool,
        "tiempos_ms": {
            "jina_original": round(
                tiempo_original * 1000, 2
            ),
            "jina_expandida": round(
                tiempo_expandida * 1000, 2
            ),
            "bge_B": round(
                tiempo_bge_b * 1000, 2
            ),
            "bge_C": round(
                tiempo_bge_c * 1000, 2
            ),
            "bge_D": round(
                tiempo_bge_d * 1000, 2
            ),
            "experimento_total": round(
                tiempo_total * 1000, 2
            ),
        },
    }


# ============================================================
# GUARDAR RESULTADOS
# ============================================================

def guardar_json(datos, ruta):

    ruta.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with ruta.open(
        "w", encoding="utf-8"
    ) as archivo:

        json.dump(
            datos,
            archivo,
            ensure_ascii=False,
            indent=2,
        )


def guardar_csv(resultados, ruta):

    campos = [
        "question_id",
        "category",
        "type",
        "difficulty",
        "configuracion",
        "rank",
        "chunk_id",
        "formato_origen",
        "tipo_fuente",
        "archivo",
        "seccion",
        "distancia",
        "score_bge",
    ]

    with ruta.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as archivo:

        escritor = csv.DictWriter(
            archivo,
            fieldnames=campos,
        )

        escritor.writeheader()

        for pregunta in resultados:

            for config, ranking in (
                pregunta["rankings"].items()
            ):

                for documento in ranking:

                    escritor.writerow({
                        "question_id": pregunta["id"],
                        "category": pregunta["category"],
                        "type": pregunta["type"],
                        "difficulty": pregunta["difficulty"],
                        "configuracion": config,
                        "rank": documento["rank"],
                        "chunk_id": documento["id"],
                        "formato_origen": documento[
                            "formato_origen"
                        ],
                        "tipo_fuente": documento[
                            "tipo_fuente"
                        ],
                        "archivo": documento["archivo"],
                        "seccion": documento["seccion"],
                        "distancia": documento["distancia"],
                        "score_bge": documento[
                            "score_bge"
                        ],
                    })


# ============================================================
# RESUMEN DESCRIPTIVO
# ============================================================

def mostrar_resumen(resultados):

    print("\n" + "=" * 65)
    print("RESUMEN DE EVALUACIÓN DOCUMENTAL")
    print("=" * 65)

    print("Preguntas evaluadas:", len(resultados))

    categorias = Counter(
        item["category"] for item in resultados
    )

    print("\nPreguntas por categoría:")

    for categoria, cantidad in sorted(
        categorias.items()
    ):
        print(f"  {categoria}: {cantidad}")

    for configuracion, descripcion in (
        CONFIGURACIONES.items()
    ):

        documentos = [
            documento
            for pregunta in resultados
            for documento in pregunta[
                "rankings"
            ][configuracion]
        ]

        fuentes = Counter(
            item["formato_origen"]
            for item in documentos
        )

        cantidades = [
            len(pregunta["rankings"][configuracion])
            for pregunta in resultados
        ]

        promedio = (
            sum(cantidades) / len(cantidades)
            if cantidades else 0.0
        )

        print("\n" + "-" * 65)
        print(configuracion, "-", descripcion)
        print(
            "Documentos seleccionados:",
            len(documentos),
        )
        print(
            "Promedio de documentos por pregunta:",
            round(promedio, 2),
        )

        print("Distribución por formato de origen:")

        for fuente, cantidad in fuentes.most_common():
            print(f"  {fuente}: {cantidad}")

    print("\nIMPORTANTE:")
    print(
        "Este resumen describe los documentos recuperados."
    )
    print(
        "No mide todavía relevancia, precisión ni "
        "exactitud de respuestas."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Evaluación comparativa de recuperación RAG"
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cantidad de preguntas para prueba inicial",
    )

    args = parser.parse_args()

    if (
        args.limit is not None
        and args.limit <= 0
    ):
        parser.error(
            "--limit debe ser mayor que cero"
        )

    preguntas = cargar_preguntas(
        limite=args.limit
    )

    print("\n" + "=" * 65)
    print("EVALUACIÓN DE RECUPERACIÓN RAG V2")
    print("=" * 65)

    print("Dataset:", DATASET_PATH)
    print("Preguntas:", len(preguntas))

    recuperador = RecuperadorDocumental()

    registros_iniciales = (
        recuperador.collection.count()
    )

    print(
        "Registros ChromaDB:",
        registros_iniciales,
    )

    resultados = []

    inicio_global = time.perf_counter()

    for indice, pregunta in enumerate(
        preguntas, start=1
    ):

        print(
            f"\n[{indice}/{len(preguntas)}] "
            f"{pregunta['id']}: "
            f"{pregunta['question']}"
        )

        resultado = evaluar_pregunta(
            recuperador,
            pregunta,
        )

        resultados.append(resultado)

        print(
            "Candidatos únicos:",
            resultado["cantidad_candidatos"][
                "unicos_multiquery"
            ],
        )

        print(
            "Tiempo:",
            resultado["tiempos_ms"][
                "experimento_total"
            ],
            "ms",
        )

    duracion = (
        time.perf_counter() - inicio_global
    )

    registros_finales = (
        recuperador.collection.count()
    )

    if registros_finales != registros_iniciales:
        raise RuntimeError(
            "El tamaño de la colección cambió "
            "durante la evaluación. "
            "No se puede garantizar una comparación "
            "con un índice constante."
        )

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S")

    nombre_base = (
        f"retrieval_v2_{len(preguntas)}_{timestamp}"
    )

    ruta_json = (
        RESULTS_DIR / f"{nombre_base}.json"
    )

    ruta_csv = (
        RESULTS_DIR / f"{nombre_base}.csv"
    )

    datos = {
        "fecha_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "dataset": str(DATASET_PATH),
        "preguntas_evaluadas": len(preguntas),
        "collection": "ipc_markdown_v3",
        "registros_chroma": registros_finales,
        "top_k_por_consulta": 10,
        "top_final": TOP_FINAL,
        "configuraciones": CONFIGURACIONES,
        "duracion_total_segundos": round(
            duracion, 2
        ),
        "resultados": resultados,
    }

    guardar_json(
        datos,
        ruta_json,
    )

    guardar_csv(
        resultados,
        ruta_csv,
    )

    mostrar_resumen(resultados)

    print("\n" + "=" * 65)
    print("ARCHIVOS GENERADOS")
    print("=" * 65)

    print("JSON:", ruta_json)
    print("CSV:", ruta_csv)
    print(
        "Tiempo total:",
        round(duracion, 2),
        "segundos",
    )


if __name__ == "__main__":
    main()
