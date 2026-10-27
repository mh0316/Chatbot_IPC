import re

SIGLAS = {
    "IPC": "Industrial Personal Computer, computador industrial",
    "PLC": "Programmable Logic Controller, controlador lógico programable",
    "ST": "Structured Text, texto estructurado",
    "FB": "Function Block, bloque de funciones",
    "POU": "Program Organization Unit",
    "HMI": "Human-Machine Interface",
    "ADS": "Automation Device Specification, comunicación Beckhoff",
    "AMS": "Automation Message Specification",
    "OPC UA": "Open Platform Communications Unified Architecture",
    "XAE": "eXtended Automation Engineering",
    "XAR": "eXtended Automation Runtime",
}


def expandir_consulta(consulta: str) -> str:
    expansiones = []

    for sigla, significado in SIGLAS.items():
        patron = rf"(?<!\w){re.escape(sigla)}(?!\w)"

        if re.search(patron, consulta, re.IGNORECASE):
            expansiones.append(
                f"{sigla}: {significado}"
            )

    if not expansiones:
        return consulta

    contexto = "; ".join(expansiones)

    return (
        f"{consulta}\n"
        f"Terminología técnica relevante: {contexto}"
    )
