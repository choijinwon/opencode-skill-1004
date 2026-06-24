import json
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
SAVE_MODEL_DIR = PROJECT_DIR / "save_model"

# MLflow/AI Studio settings
# 사용자가 아래 값을 직접 입력합니다. 비밀번호 값은 출력하지 마세요.
mlflow_tracking_url = ""
mlflow_tracking_username = ""
mlflow_tracking_password = ""
mlflow_experiment_name = "pytorch_sample"
mlflow_register_model_name = "pytorch_sample_model"


def missing_mlflow_settings() -> list[str]:
    required = {
        "mlflow_tracking_url": mlflow_tracking_url,
        "mlflow_tracking_username": mlflow_tracking_username,
        "mlflow_tracking_password": mlflow_tracking_password,
        "mlflow_experiment_name": mlflow_experiment_name,
        "mlflow_register_model_name": mlflow_register_model_name,
    }
    return [name for name, value in required.items() if not value]


def main() -> None:
    missing = missing_mlflow_settings()
    if missing:
        print("MLflow/AI Studio 설정을 run_model.py에 직접 입력하세요.")
        print("missing settings:")
        for name in missing:
            print(f"- {name}")
        print("비밀번호 값은 출력하지 않습니다.")

    SAVE_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_info = {
        "sample": "pytorch",
        "status": "template_ready",
        "next_step": "Replace this template with your PyTorch model loading or training code.",
    }
    (SAVE_MODEL_DIR / "model_info.json").write_text(
        json.dumps(model_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"prepared sample model folder: {SAVE_MODEL_DIR}")


if __name__ == "__main__":
    main()
