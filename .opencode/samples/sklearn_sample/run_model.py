import json
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
SAVE_MODEL_DIR = PROJECT_DIR / "save_model"


def main() -> None:
    SAVE_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_info = {
        "sample": "sklearn",
        "status": "template_ready",
        "next_step": "Replace this template with your sklearn training or loading code.",
    }
    (SAVE_MODEL_DIR / "model_info.json").write_text(
        json.dumps(model_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"prepared sample model folder: {SAVE_MODEL_DIR}")


if __name__ == "__main__":
    main()
