import time
import torch

from transformers import (
    Qwen3VLForConditionalGeneration,
    AutoProcessor,
    BitsAndBytesConfig,
)

MODEL_ID = "Qwen/Qwen3-VL-4B-Instruct"


def main():
    print(f"Modelo: {MODEL_ID}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=False,
    )

    print("\nCargando processor...")
    processor = AutoProcessor.from_pretrained(MODEL_ID)

    print("Cargando modelo en 4 bits...")

    model = Qwen3VLForConditionalGeneration.from_pretrained(
        MODEL_ID,
        quantization_config=quantization_config,
        device_map="auto",
        dtype=torch.float16,
	low_cpu_mem_usage=True,
    )

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

    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt",
    )

    inputs = inputs.to(model.device)

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

    generated_ids = generated_ids[
        :, inputs["input_ids"].shape[1]:
    ]

    response = processor.batch_decode(
        generated_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0]

    peak_vram = (
        torch.cuda.max_memory_allocated() / 1024**3
    )

    allocated_vram = (
        torch.cuda.memory_allocated() / 1024**3
    )

    print("\n==============================")
    print("RESPUESTA")
    print("==============================")
    print(response)

    print("\n==============================")
    print("MÉTRICAS")
    print("==============================")
    print(f"Tiempo de generación: {elapsed:.2f} s")
    print(f"VRAM asignada: {allocated_vram:.2f} GB")
    print(f"VRAM máxima: {peak_vram:.2f} GB")


if __name__ == "__main__":
    main()
