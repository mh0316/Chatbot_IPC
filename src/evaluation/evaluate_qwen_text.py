import json
import time
from pathlib import Path

import psutil
import torch

from transformers import (
    Qwen3VLForConditionalGeneration,
    AutoProcessor,
    BitsAndBytesConfig,
)

MODEL_ID = "Qwen/Qwen3-VL-4B-Instruct"

SYSTEM_PROMPT = """
Eres un tutor especializado en programación industrial, IPC (Industrial Personal Computer) y TwinCAT 3.

Responde de forma técnicamente precisa, clara y educativa.
Contesta únicamente lo necesario para responder la pregunta.
No inventes información si no estás seguro.
Mantén la respuesta entre 100 y 250 palabras en la medida de lo posible.
"""

MAX_NEW_TOKENS = 512

PROJECT_ROOT = Path(__file__).resolve().parents[2]

QUESTIONS_FILE = (
    PROJECT_ROOT / "data" / "evaluation" / "baseline_text.json"
)

RESULTS_FILE = (
    PROJECT_ROOT / "results" / "baseline" / "qwen_text_results.json"
)


def generate_response(model, processor, question):
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": question,
                }
            ],
        },
    ]

    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt",
    )

    inputs = inputs.to(model.device)

    input_tokens = inputs["input_ids"].shape[1]

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()

    process = psutil.Process()

    vram_before = (
        torch.cuda.memory_allocated() / 1024**3
    )

    ram_before = (
        process.memory_info().rss / 1024**3
    )

    torch.cuda.synchronize()
    start = time.perf_counter()

    with torch.inference_mode():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
        )

    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start

    output_ids = generated_ids[
        :, input_tokens:
    ]

    generated_tokens = output_ids.shape[1]

    response = processor.batch_decode(
        output_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0]

    peak_vram = (
        torch.cuda.max_memory_allocated() / 1024**3
    )

    allocated_vram = (
        torch.cuda.memory_allocated() / 1024**3
    )

    ram_after = (
        process.memory_info().rss / 1024**3
    )

    tokens_per_second = (
        generated_tokens / elapsed
        if elapsed > 0
        else 0
    )

    return {
        "response": response,
        "input_tokens": input_tokens,
        "generated_tokens": generated_tokens,
        "latency_seconds": round(elapsed, 3),
        "tokens_per_second": round(
            tokens_per_second, 3
        ),
        "vram_before_gb": round(
            vram_before, 3
        ),
        "vram_allocated_gb": round(
            allocated_vram, 3
        ),
        "vram_peak_gb": round(
            peak_vram, 3
        ),
        "process_ram_before_gb": round(
            ram_before, 3
        ),
        "process_ram_after_gb": round(
            ram_after, 3
        ),
    }


def main():
    print(f"Modelo: {MODEL_ID}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")

    with open(
        QUESTIONS_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        questions = json.load(file)

    print(f"Preguntas cargadas: {len(questions)}")

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=False,
    )

    print("\nCargando processor...")

    processor = AutoProcessor.from_pretrained(
        MODEL_ID
    )

    print("Cargando modelo...")

    model = Qwen3VLForConditionalGeneration.from_pretrained(
        MODEL_ID,
        quantization_config=quantization_config,
        device_map="auto",
        dtype=torch.float16,
        low_cpu_mem_usage=True,
    )

    model.eval()

    print("Modelo cargado correctamente.")

    print("\nEjecutando warm-up...")

    generate_response(
        model,
        processor,
        "Define brevemente qué es automatización industrial.",
    )

    print("Warm-up completado.")

    results = []

    RESULTS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    total = len(questions)

    for index, item in enumerate(
        questions,
        start=1,
    ):
        print(
            f"\n[{index}/{total}] "
            f"{item['id']} - "
            f"{item['category']}"
        )

        metrics = generate_response(
            model,
            processor,
            item["question"],
        )

        result = {
            "id": item["id"],
            "category": item["category"],
            "type": item["type"],
            "difficulty": item["difficulty"],
            "model": MODEL_ID,
            "quantization": "4-bit NF4",
            "question": item["question"],
            **metrics,
        }

        results.append(result)

        # Guardado progresivo
        with open(
            RESULTS_FILE,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                results,
                file,
                indent=2,
                ensure_ascii=False,
            )

        print(
            f"Latencia: "
            f"{metrics['latency_seconds']:.2f} s | "
            f"Tokens: "
            f"{metrics['generated_tokens']} | "
            f"Tokens/s: "
            f"{metrics['tokens_per_second']:.2f} | "
            f"VRAM pico: "
            f"{metrics['vram_peak_gb']:.2f} GB"
        )

    question_ids = {
        item["id"]
        for item in questions
    }

    result_ids = {
        item["id"]
        for item in results
    }

    assert len(results) == len(questions)
    assert len(result_ids) == len(results)
    assert question_ids == result_ids

    print("\n================================")
    print("BENCHMARK QWEN FINALIZADO")
    print("================================")
    print(
        f"Preguntas procesadas: "
        f"{len(results)}/{total}"
    )
    print(
        f"Resultados guardados en: "
        f"{RESULTS_FILE}"
    )


if __name__ == "__main__":
    main()
