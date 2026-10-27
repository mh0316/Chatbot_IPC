
import json
import os
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

LABELS_PATH = (
    PROJECT_ROOT
    / "data/evaluation/relevance_labels_pilot.json"
)

VALID_LABELS = {0, 1, 2}


# ============================================================
# CARGAR Y GUARDAR PLANTILLA
# ============================================================

def cargar_plantilla():
    if not LABELS_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró la plantilla: {LABELS_PATH}"
        )

    with LABELS_PATH.open("r", encoding="utf-8") as archivo:
        datos = json.load(archivo)

    if "questions" not in datos:
        raise ValueError(
            "La plantilla no contiene la clave 'questions'."
        )

    return datos


def guardar_plantilla(datos):
    """
    Guarda los cambios mediante un archivo temporal y
    reemplazo atómico, reduciendo el riesgo de corrupción.
    """
    temporal = LABELS_PATH.with_suffix(".json.tmp")

    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump(
            datos,
            archivo,
            ensure_ascii=False,
            indent=2
        )

        archivo.flush()
        os.fsync(archivo.fileno())

    os.replace(temporal, LABELS_PATH)


# ============================================================
# VALIDAR ETIQUETAS Y ACTUALIZAR ESTADOS
# ============================================================

def etiqueta_valida(valor):
    return type(valor) is int and valor in VALID_LABELS


def actualizar_estado(pregunta):
    chunks = pregunta["chunks"]

    completos = sum(
        etiqueta_valida(chunk.get("relevance"))
        for chunk in chunks
    )

    pregunta["judgment_status"] = (
        "completed"
        if len(chunks) > 0 and completos == len(chunks)
        else "pending"
    )

    return completos


def resumen_global(datos):
    total = 0
    etiquetados = 0

    for pregunta in datos["questions"]:
        actualizar_estado(pregunta)

        for chunk in pregunta["chunks"]:
            total += 1

            if etiqueta_valida(chunk.get("relevance")):
                etiquetados += 1

    return total, etiquetados


# ============================================================
# MOSTRAR INFORMACIÓN DEL FRAGMENTO
# ============================================================

def mostrar_fragmento(pregunta, chunk, indice, total):
    print("\n" + "=" * 75)
    print(f"PREGUNTA: {pregunta['id']}")
    print("=" * 75)

    print(f"\n{pregunta['question']}")

    print("\n" + "-" * 75)
    print(f"FRAGMENTO {indice + 1}/{total}")
    print("-" * 75)

    print(f"ID: {chunk['chunk_id']}")
    print(f"Fabricante: {chunk.get('fabricante')}")
    print(f"Fuente: {chunk.get('tipo_fuente')}")
    print(f"Documento: {chunk.get('archivo')}")
    print(f"Sección: {chunk.get('seccion')}")

    rankings = chunk.get("rankings", {})

    for nombre, valores in rankings.items():
        print(
            f"\n{nombre.upper()}: "
            f"Vector #{valores.get('vector_rank')} | "
            f"Reranker #{valores.get('reranker_rank')} | "
            f"Score {valores.get('reranker_score')}"
        )

    print("\nCONTENIDO DOCUMENTAL:")
    print("-" * 75)
    print(chunk.get("contenido", ""))
    print("-" * 75)

    actual = chunk.get("relevance")

    if etiqueta_valida(actual):
        print(f"\nEtiqueta actual: {actual}")
    else:
        print("\nEtiqueta actual: SIN EVALUAR")

    if chunk.get("notes"):
        print(f"Nota actual: {chunk['notes']}")


# ============================================================
# MENÚ PRINCIPAL
# ============================================================

def seleccionar_pregunta(datos):
    print("\n" + "=" * 65)
    print("EVALUACIÓN MANUAL DE RELEVANCIA RAG")
    print("=" * 65)

    total, etiquetados = resumen_global(datos)

    print(
        f"\nProgreso general: "
        f"{etiquetados}/{total} fragmentos"
    )

    print("\nPreguntas disponibles:\n")

    for indice, pregunta in enumerate(
        datos["questions"],
        start=1
    ):
        completos = sum(
            etiqueta_valida(chunk.get("relevance"))
            for chunk in pregunta["chunks"]
        )

        total_pregunta = len(pregunta["chunks"])

        estado = (
            "COMPLETADA"
            if total_pregunta > 0 and completos == total_pregunta
            else "PENDIENTE"
        )

        print(
            f"{indice}. {pregunta['id']} "
            f"[{completos}/{total_pregunta}] "
            f"{estado}"
        )

    print("\n0. Guardar y salir")

    while True:
        opcion = input(
            "\nSelecciona una pregunta: "
        ).strip()

        if opcion == "0":
            return None

        if opcion.isdigit():
            indice = int(opcion) - 1

            if 0 <= indice < len(datos["questions"]):
                return datos["questions"][indice]

        print("Opción inválida.")


