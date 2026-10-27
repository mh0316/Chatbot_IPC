import contextlib
import io
import os
import json
import re
import sys
import time

from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings


# ============================================================
# CONFIGURACIÓN
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.generation.generate_answer import (
    GeneradorQwen,
    MODEL_ID,
    MAX_NEW_TOKENS,
)

from src.retrieval.query_markdown import (
    recuperar_documentos,
    RETRIEVAL_TOP_K,
    FINAL_TOP_K,
)


# ============================================================
# MODALIDADES
# ============================================================

# MODO_RAG=0: Qwen sin recuperación documental.
# MODO_RAG=1: Qwen con RAG.

USAR_RAG = os.getenv("MODO_RAG", "1") == "1"

# Configuración C por defecto.
# RAG_MODO_ST=1 activa la configuración experimental E.

MODO_ST_EXPERIMENTAL = (
    os.getenv("RAG_MODO_ST", "0") == "1"
)

CONFIGURACION_RECUPERACION = (
    "SIN_RAG"
    if not USAR_RAG
    else (
        "E_ST_experimental"
        if MODO_ST_EXPERIMENTAL
        else "C_original"
    )
)


# ============================================================
# RUTAS
# ============================================================

RESULTS_DIR = PROJECT_ROOT / "results" / "generation"

RESULTS_FILE = RESULTS_DIR / (
    "respuestas_rag.jsonl"
    if USAR_RAG
    else "respuestas_base.jsonl"
)

DEBUG_FILE = PROJECT_ROOT / "debug_retrieval.txt"

console = Console()


# ============================================================
# MOSTRAR RESPUESTA
# ============================================================

def mostrar_respuesta(respuesta):
    console.print()

    console.print(
        Panel(
            Markdown(respuesta),
            title="Respuesta educativa",
            border_style="cyan",
            padding=(1, 2),
        )
    )


# ============================================================
# OBTENER FUENTES CITADAS
# ============================================================

def obtener_fuentes_citadas(respuesta, documentos):
    """
    Extrae las referencias [Fuente N] presentes
    en la respuesta de Qwen.

    No verifica automáticamente que la cita
    respalde correctamente cada afirmación.
    """

    if not documentos:
        return []

    indices = {
        int(numero)
        for numero in re.findall(
            r"\bFuente\s+(\d+)\b",
            respuesta,
            flags=re.IGNORECASE,
        )
    }

    # También admite referencias como:
    # [Fuente 1, Fuente 3]

    for grupo in re.findall(
        r"\[Fuentes?\s+([\d,\s]+)\]",
        respuesta,
        flags=re.IGNORECASE,
    ):
        indices.update(
            int(numero)
            for numero in re.findall(r"\d+", grupo)
        )

    fuentes = []

    for indice, documento in enumerate(
        documentos,
        start=1,
    ):
        if indice not in indices:
            continue

        metadata = documento.get("metadata") or {}

        fuentes.append(
            {
                "numero": indice,
                "id": documento.get("id"),
                "fabricante": metadata.get(
                    "fabricante",
                    "Desconocido",
                ),
                "archivo": metadata.get(
                    "archivo",
                    "Desconocido",
                ),
                "seccion": metadata.get(
                    "seccion",
                    "Sin sección",
                ),
                "chunk": metadata.get("chunk_index"),
                "ruta": metadata.get("ruta"),

                # Clave real del recuperador:
                "reranker_score": documento.get(
                    "score_reranker"
                ),
            }
        )

    return fuentes


# ============================================================
# MOSTRAR FUENTES
# ============================================================

def mostrar_fuentes(fuentes):
    console.print()
    console.rule("[bold]Fuentes documentales[/bold]")

    if not USAR_RAG:
        console.print(
            "[cyan]Modo Qwen base: "
            "no se utilizaron documentos RAG.[/cyan]"
        )
        return

    if not fuentes:
        console.print(
            "[yellow]La respuesta no contiene "
            "referencias identificables.[/yellow]"
        )
        return

    tabla = Table(
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )

    tabla.add_column("Referencia", no_wrap=True)
    tabla.add_column("Documento")
    tabla.add_column("Sección")

    for fuente in fuentes:
        tabla.add_row(
            f"[Fuente {fuente['numero']}]",
            str(fuente["archivo"]),
            str(fuente["seccion"]),
        )

    console.print(tabla)


