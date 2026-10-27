
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.query_markdown import (
    RecuperadorDocumental,
)


# ============================================================
# CONSULTAS DE PRUEBA
# ============================================================

PREGUNTA_ORIGINAL = "¿Qué es un IPC?"

PREGUNTA_EXPANDIDA = (
    "¿Qué es un IPC (Industrial Personal Computer o "
    "computador industrial), cuáles son sus características "
    "y qué función cumple dentro de un sistema de "
    "automatización industrial Beckhoff con TwinCAT 3?"
)


# ============================================================
# MOSTRAR RESULTADOS
# ============================================================

def mostrar_ranking(nombre, candidatos, scores):

    resultados = []

    for candidato, score in zip(candidatos, scores):
        resultados.append(
            {
                **candidato,
                "score": float(score),
            }
        )

    resultados.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    print("\n" + "=" * 70)
    print(nombre)
    print("=" * 70)

    for posicion, doc in enumerate(resultados, start=1):

        metadata = doc["metadata"]

        print(f"\nRESULTADO {posicion}")
        print("Archivo:", metadata.get("archivo"))
        print("Sección:", metadata.get("seccion"))
        print("Score BGE:", round(doc["score"], 4))
        print("Contenido:")
        print(doc["documento"][:500])
        print("-" * 70)


# ============================================================
# DIAGNÓSTICO
# ============================================================

def main():

    recuperador = RecuperadorDocumental()

    # Recuperar candidatos con ambas consultas.
    # Se ejecuta una sola vez para mantener
    # exactamente el mismo conjunto documental.

    grupo_original = recuperador.buscar_en_chroma(
        PREGUNTA_ORIGINAL
    )

    grupo_expandido = recuperador.buscar_en_chroma(
        PREGUNTA_EXPANDIDA
    )

    candidatos = recuperador.fusionar_candidatos(
        [
            grupo_original,
            grupo_expandido,
        ]
    )

    print("\nCandidatos de búsqueda original:",
          len(grupo_original))

    print("Candidatos de búsqueda expandida:",
          len(grupo_expandido))

    print("Candidatos únicos:",
          len(candidatos))

    if not candidatos:
        print("No se recuperaron documentos.")
        return

    # -----------------------------------------------
    # PRUEBA A: BGE CON PREGUNTA ORIGINAL
    # -----------------------------------------------

    pares_originales = [
        (PREGUNTA_ORIGINAL, doc["documento"])
        for doc in candidatos
    ]

    scores_originales = recuperador.reranker.predict(
        pares_originales,
        show_progress_bar=False,
    )

    # -----------------------------------------------
    # PRUEBA B: BGE CON PREGUNTA EXPANDIDA
    # -----------------------------------------------

    pares_expandidos = [
        (PREGUNTA_EXPANDIDA, doc["documento"])
        for doc in candidatos
    ]

    scores_expandidos = recuperador.reranker.predict(
        pares_expandidos,
        show_progress_bar=False,
    )

    # -----------------------------------------------
    # MOSTRAR TOP 5 DE CADA CONFIGURACIÓN
    # -----------------------------------------------

    mostrar_ranking(
        "A. BGE CON PREGUNTA ORIGINAL",
        candidatos,
        scores_originales,
    )

    mostrar_ranking(
        "B. BGE CON PREGUNTA EXPANDIDA",
        candidatos,
        scores_expandidos,
    )


if __name__ == "__main__":
    main()
