from __future__ import annotations

import json
from pathlib import Path

import mlflow.pyfunc
import numpy as np


def _normalize_path(path):
    value = str(path).replace("\\", "/").replace("＼", "/").replace("￦", "/").replace("₩", "/")
    while "//" in value and not value.startswith("//"):
        value = value.replace("//", "/")
    return value


def _payload_to_array(payload) -> np.ndarray:
    if isinstance(payload, dict):
        if "inputs" in payload and payload["inputs"]:
            first_input = payload["inputs"][0]
            if isinstance(first_input, dict) and "data" in first_input:
                return np.asarray(first_input["data"], dtype="float32")
        for key in ("data", "instances", "features", "x"):
            if key in payload:
                return np.asarray(payload[key], dtype="float32")
    return np.asarray(payload, dtype="float32")


class ModelWrapper(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        import tensorflow as tf

        config_path = Path(_normalize_path(context.artifacts["config"]))
        model_path = Path(_normalize_path(context.artifacts["model"]))
        self.config = json.loads(config_path.read_text(encoding="utf-8"))
        self.model = tf.keras.models.load_model(model_path)

    def predict(self, context, model_input, params=None):
        if not hasattr(self, "model"):
            return {
                "status": "model_not_loaded",
                "detail": "MLflow calls load_context() before predict().",
                "input": model_input,
            }
        array_input = _payload_to_array(model_input)
        prediction = self.model.predict(array_input, verbose=0)
        return {
            "prediction": prediction.tolist(),
        }


def predict(payload):
    wrapper = ModelWrapper()
    return wrapper.predict(None, payload)
