from __future__ import annotations

from pathlib import Path


AI_STUDIO_ENV_KEYS = (
    "mlflow_tracking_uri",
    "mlflow_tracking_username",
    "mlflow_tracking_password",
    "mlflow_experiment_name",
    "mlflow_register_model_name",
)

AUTO_DEFAULT_SETTING_KEYS = {
    "mlflow_experiment_name",
    "mlflow_register_model_name",
}

SETTING_ALIASES = {
    "mlflow_tracking_uri": (
        "mlflow_tracking_uri",
        "mlflow_tracking_url",
        "tracking_uri",
        "tracking_url",
        "MLFLOW_TRACKING_URI",
        "MLFLOW_TRACKING_URL",
    ),
    "mlflow_tracking_username": (
        "mlflow_tracking_username",
        "tracking_username",
        "mlflow_username",
        "username",
        "MLFLOW_TRACKING_USERNAME",
    ),
    "mlflow_tracking_password": (
        "mlflow_tracking_password",
        "tracking_password",
        "mlflow_password",
        "password",
        "MLFLOW_TRACKING_PASSWORD",
    ),
    "mlflow_experiment_name": (
        "mlflow_experiment_name",
        "experiment_name",
        "MLFLOW_EXPERIMENT_NAME",
    ),
    "mlflow_register_model_name": (
        "mlflow_register_model_name",
        "mlflow_register_mdoel_name",
        "register_model_name",
        "registered_model_name",
        "MLFLOW_REGISTER_MODEL_NAME",
    ),
}

ALIAS_TO_SETTING = {
    alias: setting_key
    for setting_key, aliases in SETTING_ALIASES.items()
    for alias in aliases
}

EXPORT_ENV_MAP = {
    "mlflow_tracking_uri": "MLFLOW_TRACKING_URI",
    "mlflow_tracking_username": "MLFLOW_TRACKING_USERNAME",
    "mlflow_tracking_password": "MLFLOW_TRACKING_PASSWORD",
    "mlflow_experiment_name": "MLFLOW_EXPERIMENT_NAME",
    "mlflow_register_model_name": "MLFLOW_REGISTER_MODEL_NAME",
}

REQUIRED_MLFLOW_GATE_KEYS = AI_STUDIO_ENV_KEYS


def strip_env_value(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()
    return text


def todo_placeholder(value: str) -> bool:
    text = strip_env_value(value).strip().lower()
    return text in {"", "todo", "{todo}", "<todo>", "tbd", "none", "null", "입력", "입력필요"}


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = strip_env_value(value)
    return values


def parse_setting_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, value in parse_env_file(path).items():
        setting_key = ALIAS_TO_SETTING.get(key)
        if setting_key is not None:
            values[setting_key] = value
    return values


def mlflow_setting_value(values: dict[str, str], key: str) -> str:
    for alias in SETTING_ALIASES.get(key, (key,)):
        value = values.get(alias)
        if value is not None:
            return value
    return ""
