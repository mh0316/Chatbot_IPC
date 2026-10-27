from transformers import AutoModel

MODEL_NAME = "jinaai/jina-embeddings-v5-omni-nano-retrieval"

model = AutoModel.from_pretrained(
    MODEL_NAME,
    trust_remote_code=True,
    modality="vision",
    device_map="auto"
)

print("Modelo Jina cargado correctamente")
print(model)
print("Dispositivo:", next(model.parameters()).device)
