import argparse
import json
import math
import random
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import torch
from transformers import (
    AutoProcessor,
    BitsAndBytesConfig,
    Qwen3VLForConditionalGeneration,
)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/evaluation"
RESULTS = ROOT / "results/retrieval"

INPUT = RESULTS / "retrieval_v2_76_20261019_130055.json"
HUMAN = DATA / "relevance_labels_retrieval_v2_76_20261019_130055.json"

OUTPUT = DATA / "relevance_labels_auto_20.json"
REPORT = RESULTS / "relevance_auto_20_report.json"

MODEL = "Qwen/Qwen3-VL-4B-Instruct"
CONFIGS = ("A", "B", "C", "D")
SEED = 20261019


def leer(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def guardar(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporal = path.with_suffix(".tmp")
    temporal.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    temporal.replace(path)


def muestra_20(resultados):
    grupos = defaultdict(list)
    for p in resultados:
        grupos[p["category"]].append(p)

    rng = random.Random(SEED)
    seleccionados = []

    for categoria in sorted(grupos):
        grupo = sorted(grupos[categoria], key=lambda x: x["id"])
        if len(grupo) < 2:
            raise ValueError(f"Categoría insuficiente: {categoria}")

        elegidos = []

        if categoria == "fundamentos":
            elegidos.append(
                next(p for p in grupo if p["id"] == "FUND_001")
            )

        while len(elegidos) < 2:
            restantes = [
                p for p in grupo
                if p["id"] not in {x["id"] for x in elegidos}
            ]
            dificultades = {
                p["difficulty"] for p in elegidos
            }
            distintos = [
                p for p in restantes
                if p["difficulty"] not in dificultades
            ]
            elegidos.append(rng.choice(distintos or restantes))

        seleccionados.extend(elegidos)

    ids = {p["id"] for p in seleccionados}
    return [p for p in resultados if p["id"] in ids]


def etiquetas_humanas():
    if not HUMAN.exists():
        return {}

    resultado = {}
    for pregunta in leer(HUMAN).get("preguntas", []):
        for chunk in pregunta.get("chunks", []):
            etiqueta = chunk.get("relevance")
            if etiqueta in (0, 1, 2):
                resultado[
                    (pregunta["id"], chunk["chunk_id"])
                ] = etiqueta
    return resultado


def pool_top3(pregunta):
    docs = {}
    for config in CONFIGS:
        for doc in pregunta["rankings"][config]:
            docs.setdefault(doc["id"], doc)
    return list(docs.values())


def cargar_qwen():
    print("\nCargando Qwen como juez de relevancia...")

    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )

    processor = AutoProcessor.from_pretrained(
        MODEL,
        trust_remote_code=True,
    )

    model = Qwen3VLForConditionalGeneration.from_pretrained(
        MODEL,
        quantization_config=quant,
        device_map="auto",
        dtype="auto",
        trust_remote_code=True,
    )
    model.eval()

    return processor, model


def generar_json(processor, model, pregunta, documentos):
    entradas = []

    for i, doc in enumerate(documentos):
        contenido = doc.get("documento", "")
        # Controlar memoria/contexto. El truncamiento
        # se registra para transparentar la evaluación.
        texto = contenido[:3500]
        entradas.append(
            f"FRAGMENTO {i}\n{texto}\n"
        )

    instruccion = """
Eres un evaluador de relevancia documental de
programación industrial, TwinCAT 3 y computadores IPC.

Califica cada fragmento respecto a la pregunta.

Escala:
0 = irrelevante, no aporta evidencia útil.
1 = parcialmente relevante, aporta contexto o evidencia limitada.
2 = directamente relevante, aporta evidencia concreta
para contestar una parte sustancial de la pregunta.

Evalúa SOLO el contenido proporcionado.
No uses conocimientos externos para completar fragmentos.
No favorezcas una fuente por su procedencia.
No consideres puntuaciones de embeddings o rerankers.

Devuelve únicamente un objeto JSON.
Las claves son los números de fragmento como cadenas.
Los valores son enteros 0, 1 o 2.
Incluye todas las claves solicitadas.
"""

    prompt = (
        "PREGUNTA:\n"
        + pregunta
        + "\n\nFRAGMENTOS:\n"
        + "\n".join(entradas)
        + "\nResponde exclusivamente en JSON."
    )

    messages = [
        {"role": "system", "content": instruccion},
        {"role": "user", "content": prompt},
    ]

    texto_chat = processor.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = processor(
        text=[texto_chat],
        return_tensors="pt",
        padding=True,
    ).to(model.device)

    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            max_new_tokens=220,
            do_sample=False,
            pad_token_id=processor.tokenizer.eos_token_id,
        )

    nuevos_tokens = generated[
        0, inputs["input_ids"].shape[1]:
    ]

    respuesta = processor.tokenizer.decode(
        nuevos_tokens,
        skip_special_tokens=True,
    ).strip()

    coincidencia = re.search(r"\{[\s\S]*?\}", respuesta)

    if not coincidencia:
        raise ValueError(
            f"Qwen no devolvió JSON: {respuesta[:300]}"
        )

    
    valores_originales = json.loads(coincidencia.group(0))

    # Aceptar claves "0", "1" o "FRAGMENTO 0", "FRAGMENTO 1".
    valores = {}

    for clave, valor in valores_originales.items():
        coincidencia_clave = re.fullmatch(
            r"(?:FRAGMENTO\s*)?(\d+)",
            str(clave).strip(),
            flags=re.IGNORECASE
        )

        if not coincidencia_clave:
            raise ValueError(f"Clave inválida: {clave}")

        indice = coincidencia_clave.group(1)

        if indice in valores:
            raise ValueError(f"Clave duplicada: {indice}")

        valores[indice] = valor

    esperado = {str(i) for i in range(len(documentos))}

    if set(valores.keys()) != esperado:
        raise ValueError(f"Claves incompletas: {valores}")

    if any(
        type(v) is not int or v not in (0, 1, 2)
        for v in valores.values()
    ):
        raise ValueError(f"Etiquetas inválidas: {valores}")

    return valores


