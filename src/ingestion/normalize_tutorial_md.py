
from pathlib import Path
import re


PROJECT_ROOT = Path.home() / "chatbot_ipc"

INPUT_MD = (
    PROJECT_ROOT
    / "documents/processed/twincat_tutorial"
    / "Tutorial TwinCAT 3.md"
)

OUTPUT_MD = (
    PROJECT_ROOT
    / "documents/processed/twincat_tutorial"
    / "Tutorial TwinCAT 3_normalizado.md"
)


def normalizar_markdown(texto):
    lineas = texto.splitlines()
    resultado = []

    en_indice = False
    encabezados_eliminados = 0
    encabezados_corregidos = 0

    i = 0

    while i < len(lineas):
        linea = lineas[i]
        contenido = linea.strip()

        # -------------------------------------------
        # Eliminar el índice inicial
        # -------------------------------------------

        if contenido == "Contenido":
            siguientes = "\n".join(lineas[i + 1:i + 8])

            if re.search(
                r"^##\s+1\.\s+",
                siguientes,
                flags=re.MULTILINE,
            ):
                en_indice = True
                i += 1
                continue

        if en_indice:
            if re.match(
                r"^<!-- Página PDF \d+ -->$",
                contenido,
            ):
                en_indice = False
            else:
                if re.match(r"^##\s+\d+\.", contenido):
                    encabezados_eliminados += 1

                i += 1
                continue

        # -------------------------------------------
        # Corregir falso encabezado TwinCAT 3.1
        # -------------------------------------------

        if contenido.startswith(
            "### 3.1 Build 4026"
        ):
            linea = linea.replace("### ", "", 1)
            encabezados_corregidos += 1

        # -------------------------------------------
        # Unir encabezados divididos
        # -------------------------------------------

        if re.match(r"^##\s+\d+\.\s+", linea):
            if i + 1 < len(lineas):
                siguiente = lineas[i + 1].strip()

                # Unir continuación en minúscula,
                # sin alterar otros encabezados.
                if (
                    siguiente
                    and not siguiente.startswith(
                        ("#", "<!--", "![")
                    )
                    and re.match(
                        r"^[a-záéíóúñ]",
                        siguiente,
                    )
                    and linea.rstrip().endswith(
                        (" de", " y", " aplicaciones")
                    )
                ):
                    linea = (
                        linea.rstrip()
                        + " "
                        + siguiente
                    )

                    encabezados_corregidos += 1
                    i += 1

        resultado.append(linea)
        i += 1

    texto_final = "\n".join(resultado)

    texto_final = re.sub(
        r"\n{4,}",
        "\n\n\n",
        texto_final,
    )

    return (
        texto_final.strip() + "\n",
        encabezados_eliminados,
        encabezados_corregidos,
    )


def main():
    if not INPUT_MD.exists():
        raise FileNotFoundError(INPUT_MD)

    texto = INPUT_MD.read_text(
        encoding="utf-8"
    )

    normalizado, eliminados, corregidos = (
        normalizar_markdown(texto)
    )

    OUTPUT_MD.write_text(
        normalizado,
        encoding="utf-8",
    )

    print("Normalización finalizada")
    print("Archivo:", OUTPUT_MD)
    print("Encabezados de índice eliminados:", eliminados)
    print("Encabezados corregidos:", corregidos)
    print("ChromaDB no ha sido modificado.")


if __name__ == "__main__":
    main()
