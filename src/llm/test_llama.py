import time
import torch

from transformers import (
    MllamaForConditionalGeneration,
    AutoProcessor,
    BitsAndBytesConfig,
)

MODEL_ID = "meta-llama/Llama-3.2-11B-Vision-Instruct"


def main():
    print(f"Modelo: {MODEL_ID}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=False
    )

    print("\nCargando processor...")
    processor = AutoProcessor.from_pretrained(MODEL_ID)

    print("Cargando modelo en 4 bits...")

    model = MllamaForConditionalGeneration.from_pretrained(
        MODEL_ID,
        quantization_config=quantization_config,
        device_map={"": 0},
        dtype=torch.float16,
        low_cpu_mem_usage=True,
    )

    model.eval()

    print("Modelo cargado correctamente.")

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Explica brevemente qué es un PLC y cuál es su "
                        "función principal en automatización industrial."
                    ),
                }
            ],
        }
    ]

    input_text = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=False,
    )

    inputs = processor(
        text=input_text,
        return_tensors="pt",
    )

    inputs = {
        key: value.to(model.device)
        for key, value in inputs.items()
    }

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()

    start = time.perf_counter()

    with torch.inference_mode():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=512,
            do_sample=False,
        )

    torch.cuda.synchronize()

    elapsed = time.perf_counter() - start

    input_tokens = inputs["input_ids"].shape[1]

    output_ids = generated_ids[:, input_tokens:]

    response = processor.batch_decode(
        output_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0]

    generated_tokens = output_ids.shape[1]

    peak_vram = (
        torch.cuda.max_memory_allocated() / 1024**3
    )

    allocated_vram = (
        torch.cuda.memory_allocated() / 1024**3
    )

    tokens_per_second = (
        generated_tokens / elapsed
        if elapsed > 0
        else 0
    )

    print("\n==============================")
    print("RESPUESTA")
    print("==============================")
    print(response)

    print("\n==============================")
    print("MÉTRICAS")
    print("==============================")
    print(f"Tiempo de generación: {elapsed:.2f} s")
    print(f"Tokens generados: {generated_tokens}")
    print(f"Tokens/s: {tokens_per_second:.2f}")
    print(f"VRAM asignada: {allocated_vram:.2f} GB")
    print(f"VRAM máxima: {peak_vram:.2f} GB")


if __name__ == "__main__":
    main()
