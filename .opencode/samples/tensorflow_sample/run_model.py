import json
import os
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
AI_STUDIO_DIR = PROJECT_DIR / "ai_studio"

# MLflow/AI Studio settings
# 사용자가 아래 값을 직접 입력합니다. 비밀번호 값은 출력하지 마세요.
mlflow_tracking_url = ""
mlflow_tracking_username = ""
mlflow_tracking_password = ""
mlflow_experiment_name = "tensorflow_sample"
mlflow_register_model_name = "tensorflow_sample_model"


def missing_mlflow_settings() -> list[str]:
    required = {
        "mlflow_tracking_url": mlflow_tracking_url,
        "mlflow_tracking_username": mlflow_tracking_username,
        "mlflow_tracking_password": mlflow_tracking_password,
        "mlflow_experiment_name": mlflow_experiment_name,
        "mlflow_register_model_name": mlflow_register_model_name,
    }
    return [name for name, value in required.items() if not value]


def export_mlflow_environment() -> None:
    exports = {
        "MLFLOW_TRACKING_URI": mlflow_tracking_url,
        "MLFLOW_TRACKING_USERNAME": mlflow_tracking_username,
        "MLFLOW_TRACKING_PASSWORD": mlflow_tracking_password,
        "MLFLOW_EXPERIMENT_NAME": mlflow_experiment_name,
        "MLFLOW_REGISTER_MODEL_NAME": mlflow_register_model_name,
    }
    for name, value in exports.items():
        if value:
            os.environ[name] = value


def main() -> None:
    missing = missing_mlflow_settings()
    if missing:
        print("MLflow/AI Studio 설정을 run_model.py에 직접 입력하세요.")
        print("missing settings:")
        for name in missing:
            print(f"- {name}")
        print("비밀번호 값은 출력하지 않습니다.")
    export_mlflow_environment()

    AI_STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    model_info = {
        "sample": "tensorflow",
        "status": "template_ready",
        "next_step": "Replace this template with your TensorFlow or Keras model loading code.",
    }
    (AI_STUDIO_DIR / "model_info.json").write_text(
        json.dumps(model_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"prepared AI Studio artifact folder: {AI_STUDIO_DIR}")


if __name__ == "__main__":
    main()
