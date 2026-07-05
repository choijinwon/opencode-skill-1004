from __future__ import annotations

import io
import json
import logging
import os
import sys
from pathlib import Path
from urllib.parse import quote

import mlflow
import numpy as np

from aiu_custom.predict import ModelWrapper


logging.getLogger("mlflow").setLevel(logging.ERROR)


def configure_utf8_stdio() -> None:
    if os.name != "nt":
        return
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
        elif hasattr(stream, "buffer"):
            setattr(sys, stream_name, io.TextIOWrapper(stream.buffer, encoding="utf-8"))


configure_utf8_stdio()

PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_MODEL_PATH = PROJECT_DIR / "saved_model" / "model.keras"
DATA_MODEL_PATH = SOURCE_MODEL_PATH
MODEL_KIND = "tensorflow_keras"
MODEL_LOAD_HINT = "tf.keras.models.load_model(MODEL_PATH)"
INPUT_EXAMPLE_PATH = PROJECT_DIR / "input_example.json"
CONFIG_DIR = PROJECT_DIR / "config"
CONFIG_PATH = CONFIG_DIR / "config.json"
MODEL_DIR = PROJECT_DIR / "saved_model"
MODEL_PATH = MODEL_DIR / "model.keras"

# AI 환경 설정
mlflow_tracking_uri = ""
mlflow_tracking_username = ""
mlflow_tracking_password = ""
mlflow_experiment_name = "tensorflow_sample"
mlflow_register_model_name = "tensorflow_sample_model"


def missing_mlflow_settings() -> list[str]:
    required = {
        "mlflow_tracking_uri": mlflow_tracking_uri,
        "mlflow_tracking_username": mlflow_tracking_username,
        "mlflow_tracking_password": mlflow_tracking_password,
    }
    return [name for name, value in required.items() if not value]


def export_mlflow_environment() -> None:
    exports = {
        "MLFLOW_TRACKING_URI": mlflow_tracking_uri,
        "MLFLOW_TRACKING_USERNAME": mlflow_tracking_username,
        "MLFLOW_TRACKING_PASSWORD": mlflow_tracking_password,
        "MLFLOW_EXPERIMENT_NAME": mlflow_experiment_name,
        "MLFLOW_REGISTER_MODEL_NAME": mlflow_register_model_name,
    }
    for name, value in exports.items():
        if value:
            os.environ[name] = value


def mlflow_ui_urls(experiment_id: str, run_id: str | None = None) -> dict[str, str]:
    base_url = str(mlflow_tracking_uri).strip().rstrip("/")
    urls = {
        "tracking_uri": base_url,
        "experiment_url": f"{base_url}/#/experiments/{experiment_id}",
        "experiment_models_url": f"{base_url}/#/experiments/{experiment_id}/models",
        "traces_url": f"{base_url}/#/experiments/{experiment_id}/traces?startTime=ALL",
    }
    if run_id:
        urls["run_url"] = f"{base_url}/#/experiments/{experiment_id}/runs/{run_id}"
    if mlflow_register_model_name:
        model_name = quote(mlflow_register_model_name, safe="")
        urls["registered_model_url"] = f"{base_url}/#/models/{model_name}"
    return urls


def print_mlflow_ui_urls(experiment_id: str, run_id: str | None = None) -> None:
    urls = mlflow_ui_urls(experiment_id, run_id)
    print("MLflow Tracking URI:", urls["tracking_uri"])
    print("MLflow Experiment URI:", urls["experiment_url"])
    print("MLflow Experiment Models URI:", urls["experiment_models_url"])
    print("MLflow Traces URI:", urls["traces_url"])
    if "run_url" in urls:
        print("MLflow Run URI:", urls["run_url"])
    if "registered_model_url" in urls:
        print("MLflow Registered Model URI:", urls["registered_model_url"])


def ensure_registered_model(model_info) -> str:
    model_name = str(mlflow_register_model_name).strip()
    if not model_name:
        return "skipped: mlflow_register_model_name empty"
    try:
        client = mlflow.tracking.MlflowClient()
        client.get_registered_model(model_name)
        return f"exists: {model_name}"
    except Exception:
        pass
    model_uri = getattr(model_info, "model_uri", "")
    if not model_uri:
        return "failed: model_uri missing"
    try:
        registered = mlflow.register_model(model_uri=model_uri, name=model_name)
        version = getattr(registered, "version", "unknown")
        return f"registered: {model_name}, version={version}"
    except Exception as exc:
        return f"failed: {type(exc).__name__}: {exc}"