# ============================================================
# BUSCAR PRIMER FRAGMENTO SIN ETIQUETA
# ============================================================

def primer_fragmento_pendiente(chunks):
    """
    Devuelve la posición del primer fragmento sin
    etiqueta válida.

    Si todos están etiquetados, retorna 0 para
    permitir revisar las anotaciones existentes.
    """
    return next(
        (
            i for i, chunk in enumerate(chunks)
            if not etiqueta_valida(chunk.get("relevance"))
        ),
        0
    )


# ============================================================
# EVALUACIÓN INTERACTIVA DE FRAGMENTOS
# ============================================================

def evaluar_pregunta(pregunta, datos):
    chunks = pregunta["chunks"]

    if not chunks:
        print("\nEsta pregunta no tiene fragmentos.")
        return

    # Reanudar desde el primer fragmento pendiente.
    indice = primer_fragmento_pendiente(chunks)

    while indice < len(chunks):
        chunk = chunks[indice]

        mostrar_fragmento(
            pregunta,
            chunk,
            indice,
            len(chunks)
        )

        print("\nOpciones:")
        print("  0 = Irrelevante")
        print("  1 = Parcialmente relevante")
        print("  2 = Directamente relevante")
        print("  n = Siguiente fragmento")
        print("  p = Fragmento anterior")
        print("  s = Siguiente fragmento sin etiqueta")
        print("  q = Volver al menú principal")

        opcion = input(
            "\nTu elección: "
        ).strip().lower()

        # ----------------------------------------------------
        # ASIGNAR O CORREGIR UNA ETIQUETA
        # ----------------------------------------------------

        if opcion in ("0", "1", "2"):
            chunk["relevance"] = int(opcion)

            print("\nDescribe brevemente tu evaluación.")

            nota = input(
                "Justificación "
                "(Enter para conservar la actual): "
            ).strip()

            if nota:
                chunk["notes"] = nota

            completos = actualizar_estado(pregunta)

            guardar_plantilla(datos)

            print(
                f"\nEtiqueta guardada correctamente. "
                f"Progreso: {completos}/{len(chunks)}"
            )

            indice += 1

        # ----------------------------------------------------
        # SIGUIENTE FRAGMENTO
        # ----------------------------------------------------

        elif opcion == "n":
            if indice < len(chunks) - 1:
                indice += 1
            else:
                print(
                    "\nYa estás en el último fragmento."
                )

        # ----------------------------------------------------
        # FRAGMENTO ANTERIOR
        # ----------------------------------------------------

        elif opcion == "p":
            if indice > 0:
                indice -= 1
            else:
                print(
                    "\nYa estás en el primer fragmento."
                )

        # ----------------------------------------------------
        # BUSCAR SIGUIENTE FRAGMENTO PENDIENTE
        # ----------------------------------------------------

        elif opcion == "s":
            siguiente = next(
                (
                    i
                    for i in range(
                        indice + 1,
                        len(chunks)
                    )
                    if not etiqueta_valida(
                        chunks[i].get("relevance")
                    )
                ),
                None
            )

            # Si no hay pendientes hacia adelante,
            # buscar desde el comienzo.
            if siguiente is None:
                siguiente = next(
                    (
                        i
                        for i in range(len(chunks))
                        if not etiqueta_valida(
                            chunks[i].get("relevance")
                        )
                    ),
                    None
                )

            if siguiente is None:
                print(
                    "\nTodos los fragmentos "
                    "están etiquetados."
                )
            else:
                indice = siguiente

        # ----------------------------------------------------
        # REGRESAR AL MENÚ PRINCIPAL
        # ----------------------------------------------------

        elif opcion == "q":
            actualizar_estado(pregunta)
            guardar_plantilla(datos)

            print("\nProgreso guardado.")

            return

        else:
            print("\nOpción no reconocida.")

    # Guardar al llegar al final de la pregunta.
    completos = actualizar_estado(pregunta)
    guardar_plantilla(datos)

    print("\nHas llegado al final de esta pregunta.")

    if completos == len(chunks):
        print(
            f"La pregunta {pregunta['id']} "
            "está COMPLETADA."
        )
    else:
        print(
            f"La pregunta {pregunta['id']} "
            f"tiene {len(chunks) - completos} "
            "fragmentos pendientes."
        )


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():
    datos = cargar_plantilla()

    try:
        while True:
            pregunta = seleccionar_pregunta(datos)

            if pregunta is None:
                break

            evaluar_pregunta(pregunta, datos)

    except (KeyboardInterrupt, EOFError):
        print("\n\nEvaluación interrumpida.")

    finally:
        total, etiquetados = resumen_global(datos)

        guardar_plantilla(datos)

        print("\n" + "=" * 65)
        print("PROGRESO GUARDADO")
        print("=" * 65)

        print(
            f"Fragmentos evaluados: "
            f"{etiquetados}/{total}"
        )

        print(f"Archivo: {LABELS_PATH}")


if __name__ == "__main__":
    main()
