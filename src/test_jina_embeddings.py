from sentence_transformers import SentenceTransformer

MODEL_NAME = "jinaai/jina-embeddings-v5-omni-nano-retrieval"

model = SentenceTransformer(
    MODEL_NAME,
    trust_remote_code=True,
    device="cuda"
)

print("Modelo cargado en:", model.device)

consulta = "¿Cómo funciona un temporizador TON en TwinCAT 3?"
documento = """
El bloque TON es un temporizador de retardo a la conexión.
Cuando la entrada IN permanece activada durante el tiempo definido en PT,
la salida Q cambia a TRUE.
"""

query_embedding = model.encode_query(consulta)
document_embedding = model.encode_document(documento)

print("Dimensión consulta:", query_embedding.shape)
print("Dimensión documento:", document_embedding.shape)

print("Primeros 10 valores del embedding de consulta:")
print(query_embedding[:10])

print("Primeros 10 valores del embedding del documento:")
print(document_embedding[:10])
