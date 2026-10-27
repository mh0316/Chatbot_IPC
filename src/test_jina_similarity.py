from sentence_transformers import SentenceTransformer
import numpy as np

MODEL_NAME = "jinaai/jina-embeddings-v5-omni-nano-retrieval"

model = SentenceTransformer(
    MODEL_NAME,
    trust_remote_code=True,
    device="cuda"
)

consulta = "¿Cómo funciona un temporizador TON en TwinCAT 3?"

documentos = [
    """
    El bloque TON es un temporizador de retardo a la conexión.
    Cuando la entrada IN permanece activa durante el tiempo PT,
    la salida Q cambia a TRUE.
    """,

    """
    EtherCAT es un protocolo de comunicación industrial Ethernet
    utilizado para comunicación en tiempo real entre dispositivos.
    """,

    """
    Una variable BOOL puede almacenar los valores TRUE o FALSE
    y puede utilizarse en Structured Text para representar estados lógicos.
    """
]

query_embedding = model.encode_query(consulta)

document_embeddings = model.encode_document(documentos)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

resultados = []

for i, embedding in enumerate(document_embeddings):
    similitud = cosine_similarity(query_embedding, embedding)
    resultados.append((i, similitud))

resultados.sort(key=lambda x: x[1], reverse=True)

print("\nConsulta:")
print(consulta)

print("\nResultados ordenados por similitud:\n")

for indice, similitud in resultados:
    print(f"Documento {indice + 1}: {similitud:.4f}")
    print(documentos[indice].strip())
    print("-" * 60)
