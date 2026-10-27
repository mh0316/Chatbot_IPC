
import json
import random
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ORIGEN = (
    ROOT / "results/retrieval"
    / "retrieval_v2_76_20261019_130055.json"
)

ETIQUETAS_ORIGINALES = (
    ROOT / "data/evaluation"
    / "relevance_labels_retrieval_v2_76_20261019_130055.json"
)

DESTINO = (
    ROOT / "results/retrieval"
    / "retrieval_v2_20_muestra.json"
)

ETIQUETAS_DESTINO = (
    ROOT / "data/evaluation"
    / "relevance_labels_retrieval_v2_20_muestra.json"
)

SEED = 20261019
CONFIGS = ("A", "B", "C", "D")


def leer(ruta):
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def guardar(ruta, contenido):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as f:
        json.dump(
            contenido, f,
            ensure_ascii=False, indent=2
        )


def seleccionar(datos):
    grupos = defaultdict(list)

    for pregunta in datos:
        grupos[pregunta["category"]].append(pregunta)

    if len(grupos) != 10:
        raise ValueError(
            f"Se esperaban 10 categorías; hay {len(grupos)}."
        )

    rng = random.Random(SEED)
    seleccion = []

    for categoria in sorted(grupos):
        grupo = sorted(
            grupos[categoria], key=lambda p: p["id"]
        )

        if len(grupo) < 2:
            raise ValueError(
                f"Menos de 2 preguntas en {categoria}"
            )

        elegidas = []

        # Preservamos la pregunta ya anotada.
        if categoria == "fundamentos":
            inicial = next(
                (p for p in grupo if p["id"] == "FUND_001"),
                None
            )
            if inicial is None:
                raise ValueError("No existe FUND_001")
            elegidas.append(inicial)

        # Favorecer distinta dificultad cuando exista.
        while len(elegidas) < 2:
            restantes = [
                p for p in grupo if p not in elegidas
            ]
            dificultades = {
                p["difficulty"] for p in elegidas
            }

            diferentes = [
                p for p in restantes
                if p["difficulty"] not in dificultades
            ]

            candidatos = diferentes or restantes
            elegidas.append(rng.choice(candidatos))

        seleccion.extend(elegidas)

    # Conservar el orden original de las preguntas.
    ids = {p["id"] for p in seleccion}
    return [p for p in datos if p["id"] in ids]


def preparar_etiquetas(preguntas, anteriores):
    anteriores_por_id = {
        p["id"]: p for p in anteriores.get("preguntas", [])
    }

    nuevas = []
    reutilizadas = 0

    for pregunta in preguntas:
        previo = anteriores_por_id.get(
            pregunta["id"], {}
        )

        previos_por_chunk = {
            c["chunk_id"]: c
            for c in previo.get("chunks", [])
        }

        chunks = {}

        for config in CONFIGS:
            for doc in pregunta["rankings"][config]:
                cid = doc["id"]
                if cid in chunks:
                    continue

                anterior = previos_por_chunk.get(cid, {})
                etiqueta = anterior.get("relevance")

                if etiqueta is not None:
                    reutilizadas += 1

                chunks[cid] = {
                    "chunk_id": cid,
                    "archivo": doc.get("archivo"),
                    "seccion": doc.get("seccion"),
                    "ruta": doc.get("ruta"),
                    "tipo_fuente": doc.get("tipo_fuente"),
                    "formato_origen": doc.get(
                        "formato_origen"
                    ),
                    "elementos": doc.get("elementos", {}),
                    "contenido": doc.get("documento", ""),
                    "relevance": etiqueta,
                    "notes": anterior.get("notes", ""),
                }

        nuevas.append({
            "id": pregunta["id"],
            "question": pregunta["question"],
            "category": pregunta["category"],
            "type": pregunta.get("type"),
            "difficulty": pregunta["difficulty"],
            "chunks": list(chunks.values()),
        })

    return {
        "archivo_origen": DESTINO.name,
        "escala": {
            "0": "Irrelevante",
            "1": "Parcialmente relevante",
            "2": "Directamente relevante",
        },
        "preguntas": nuevas,
    }, reutilizadas


def main():
    if DESTINO.exists() or ETIQUETAS_DESTINO.exists():
        raise FileExistsError(
            "La muestra ya existe. No se sobrescribe para "
            "proteger las etiquetas manuales."
        )

    evaluacion = leer(ORIGEN)
    preguntas = seleccionar(evaluacion["resultados"])

    if len(preguntas) != 20:
        raise ValueError("La muestra no tiene 20 preguntas.")

    muestra = {
        **{
            k: v for k, v in evaluacion.items()
            if k != "resultados"
        },
        "preguntas_evaluadas": 20,
        "tipo_muestra": "estratificada_2_por_categoria",
        "semilla": SEED,
        "archivo_evaluacion_completa": ORIGEN.name,
        "resultados": preguntas,
    }

    anteriores = (
        leer(ETIQUETAS_ORIGINALES)
        if ETIQUETAS_ORIGINALES.exists()
        else {"preguntas": []}
    )

    etiquetas, reutilizadas = preparar_etiquetas(
        preguntas, anteriores
    )

    guardar(DESTINO, muestra)
    guardar(ETIQUETAS_DESTINO, etiquetas)

    print("\nMUESTRA DE EVALUACIÓN RAG")
    print("=" * 55)
    print("Preguntas:", len(preguntas))
    print("Etiquetas humanas reutilizadas:", reutilizadas)

    for pregunta in preguntas:
        print(
            pregunta["id"],
            "|", pregunta["category"],
            "|", pregunta["difficulty"]
        )

    total = sum(
        len(p["chunks"]) for p in etiquetas["preguntas"]
    )

    print("\nFragmentos para etiquetar:", total)
    print("Fragmentos pendientes:", total - reutilizadas)
    print("\nMuestra:", DESTINO)
    print("Etiquetas:", ETIQUETAS_DESTINO)


if __name__ == "__main__":
    main()