# ============================================================
# CONSTRUIR MÉTRICAS
# ============================================================

def construir_metricas(
    resultado,
    tiempo_retrieval,
    tiempo_total,
    cantidad_documentos,
):
    return {
        "tiempo_retrieval_s": round(
            tiempo_retrieval,
            4,
        ),
        "tiempo_generacion_s": round(
            resultado["tiempo_generacion"],
            4,
        ),
        "tiempo_total_s": round(
            tiempo_total,
            4,
        ),
        "tokens_entrada": resultado["tokens_entrada"],
        "tokens_salida": resultado["tokens_salida"],
        "tokens_por_segundo": round(
            resultado["tokens_por_segundo"],
            2,
        ),
        "limite_alcanzado": resultado["limite_alcanzado"],
        "vram_asignada_gb": round(
            resultado["vram_asignada_gb"],
            3,
        ),
        "vram_maxima_pytorch_gb": round(
            resultado["vram_maxima_gb"],
            3,
        ),
        "documentos_recuperados": cantidad_documentos,
    }


# ============================================================
# MOSTRAR MÉTRICAS
# ============================================================

def mostrar_metricas(metricas):
    console.print()
    console.rule("[bold]Métricas de la respuesta[/bold]")

    tabla = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
    )

    tabla.add_column("Métrica", style="bold")
    tabla.add_column("Valor", justify="right")

    tabla.add_row(
        "Tiempo de recuperación",
        f"{metricas['tiempo_retrieval_s']:.2f} s",
    )

    tabla.add_row(
        "Tiempo de generación",
        f"{metricas['tiempo_generacion_s']:.2f} s",
    )

    tabla.add_row(
        "Tiempo total",
        f"{metricas['tiempo_total_s']:.2f} s",
    )

    tabla.add_row(
        "Tokens de entrada",
        str(metricas["tokens_entrada"]),
    )

    tabla.add_row(
        "Tokens de salida",
        str(metricas["tokens_salida"]),
    )

    tabla.add_row(
        "Tokens por segundo",
        f"{metricas['tokens_por_segundo']:.2f}",
    )

    tabla.add_row(
        "Límite de tokens alcanzado",
        (
            "Sí"
            if metricas["limite_alcanzado"]
            else "No"
        ),
    )

    tabla.add_row(
        "VRAM máxima PyTorch",
        f"{metricas['vram_maxima_pytorch_gb']:.2f} GB",
    )

    console.print(tabla)


# ============================================================
# REGISTRO DE DOCUMENTOS RECUPERADOS
# ============================================================

def guardar_debug_retrieval(consulta, documentos):
    """
    Registra los documentos entregados a Qwen.

    Solamente se utiliza cuando RAG está activo.
    """

    if not USAR_RAG or not documentos:
        return

    with DEBUG_FILE.open(
        "a",
        encoding="utf-8",
    ) as archivo:

        archivo.write("\n" + "=" * 70 + "\n")
        archivo.write(f"PREGUNTA: {consulta}\n")
        archivo.write(
            f"CONFIGURACIÓN: "
            f"{CONFIGURACION_RECUPERACION}\n"
        )

        for i, documento in enumerate(
            documentos,
            start=1,
        ):
            metadata = documento.get("metadata") or {}

            archivo.write(f"\n--- FUENTE {i} ---\n")

            archivo.write(
                f"Archivo: "
                f"{metadata.get('archivo', 'N/D')}\n"
            )

            archivo.write(
                f"Sección: "
                f"{metadata.get('seccion', 'N/D')}\n"
            )

            archivo.write(
                f"Score BGE: "
                f"{documento.get('score_reranker', 'N/D')}\n"
            )

            archivo.write(
                f"Contenido:\n"
                f"{documento.get('documento', '')}\n"
            )


