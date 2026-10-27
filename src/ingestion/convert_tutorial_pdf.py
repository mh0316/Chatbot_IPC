
from pathlib import Path
import hashlib
import json
import re

import pymupdf


# ============================================================
# CONFIGURACIÓN
# ============================================================

PROJECT_ROOT = Path.home() / "chatbot_ipc"

PDF_PATH = (
    PROJECT_ROOT
    / "documents"
    / "raw"
    / "Corpus documental Beckhoff"
    / "TwinCAT 3"
    / "Tutorial TwinCAT 3.pdf"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "documents"
    / "processed"
    / "twincat_tutorial"
)

ASSETS_DIR = OUTPUT_DIR / "assets_v2"

OUTPUT_MD = OUTPUT_DIR / "Tutorial TwinCAT 3.md"
MANIFEST_PATH = OUTPUT_DIR / "imagenes_manifest.json"

# Evita guardar imágenes diminutas que aparecen
# como elementos decorativos o de navegación.
MIN_IMAGE_WIDTH_PT = 40
MIN_IMAGE_HEIGHT_PT = 30

# Si el PDF contiene una imagen de página completa,
# preferimos que quede registrada para revisión.
MAX_IMAGE_RECTS_PER_PAGE = 100


# ============================================================
# LIMPIAR TEXTO
# ============================================================

def limpiar_texto(texto):
    texto = texto.replace("\r\n", "\n")
    texto = texto.replace("\r", "\n")

    lineas = []

    for linea in texto.splitlines():
        linea = linea.strip()

        # Eliminar encabezados y pies repetidos.
        if re.fullmatch(
            r"Página\s+\d+",
            linea,
            flags=re.IGNORECASE,
        ):
            continue

        if re.match(
            r"^Tutorial TwinCAT 3\s*\|",
            linea,
            flags=re.IGNORECASE,
        ):
            continue

        lineas.append(linea)

    texto = "\n".join(lineas)

    texto = re.sub(
        r"\n{3,}",
        "\n\n",
        texto,
    )

    return texto.strip()


# ============================================================
# DETECTAR ENCABEZADOS
# ============================================================

def convertir_encabezados(texto):
    """
    Detecta títulos habituales del tutorial.

    No altera el código Structured Text.
    """

    resultado = []

    for linea in texto.splitlines():
        linea = linea.strip()

        if not linea:
            resultado.append("")
            continue

        # Capítulos: 1. Qué es TwinCAT 3...
        # Excluye números con múltiples puntos.
        if re.match(
            r"^\d{1,2}\.\s+[A-Za-zÁÉÍÓÚÜÑ¿]",
            linea,
        ):
            resultado.append(f"## {linea}")
            continue

        # Apartados: 1.1 Del PLC clásico...
        if re.match(
            r"^\d{1,2}\.\d{1,2}\s+",
            linea,
        ):
            resultado.append(f"### {linea}")
            continue

        resultado.append(linea)

    return "\n".join(resultado)


# ============================================================
# EXTRACCIÓN DE IMÁGENES
# ============================================================

def obtener_imagenes_visibles(documento, pagina):
    """
    Devuelve imágenes que tienen al menos una
    ubicación visual reconocible en la página.

    get_images() lista recursos del PDF.
    get_image_rects() permite comprobar sus
    ubicaciones de representación.

    Esto no detecta gráficos puramente vectoriales.
    """

    imagenes_visibles = []
    xrefs_pagina = set()

    for imagen in pagina.get_images(full=True):
        xref = imagen[0]

        if xref in xrefs_pagina:
            continue

        xrefs_pagina.add(xref)

        try:
            rectangulos = pagina.get_image_rects(xref)
        except Exception as error:
            print(
                f"Advertencia: no se pudo localizar "
                f"xref={xref}: {error}"
            )
            continue

        for rect in rectangulos[
            :MAX_IMAGE_RECTS_PER_PAGE
        ]:
            if (
                rect.width < MIN_IMAGE_WIDTH_PT
                or rect.height < MIN_IMAGE_HEIGHT_PT
            ):
                continue

            imagenes_visibles.append(
                {
                    "xref": xref,
                    "rect": rect,
                }
            )

    imagenes_visibles.sort(
        key=lambda item: (
            item["rect"].y0,
            item["rect"].x0,
        )
    )

    return imagenes_visibles


