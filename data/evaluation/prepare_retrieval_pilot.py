
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_PATH = (
    PROJECT_ROOT / "data/evaluation/baseline_text.json"
)

OUTPUT_PATH = (
    PROJECT_ROOT / "data/evaluation/retrieval_pilot_15.json"
)

PILOT_IDS = [
    "FUND_001",
    "FUND_004",
    "ST_001",
    "ST_006",
    "ST_CODE_001",
    "FB_002",
    "FB_007",
    "RT_003",
    "RT_006",
    "ECAT_004",
    "ADS_003",
    "LIB_003",
    "HMI_004",
    "SAFE_001",
    "TC_004",
]


def main():
    with INPUT_PATH.open("r", encoding="utf-8") as file:
        preguntas = json.load(file)

    preguntas_por_id = {}

    for pregunta in preguntas:
        question_id = pregunta["id"]

        if question_id in preguntas_por_id:
            raise ValueError(f"ID duplicado: {question_id}")

        preguntas_por_id[question_id] = pregunta

    faltantes = [
        question_id
        for question_id in PILOT_IDS
        if question_id not in preguntas_por_id
    ]

    if faltantes:
        raise ValueError(
            f"Preguntas no encontradas: {faltantes}"
        )

    piloto = [
        preguntas_por_id[question_id]
        for question_id in PILOT_IDS
    ]

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            piloto,
            file,
            ensure_ascii=False,
            indent=2
        )

    print("\nConjunto piloto preparado correctamente")
    print(f"Preguntas seleccionadas: {len(piloto)}")
    print(f"Archivo generado: {OUTPUT_PATH}")

    print("\nPreguntas incluidas:")

    for pregunta in piloto:
        print(
            f"{pregunta['id']} | "
            f"{pregunta['category']} | "
            f"{pregunta['difficulty']}"
        )


if __name__ == "__main__":
    main()