# ============================================================
# REGISTRO JSONL PARA EVALUACIÓN
# ============================================================

def guardar_resultado(
    consulta,
    respuesta,
    documentos,
    fuentes,
    metricas,
    numero_consulta,
):
    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    registro = {
        "fecha_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "numero_consulta": numero_consulta,

        "metodo": (
            "RAG"
            if USAR_RAG
            else "BASE"
        ),

        "modelo": MODEL_ID,

        "pregunta": consulta,

        "respuesta": respuesta,

        "configuracion": {
            "usar_rag": USAR_RAG,

            "retrieval_top_k": (
                RETRIEVAL_TOP_K if USAR_RAG else 0
            ),

            "final_top_k": (
                3 if USAR_RAG else 0
            ),

            "configuracion_recuperacion":
                CONFIGURACION_RECUPERACION,

            "multi_query": (
                True if USAR_RAG else False
            ),

            "reranker_expansion": False,

            "modo_st_experimental": (
                MODO_ST_EXPERIMENTAL
                if USAR_RAG
                else False
            ),

            "max_new_tokens": MAX_NEW_TOKENS,

            "filtro_fabricante": (
                "Beckhoff"
                if USAR_RAG
                else None
            ),
        },

        "metricas": metricas,

        "fuentes_citadas": fuentes,

        "documentos_recuperados": [
            {
                "id": documento.get("id"),

                "metadata": documento.get("metadata"),

                # Se lee la puntuación real y se conserva
                # el nombre de salida JSONL anterior.
                "reranker_score": documento.get(
                    "score_reranker"
                ),

                "distancia": documento.get("distancia"),

                "documento": documento.get("documento"),
            }
            for documento in documentos
        ],
    }

    with RESULTS_FILE.open(
        "a",
        encoding="utf-8",
    ) as archivo:

        archivo.write(
            json.dumps(
                registro,
                ensure_ascii=False,
                default=str,
            ) + "\n"
        )



def leer_consulta_multilinea():
    """
    Permite escribir o pegar preguntas y código
    Structured Text de múltiples líneas.

    La consulta termina cuando el usuario escribe
    FIN en una línea independiente.
    """

    console.print()
    console.print(
        "[bold cyan]Tu pregunta[/bold cyan] "
        "[dim](escribe FIN en una línea "
        "independiente para enviar)[/dim]"
    )

    lineas = []

    while True:
        try:
            linea = input()

        except EOFError:
            if not lineas:
                raise
            break

        if linea.strip() == "FIN":
            break

        # Permitir salir sin enviar consulta.
        if not lineas and linea.strip().lower() in (
            "salir",
            "exit",
        ):
            return "salir"

        lineas.append(linea)

    return "\n".join(lineas).strip()



# ============================================================
# ENTRADA INTERACTIVA DE CONSULTAS
# ============================================================

def crear_lector_consultas():
    """
    Entrada general para preguntas teóricas y código ST.

    Enter: enviar consulta.
    Alt + Enter: agregar salto de línea.
    Ctrl + J: agregar salto de línea alternativo.

    Admite pegar texto multilínea sin enviarlo
    automáticamente, cuando la terminal soporta
    bracketed paste.
    """

    teclas = KeyBindings()

    @teclas.add("enter")
    def enviar_consulta(event):
        texto = event.current_buffer.text

        if texto.strip():
            event.current_buffer.validate_and_handle()

    @teclas.add("escape", "enter")
    def nueva_linea_alt(event):
        event.current_buffer.insert_text("\n")

    @teclas.add("c-j")
    def nueva_linea_ctrl(event):
        event.current_buffer.insert_text("\n")

    sesion = PromptSession(
        multiline=True,
        key_bindings=teclas,
        enable_history_search=True,
        prompt_continuation=lambda width, line_number, is_soft_wrap: (
            " " * width
        ),
    )

    return sesion


def leer_consulta(sesion):
    """
    Devuelve la pregunta completa como un único texto.
    """

    return sesion.prompt("Tu pregunta: ").strip()



# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():
    console.print()

    console.print(
        Panel.fit(
            "[bold]TUTOR DE PROGRAMACIÓN INDUSTRIAL[/bold]\n"
            "[cyan]Beckhoff · TwinCAT 3[/cyan]",
            border_style="cyan",
            padding=(1, 4),
        )
    )

    # Mostrar la modalidad actual.

    if USAR_RAG:
        console.print(
            "[green]Modalidad: Qwen + RAG[/green]"
        )

        console.print(
            f"[cyan]Recuperación: "
            f"{CONFIGURACION_RECUPERACION}[/cyan]"
        )
    else:
        console.print(
            "[yellow]Modalidad: Qwen base "
            "(SIN_RAG)[/yellow]"
        )

    # --------------------------------------------------------
    # CARGAR QWEN
    # --------------------------------------------------------

    with console.status(
        "[cyan]Preparando el tutor...[/cyan]",
        spinner="dots",
    ):
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            generador = GeneradorQwen()

    console.print(
        "[green]Tutor listo para responder.[/green]"
    )

    numero_consulta = 0
    sesion_consultas = crear_lector_consultas()

    # --------------------------------------------------------
    # CICLO DE CONSULTAS
    # --------------------------------------------------------

    while True:
        console.print()

        try:
            consulta = leer_consulta(sesion_consultas)

        except (KeyboardInterrupt, EOFError):
            console.print("\nSesión finalizada.")
            break

        if consulta.lower() in ("salir", "exit"):
            console.print("\nSesión finalizada.")
            break

        if not consulta:
            continue

        numero_consulta += 1

        try:
            inicio_total = time.perf_counter()

            documentos = []
            tiempo_retrieval = 0.0

            # ------------------------------------------------
            # RECUPERACIÓN Y GENERACIÓN
            # ------------------------------------------------

            with console.status(
                "[cyan]Preparando respuesta...[/cyan]",
                spinner="dots",
            ):
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):

                    # ----------------------------------------
                    # RECUPERACIÓN DOCUMENTAL OPCIONAL
                    # ----------------------------------------

                    if USAR_RAG:
                        inicio_retrieval = time.perf_counter()

                        documentos = recuperar_documentos(
                            consulta,
                            top_final=3,
                            multi_query=True,
                            reranker_expansion=False,
                            modo_st=MODO_ST_EXPERIMENTAL,
                        )

                        tiempo_retrieval = (
                            time.perf_counter()
                            - inicio_retrieval
                        )

                        guardar_debug_retrieval(
                            consulta,
                            documentos,
                        )

                    # ----------------------------------------
                    # GENERACIÓN CON QWEN
                    # ----------------------------------------

                    # En modo BASE, documentos = [].
                    # La función construir_prompt_usuario
                    # debe admitir listas vacías.

                    resultado = generador.generar_respuesta(
                        consulta,
                        documentos,
                    )

            # ------------------------------------------------
            # MÉTRICAS
            # ------------------------------------------------

            tiempo_total = (
                time.perf_counter() - inicio_total
            )

            respuesta = resultado["respuesta"]

            metricas = construir_metricas(
                resultado,
                tiempo_retrieval,
                tiempo_total,
                len(documentos),
            )

            # ------------------------------------------------
            # FUENTES
            # ------------------------------------------------

            fuentes = obtener_fuentes_citadas(
                respuesta,
                documentos,
            )

            # ------------------------------------------------
            # PRESENTACIÓN
            # ------------------------------------------------

            mostrar_respuesta(respuesta)
            mostrar_fuentes(fuentes)
            mostrar_metricas(metricas)

            # ------------------------------------------------
            # GUARDAR RESULTADOS
            # ------------------------------------------------

            guardar_resultado(
                consulta,
                respuesta,
                documentos,
                fuentes,
                metricas,
                numero_consulta,
            )

        except Exception as error:
            console.print(
                f"\n[bold red]Error:[/bold red] "
                f"{error}"
            )


if __name__ == "__main__":
    main()