def guardar_imagen_unica(
    documento,
    xref,
    imagenes_guardadas,
):
    """
    Guarda una sola copia por xref y reutiliza
    su ruta cuando aparece en otra página.
    """

    if xref in imagenes_guardadas:
        return imagenes_guardadas[xref]

    datos = documento.extract_image(xref)

    contenido = datos["image"]
    extension = datos["ext"].lower()

    # Nombre estable basado en contenido.
    hash_imagen = hashlib.sha256(
        contenido
    ).hexdigest()[:16]

    nombre = f"imagen_{hash_imagen}.{extension}"

    ruta = ASSETS_DIR / nombre

    if not ruta.exists():
        ruta.write_bytes(contenido)

    ruta_relativa = f"assets_v2/{nombre}"

    imagenes_guardadas[xref] = ruta_relativa

    return ruta_relativa


# ============================================================
# CONVERSIÓN PRINCIPAL
# ============================================================

def convertir_pdf():
    if not PDF_PATH.is_file():
        raise FileNotFoundError(
            f"No existe el archivo: {PDF_PATH}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    ASSETS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    imagenes_guardadas = {}
    manifest = []
    partes = [
        "# Tutorial TwinCAT 3",
        "",
        "Fuente original: Tutorial TwinCAT 3.pdf",
        "Fabricante: Beckhoff (material didáctico)",
        "",
    ]

    with pymupdf.open(PDF_PATH) as documento:
        total_paginas = len(documento)

        total_imagenes_visibles = 0

        for numero, pagina in enumerate(
            documento,
            start=1,
        ):
            print(
                f"Procesando página "
                f"{numero}/{total_paginas}"
            )

            partes.append(
                f"\n<!-- Página PDF {numero} -->\n"
            )

            # ----------------------------------------
            # TEXTO
            # ----------------------------------------

            texto = pagina.get_text(
                "text",
                sort=True,
            )

            texto = limpiar_texto(texto)

            texto = convertir_encabezados(texto)

            if texto:
                partes.append(texto)
                partes.append("")

            # ----------------------------------------
            # IMÁGENES VISIBLES
            # ----------------------------------------

            imagenes = obtener_imagenes_visibles(
                documento,
                pagina,
            )

            total_imagenes_visibles += len(imagenes)

            referencias_pagina = set()

            for imagen in imagenes:
                xref = imagen["xref"]
                rect = imagen["rect"]

                ruta_relativa = guardar_imagen_unica(
                    documento,
                    xref,
                    imagenes_guardadas,
                )

                manifest.append(
                    {
                        "pagina": numero,
                        "xref": xref,
                        "imagen": ruta_relativa,
                        "rectangulo": [
                            round(rect.x0, 2),
                            round(rect.y0, 2),
                            round(rect.x1, 2),
                            round(rect.y1, 2),
                        ],
                    }
                )

                # Evita repetir el mismo enlace a una
                # imagen más de una vez por página.
                if ruta_relativa in referencias_pagina:
                    continue

                referencias_pagina.add(
                    ruta_relativa
                )

                partes.append(
                    f"![Recurso gráfico de la "
                    f"página {numero}]"
                    f"({ruta_relativa})"
                )
                partes.append("")

            print(
                "  Imágenes visibles:",
                len(imagenes),
            )

        # --------------------------------------------
        # GUARDAR MARKDOWN
        # --------------------------------------------

        contenido_md = "\n".join(partes).strip()

        OUTPUT_MD.write_text(
            contenido_md + "\n",
            encoding="utf-8",
        )

        # --------------------------------------------
        # GUARDAR MANIFEST DE IMÁGENES
        # --------------------------------------------

        MANIFEST_PATH.write_text(
            json.dumps(
                {
                    "pdf": str(PDF_PATH),
                    "paginas": total_paginas,
                    "imagenes": manifest,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    print("\n" + "=" * 60)
    print("CONVERSIÓN FINALIZADA")
    print("=" * 60)

    print("Páginas procesadas:", total_paginas)
    print(
        "Apariciones visuales detectadas:",
        total_imagenes_visibles,
    )
    print(
        "Recursos únicos guardados:",
        len(imagenes_guardadas),
    )
    print("Markdown:", OUTPUT_MD)
    print("Manifest:", MANIFEST_PATH)

    print(
        "\nIMPORTANTE: "
        "ChromaDB no ha sido modificado."
    )


if __name__ == "__main__":
    convertir_pdf()