def log_aiu_pyfunc_model(input_example):
    log_model_params = mlflow.pyfunc.log_model.__wrapped__.__code__.co_varnames if hasattr(mlflow.pyfunc.log_model, "__wrapped__") else ()
    log_model_args = {
        "python_model": ModelWrapper(),
        "artifacts": {
            "model": MODEL_PATH.as_posix(),
            "config": CONFIG_PATH.as_posix(),
        },
        "input_example": input_example,
        "code_paths": [(Path(__file__).resolve().parent / "aiu_custom").as_posix()],
        "pip_requirements": "requirements.txt",
    }
    if "name" in log_model_params:
        log_model_args["name"] = "ai_studio"
    else:
        log_model_args["artifact_path"] = "ai_studio"
    model_info = mlflow.pyfunc.log_model(**log_model_args)
    registry_status = ensure_registered_model(model_info)
    return model_info, registry_status


def prepare_data():
    rng = np.random.default_rng(seed=42)
    train_x = rng.normal(size=(32, 4)).astype("float32")
    train_y = (train_x.sum(axis=1) > 0).astype("float32")
    test_x = rng.normal(size=(10, 4)).astype("float32")
    test_y = (test_x.sum(axis=1) > 0).astype("float32")
    return train_x, train_y, test_x, test_y


def build_and_train_model(train_x, train_y):
    import tensorflow as tf

    tf.random.set_seed(42)
    model = tf.keras.Sequential(
        [
            tf.keras.layers.Input(shape=(train_x.shape[1],)),
            tf.keras.layers.Dense(8, activation="relu"),
            tf.keras.layers.Dense(1, activation="sigmoid"),
        ]
    )
    model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
    model.fit(train_x, train_y, epochs=5, verbose=0)
    return model


def compute_metrics(model, test_x, test_y) -> dict[str, float]:
    loss, accuracy = model.evaluate(test_x, test_y, verbose=0)
    return {"accuracy": float(accuracy), "loss": float(loss)}


def write_input_example(test_x) -> dict:
    sample_data = test_x[:2]
    input_example = {
        "inputs": [
            {
                "name": "tensorflow_tensor_example",
                "shape": list(sample_data.shape),
                "datatype": str(sample_data.dtype),
                "data": sample_data.tolist(),
            }
        ]
    }
    INPUT_EXAMPLE_PATH.write_text(json.dumps(input_example, ensure_ascii=False, indent=2), encoding="utf-8")
    return input_example


def main() -> None:
    missing = missing_mlflow_settings()
    if missing:
        print("원격 MLflow 등록 실행을 위해 MLflow/AI Studio 설정을 runtest.py에 직접 입력하세요.")
        print("누락 항목: " + ", ".join(missing))
        for name in missing:
            print(f"- {name}")
        print("비밀번호 값은 출력하지 않습니다.")
        return

    try:
        import tensorflow as tf
    except Exception as exc:
        print(f"TensorFlow import failed. Install packages from requirements.txt first. reason={exc}")
        return

    export_mlflow_environment()
    mlflow.set_tracking_uri(mlflow_tracking_uri)
    mlflow.set_experiment(mlflow_experiment_name)

    train_x, train_y, test_x, test_y = prepare_data()
    model = build_and_train_model(train_x, train_y)
    metrics = compute_metrics(model, test_x, test_y)
    input_example = write_input_example(test_x)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    config = {"framework": "tensorflow", "input_dim": int(train_x.shape[1]), "output_dim": 1}
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=4), encoding="utf-8")
    model.save(MODEL_PATH)

    with mlflow.start_run(run_name=mlflow_register_model_name) as run:
        mlflow.set_tag("data.name", "synthetic_tensor(tensorflow)")
        mlflow.log_params(config)
        mlflow.log_metrics(metrics)
        model_info, registry_status = log_aiu_pyfunc_model(input_example)

    print(f"input_example written: {INPUT_EXAMPLE_PATH}")
    print(f"config written: {CONFIG_PATH}")
    print(f"model written: {MODEL_PATH}")
    print("MLflow model logged with artifact_path='ai_studio'")
    print("Model URI:", getattr(model_info, "model_uri", "unknown"))
    print("MLflow Registry:", registry_status)
    print_mlflow_ui_urls(run.info.experiment_id, run.info.run_id)


if __name__ == "__main__":
    main()
