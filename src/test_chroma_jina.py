import chromadb
from sentence_transformers import SentenceTransformer

MODEL_NAME = "jinaai/jina-embeddings-v5-omni-nano-retrieval"

# 1. Cargar modelo de embeddings
model = SentenceTransformer(
    MODEL_NAME,
    trust_remote_code=True,
    device="cuda"
)

print("Modelo Jina cargado en:", model.device)

# 2. Crear cliente persistente de ChromaDB
client = chromadb.PersistentClient(
    path="/home/mhenriquez/chatbot_ipc/chroma_db"
)

# 3. Crear o recuperar colección
collection = client.get_or_create_collection(
    name="ipc_knowledge"
)

# 4. Documentos de prueba
documentos = [
    "El bloque TON es un temporizador de retardo a la conexión. Cuando IN permanece activo durante PT, Q cambia a TRUE.",

    "EtherCAT es un protocolo Ethernet industrial utilizado para comunicación en tiempo real entre dispositivos.",

    "Una variable BOOL puede tomar los valores TRUE o FALSE y se utiliza para representar estados lógicos."
]

ids = [
    "doc_1",
    "doc_2",
    "doc_3"
]

metadatos = [
    {
        "tema": "temporizadores",
        "tipo": "texto",
        "fuente": "prueba"
    },
    {
        "tema": "ethercat",
        "tipo": "texto",
        "fuente": "prueba"
    },
    {
        "tema": "variables",
        "tipo": "texto",
        "fuente": "prueba"
    }
]

# 5. Generar embeddings de documentos
embeddings = model.encode_document(documentos)

# ChromaDB espera listas Python
embeddings = embeddings.tolist()

# 6. Insertar documentos en ChromaDB
collection.upsert(
    ids=ids,
    documents=documentos,
    embeddings=embeddings,
    metadatas=metadatos
)

print("\nDocumentos almacenados correctamente.")
print("Cantidad de documentos:", collection.count())

# 7. Consulta de prueba
consulta = "¿Cómo funciona un temporizador TON?"

query_embedding = model.encode_query(consulta).tolist()

# 8. Buscar documentos similares
resultados = collection.query(
    query_embeddings=[query_embedding],
    n_results=3
)

print("\nConsulta:")
print(consulta)

print("\nResultados recuperados:\n")

for i in range(len(resultados["ids"][0])):
    print("ID:", resultados["ids"][0][i])
    print("Documento:", resultados["documents"][0][i])
    print("Metadatos:", resultados["metadatas"][0][i])
    print("Distancia:", resultados["distances"][0][i])
    print("-" * 60)