def dcg(rels):
    return sum(
        (2 ** rel - 1) / math.log2(i + 2)
        for i, rel in enumerate(rels)
    )


def generar_reporte(preguntas, juicios):
    resumen = {}

    for config in CONFIGS:
        valores = []
        por_categoria = defaultdict(list)
        por_formato = defaultdict(list)

        for p in preguntas:
            pool = pool_top3(p)
            qid = p["id"]

            # Ranking ideal común a las cuatro configuraciones
            todas = [
                juicios.get(qid, {}).get(d["id"], {}).get("relevance")
                for d in pool
            ]

            if any(v is None for v in todas):
                continue

            ranking = p["rankings"][config]
            if len(ranking) != 3:
                continue

            rel = [
                juicios[qid][d["id"]]["relevance"]
                for d in ranking
            ]

            ideal = sorted(todas, reverse=True)[:3]
            ideal_dcg = dcg(ideal)

            registro = {
                "precision3": sum(x == 2 for x in rel) / 3,
                "hit3": int(any(x == 2 for x in rel)),
                "ndcg3": (
                    dcg(rel) / ideal_dcg
                    if ideal_dcg > 0 else 0.0
                ),
            }

            valores.append(registro)
            por_categoria[p["category"]].append(registro)

            for doc, relevance in zip(ranking, rel):
                por_formato[
                    doc.get("formato_origen", "desconocido")
                ].append(relevance)

        def promedio(registros, campo):
            if not registros:
                return None
            return sum(x[campo] for x in registros) / len(registros)

        resumen[config] = {
            "preguntas_evaluadas": len(valores),
            "precision_at_3": promedio(valores, "precision3"),
            "hit_at_3": promedio(valores, "hit3"),
            "ndcg_at_3": promedio(valores, "ndcg3"),
            "precision_por_categoria": {
                cat: promedio(reg, "precision3")
                for cat, reg in por_categoria.items()
            },
            "relevancia_por_formato": {
                formato: {
                    "fragmentos": len(rels),
                    "directamente_relevantes": sum(
                        r == 2 for r in rels
                    ),
                }
                for formato, rels in por_formato.items()
            },
        }

    return resumen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    if args.limit not in (20, 76):
        parser.error("--limit debe ser 20 o 76")

    evaluacion = leer(INPUT)
    preguntas = (
        muestra_20(evaluacion["resultados"])
        if args.limit == 20
        else evaluacion["resultados"]
    )

    output = (
        OUTPUT if args.limit == 20
        else DATA / "relevance_labels_auto_76.json"
    )
    report = (
        REPORT if args.limit == 20
        else RESULTS / "relevance_auto_76_report.json"
    )

    if output.exists():
        guardado = leer(output)
        if (
            guardado.get("modelo") != MODEL
            or guardado.get("ids_preguntas")
            != [p["id"] for p in preguntas]
        ):
            raise ValueError(
                "La evaluación guardada no corresponde "
                "a este modelo o muestra."
            )
        juicios = guardado["juicios"]
    else:
        juicios = {}

    humanos = etiquetas_humanas()

    # Los juicios humanos tienen prioridad.
    for p in preguntas:
        qid = p["id"]
        juicios.setdefault(qid, {})

        for doc in pool_top3(p):
            cid = doc["id"]
            if (qid, cid) in humanos:
                juicios[qid][cid] = {
                    "relevance": humanos[(qid, cid)],
                    "evaluador": "humano",
                }

    def guardar_progreso():
        guardar(output, {
            "modelo": MODEL,
            "metodo": "LLM_as_a_judge",
            "escala": [0, 1, 2],
            "ids_preguntas": [p["id"] for p in preguntas],
            "juicios": juicios,
        })

    guardar_progreso()

    pendientes = sum(
        1
        for p in preguntas
        for doc in pool_top3(p)
        if doc["id"] not in juicios[p["id"]]
    )

    print("Preguntas:", len(preguntas))
    print("Etiquetas pendientes:", pendientes)
    print("Resultado:", output)

    if pendientes:
        processor, model = cargar_qwen()

        for numero, p in enumerate(preguntas, 1):
            qid = p["id"]
            docs = [
                doc for doc in pool_top3(p)
                if doc["id"] not in juicios[qid]
            ]

            if not docs:
                continue

            print(
                f"[{numero}/{len(preguntas)}] "
                f"{qid}: {len(docs)} documentos",
                flush=True,
            )

            # Segundo intento si la salida JSON falla.
            for intento in range(2):
                try:
                    etiquetas = generar_json(
                        processor, model,
                        p["question"], docs
                    )
                    break
                except Exception as exc:
                    if intento == 1:
                        print(
                            f"ERROR {qid}: {exc}. "
                            "Se deja pendiente."
                        )
                        etiquetas = None

            if etiquetas is None:
                continue

            for i, doc in enumerate(docs):
                juicios[qid][doc["id"]] = {
                    "relevance": etiquetas[str(i)],
                    "evaluador": "Qwen_automatico",
                    "texto_truncado": (
                        len(doc.get("documento", "")) > 3500
                    ),
                }

            guardar_progreso()

    metricas = generar_reporte(preguntas, juicios)

    informe = {
        "fecha_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "evaluacion": "automatica_exploratoria",
        "modelo_juez": MODEL,
        "preguntas_objetivo": len(preguntas),
        "metricas": metricas,
        "limitaciones": [
            "Juicios del modelo no equivalen a etiquetas humanas.",
            "Los textos extensos pueden estar truncados.",
            "nDCG se calcula contra el pool común de Top 3.",
            "No se ha evaluado aún la generación de respuestas.",
        ],
    }

    guardar(report, informe)

    print("\nRESULTADOS")
    print("=" * 55)

    for config, datos in metricas.items():
        print(f"\nConfiguración {config}")
        print("Preguntas completas:", datos["preguntas_evaluadas"])

        for nombre in (
            "precision_at_3",
            "hit_at_3",
            "ndcg_at_3",
        ):
            valor = datos[nombre]
            print(
                nombre,
                f"{valor:.4f}" if valor is not None else "N/D"
            )

    print("\nEtiquetas:", output)
    print("Informe:", report)


if __name__ == "__main__":
    main()
