#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


SUPPORTED_MODEL_KINDS = {
    ".pkl": "sklearn_pickle",
    ".joblib": "sklearn_joblib",
    ".pt": "pytorch",
    ".pth": "pytorch",
    ".onnx": "onnx",
    ".keras": "tensorflow_keras",
    ".h5": "tensorflow_h5",
    ".safetensors": "safetensors",
    ".bst": "xgboost_bst",
    ".ubj": "xgboost_ubj",
}
DATA_FILE_SUFFIXES = {".csv"}
GENERIC_MODEL_STEMS = {
    "best",
    "checkpoint",
    "final",
    "model",
    "pytorch_model",
    "weights",
}

REFERENCE_ENTRYPOINTS = [
    "runtest.py",
    "run_test.py",
]
PROTECTED_REFERENCE_ENTRYPOINTS = set(REFERENCE_ENTRYPOINTS)
PYTHON_ENTRYPOINTS = [
    "runtest.py",
    "run_test.py",
    "run_model.py",
    "run.py",
    "main.py",
    "train.py",
    "app.py",
]
ROOT = Path(__file__).resolve().parents[2]
AIU_STUDIO_SAMPLE_DIR_NAME = "aiu_studio"
AIU_STUDIO_SAMPLE_DIR = ROOT / "samples" / AIU_STUDIO_SAMPLE_DIR_NAME
REQUIRED_REQUIREMENTS_FILE = ROOT / "scripts" / "03-environment-check" / "requirements.required.txt"
CHECK_ENVIRONMENT_SCRIPT = ROOT / "scripts" / "03-environment-check" / "check_environment.py"
PREPARE_SELECTED_MODEL_SCRIPT = ROOT / "scripts" / "04-train-model" / "prepare_selected_model.py"
RUN_TRAINING_SCRIPT = ROOT / "scripts" / "04-train-model" / "run_training.py"
VERIFY_MLFLOW_SCRIPT = ROOT / "scripts" / "06-mlflow-verify" / "verify_mlflow.py"
PYTORCH_REFERENCE_ENTRYPOINT = ROOT / "samples" / "pytorch_sample" / "runtest.py"
REFERENCE_ENTRYPOINT_BY_KIND = {
    "pytorch": PYTORCH_REFERENCE_ENTRYPOINT,
    "safetensors": PYTORCH_REFERENCE_ENTRYPOINT,
    "sklearn_pickle": ROOT / "samples" / "sklearn_sample" / "run_model.py",
    "sklearn_joblib": ROOT / "samples" / "sklearn_sample" / "run_model.py",
    "xgboost_bst": ROOT / "samples" / "sklearn_sample" / "run_model.py",
    "xgboost_ubj": ROOT / "samples" / "sklearn_sample" / "run_model.py",
    "tensorflow_keras": ROOT / "samples" / "tensorflow_sample" / "run_model.py",
    "tensorflow_h5": ROOT / "samples" / "tensorflow_sample" / "run_model.py",
}
AIU_STUDIO_COPY_IGNORE_DIRS = {"__pycache__", "code", "metrics", "tracking"}
MODEL_SCAN_SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".opencode",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "ai_studio",
    "build",
    "dist",
    "env",
    "node_modules",
    "venv",
}
MLFLOW_SETTING_NAMES = {
    "mlflow_tracking_url",
    "mlflow_tracking_username",
    "mlflow_tracking_password",
    "mlflow_experiment_name",
    "mlflow_register_model_name",
}
MODEL_RELATED_SETTING_NAMES = {
    "SOURCE_MODEL_PATH",
    "DATA_MODEL_PATH",
    "MODEL_PATH",
    "MODEL_OUTPUT_DIR",
    "MODEL_OUTPUT_PATH",
    "CONFIG_DIR",
    "CONFIG_PATH",
    "MODEL_KIND",
    "source_model_path",
    "data_model_path",
    "model_path",
    "model_dir",
    "model_output_dir",
    "model_output_path",
    "saved_model_dir",
    "config_dir",
    "config_path",
    "MODEL_FILE",
    "model_file",
    "CHECKPOINT_PATH",
    "checkpoint_path",
    "MODEL_LOAD_HINT",
    "model_load_hint",
    "REQUIRED_PACKAGE",
    "required_package",
    "INPUT_EXAMPLE_PATH",
    "input_example_path",
    "INPUT_EXAMPLE_FILE",
    "input_example_file",
    "SAMPLE_INPUT_PATH",
    "sample_input_path",
    "AI_STUDIO_DIR",
    "AI_STUDIO_CODE_DIR",
    "AI_STUDIO_METRICS_DIR",
    "AI_STUDIO_TRACKING_DIR",
    "PROJECT_DIR",
}
MODEL_PATH_VARIABLE_NAMES = {
    "SOURCE_MODEL_PATH",
    "DATA_MODEL_PATH",
    "MODEL_PATH",
    "source_model_path",
    "data_model_path",
    "model_path",
    "MODEL_FILE",
    "model_file",
    "CHECKPOINT_PATH",
    "checkpoint_path",
}
INPUT_EXAMPLE_VARIABLE_NAMES = {
    "INPUT_EXAMPLE_PATH",
    "input_example_path",
    "INPUT_EXAMPLE_FILE",
    "input_example_file",
    "SAMPLE_INPUT_PATH",
    "sample_input_path",
}
DATA_PREP_VARIABLE_NAMES = {
    "dataset",
    "dataloader",
    "features",
    "input_example",
    "labels",
    "loader",
    "sample_data",
    "sample_input",
    "batch_size",
    "test_df",
    "test_dataset",
    "test_loader",
    "test_x",
    "test_y",
    "train_df",
    "train_dataset",
    "train_loader",
    "train_x",
    "train_y",
    "x_test",
    "x_train",
    "y_test",
    "y_train",
}
DATA_PREP_CALL_PATTERN = re.compile(
    r"\b(TensorDataset|TensorDastaset|DataLoader|load_diabetes|load_iris|FashionMNIST|MNIST)\s*\("
)
MODEL_PREP_VARIABLE_NAMES = {
    "classifier",
    "clf",
    "criterion",
    "estimator",
    "model",
    "net",
    "optimizer",
    "regressor",
}
MODEL_PREP_CALL_PATTERN = re.compile(
    r"\b("
    r"ElasticNet|LinearRegression|LogisticRegression|RandomForestClassifier|RandomForestRegressor|"
    r"DecisionTreeClassifier|DecisionTreeRegressor|XGBClassifier|XGBRegressor|"
    r"ImageClassifier|Imageclassifier|torchvision\.models\.[A-Za-z_][A-Za-z0-9_]*|"
    r"nn\.Sequential|torch\.nn\.Sequential|keras\.Sequential|tf\.keras\.Sequential"
    r")\s*\("
)
MODEL_TRAIN_CALL_PATTERN = re.compile(
    r"\b("
    r"(?:model|clf|classifier|regressor|estimator|net)\.fit|"
    r"(?:model|net)\.train|"
    r"optimizer\.step|loss\.backward|criterion\("
    r")"
)
SUMMARY_VARIABLE_NAMES = {
    "summary",
    "summary_file",
    "summary_json",
    "summary_path",
    "model_summary",
    "training_summary",
}
SUMMARY_PATH_VARIABLE_NAMES = {
    "summary_file",
    "summary_json",
    "summary_path",
}
SUMMARY_CALL_PATTERN = re.compile(r"(?<![A-Za-z0-9_])summary\s*\(|\.\s*summary\s*\(")
MODEL_COMMENT_HINT_PATTERN = re.compile(
    r"(모델|로드|로딩|추론|model|load|loading|predict|inference|"
    r"sklearn|scikit|joblib|pickle|pytorch|torch|tensorflow|keras|onnx|xgboost|safetensors)",
    re.IGNORECASE,
)
MODEL_IMPORT_PACKAGE_NAMES = {
    "joblib": "joblib",
    "sklearn": "joblib",
    "torch": "torch",
    "tensorflow": "tensorflow",
    "keras": "tensorflow",
    "onnxruntime": "onnxruntime",
    "xgboost": "xgboost",
    "safetensors": "safetensors",
}
ALWAYS_KEEP_IMPORT_MODULES = {
    "sys",
    "io",
    "os",
    "json",
    "joblib",
    "mlflow",
    "logging",
}
MODEL_PATH_REFERENCE_PATTERN = re.compile(
    r"(?P<path>[A-Za-z0-9가-힣_./\\() -]+(?:"
    + "|".join(re.escape(suffix) for suffix in sorted(SUPPORTED_MODEL_KINDS, key=len, reverse=True))
    + r"))",
    re.IGNORECASE,
)
PATH_SEPARATOR_TRANSLATION = str.maketrans({
    "\\": "/",
    "＼": "/",
    "￦": "/",
    "₩": "/",
})
PATH_LIKE_STRING_PATTERN = re.compile(
    r"("
    r"(?:/mnt|/data|/home|/workspace|/tmp|aiu_studio|ai_studio|data|models?|artifacts?|saved_model)"
    r"[A-Za-z0-9가-힣_./\\＼￦₩() -]*"
    r")",
    re.IGNORECASE,
)
PYTHON_STRING_LITERAL_PATTERN = re.compile(
    r"(?P<prefix>[rRuUbBfF]*)(?P<quote>['\"])(?P<body>(?:\\.|[^\\])*?)(?P=quote)"
)
MODEL_LOADER_CALL_PATTERN = re.compile(
    r"\b("
    r"joblib\.load|"
    r"pickle\.load|"
    r"torch\.load|"
    r"tf\.keras\.models\.load_model|"
    r"keras\.models\.load_model|"
    r"onnxruntime\.InferenceSession|"
    r"ort\.InferenceSession|"
    r"mlflow\.pyfunc\.load_model|"
    r"load_file"
    r")\s*\("
)
MODEL_KIND_DETAILS = {
    "sklearn_pickle": {
        "required_package": "joblib",
        "load_hint": "joblib.load(MODEL_PATH)",
        "loader": """def load_selected_model():\n    import joblib\n\n    return joblib.load(MODEL_PATH)\n""",
    },
    "sklearn_joblib": {
        "required_package": "joblib",
        "load_hint": "joblib.load(MODEL_PATH)",
        "loader": """def load_selected_model():\n    import joblib\n\n    return joblib.load(MODEL_PATH)\n""",
    },
    "pytorch": {
        "required_package": "torch",
        "load_hint": "torch.load(MODEL_PATH, map_location='cpu')",
        "loader": """def load_selected_model():\n    import torch\n\n    return torch.load(MODEL_PATH, map_location=\"cpu\")\n""",
    },
    "onnx": {
        "required_package": "onnxruntime",
        "load_hint": "onnxruntime.InferenceSession(str(MODEL_PATH))",
        "loader": """def load_selected_model():\n    import onnxruntime as ort\n\n    return ort.InferenceSession(str(MODEL_PATH))\n""",
    },
    "tensorflow_keras": {
        "required_package": "tensorflow",
        "load_hint": "tf.keras.models.load_model(MODEL_PATH)",
        "loader": """def load_selected_model():\n    import tensorflow as tf\n\n    return tf.keras.models.load_model(MODEL_PATH)\n""",
    },
    "tensorflow_h5": {
        "required_package": "tensorflow",
        "load_hint": "tf.keras.models.load_model(MODEL_PATH)",
        "loader": """def load_selected_model():\n    import tensorflow as tf\n\n    return tf.keras.models.load_model(MODEL_PATH)\n""",
    },
    "safetensors": {
        "required_package": "safetensors",
        "load_hint": "safetensors.torch.load_file(str(MODEL_PATH))",
        "loader": """def load_selected_model():\n    from safetensors.torch import load_file\n\n    return load_file(str(MODEL_PATH))\n""",
    },
    "xgboost_bst": {
        "required_package": "xgboost",
        "load_hint": "xgboost.Booster().load_model(str(MODEL_PATH))",
        "loader": """def load_selected_model():\n    import xgboost as xgb\n\n    booster = xgb.Booster()\n    booster.load_model(str(MODEL_PATH))\n    return booster\n""",
    },
    "xgboost_ubj": {
        "required_package": "xgboost",
        "load_hint": "xgboost.Booster().load_model(str(MODEL_PATH))",
        "loader": """def load_selected_model():\n    import xgboost as xgb\n\n    booster = xgb.Booster()\n    booster.load_model(str(MODEL_PATH))\n    return booster\n""",
    },
}


@dataclass
class PreparedModelReport:
    project_path: str
    data_root: str
    model_artifact_paths: list[str]
    data_file_paths: list[str]
    entrypoint_paths: list[str]
    selected_model_path: str | None
    model_kind: str | None
    reference_entrypoint: str | None
    generated_entrypoint: str
    generated_inference_test: str
    execute: bool
    required_requirements: list[str] = field(default_factory=list)
    additional_requirements: list[str] = field(default_factory=list)
    prepared_paths: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


def rel(path: Path, base: Path) -> str:
    try:
        return normalize_path_text(path.relative_to(base).as_posix())
    except ValueError:
        return normalize_path_text(path.as_posix())


def normalize_path_text(value: str) -> str:
    return re.sub(r"/+", "/", value.translate(PATH_SEPARATOR_TRANSLATION))


def normalize_path_literal_text(value: str) -> str:
    if not any(separator in value for separator in ["\\", "＼", "￦", "₩"]):
        return value
    return PATH_LIKE_STRING_PATTERN.sub(lambda match: normalize_path_text(match.group(0)), value)


def model_kind(path: Path) -> str | None:
    return SUPPORTED_MODEL_KINDS.get(path.suffix.lower())


def is_filesystem_root(path: Path) -> bool:
    return path.parent == path


def is_opencode_sample_source(path: Path) -> bool:
    parts = path.resolve().parts
    if ".opencode" in parts:
        return True
    for index, part in enumerate(parts[:-1]):
        if part == ".opencode" and parts[index + 1] in {"sample", "samples"}:
            return True
    return False


def scan_model_artifacts(project: Path) -> list[Path]:
    if is_opencode_sample_source(project):
        return []
    found: list[Path] = []

    # Search only the selected project root and its data/** tree. Do not scan
    # arbitrary sibling folders or the whole drive/workspace.
    for path in project.iterdir():
        if path.is_file() and model_kind(path):
            found.append(path)

    data_root = project / "data"
    if not data_root.is_dir():
        return sorted(set(found))

    for path in data_root.rglob("*"):
        try:
            relative_parts = path.relative_to(project).parts
        except ValueError:
            continue
        if any(part in MODEL_SCAN_SKIP_DIRS for part in relative_parts):
            continue
        if path.is_file() and model_kind(path):
            found.append(path)
    return sorted(set(found))


def scan_data_files(project: Path) -> list[Path]:
    if is_opencode_sample_source(project):
        return []
    found: list[Path] = []
    for path in project.iterdir():
        if path.is_file() and path.suffix.lower() in DATA_FILE_SUFFIXES:
            found.append(path)

    data_root = project / "data"
    if data_root.is_dir():
        for path in data_root.rglob("*"):
            try:
                relative_parts = path.relative_to(project).parts
            except ValueError:
                continue
            if any(part in MODEL_SCAN_SKIP_DIRS for part in relative_parts):
                continue
            if path.is_file() and path.suffix.lower() in DATA_FILE_SUFFIXES:
                found.append(path)
    return sorted(set(found))


def find_python_entrypoints(project: Path) -> list[Path]:
    if is_opencode_sample_source(project):
        return []
    found: list[Path] = []
    for name in PYTHON_ENTRYPOINTS:
        path = project / name
        if path.is_file():
            found.append(path)
    found.extend(sorted(path for path in project.glob("*.py") if path.is_file()))
    return sorted(set(found))


def artifacts_under(path: Path) -> list[Path]:
    if path.is_file() and model_kind(path):
        return [path]
    if not path.is_dir():
        return []
    found = []
    for child in path.rglob("*"):
        if child.is_file() and model_kind(child):
            found.append(child)
    return sorted(set(found))


def resolve_single_artifact(project: Path, candidates: list[Path], raw: str) -> tuple[Path | None, str | None]:
    candidates = sorted(set(path.resolve() for path in candidates))
    if len(candidates) == 1:
        return candidates[0], None
    if not candidates:
        return None, f"model_path_not_found:{raw}"
    relative_candidates = ", ".join(rel(path, project) for path in candidates[:10])
    suffix = "" if len(candidates) <= 10 else f", ...(+{len(candidates) - 10})"
    return None, f"model_path_ambiguous:{raw}:[{relative_candidates}{suffix}]"


def match_model_by_text(project: Path, models: list[Path], raw: str) -> tuple[Path | None, str | None]:
    value = normalize_path_text(raw.strip()).strip("/")
    lowered = value.lower()
    matches = []
    for model in models:
        relative = rel(model, project)
        relative_lower = relative.lower()
        parts_lower = [part.lower() for part in Path(relative).parts]
        if lowered in {
            model.name.lower(),
            model.stem.lower(),
            model.parent.name.lower(),
            relative_lower,
        }:
            matches.append(model)
            continue
        if lowered in parts_lower or relative_lower.endswith("/" + lowered):
            matches.append(model)
    return resolve_single_artifact(project, matches, raw)


def stored_selected_model_path(project: Path) -> Path | None:
    mapping_path = project / "aiu_custom" / "mapping.json"
    if not mapping_path.is_file():
        return None
    try:
        payload = json.loads(mapping_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    source_path = payload.get("model", {}).get("source_path")
    if not isinstance(source_path, str) or not source_path.strip():
        return None
    normalized = normalize_path_text(source_path.strip())
    candidate = Path(normalized).expanduser()
    if not candidate.is_absolute():
        candidate = project / candidate
    return candidate.resolve() if candidate.is_file() else None


def eval_project_path_expr(node: ast.AST, project: Path, symbols: dict[str, Path | str] | None = None) -> Path | str | None:
    symbols = symbols or {}
    if isinstance(node, ast.Name):
        if node.id == "PROJECT_DIR":
            return project
        if node.id == "AI_STUDIO_DIR":
            return project
        if node.id in symbols:
            return symbols[node.id]
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = eval_project_path_expr(node.left, project, symbols)
        right = eval_project_path_expr(node.right, project, symbols)
        if left is None or right is None:
            return None
        return Path(left) / str(right)
    return None


def selected_model_from_runtest_2(project: Path) -> tuple[Path | None, str | None, str | None]:
    runtest_2 = project / "runtest_2.py"
    if not runtest_2.is_file():
        return None, None, "runtest_2_missing"
    try:
        tree = ast.parse(runtest_2.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError as exc:
        return None, None, f"runtest_2_parse_error:{exc.lineno}"

    selected_model: Path | None = None
    selected_kind: str | None = None
    symbols: dict[str, Path | str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
        value = eval_project_path_expr(node.value, project, symbols)
        for target_name in targets:
            if value is not None:
                symbols[target_name] = value
        if "SOURCE_MODEL_PATH" in targets:
            if value is not None:
                selected_model = Path(value)
                if not selected_model.is_absolute():
                    selected_model = project / selected_model
                selected_model = selected_model.resolve()
        if "MODEL_KIND" in targets and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            selected_kind = node.value.value

    if selected_model is None:
        return None, selected_kind, "runtest_2_source_model_path_missing"
    if selected_kind is None:
        return selected_model, None, "runtest_2_model_kind_missing"
    if not selected_model.is_file():
        return selected_model, selected_kind, f"runtest_2_selected_model_not_found:{rel(selected_model, project)}"
    return selected_model, selected_kind, None


def current_selected_model_path(project: Path) -> Path | None:
    selected_model, _selected_kind, _selection_error = selected_model_from_runtest_2(project)
    if selected_model is not None:
        return selected_model
    return stored_selected_model_path(project)


def resolve_model_selection(project: Path, models: list[Path], raw: str | None) -> tuple[Path | None, str | None]:
    if not raw:
        return None, "model_selection_required"
    value = normalize_path_text(raw.strip())
    if value.lower() in {"selected", "current", "last", "기존", "현재", "선택"}:
        stored = current_selected_model_path(project)
        if stored is not None:
            return stored, None
        return None, "stored_model_selection_missing"
    if value.isdigit():
        current_selected = current_selected_model_path(project)
        if current_selected is not None and current_selected.is_file():
            return current_selected, None
        index = int(value)
        if 1 <= index <= len(models):
            return models[index - 1], None
        return None, f"model_index_out_of_range:{value}"

    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = project / candidate
    candidate = candidate.resolve()
    if candidate.exists():
        return resolve_single_artifact(project, artifacts_under(candidate), value)
    return match_model_by_text(project, models, value)


def ensure_under_project(project: Path, model_path: Path) -> bool:
    try:
        model_path.resolve().relative_to(project.resolve())
        return True
    except ValueError:
        return False


def find_reference_entrypoint(project: Path, kind: str | None = None) -> Path | None:
    for name in REFERENCE_ENTRYPOINTS:
        candidate = project / name
        if candidate.is_file():
            return candidate
    sample_reference = REFERENCE_ENTRYPOINT_BY_KIND.get(kind or "")
    if sample_reference is not None and sample_reference.is_file():
        return sample_reference
    return None


def preserve_reference_code(reference: Path) -> bool:
    if reference.resolve() == PYTORCH_REFERENCE_ENTRYPOINT.resolve():
        return True
    if not PYTORCH_REFERENCE_ENTRYPOINT.is_file():
        return False
    try:
        if file_sha256(reference) == file_sha256(PYTORCH_REFERENCE_ENTRYPOINT):
            return True
    except OSError:
        return False
    text = reference.read_text(encoding="utf-8", errors="ignore")
    pytorch_sample_markers = [
        "TinyTorchModel",
        "def prepare_data(",
        "def train_model(",
        "def compute_metrics(",
        "mlflow.pyfunc.log_model(",
    ]
    return all(marker in text for marker in pytorch_sample_markers)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_mlflow_name(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_]+", "_", value).strip("_").lower()
    return normalized or fallback


def powershell_quote_path(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def powershell_set_project_location(path: Path) -> str:
    return f"Set-Location -LiteralPath {powershell_quote_path(path)}"


def powershell_python_script(path: Path, *args: str) -> str:
    command = f"python {powershell_quote_path(path)}"
    if args:
        command += " " + " ".join(args)
    return command


def absolute_path_text(path: Path) -> str:
    return str(path.resolve())


def runtime_path_expr(path: Path, constructor: str = "_AIUPath") -> str:
    return f"{constructor}({absolute_path_text(path)!r})"


def selected_model_display_name(project: Path, selected_model: Path) -> str:
    stem = selected_model.stem
    parent_name = selected_model.parent.name
    try:
        relative_parts = selected_model.relative_to(project).parts
    except ValueError:
        relative_parts = selected_model.parts
    if stem.lower() in GENERIC_MODEL_STEMS and parent_name not in {"", ".", "data"}:
        return parent_name
    if len(relative_parts) >= 3 and relative_parts[0] == "data" and stem.lower() in GENERIC_MODEL_STEMS:
        return relative_parts[-2]
    return stem


def default_mlflow_names(project: Path, selected_model: Path) -> tuple[str, str]:
    experiment_name = safe_mlflow_name(selected_model_display_name(project, selected_model), "aiu_studio")
    return experiment_name, f"{experiment_name}_model"


def model_profile(project: Path, selected_model: Path, kind: str) -> dict[str, str]:
    details = MODEL_KIND_DETAILS.get(kind, {})
    return {
        "model_name": selected_model.name,
        "selected_model_name": selected_model_display_name(project, selected_model),
        "model_suffix": selected_model.suffix.lower(),
        "model_kind": kind,
        "model_relative_path": rel(selected_model, project),
        "runtime_model_path": rel(selected_model, project),
        "model_parent": rel(selected_model.parent, project),
        "required_package": details.get("required_package", "unknown"),
        "load_hint": details.get("load_hint", "custom loader required"),
    }


def runtime_project_path_expr(project: Path, path: Path) -> str:
    relative = rel(path, project)
    if Path(relative).is_absolute():
        return f'_AIUPath({relative!r})'
    return f'AI_STUDIO_DIR / "{relative}"'


def reference_display_path(reference: Path) -> str:
    try:
        return ".opencode/" + normalize_path_text(reference.resolve().relative_to(ROOT).as_posix())
    except ValueError:
        return normalize_path_text(reference.as_posix())


def conversion_reference_step(kind: str, reference: Path) -> str:
    display_path = reference_display_path(reference)
    if kind in {"pytorch", "safetensors"}:
        return f"4. samples/pytorch_sample/ 내부 참조(복사 금지): {display_path}"
    return f"4. 선택 모델 기준 참조: {display_path}"


def runtest_2_sequence(project: Path, selected_model: Path, kind: str, reference: Path) -> list[str]:
    return [
        "1. aiu_studio/ 템플릿 복사",
        f"2. 선택 모델 경로 및 형식 확인: {rel(selected_model, project)} / MODEL_KIND={kind}",
        "3. 복사된 템플릿을 선택 모델 형식에 맞게 변환",
        f"4. 참조 entrypoint 확인: {reference_display_path(reference)}",
        "5. 변환 결과 검증",
    ]


def copy_aiu_studio_folder(project: Path, execute: bool) -> tuple[list[str], list[str], list[str]]:
    copied: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    target = project
    if not AIU_STUDIO_SAMPLE_DIR.is_dir():
        failures.append(f"aiu_studio_folder_missing:{AIU_STUDIO_SAMPLE_DIR}")
        return copied, skipped, failures
    if target.exists() and not target.is_dir():
        failures.append(f"workspace_target_not_directory:{target}")
        return copied, skipped, failures
    if execute:
        for source in AIU_STUDIO_SAMPLE_DIR.rglob("*"):
            relative = source.relative_to(AIU_STUDIO_SAMPLE_DIR)
            if any(part in AIU_STUDIO_COPY_IGNORE_DIRS for part in relative.parts):
                continue
            destination = target / relative
            if source.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            if relative.as_posix() in PROTECTED_REFERENCE_ENTRYPOINTS and destination.exists():
                skipped.append(f"{relative.as_posix()} protected_existing_reference")
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    copied.append(".opencode/samples/aiu_studio/* -> workspace root")
    return copied, skipped, failures


def ensure_aiu_custom_template_copied(project: Path, execute: bool) -> tuple[list[str], list[str], list[str]]:
    changed: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    template_dir = AIU_STUDIO_SAMPLE_DIR / "aiu_custom"
    target_dir = project / "aiu_custom"
    if not template_dir.is_dir():
        failures.append(f"aiu_custom_template_missing:{template_dir}")
        return changed, skipped, failures
    template_files = [
        path.relative_to(template_dir).as_posix()
        for path in template_dir.rglob("*")
        if path.is_file()
        and not any(part in AIU_STUDIO_COPY_IGNORE_DIRS for part in path.relative_to(template_dir).parts)
    ]
    if not template_files:
        failures.append("aiu_custom_template_files_empty")
        return changed, skipped, failures
    if not execute:
        skipped.append("aiu_custom/ template copy verification:dry_run")
        return changed, skipped, failures
    missing = [relative for relative in template_files if not (target_dir / relative).is_file()]
    if missing:
        failures.append("aiu_custom_template_copy_missing:" + ",".join(missing))
        return changed, skipped, failures
    changed.append("aiu_custom/ template copied")
    return changed, skipped, failures


def ensure_runtime_directories(project: Path, execute: bool) -> tuple[list[str], list[str], list[str]]:
    changed: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    runtime_dirs = ["config", "saved_model", "local_serving"]
    if not execute:
        skipped.extend(f"{name}/:dry_run" for name in runtime_dirs)
        return changed, skipped, failures
    for name in runtime_dirs:
        path = project / name
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            failures.append(f"runtime_dir_create_failed:{name}:{exc}")
            continue
        changed.append(f"{name}/")
    return changed, skipped, failures


def split_inline_comment(value: str) -> tuple[str, str]:
    in_single = False
    in_double = False
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == "#" and not in_single and not in_double:
            return value[:index].rstrip(), value[index:].rstrip()
    return value.rstrip(), ""


def assignment_line(name: str, expression: str, comment: str) -> str:
    suffix = f"  {comment}" if comment else ""
    return f"{name} = {expression}{suffix}\n"


def converted_assignment_comment(name: str, selected_relative: str, kind: str, load_hint: str, required_package: str) -> str | None:
    if name in {"MODEL_KIND"}:
        return f"# AIU Studio 변환: 선택 모델 종류 {kind}"
    if name in {"MODEL_LOAD_HINT", "model_load_hint"}:
        return f"# AIU Studio 변환: 선택 모델 로더 {load_hint}"
    if name in {"REQUIRED_PACKAGE", "required_package"}:
        return f"# AIU Studio 변환: 선택 모델 필요 패키지 {required_package}"
    if name in DATA_PREP_VARIABLE_NAMES:
        return f"# AIU Studio 변환: 선택 모델 {kind} 기준 데이터 준비 값"
    if name in MODEL_PREP_VARIABLE_NAMES:
        return f"# AIU Studio 변환: 선택 모델 {kind} 기준 모델 준비 값"
    if name in SUMMARY_VARIABLE_NAMES:
        return f"# AIU Studio 변환: 선택 모델 {kind} 기준 요약 산출물"
    if name in MODEL_RELATED_SETTING_NAMES:
        return f"# AIU Studio 변환: 선택 모델 {selected_relative} 기준 경로"
    return None


def replacement_expression(name: str, replacements: dict[str, str]) -> str | None:
    if name in replacements:
        return replacements[name]
    lower_name = name.lower()
    if lower_name in replacements:
        return replacements[lower_name]
    return None


def text_contains_model_path(value: str) -> bool:
    return any(suffix in value.lower() for suffix in SUPPORTED_MODEL_KINDS)


def rewrite_model_comment(comment: str, selected_relative: str, kind: str, load_hint: str) -> str:
    if not text_contains_model_path(comment):
        if MODEL_COMMENT_HINT_PATTERN.search(comment):
            return f"# AIU Studio 변환: 선택 모델 {selected_relative} 기준 (MODEL_KIND={kind}, loader={load_hint})"
        return comment
    prefix = "#"
    body = comment[1:].strip() if comment.lstrip().startswith("#") else comment.strip()
    converted = MODEL_PATH_REFERENCE_PATTERN.sub(selected_relative, body)
    if converted == body:
        return f"# AIU Studio 변환: 선택 모델 {selected_relative} 기준 (MODEL_KIND={kind}, loader={load_hint})"
    return f"{prefix} AIU Studio 변환: {converted}"


def model_path_literal_expression(token_text: str) -> str | None:
    try:
        value = ast.literal_eval(token_text)
    except (SyntaxError, ValueError):
        return None
    if not isinstance(value, str) or not text_contains_model_path(value):
        return None
    if MODEL_PATH_REFERENCE_PATTERN.search(value):
        return "str(MODEL_PATH)"
    return None


def rewrite_model_string_literals(line: str, selected_relative: str, kind: str, load_hint: str) -> str:
    if not text_contains_model_path(line) and not MODEL_COMMENT_HINT_PATTERN.search(line):
        return line
    suffix = "\n" if line.endswith("\n") else ""
    body = line.rstrip("\n")
    if body.lstrip().startswith("#"):
        indent = body[: len(body) - len(body.lstrip())]
        return f"{indent}{rewrite_model_comment(body.lstrip(), selected_relative, kind, load_hint)}{suffix}"

    code, comment = split_inline_comment(body)

    def replace_literal(match: re.Match[str]) -> str:
        literal = match.group(0)
        if "f" in match.group("prefix").lower():
            return literal
        expression = model_path_literal_expression(literal)
        return expression if expression else literal

    converted_code = PYTHON_STRING_LITERAL_PATTERN.sub(replace_literal, code)
    converted_comment = rewrite_model_comment(comment, selected_relative, kind, load_hint) if comment else ""
    if converted_comment:
        return f"{converted_code}  {converted_comment}{suffix}"
    return f"{converted_code}{suffix}"


def rewrite_path_separator_literals(line: str) -> str:
    if not any(separator in line for separator in ["\\", "＼", "￦", "₩"]):
        return line
    suffix = "\n" if line.endswith("\n") else ""
    body = line.rstrip("\n")

    def replace_literal(match: re.Match[str]) -> str:
        literal = match.group(0)
        if "f" in match.group("prefix").lower():
            return literal
        raw_body = match.group("body")
        raw_normalized = normalize_path_literal_text(raw_body)
        if raw_normalized != raw_body:
            quote = match.group("quote")
            escaped = raw_normalized.replace("\\", "\\\\")
            if quote == '"':
                escaped = escaped.replace('"', '\\"')
            else:
                escaped = escaped.replace("'", "\\'")
            return f"{match.group('prefix')}{quote}{escaped}{quote}"
        try:
            value = ast.literal_eval(literal)
        except (SyntaxError, ValueError):
            return literal
        if not isinstance(value, str):
            return literal
        normalized = normalize_path_literal_text(value)
        if normalized == value:
            return literal
        quote = match.group("quote")
        escaped = normalized.replace("\\", "\\\\")
        if quote == '"':
            escaped = escaped.replace('"', '\\"')
        else:
            escaped = escaped.replace("'", "\\'")
        return f"{match.group('prefix')}{quote}{escaped}{quote}"

    return PYTHON_STRING_LITERAL_PATTERN.sub(replace_literal, body) + suffix


def input_example_literal_expression(token_text: str) -> str | None:
    try:
        value = ast.literal_eval(token_text)
    except (SyntaxError, ValueError):
        return None
    if not isinstance(value, str):
        return None
    normalized = normalize_path_text(value)
    if normalized == "input_example.json":
        return "str(INPUT_EXAMPLE_PATH)"
    if normalized in {"sample_input.json", "example.json"}:
        return "str(INPUT_EXAMPLE_PATH)"
    return None


def rewrite_input_example_literals(line: str) -> str:
    if not any(name in line for name in ["input_example.json", "sample_input.json", "example.json"]):
        return line
    suffix = "\n" if line.endswith("\n") else ""
    body = line.rstrip("\n")

    def replace_literal(match: re.Match[str]) -> str:
        literal = match.group(0)
        if "f" in match.group("prefix").lower():
            return literal
        expression = input_example_literal_expression(literal)
        return expression if expression else literal

    return PYTHON_STRING_LITERAL_PATTERN.sub(replace_literal, body) + suffix


def loader_call_uses_model_path(code: str) -> bool:
    if "MODEL_PATH" in code:
        return True
    return any(re.search(rf"\b{re.escape(name)}\b", code) for name in MODEL_PATH_VARIABLE_NAMES)


def rewrite_model_loader_line(line: str, kind: str, load_hint: str) -> str:
    code, comment = split_inline_comment(line.rstrip("\n"))
    if not MODEL_LOADER_CALL_PATTERN.search(code) or not loader_call_uses_model_path(code):
        return line
    suffix = "\n" if line.endswith("\n") else ""
    indent = code[: len(code) - len(code.lstrip())]
    stripped_code = code.strip()
    if "=" in stripped_code:
        lhs = stripped_code.split("=", 1)[0].strip()
        converted_code = f"{indent}{lhs} = load_selected_model()"
    else:
        converted_code = f"{indent}load_selected_model()"
    converted_comment = f"# AIU Studio 변환: 선택 모델 종류 {kind}, 로더 {load_hint}"
    return f"{converted_code}  {converted_comment}{suffix}"


def rewrite_data_prep_call_line(line: str, kind: str) -> str:
    code, comment = split_inline_comment(line.rstrip("\n"))
    if not DATA_PREP_CALL_PATTERN.search(code):
        return line
    suffix = "\n" if line.endswith("\n") else ""
    indent = code[: len(code) - len(code.lstrip())]
    stripped_code = code.strip()
    converted_comment = f"# AIU Studio 변환: 선택 모델 {kind} 기준 synthetic input_example 사용"
    if "=" in stripped_code:
        lhs = stripped_code.split("=", 1)[0].strip()
        name = lhs.split(",", 1)[0].strip()
        if name in {"train_loader", "test_loader", "dataloader", "loader"}:
            converted_code = f"{indent}{lhs} = _aiu_model_input_example()[\"inputs\"]"
        elif name in {"train_dataset", "test_dataset", "dataset"}:
            converted_code = f"{indent}{lhs} = _aiu_model_input_example()"
        else:
            converted_code = f"{indent}{lhs} = _aiu_model_input_example()"
    else:
        converted_code = f"{indent}_aiu_model_input_example()"
    return f"{converted_code}  {converted_comment}{suffix}"


def rewrite_model_prep_line(line: str, kind: str) -> str:
    code, comment = split_inline_comment(line.rstrip("\n"))
    suffix = "\n" if line.endswith("\n") else ""
    indent = code[: len(code) - len(code.lstrip())]
    stripped_code = code.strip()

    if MODEL_TRAIN_CALL_PATTERN.search(code):
        return (
            f"{indent}# AIU Studio 변환: 선택 모델 {kind}은 이미 학습된 모델을 로드하므로 원본 학습 호출을 실행하지 않습니다.{suffix}"
            f"{indent}# {stripped_code}{suffix}"
        )

    if not MODEL_PREP_CALL_PATTERN.search(code):
        return line

    converted_comment = f"# AIU Studio 변환: 선택 모델 {kind} 기준 load_selected_model() 사용"
    if "=" in stripped_code:
        lhs = stripped_code.split("=", 1)[0].strip()
        first_name = lhs.split(",", 1)[0].strip()
        if first_name not in MODEL_PREP_VARIABLE_NAMES:
            return line
        return f"{indent}{lhs} = load_selected_model()  {converted_comment}{suffix}"
    return (
        f"{indent}# AIU Studio 변환: 선택 모델 {kind}은 load_selected_model()으로 준비됩니다.{suffix}"
        f"{indent}# {stripped_code}{suffix}"
    )


def rewrite_summary_line(line: str, kind: str) -> str:
    code, comment = split_inline_comment(line.rstrip("\n"))
    if not SUMMARY_CALL_PATTERN.search(code):
        return line

    stripped_code = code.strip()
    if stripped_code.startswith("def "):
        return line

    suffix = "\n" if line.endswith("\n") else ""
    indent = code[: len(code) - len(code.lstrip())]
    converted_comment = f"# AIU Studio 변환: 선택 모델 {kind} 기준 요약으로 대체"

    if "=" in stripped_code:
        lhs = stripped_code.split("=", 1)[0].strip()
        first_name = lhs.split(",", 1)[0].strip()
        expression = "_aiu_write_summary()" if first_name in SUMMARY_PATH_VARIABLE_NAMES else "_aiu_model_summary()"
        return f"{indent}{lhs} = {expression}  {converted_comment}{suffix}"

    if stripped_code.startswith("return "):
        return f"{indent}return _aiu_model_summary()  {converted_comment}{suffix}"

    if stripped_code.startswith("print("):
        return f"{indent}print(_aiu_model_summary())  {converted_comment}{suffix}"

    return (
        f"{indent}# AIU Studio 변환: 원본 summary 호출은 선택 모델 요약으로 대체합니다.{suffix}"
        f"{indent}_aiu_model_summary()  {converted_comment}{suffix}"
    )


def import_package_for_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    match = re.match(r"import\s+([A-Za-z_][A-Za-z0-9_]*)\b", stripped)
    if match:
        module_name = match.group(1)
        package_name = MODEL_IMPORT_PACKAGE_NAMES.get(module_name)
        return (module_name, package_name) if package_name else None
    match = re.match(r"from\s+([A-Za-z_][A-Za-z0-9_]*)\b\s+import\s+", stripped)
    if match:
        module_name = match.group(1)
        package_name = MODEL_IMPORT_PACKAGE_NAMES.get(module_name)
        return (module_name, package_name) if package_name else None
    return None


def rewrite_model_import_line(line: str, required_package: str) -> str:
    package = import_package_for_line(line)
    if package is None:
        return line
    module_name, package_name = package
    if module_name in ALWAYS_KEEP_IMPORT_MODULES:
        return line
    if package_name == required_package:
        return line
    suffix = "\n" if line.endswith("\n") else ""
    indent = line[: len(line) - len(line.lstrip())]
    original = line.rstrip("\n")
    return (
        f"{indent}# AIU Studio 변환: 선택 모델 로더는 {required_package} 기준이라 {module_name} import를 비활성화합니다.{suffix}"
        f"{indent}# {original.lstrip()}{suffix}"
    )


def rewrite_reference_line(line: str, selected_relative: str, kind: str, load_hint: str, required_package: str) -> str:
    import_converted = rewrite_model_import_line(line, required_package)
    if import_converted != line:
        return import_converted
    converted = rewrite_model_string_literals(line, selected_relative, kind, load_hint)
    converted = rewrite_path_separator_literals(converted)
    converted = rewrite_input_example_literals(converted)
    converted = rewrite_data_prep_call_line(converted, kind)
    converted = rewrite_model_prep_line(converted, kind)
    converted = rewrite_summary_line(converted, kind)
    return rewrite_model_loader_line(converted, kind, load_hint)


def rewrite_preserved_line(line: str) -> str:
    converted = rewrite_path_separator_literals(line)
    return rewrite_input_example_literals(converted)


SAFE_EXECUTION_REGISTRATION_FIELDS = {
    "AI_STUDIO_DIR",
    "PROJECT_DIR",
    "SOURCE_MODEL_PATH",
    "DATA_MODEL_PATH",
    "MODEL_PATH",
    "MODEL_KIND",
    "MODEL_LOAD_HINT",
    "INPUT_EXAMPLE_PATH",
    "CONFIG_DIR",
    "CONFIG_PATH",
    "mlflow_tracking_url",
    "mlflow_tracking_username",
    "mlflow_tracking_password",
    "mlflow_experiment_name",
    "mlflow_register_model_name",
}


def transform_reference_text(
    reference_text: str,
    injected_block: str,
    replacements: dict[str, str],
    selected_relative: str,
    kind: str,
    load_hint: str,
    required_package: str,
    preserve_code: bool = False,
) -> str:
    lines = reference_text.splitlines(keepends=True)
    output: list[str] = []
    inserted = False
    future_import_pattern = re.compile(r"^\s*from\s+__future__\s+import\s+")
    import_pattern = re.compile(r"^\s*(import\s+[A-Za-z_][A-Za-z0-9_]*(?:\s+as\s+[A-Za-z_][A-Za-z0-9_]*)?|from\s+[A-Za-z_][A-Za-z0-9_.]*\s+import\s+.+)")
    assignment_pattern = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")

    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    while insert_at < len(lines) and re.match(r"^#.*coding[:=]", lines[insert_at]):
        insert_at += 1
    while insert_at < len(lines):
        line = lines[insert_at]
        if not line.strip():
            insert_at += 1
            continue
        if future_import_pattern.match(line):
            insert_at += 1
            continue
        break
    while insert_at < len(lines):
        line = lines[insert_at]
        if not line.strip():
            next_index = insert_at + 1
            while next_index < len(lines) and not lines[next_index].strip():
                next_index += 1
            if next_index < len(lines) and import_pattern.match(lines[next_index]):
                insert_at += 1
                continue
            break
        if import_pattern.match(line):
            insert_at += 1
            continue
        break

    for index, line in enumerate(lines):
        if not preserve_code and index == insert_at and not inserted:
            output.append(injected_block)
            inserted = True

        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        if not preserve_code and stripped.startswith("#") and not re.match(r"^#.*coding[:=]", stripped):
            next_index = index + 1
            while next_index < len(lines) and not lines[next_index].strip():
                next_index += 1
            if next_index < len(lines):
                next_stripped = lines[next_index].lstrip()
                next_match = assignment_pattern.match(next_stripped.rstrip("\n"))
                if next_match:
                    next_name = next_match.group(1)
                    if replacement_expression(next_name, replacements) is not None:
                        converted_comment = converted_assignment_comment(next_name, selected_relative, kind, load_hint, required_package)
                        if converted_comment:
                            output.append(f"{indent}{converted_comment}\n")
                            continue
        match = assignment_pattern.match(stripped.rstrip("\n"))
        if not match:
            output.append(rewrite_preserved_line(line) if preserve_code else rewrite_reference_line(line, selected_relative, kind, load_hint, required_package))
            continue

        name, raw_value = match.groups()
        expression = replacement_expression(name, replacements)
        if expression is None:
            output.append(rewrite_preserved_line(line) if preserve_code else rewrite_reference_line(line, selected_relative, kind, load_hint, required_package))
            continue
        if preserve_code and name not in SAFE_EXECUTION_REGISTRATION_FIELDS:
            output.append(rewrite_preserved_line(line))
            continue

        if not preserve_code and name in MLFLOW_SETTING_NAMES and not indent:
            output.append(f"# AIU Studio preserved original assignment; value is defined in the conversion block above.\n")
            output.append(f"# {line.rstrip()}\n")
            continue
        if not preserve_code and name in MLFLOW_SETTING_NAMES:
            output.append(rewrite_preserved_line(line) if preserve_code else rewrite_reference_line(line, selected_relative, kind, load_hint, required_package))
            continue

        _, comment = split_inline_comment(raw_value)
        converted_comment = None if preserve_code else converted_assignment_comment(name, selected_relative, kind, load_hint, required_package)
        if converted_comment:
            comment = converted_comment
        output.append(f"{indent}{assignment_line(name, expression, comment)}")

    if not preserve_code and not inserted:
        output.insert(0, injected_block)

    if output and not output[-1].endswith("\n"):
        output[-1] += "\n"
    return "".join(output)


def aiu_injected_block(project: Path, selected_model: Path, kind: str, reference: Path) -> str:
    selected_relative = rel(selected_model, project)
    reference_expr = runtime_project_path_expr(project, reference)
    aiu_studio_path = project
    selected_model_expr = runtime_project_path_expr(project, selected_model)
    input_example_expr = 'AI_STUDIO_DIR / "input_example.json"'
    config_dir_expr = 'AI_STUDIO_DIR / "config"'
    config_path_expr = 'AI_STUDIO_DIR / "config" / "config.json"'
    model_output_dir_expr = 'AI_STUDIO_DIR / "saved_model"'
    model_output_path_expr = 'AI_STUDIO_DIR / "saved_model" / "model.pkl"'
    default_experiment_name, default_register_model_name = default_mlflow_names(project, selected_model)
    profile = model_profile(project, selected_model, kind)
    details = MODEL_KIND_DETAILS.get(kind, {})
    required_package = details.get("required_package", "unknown")
    load_hint = details.get("load_hint", "custom loader required")
    loader = details.get(
        "loader",
        """def load_selected_model():\n    raise ValueError(f\"unsupported MODEL_KIND: {MODEL_KIND}\")\n""",
    )
    data_prep = aiu_data_prep_block(kind)
    return f'''

# --- AIU Studio selected model conversion ---
# 선택된 모델을 먼저 판별하고, 원본 모델 경로를 직접 읽도록 변환합니다.
# MODEL_KIND에 맞는 load_selected_model()을 생성해 워크스페이스 템플릿 코드를 선택 모델 기준으로 갱신합니다.
# 이 블록은 자동 변환되지만 아래 원본 runtest.py 구조와 주석은 최대한 유지합니다.
import os as _aiu_os
import atexit as _aiu_atexit
import json as _aiu_json
from pathlib import Path as _AIUPath

AI_STUDIO_DIR = _AIUPath(__file__).resolve().parent
ORIGINAL_MODEL_PATH = {selected_model_expr}
SOURCE_MODEL_PATH = {selected_model_expr}
DATA_MODEL_PATH = SOURCE_MODEL_PATH
MODEL_PATH = SOURCE_MODEL_PATH
INPUT_EXAMPLE_PATH = {input_example_expr}
CONFIG_DIR = {config_dir_expr}
CONFIG_PATH = {config_path_expr}
MODEL_OUTPUT_DIR = {model_output_dir_expr}
MODEL_OUTPUT_PATH = {model_output_path_expr}
MODEL_KIND = "{kind}"
MODEL_PROFILE = {json.dumps(profile, ensure_ascii=False, indent=4)}
AIU_REQUIRED_PACKAGE = "{required_package}"
AIU_LOAD_HINT = "{load_hint}"
REFERENCE_ENTRYPOINT = {reference_expr}

# 자주 쓰는 소문자 변수명도 선택 모델 및 aiu_studio 산출물 경로를 보도록 맞춥니다.
source_model_path = str(SOURCE_MODEL_PATH)
data_model_path = str(DATA_MODEL_PATH)
model_path = str(MODEL_PATH)
input_example_path = str(INPUT_EXAMPLE_PATH)
config_dir = str(CONFIG_DIR)
config_path = str(CONFIG_PATH)
model_dir = str(MODEL_OUTPUT_DIR)
model_output_dir = str(MODEL_OUTPUT_DIR)
model_output_path = str(MODEL_OUTPUT_PATH)
saved_model_dir = str(MODEL_OUTPUT_DIR)

# Step 6 원격 MLflow 등록 실행 중 상대경로 산출물은 선택한 현재 프로젝트 경로 아래에 생성되도록 고정합니다.
_aiu_os.chdir(AI_STUDIO_DIR)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
MODEL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# MLflow/AI Studio settings
# tracking URL, username, password는 사용자가 직접 입력합니다.
# experiment/model name은 선택 모델 파일명 기준으로 자동 생성됩니다.
# password 값은 출력하지 않습니다.
mlflow_tracking_url = ""
mlflow_tracking_username = ""
mlflow_tracking_password = ""
mlflow_experiment_name = "{default_experiment_name}"
mlflow_register_model_name = "{default_register_model_name}"

effective_mlflow_tracking_uri = mlflow_tracking_url

{loader}

{data_prep}

if not mlflow_tracking_url:
    raise ValueError("mlflow_tracking_url_required: set remote MLflow tracking URL before deployment")

for _aiu_env_name, _aiu_env_value in {{
    "MLFLOW_TRACKING_URI": effective_mlflow_tracking_uri,
    "MLFLOW_TRACKING_USERNAME": mlflow_tracking_username,
    "MLFLOW_TRACKING_PASSWORD": mlflow_tracking_password,
    "MLFLOW_EXPERIMENT_NAME": mlflow_experiment_name,
    "MLFLOW_REGISTER_MODEL_NAME": mlflow_register_model_name,
}}.items():
    if _aiu_env_value:
        _aiu_os.environ[_aiu_env_name] = _aiu_env_value

def _aiu_print_existing_model_tod():
    print("\\nTOD Guide:")
    print("- 1. 모델 목록 확인 - 완료")
    print("- 2. 모델 경로로 선택 - 완료")
    print("- 3. 선택 모델 환경 변환 + requirements.txt 재정의/확인 - 완료")
    print("- 4. 모델 환경변수/패키지 상태 체크 - 다음")
    print("- 5. 원격 MLflow 등록 실행 - 완료")
    print("- 6. 추론 테스트 - 다음")
    print("- 7. MLflow 검증 - 다음")
    print("- 8. 오류 수정 및 재검증 - 오류 시")

_aiu_atexit.register(_aiu_print_existing_model_tod)
# --- /AIU Studio selected model conversion ---

'''


def aiu_data_prep_payload(kind: str) -> str:
    if kind in {"pytorch", "safetensors"}:
        return '''{
        "inputs": [
            {
                "name": "synthetic_image",
                "shape": [1, 1, 28, 28],
                "datatype": "FP32",
                "data": [0.0 for _ in range(1 * 1 * 28 * 28)],
            }
        ],
        "model_kind": MODEL_KIND,
        "model_path": str(MODEL_PATH),
    }'''
    if kind in {"sklearn_pickle", "sklearn_joblib", "xgboost_bst", "xgboost_ubj"}:
        return '''{
        "inputs": [
            {
                "name": "synthetic_tabular",
                "shape": [1, 4],
                "datatype": "FP32",
                "data": [[0.0, 0.0, 0.0, 0.0]],
            }
        ],
        "model_kind": MODEL_KIND,
        "model_path": str(MODEL_PATH),
    }'''
    if kind == "onnx":
        return '''{
        "inputs": [
            {
                "name": "input",
                "shape": [1, 4],
                "datatype": "FP32",
                "data": [[0.0, 0.0, 0.0, 0.0]],
            }
        ],
        "model_kind": MODEL_KIND,
        "model_path": str(MODEL_PATH),
    }'''
    if kind in {"tensorflow_keras", "tensorflow_h5"}:
        return '''{
        "inputs": [
            {
                "name": "synthetic_tensor",
                "shape": [1, 4],
                "datatype": "FP32",
                "data": [[0.0, 0.0, 0.0, 0.0]],
            }
        ],
        "model_kind": MODEL_KIND,
        "model_path": str(MODEL_PATH),
    }'''
    return '''{
        "inputs": [
            {
                "name": "synthetic_input",
                "shape": [1],
                "datatype": "FP32",
                "data": [0.0],
            }
        ],
        "model_kind": MODEL_KIND,
        "model_path": str(MODEL_PATH),
    }'''


def aiu_data_prep_block(kind: str) -> str:
    payload = aiu_data_prep_payload(kind)
    return f'''# 데이터 준비
# 선택 모델 종류에 맞는 최소 input_example을 생성합니다.
# 외부 데이터셋(FashionMNIST 등)을 다운로드하지 않고 원격 배포/검증용 synthetic 입력만 만듭니다.
# MODEL_KIND={kind} 기준으로 생성된 데이터 준비 코드입니다.
import json as _aiu_json

try:
    INPUT_EXAMPLE_PATH
except NameError:
    INPUT_EXAMPLE_PATH = AI_STUDIO_DIR / "input_example.json"

def _aiu_flat_zeros(size):
    return [0.0 for _ in range(size)]

def _aiu_model_input_example():
    return {payload}

def _aiu_model_summary():
    return {{
        "model_kind": MODEL_KIND,
        "model_path": str(MODEL_PATH),
        "input_example_path": str(INPUT_EXAMPLE_PATH),
    }}

def _aiu_write_summary():
    try:
        summary_dir = AI_STUDIO_CODE_DIR
    except NameError:
        summary_dir = AI_STUDIO_DIR / "code"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / "training_summary.json"
    summary_path.write_text(_aiu_json.dumps(_aiu_model_summary(), ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_path

def _aiu_write_input_example():
    INPUT_EXAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = _aiu_model_input_example()
    INPUT_EXAMPLE_PATH.write_text(_aiu_json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

input_example = _aiu_write_input_example()
'''


def insert_preserved_data_prep_block(text: str, kind: str) -> str:
    if "_aiu_model_input_example" in text:
        return text
    marker = "\ndef load_selected_model"
    block = "\n\n" + aiu_data_prep_block(kind).rstrip() + "\n"
    if marker in text:
        return text.replace(marker, block + marker, 1)
    main_marker = "\ndef main"
    if main_marker in text:
        return text.replace(main_marker, block + main_marker, 1)
    return text.rstrip() + block


def selected_model_input_example_payload(kind: str) -> str:
    if kind in {"pytorch", "safetensors"}:
        return '''{
        "inputs": [
            {
                "name": "selected_pytorch_tensor",
                "shape": [1, 1, 28, 28],
                "datatype": "FP32",
                "data": [0.0 for _ in range(1 * 1 * 28 * 28)],
            }
        ],
        "model_kind": MODEL_KIND,
        "model_path": str(SOURCE_MODEL_PATH),
    }'''
    if kind in {"sklearn_pickle", "sklearn_joblib", "xgboost_bst", "xgboost_ubj"}:
        return '''{
        "inputs": [
            {
                "name": "selected_tabular",
                "shape": [1, 4],
                "datatype": "FP32",
                "data": [[0.0, 0.0, 0.0, 0.0]],
            }
        ],
        "model_kind": MODEL_KIND,
        "model_path": str(SOURCE_MODEL_PATH),
    }'''
    if kind == "onnx":
        return '''{
        "inputs": [
            {
                "name": "input",
                "shape": [1, 4],
                "datatype": "FP32",
                "data": [[0.0, 0.0, 0.0, 0.0]],
            }
        ],
        "model_kind": MODEL_KIND,
        "model_path": str(SOURCE_MODEL_PATH),
    }'''
    if kind in {"tensorflow_keras", "tensorflow_h5"}:
        return '''{
        "inputs": [
            {
                "name": "selected_tensor",
                "shape": [1, 4],
                "datatype": "FP32",
                "data": [[0.0, 0.0, 0.0, 0.0]],
            }
        ],
        "model_kind": MODEL_KIND,
        "model_path": str(SOURCE_MODEL_PATH),
    }'''
    return '''{
        "inputs": [
            {
                "name": "selected_input",
                "shape": [1],
                "datatype": "FP32",
                "data": [0.0],
            }
        ],
        "model_kind": MODEL_KIND,
        "model_path": str(SOURCE_MODEL_PATH),
    }'''


def selected_model_input_example_block(kind: str) -> str:
    payload = selected_model_input_example_payload(kind)
    return f'''
def selected_model_input_example():
    # AIU Studio 변환: 선택 모델 종류에 맞는 배포용 synthetic input_example입니다.
    return {payload}


def write_selected_input_example():
    input_example = selected_model_input_example()
    INPUT_EXAMPLE_PATH.write_text(
        json.dumps(input_example, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return input_example
'''


def selected_model_input_example_data(project: Path, selected_model: Path, kind: str) -> dict:
    if kind in {"pytorch", "safetensors"}:
        payload = {
            "inputs": [
                {
                    "name": "selected_pytorch_tensor",
                    "shape": [1, 1, 28, 28],
                    "datatype": "FP32",
                    "data": [0.0 for _ in range(1 * 1 * 28 * 28)],
                }
            ],
        }
    elif kind in {"sklearn_pickle", "sklearn_joblib", "xgboost_bst", "xgboost_ubj", "onnx", "tensorflow_keras", "tensorflow_h5"}:
        payload = {
            "inputs": [
                {
                    "name": "selected_tabular",
                    "shape": [1, 4],
                    "datatype": "FP32",
                    "data": [[0.0, 0.0, 0.0, 0.0]],
                }
            ],
        }
    else:
        payload = {"inputs": []}
    payload["model_kind"] = kind
    payload["model_path"] = rel(selected_model, project)
    return payload


def ensure_linux_code_paths(text: str) -> str:
    if "mlflow.pyfunc.log_model(" not in text or "code_paths=" in text:
        return text
    marker = "            pip_requirements=\"requirements.txt\","
    code_paths_line = (
        "            code_paths=[(__import__(\"pathlib\").Path(__file__).resolve().parent / \"aiu_custom\").as_posix()],\n"
    )
    if marker in text:
        return text.replace(marker, code_paths_line + marker, 1)
    marker = "            registered_model_name=mlflow_register_model_name,\n"
    if marker in text:
        return text.replace(marker, marker + code_paths_line, 1)
    return text


def generated_selected_model_runtest_text(project: Path, selected_model: Path, kind: str, reference: Path) -> str:
    selected_relative = rel(selected_model, project)
    text = reference.read_text(encoding="utf-8", errors="ignore")
    default_experiment_name, default_register_model_name = default_mlflow_names(project, selected_model)
    details = MODEL_KIND_DETAILS.get(kind, {})
    load_hint = details.get("load_hint", "custom loader required")
    loader = details.get(
        "loader",
        """def load_selected_model():\n    raise ValueError(f\"unsupported model kind: {MODEL_KIND}\")\n""",
    )
    loader = loader.replace("MODEL_PATH", "SOURCE_MODEL_PATH")
    selected_path_expr = "PROJECT_DIR" + "".join(f" / {json.dumps(part, ensure_ascii=False)}" for part in Path(selected_relative).parts)
    selected_connection_block = f'''
{loader}
{selected_model_input_example_block(kind)}
'''
    original_path_block = '''PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_MODEL_PATH = PROJECT_DIR / "data" / "torch" / "model.pt"
DATA_MODEL_PATH = SOURCE_MODEL_PATH
MODEL_KIND = "pytorch"
MODEL_LOAD_HINT = "torch.load(MODEL_PATH, map_location='cpu')"
INPUT_EXAMPLE_PATH = PROJECT_DIR / "input_example.json"
CONFIG_DIR = PROJECT_DIR / "config"
CONFIG_PATH = CONFIG_DIR / "config.json"
MODEL_DIR = PROJECT_DIR / "saved_model"
MODEL_PATH = MODEL_DIR / "model.pt"'''
    text = text.replace("import mlflow\n", "")
    text = re.sub(r"(?m)^SOURCE_MODEL_PATH\s*=.*$", f"SOURCE_MODEL_PATH = {selected_path_expr}", text, count=1)
    text = re.sub(r"(?m)^DATA_MODEL_PATH\s*=.*$", "DATA_MODEL_PATH = SOURCE_MODEL_PATH", text, count=1)
    text = re.sub(r"(?m)^MODEL_KIND\s*=.*$", f"MODEL_KIND = {kind!r}", text, count=1)
    text = re.sub(r"(?m)^MODEL_LOAD_HINT\s*=.*$", f"MODEL_LOAD_HINT = {load_hint.replace('MODEL_PATH', 'SOURCE_MODEL_PATH')!r}", text, count=1)
    text = re.sub(r"(?m)^INPUT_EXAMPLE_PATH\s*=.*$", 'INPUT_EXAMPLE_PATH = PROJECT_DIR / "input_example.json"', text, count=1)
    text = re.sub(r"(?m)^CONFIG_DIR\s*=.*$", 'CONFIG_DIR = PROJECT_DIR / "config"', text, count=1)
    text = re.sub(r"(?m)^CONFIG_PATH\s*=.*$", 'CONFIG_PATH = CONFIG_DIR / "config.json"', text, count=1)
    text = re.sub(r"(?m)^MODEL_DIR\s*=.*$", 'MODEL_DIR = PROJECT_DIR / "saved_model"', text, count=1)
    if "def load_selected_model(" not in text:
        insert_marker = "\n# AI 환경 설정\n"
        if insert_marker in text:
            text = text.replace(insert_marker, "\n" + selected_connection_block.strip() + "\n" + insert_marker, 1)
        else:
            text = text.replace("configure_utf8_stdio()\n", "configure_utf8_stdio()\n\n" + selected_connection_block.strip() + "\n", 1)
    text = text.replace('mlflow_experiment_name = "pytorch_sample"', f"mlflow_experiment_name = {default_experiment_name!r}")
    text = text.replace('mlflow_register_model_name = "pytorch_sample_model"', f"mlflow_register_model_name = {default_register_model_name!r}")
    text = text.replace("runtest.py에 직접 입력하세요.", "runtest_2.py에 직접 입력하세요.")
    text = text.replace(
        "    export_mlflow_environment()\n    mlflow.set_tracking_uri(mlflow_tracking_url)",
        "    try:\n"
        "        import mlflow\n"
        "    except Exception as exc:\n"
        "        print(f\"MLflow import failed. Install packages from requirements.txt first. reason={exc}\")\n"
        "        return\n\n"
        "    export_mlflow_environment()\n"
        "    mlflow.set_tracking_uri(mlflow_tracking_url)",
    )
    text = re.sub(
        r"(?m)^    model\s*=\s*TinyTorchModel\(.*\)\n",
        "    model = load_selected_model()\n"
        "    # 모델 준비: 선택된 모델을 그대로 사용하고 재학습하지 않습니다.\n",
        text,
        count=1,
    )
    text = re.sub(
        r"(?m)^    train_x,\s*train_y,\s*test_x,\s*test_y\s*=\s*prepare_data\(\)\n",
        "    input_example = write_selected_input_example()\n",
        text,
        count=1,
    )
    text = re.sub(
        r"(?m)^    train_model\(.*\)\n",
        "    # 선택 모델은 이미 학습된 모델이므로 원본 train_model 호출은 실행하지 않습니다.\n",
        text,
        count=1,
    )
    text = re.sub(
        r"(?m)^    metrics\s*=\s*compute_metrics\(.*\)\n",
        "    metrics = {\"model_loaded\": 1.0 if model is not None else 0.0}\n",
        text,
        count=1,
    )
    text = re.sub(
        r"(?m)^    input_example\s*=\s*write_input_example\(.*\)\n",
        "",
        text,
        count=1,
    )
    text = re.sub(
        r"(?m)^    config\s*=\s*\{.*\"framework\".*\}\n",
        '    config = {"framework": MODEL_KIND, "model_path": str(SOURCE_MODEL_PATH), "model_relative_path": '
        + repr(selected_relative)
        + "}\n",
        text,
        count=1,
    )
    text = re.sub(
        r"(?m)^    torch\.save\(.*\)\n",
        "    selected_model_path = SOURCE_MODEL_PATH\n",
        text,
        count=1,
    )
    text = text.replace('        mlflow.set_tag("data.name", "synthetic_tensor(pytorch)")', '        mlflow.set_tag("data.name", "selected_model")')
    text = text.replace("            artifacts={\n                \"model\": MODEL_PATH.as_posix(),", "            artifacts={\n                \"model\": selected_model_path.as_posix(),")
    text = text.replace("            artifacts={\n                \"model\": MODEL_DIR.as_posix(),", "            artifacts={\n                \"model\": selected_model_path.as_posix(),")
    text = text.replace('    print(f"model written: {MODEL_PATH}")', '    print(f"selected model: {selected_model_path}")')
    text = ensure_linux_code_paths(text)
    return text.rstrip() + "\n"


def generated_runtest_text(project: Path, selected_model: Path, kind: str, reference: Path) -> str:
    reference_text = reference.read_text(encoding="utf-8", errors="ignore")
    selected_relative = rel(selected_model, project)
    preserve_code = preserve_reference_code(reference)
    if preserve_code:
        return generated_selected_model_runtest_text(project, selected_model, kind, reference)
    path_constructor = "Path" if preserve_code else "_AIUPath"
    aiu_studio_path = project
    default_experiment_name, default_register_model_name = default_mlflow_names(project, selected_model)
    details = MODEL_KIND_DETAILS.get(kind, {})
    required_package = details.get("required_package", "unknown")
    load_hint = details.get("load_hint", "custom loader required")
    replacements = {
        "AI_STUDIO_DIR": f"{path_constructor}(__file__).resolve().parent",
        "PROJECT_DIR": f"{path_constructor}(__file__).resolve().parent",
        "AI_STUDIO_CODE_DIR": 'AI_STUDIO_DIR / "code"',
        "AI_STUDIO_METRICS_DIR": 'AI_STUDIO_DIR / "metrics"',
        "AI_STUDIO_TRACKING_DIR": "AI_STUDIO_DIR",
        "SOURCE_MODEL_PATH": f'AI_STUDIO_DIR / "{selected_relative}"',
        "DATA_MODEL_PATH": "SOURCE_MODEL_PATH",
        "MODEL_PATH": "SOURCE_MODEL_PATH",
        "CONFIG_DIR": 'AI_STUDIO_DIR / "config"',
        "CONFIG_PATH": 'AI_STUDIO_DIR / "config" / "config.json"',
        "MODEL_OUTPUT_DIR": 'AI_STUDIO_DIR / "saved_model"',
        "MODEL_OUTPUT_PATH": 'AI_STUDIO_DIR / "saved_model" / "model.pkl"',
        "MODEL_KIND": repr(kind),
        "MODEL_LOAD_HINT": repr(load_hint),
        "classifier": "load_selected_model()",
        "clf": "load_selected_model()",
        "INPUT_EXAMPLE_PATH": 'AI_STUDIO_DIR / "input_example.json"',
        "dataset": "_aiu_model_input_example()",
        "dataloader": '_aiu_model_input_example()["inputs"]',
        "features": '_aiu_model_input_example()["inputs"][0]["data"]',
        "input_example": "_aiu_write_input_example()",
        "input_example_path": "str(INPUT_EXAMPLE_PATH)",
        "loader": '_aiu_model_input_example()["inputs"]',
        "labels": "[]",
        "model": "load_selected_model()",
        "INPUT_EXAMPLE_FILE": "INPUT_EXAMPLE_PATH",
        "input_example_file": "str(INPUT_EXAMPLE_PATH)",
        "SAMPLE_INPUT_PATH": "INPUT_EXAMPLE_PATH",
        "sample_input_path": "str(INPUT_EXAMPLE_PATH)",
        "sample_data": '_aiu_model_input_example()["inputs"][0]["data"]',
        "sample_input": '_aiu_model_input_example()["inputs"][0]["data"]',
        "batch_size": "1",
        "criterion": "None",
        "estimator": "load_selected_model()",
        "net": "load_selected_model()",
        "optimizer": "None",
        "regressor": "load_selected_model()",
        "summary": "_aiu_model_summary()",
        "summary_file": "_aiu_write_summary()",
        "summary_json": "_aiu_write_summary()",
        "summary_path": "_aiu_write_summary()",
        "model_summary": "_aiu_model_summary()",
        "training_summary": "_aiu_model_summary()",
        "test_dataset": "_aiu_model_input_example()",
        "test_df": "_aiu_model_input_example()",
        "test_loader": '_aiu_model_input_example()["inputs"]',
        "test_x": '_aiu_model_input_example()["inputs"][0]["data"]',
        "test_y": "[]",
        "train_dataset": "_aiu_model_input_example()",
        "train_df": "_aiu_model_input_example()",
        "train_loader": '_aiu_model_input_example()["inputs"]',
        "train_x": '_aiu_model_input_example()["inputs"][0]["data"]',
        "train_y": "[]",
        "x_test": '_aiu_model_input_example()["inputs"][0]["data"]',
        "x_train": '_aiu_model_input_example()["inputs"][0]["data"]',
        "y_test": "[]",
        "y_train": "[]",
        "source_model_path": "str(SOURCE_MODEL_PATH)",
        "data_model_path": "str(DATA_MODEL_PATH)",
        "model_path": "str(MODEL_OUTPUT_PATH)",
        "model_dir": "str(MODEL_OUTPUT_DIR)",
        "model_output_dir": "str(MODEL_OUTPUT_DIR)",
        "model_output_path": "str(MODEL_OUTPUT_PATH)",
        "saved_model_dir": "str(MODEL_OUTPUT_DIR)",
        "config_dir": "str(CONFIG_DIR)",
        "config_path": "str(CONFIG_PATH)",
        "MODEL_FILE": "SOURCE_MODEL_PATH",
        "model_file": "str(MODEL_PATH)",
        "CHECKPOINT_PATH": "SOURCE_MODEL_PATH",
        "checkpoint_path": "str(MODEL_PATH)",
        "MODEL_LOAD_HINT": repr(load_hint) if preserve_code else "AIU_LOAD_HINT",
        "model_load_hint": "AIU_LOAD_HINT",
        "REQUIRED_PACKAGE": "AIU_REQUIRED_PACKAGE",
        "required_package": "AIU_REQUIRED_PACKAGE",
        "mlflow_tracking_url": '""',
        "mlflow_tracking_username": '""',
        "mlflow_tracking_password": '""',
        "mlflow_experiment_name": repr(default_experiment_name),
        "mlflow_register_model_name": repr(default_register_model_name),
    }
    if preserve_code:
        replacements.update(
            {
                "mlflow_tracking_url": '""',
                "mlflow_experiment_name": repr(default_experiment_name),
                "mlflow_register_model_name": repr(default_register_model_name),
            }
        )
    transformed = transform_reference_text(
        reference_text,
        aiu_injected_block(project, selected_model, kind, reference),
        replacements,
        selected_relative,
        kind,
        load_hint,
        required_package,
        preserve_code=preserve_code,
    )
    if preserve_code:
        transformed = insert_preserved_data_prep_block(transformed, kind)
    transformed = transformed.replace(
        "원격 MLflow 등록 실행을 위해 MLflow/AI Studio 설정을 runtest.py에 직접 입력하세요.",
        "원격 MLflow 등록 실행을 위해 MLflow/AI Studio 설정을 runtest_2.py에 직접 입력하세요.",
    )
    transformed = ensure_linux_code_paths(transformed)
    return transformed.rstrip() + "\n"


def generated_localservingtest_text(project: Path, selected_model: Path, kind: str, reference: Path) -> str:
    selected_relative = rel(selected_model, project)
    profile = model_profile(project, selected_model, kind)
    details = MODEL_KIND_DETAILS.get(kind, {})
    required_package = details.get("required_package", "unknown")
    load_hint = details.get("load_hint", "custom loader required")
    loader = details.get(
        "loader",
        """def load_selected_model():\n    raise ValueError(f\"unsupported MODEL_KIND: {MODEL_KIND}\")\n""",
    )
    return f'''#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


LOCAL_SERVING_DIR = Path(__file__).resolve().parent
AI_STUDIO_DIR = LOCAL_SERVING_DIR.parent
ORIGINAL_MODEL_PATH = AI_STUDIO_DIR / {selected_relative!r}
SOURCE_MODEL_PATH = ORIGINAL_MODEL_PATH
DATA_MODEL_PATH = SOURCE_MODEL_PATH
MODEL_PATH = SOURCE_MODEL_PATH
MODEL_KIND = "{kind}"
MODEL_PROFILE = {json.dumps(profile, ensure_ascii=False, indent=4)}
AIU_REQUIRED_PACKAGE = "{required_package}"
AIU_LOAD_HINT = "{load_hint}"
REFERENCE_ENTRYPOINT = {reference_display_path(reference)!r}

# AIU Studio 변환: 선택 모델 원본 경로 {selected_relative} 기준 추론 테스트입니다.
# 모델 파일은 템플릿 폴더로 복사하지 않고 프로젝트 내 원본 위치에서 직접 읽습니다.
# MODEL_KIND={kind}, loader={load_hint}

{loader}


def load_input_example():
    for name in ["input_example.json", "sample_input.json", "example.json"]:
        candidate = AI_STUDIO_DIR / name
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return {{}}


def load_aiu_custom_wrapper():
    # AI Studio 배포 경로와 동일하게 predict.py를 먼저 사용합니다.
    for relative in ["aiu_custom/predict.py", "aiu_custom/model.py", "aiu_custom/model_wrapper.py"]:
        wrapper_path = AI_STUDIO_DIR / relative
        if not wrapper_path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("aiu_custom_model_wrapper", wrapper_path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        wrapper_class = getattr(module, "ModelWrapper", None)
        if wrapper_class is not None:
            return wrapper_class()
    return None


def run_inference():
    payload = load_input_example()
    wrapper = load_aiu_custom_wrapper()
    if wrapper is not None:
        return wrapper.predict(None, payload)

    model = load_selected_model()
    if hasattr(model, "predict"):
        return model.predict(payload)
    if callable(model):
        return model(payload)
    return {{
        "status": "loaded",
        "model_kind": MODEL_KIND,
        "model_path": str(MODEL_PATH),
        "input_example": payload,
    }}


def _print_tod(local_status="완료"):
    print("\\nTOD Guide:")
    print("- 1. 모델 목록 확인 - 완료")
    print("- 2. 모델 경로로 선택 - 완료")
    print("- 3. 선택 모델 환경 변환 + requirements.txt 재정의/확인 - 완료")
    print("- 4. 모델 환경변수/패키지 상태 체크 - 다음")
    print("- 5. 원격 MLflow 등록 실행 - 완료")
    print(f"- 6. 추론 테스트 - {{local_status}}")
    print("- 7. MLflow 검증 - 다음")
    print("- 8. 오류 수정 및 재검증 - 오류 시")


def main():
    local_status = "확인 필요"
    try:
        result = run_inference()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        local_status = "완료"
    finally:
        _print_tod(local_status)


if __name__ == "__main__":
    main()
'''


def generated_model_text(project: Path, selected_model: Path, kind: str) -> str:
    details = MODEL_KIND_DETAILS.get(kind, {})
    required_package = details.get("required_package", "unknown")
    load_hint = details.get("load_hint", "custom loader required")
    loader = details.get(
        "loader",
        """def load_selected_model():\n    raise ValueError(f\"unsupported MODEL_KIND: {MODEL_KIND}\")\n""",
    )
    loader = loader.replace("MODEL_PATH", "_resolve_model_path()")
    return f'''from __future__ import annotations

import json
from pathlib import Path


def _load_mapping():
    mapping_path = Path(__file__).resolve().with_name("mapping.json")
    if not mapping_path.is_file():
        return {{}}
    return json.loads(mapping_path.read_text(encoding="utf-8"))


def _mapping_model():
    mapping = _load_mapping()
    model = mapping.get("model", {{}})
    return model if isinstance(model, dict) else {{}}


def _mapping_runtime():
    mapping = _load_mapping()
    runtime = mapping.get("runtime", {{}})
    return runtime if isinstance(runtime, dict) else {{}}


_CONTEXT_ARTIFACT_MODEL_PATH = None
_CONTEXT_ARTIFACT_CONFIG_PATH = None


def _resolve_model_path():
    if _CONTEXT_ARTIFACT_MODEL_PATH is not None:
        return _CONTEXT_ARTIFACT_MODEL_PATH
    model = _mapping_model()
    raw_path = model.get("relative_path") or model.get("source_path")
    if not raw_path:
        raise ValueError("selected_model_path_missing: aiu_custom/mapping.json")
    path = Path(str(raw_path))
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[1] / path


def _context_artifact_path(context, name):
    if context is None or not hasattr(context, "artifacts"):
        return None
    artifact_path = context.artifacts.get(name)
    if not artifact_path:
        return None
    return Path(str(artifact_path).replace("\\\\", "/"))


def _model_kind():
    return str(_mapping_model().get("kind") or "{kind}")


MODEL_KIND = _model_kind()
AIU_REQUIRED_PACKAGE = str(_mapping_model().get("required_package") or "{required_package}")
AIU_LOAD_HINT = str(_mapping_model().get("load_hint") or "{load_hint}")

# AIU Studio 변환: model.py에는 선택 모델 경로 설정을 직접 쓰지 않습니다.
# 모델 위치와 종류는 aiu_custom/mapping.json에서 읽습니다.
# MODEL_KIND={kind}, loader={load_hint}

{loader}


def _payload_to_model_input(payload):
    if isinstance(payload, dict):
        for key in ["data", "inputs", "instances", "features", "x"]:
            if key in payload:
                return payload[key]
    return payload


class ModelWrapper:
    def __init__(self):
        self.model = None
        self.artifact_model_path = None
        self.config_path = None

    def load_context(self, context=None):
        if self.model is None:
            artifact_model_path = _context_artifact_path(context, "model")
            config_path = _context_artifact_path(context, "config")
            self.artifact_model_path = artifact_model_path
            self.config_path = config_path
            if artifact_model_path is not None:
                global _CONTEXT_ARTIFACT_MODEL_PATH
                _CONTEXT_ARTIFACT_MODEL_PATH = artifact_model_path
            if config_path is not None:
                global _CONTEXT_ARTIFACT_CONFIG_PATH
                _CONTEXT_ARTIFACT_CONFIG_PATH = config_path
            self.model = load_selected_model()
        return self.model

    def predict(self, context, model_input):
        model = self.load_context(context)
        payload = _payload_to_model_input(model_input)

        if MODEL_KIND == "onnx":
            input_name = model.get_inputs()[0].name
            return model.run(None, {{input_name: payload}})

        if MODEL_KIND in {{"pytorch", "safetensors"}}:
            return _predict_torch_like(model, payload)

        if hasattr(model, "predict"):
            return model.predict(payload)

        if callable(model):
            return model(payload)

        return {{
            "status": "loaded",
            "model_kind": MODEL_KIND,
            "model_path": str(_resolve_model_path()),
            "input": payload,
        }}


def _predict_torch_like(model, payload):
    try:
        import torch

        if hasattr(model, "eval"):
            model.eval()
        tensor_input = payload if hasattr(payload, "shape") else torch.tensor(payload)
        with torch.no_grad():
            result = model(tensor_input) if callable(model) else model
        if hasattr(result, "detach"):
            result = result.detach().cpu().numpy()
        return result
    except Exception as exc:
        return {{
            "status": "loaded",
            "model_kind": MODEL_KIND,
            "model_path": str(_resolve_model_path()),
            "input": payload,
            "inference_error": str(exc),
        }}


def predict(payload):
    return ModelWrapper().predict(None, payload)
'''


def generated_predict_text(template_text: str) -> str:
    text = template_text
    if "import importlib.util" not in text:
        if "from __future__ import annotations\n\n" in text:
            text = text.replace("from __future__ import annotations\n\n", "from __future__ import annotations\n\nimport importlib.util\n", 1)
        else:
            text = "import importlib.util\n" + text

    delegate_block = '''def _model_module_path() -> Path:
    return Path(__file__).resolve().parent / "model.py"


def _load_model_module():
    model_module_path = _model_module_path()
    if not model_module_path.is_file():
        raise FileNotFoundError("aiu_custom/model.py is required for AI Studio deployment")

    spec = importlib.util.spec_from_file_location("aiu_custom_selected_model", model_module_path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load aiu_custom/model.py")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_delegate():
    module = _load_model_module()
    wrapper_class = getattr(module, "ModelWrapper", None)
    if wrapper_class is None:
        raise AttributeError("ModelWrapper missing in aiu_custom/model.py")
    return wrapper_class()


class ModelWrapper(mlflow.pyfunc.PythonModel):
    def __init__(self):
        self._delegate = None

    def load_context(self, context=None):
        if self._delegate is None:
            self._delegate = _create_delegate()
            if hasattr(self._delegate, "load_context"):
                self._delegate.load_context(context)
        return self._delegate

    def predict(self, context, model_input, params=None):
        delegate = self.load_context(context)
        return delegate.predict(context, model_input)
'''
    pattern = re.compile(r"\nclass\s+ModelWrapper\b.*?(?=\ndef\s+predict\b)", re.DOTALL)
    if pattern.search(text):
        text = pattern.sub("\n\n" + delegate_block.rstrip() + "\n", text, count=1)
    elif "def predict(payload):" in text:
        text = text.replace("\ndef predict(payload):", "\n\n" + delegate_block.rstrip() + "\n\n\ndef predict(payload):", 1)
    else:
        text = text.rstrip() + "\n\n" + delegate_block.rstrip() + "\n\n\ndef predict(payload):\n    return ModelWrapper().predict(None, payload)\n"
    text = text.replace("runtest.py", "runtest_2.py")
    return text.rstrip() + "\n"


def generated_mapping_json(project: Path, selected_model: Path, kind: str) -> str:
    selected_relative = rel(selected_model, project)
    details = MODEL_KIND_DETAILS.get(kind, {})
    mapping = {
        "model": {
            "name": selected_model.name,
            "kind": kind,
            "relative_path": selected_relative,
            "source_path": selected_relative,
            "load_hint": details.get("load_hint", "custom loader required"),
            "required_package": details.get("required_package", "unknown"),
        },
        "runtime": {
            "workspace_root": ".",
            "model_entrypoint": "aiu_custom/model.py",
            "predict_entrypoint": "aiu_custom/predict.py",
            "deployment_entrypoint": "aiu_custom/predict.py",
            "wrapper_class": "ModelWrapper",
            "local_serving_test": "local_serving/localservingtest.py",
        },
        "policy": {
            "copy_model_to_aiu_studio": False,
            "model_source": "selected_project_model_path",
            "transform_aiu_studio_templates": True,
            "secret_output": "masked",
        },
    }
    return json.dumps(mapping, ensure_ascii=False, indent=2) + "\n"


def requirements_packages_for_kind(kind: str) -> tuple[list[str], list[str], list[str]]:
    if REQUIRED_REQUIREMENTS_FILE.exists():
        required = [
            line.strip()
            for line in REQUIRED_REQUIREMENTS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    else:
        required = [
            "mlflow==3.10.0",
            "torch==2.12.1",
            "numpy==1.26.4",
            "kserve==0.15.0",
            "pandas==2.23",
        ]
    extras_by_kind = {
        "sklearn_pickle": ["scikit-learn==1.7.0", "joblib==1.5.1"],
        "sklearn_joblib": ["scikit-learn==1.7.0", "joblib==1.5.1"],
        "safetensors": ["safetensors==0.5.3"],
        "xgboost_bst": ["xgboost==3.0.2"],
        "xgboost_ubj": ["xgboost==3.0.2"],
    }
    additional = extras_by_kind.get(kind, [])
    packages = required + additional
    unique_packages: list[str] = []
    seen: set[str] = set()
    for package in packages:
        key = package.split("==", 1)[0].lower()
        if key in seen:
            continue
        seen.add(key)
        unique_packages.append(package)
    return required, additional, unique_packages


def generated_requirements_text(kind: str) -> str:
    _required, _additional, packages = requirements_packages_for_kind(kind)
    return "\n".join(packages) + "\n"


def write_runtest_2(project: Path, selected_model: Path, kind: str, reference: Path, execute: bool, force: bool) -> tuple[list[str], list[str], list[str]]:
    target = project / "runtest_2.py"
    changed: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    reference_digest_before = file_sha256(reference)
    existed_before = target.exists()
    if execute:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(generated_runtest_text(project, selected_model, kind, reference), encoding="utf-8")
        reference_digest_after = file_sha256(reference)
        if reference_digest_after != reference_digest_before:
            failures.append(f"reference_entrypoint_modified:{rel(reference, project)}")
            return changed, skipped, failures
    changed.append("runtest_2.py sequence generated + transformed (refreshed)" if existed_before else "runtest_2.py sequence generated + transformed")
    return changed, skipped, failures


def write_requirements(project: Path, kind: str, execute: bool) -> tuple[list[str], list[str], list[str]]:
    target = project / "requirements.txt"
    changed: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    existed_before = target.exists()
    if execute:
        target.write_text(generated_requirements_text(kind), encoding="utf-8")
    changed.append("requirements.txt (refreshed)" if existed_before else "requirements.txt")
    return changed, skipped, failures


def write_input_example(project: Path, selected_model: Path, kind: str, execute: bool) -> tuple[list[str], list[str], list[str]]:
    target = project / "input_example.json"
    changed: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    existed_before = target.exists()
    if execute:
        target.write_text(
            json.dumps(selected_model_input_example_data(project, selected_model, kind), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    changed.append("input_example.json (refreshed)" if existed_before else "input_example.json")
    return changed, skipped, failures


def write_localservingtest(project: Path, selected_model: Path, kind: str, reference: Path, execute: bool) -> tuple[list[str], list[str], list[str]]:
    target = project / "local_serving" / "localservingtest.py"
    changed: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    reference_digest_before = file_sha256(reference)
    existed_before = target.exists()
    if execute:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(generated_localservingtest_text(project, selected_model, kind, reference), encoding="utf-8")
        reference_digest_after = file_sha256(reference)
        if reference_digest_after != reference_digest_before:
            failures.append(f"reference_entrypoint_modified:{rel(reference, project)}")
            return changed, skipped, failures
    changed.append("local_serving/localservingtest.py (refreshed)" if existed_before else "local_serving/localservingtest.py")
    return changed, skipped, failures


def write_aiu_model(project: Path, selected_model: Path, kind: str, execute: bool) -> tuple[list[str], list[str], list[str]]:
    target = project / "aiu_custom" / "model.py"
    changed: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    existed_before = target.exists()
    if execute:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(generated_model_text(project, selected_model, kind), encoding="utf-8")
    changed.append("aiu_custom/model.py (refreshed)" if existed_before else "aiu_custom/model.py")
    return changed, skipped, failures


def write_aiu_predict(project: Path, selected_model: Path, kind: str, execute: bool) -> tuple[list[str], list[str], list[str]]:
    target = project / "aiu_custom" / "predict.py"
    changed: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    if not execute:
        skipped.append("aiu_custom/predict.py deployment entrypoint:dry_run")
        return changed, skipped, failures
    existed_before = target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        template_text = target.read_text(encoding="utf-8", errors="ignore")
    else:
        template_path = AIU_STUDIO_SAMPLE_DIR / "aiu_custom" / "predict.py"
        template_text = template_path.read_text(encoding="utf-8", errors="ignore") if template_path.is_file() else ""
    target.write_text(generated_predict_text(template_text), encoding="utf-8")
    changed.append("aiu_custom/predict.py deployment entrypoint (refreshed)" if existed_before else "aiu_custom/predict.py deployment entrypoint")
    return changed, skipped, failures


def write_aiu_mapping(project: Path, selected_model: Path, kind: str, execute: bool) -> tuple[list[str], list[str], list[str]]:
    target = project / "aiu_custom" / "mapping.json"
    changed: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    existed_before = target.exists()
    if execute:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(generated_mapping_json(project, selected_model, kind), encoding="utf-8")
    changed.append("aiu_custom/mapping.json (refreshed)" if existed_before else "aiu_custom/mapping.json")
    return changed, skipped, failures


def verify_selected_model_conversion(project: Path, selected_model: Path, kind: str, models: list[Path], execute: bool) -> tuple[list[str], list[str], list[str]]:
    if not execute:
        return [], ["selected_model_conversion_verification:dry_run"], []

    selected_relative = rel(selected_model, project)
    selected_absolute = absolute_path_text(selected_model)
    required_text_files = [
        project / "runtest_2.py",
    ]
    changed = ["runtest_2.py 선택 모델 연결부 변환 검증"]
    failures: list[str] = []

    for path in required_text_files:
        display_path = rel(path, project)
        if not path.is_file():
            failures.append(f"selected_model_conversion_missing:{display_path}")
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        if selected_relative not in text and selected_absolute not in text:
            failures.append(f"selected_model_not_reflected:{display_path}:{selected_absolute}")
        if display_path == "runtest_2.py":
            if "def load_selected_model(" not in text or "SOURCE_MODEL_PATH" not in text:
                failures.append("runtest_2_selected_model_loader_missing:runtest_2.py")
            if '"model_relative_path"' not in text and "SOURCE_MODEL_PATH =" not in text:
                failures.append("runtest_2_selected_artifact_path_missing:runtest_2.py")
            forbidden_helpers = [
                "_workspace_dir",
                "_selected_model_path",
                "_selected_model_kind",
                "_mapping_path",
            ]
            embedded = [name for name in forbidden_helpers if name in text]
            if embedded:
                failures.append(f"runtest_2_should_preserve_format_without_helpers:{','.join(embedded)}")

        for other_model in models:
            other_relative = rel(other_model, project)
            other_absolute = absolute_path_text(other_model)
            if other_relative != selected_relative and (other_relative in text or other_absolute in text):
                failures.append(f"stale_model_path_in_generated:{display_path}:{other_relative}")

    return changed, [], failures


def build_report(args: argparse.Namespace) -> PreparedModelReport:
    project = Path(args.project).expanduser().resolve()
    if not project.exists():
        raise FileNotFoundError(f"project folder not found: {project}")
    if is_filesystem_root(project):
        raise ValueError("drive/root scan is not allowed. Run from the model project folder or pass --project <current-project-folder>.")
    if is_opencode_sample_source(project):
        raise ValueError(".opencode/는 분석 대상이 아닙니다. 선택한 실제 모델 프로젝트 폴더를 --project로 지정하세요.")

    data_root = project / "data"
    models = scan_model_artifacts(project)
    data_files = scan_data_files(project)
    entrypoints = find_python_entrypoints(project)
    model_paths = [rel(path, project) for path in models]
    data_paths = [rel(path, project) for path in data_files]
    entrypoint_paths = [rel(path, project) for path in entrypoints]
    selected_model, selection_error = resolve_model_selection(project, models, args.model)
    selected_kind = model_kind(selected_model) if selected_model else None
    if args.sync_runtime:
        selected_model, selected_kind, selection_error = selected_model_from_runtest_2(project)

    report = PreparedModelReport(
        project_path=str(project),
        data_root=str(data_root),
        model_artifact_paths=model_paths,
        data_file_paths=data_paths,
        entrypoint_paths=entrypoint_paths,
        selected_model_path=rel(selected_model, project) if selected_model else None,
        model_kind=selected_kind,
        reference_entrypoint=None,
        generated_entrypoint="runtest_2.py",
        generated_inference_test="local_serving/localservingtest.py",
        execute=args.execute,
    )
    if selected_kind:
        required_requirements, additional_requirements, _packages = requirements_packages_for_kind(selected_kind)
        report.required_requirements = required_requirements
        report.additional_requirements = additional_requirements

    if not models:
        if entrypoints and data_files:
            report.failures.append("model_artifact_missing_entrypoint_with_csv")
            report.next_steps.append("CSV 파일은 모델이 아니라 데이터로 판단합니다. Python 실행파일을 모델 생성/등록 entrypoint로 사용하세요.")
            report.next_steps.append(f"감지된 CSV 데이터: {', '.join(data_paths[:5])}")
            report.next_steps.append(f"감지된 Python 실행파일: {', '.join(entrypoint_paths[:5])}")
            report.next_steps.append(f"실행 예: python .opencode/scripts/04-train-model/run_training.py --project {powershell_quote_path(project)} --entrypoint {powershell_quote_path(Path(entrypoint_paths[0]))} --execute")
        elif data_files:
            report.failures.append("csv_data_without_model_entrypoint")
            report.next_steps.append("CSV 파일은 모델이 아니라 데이터입니다. 모델을 생성/로드/등록하는 Python 실행파일을 프로젝트 루트에 넣어주세요.")
            report.next_steps.append(f"감지된 CSV 데이터: {', '.join(data_paths[:5])}")
        elif entrypoints:
            report.failures.append("entrypoint_without_model_artifact")
            report.next_steps.append("모델 artifact는 없지만 Python 실행파일이 있습니다. 해당 파일이 모델 생성/등록 entrypoint인지 확인해 실행하세요.")
            report.next_steps.append(f"실행 예: python .opencode/scripts/04-train-model/run_training.py --project {powershell_quote_path(project)} --entrypoint {powershell_quote_path(Path(entrypoint_paths[0]))} --execute")
        else:
            report.failures.append("model_artifact_paths_empty")
            report.next_steps.append("현재 프로젝트 루트 바로 아래 또는 data/** 아래에 .pkl, .joblib, .pt, .pth, .onnx, .keras, .h5, .safetensors, .bst, .ubj 모델 파일을 넣어주세요.")
    if selection_error and (models or args.model):
        report.failures.append(selection_error)
        if models:
            report.next_steps.append("사용할 모델을 번호 또는 경로로 선택하세요. 예: --model 1, --model model.joblib, --model data/torch/model.pt")
            report.next_steps.append(
                "모델 선택 후 자동 준비 실행: python .opencode/scripts/04-train-model/prepare_selected_model.py --project <model-project-folder> --model <번호|경로> --execute"
            )
    if selected_model and not ensure_under_project(project, selected_model):
        report.failures.append("selected_model_outside_project")
        report.next_steps.append("선택 모델은 <model-project-folder> 아래에 있어야 합니다.")
    if selected_model and selected_kind is None:
        report.failures.append("unsupported_model_suffix")

    if report.failures:
        return report
    current_selected = current_selected_model_path(project)
    if (
        args.model
        and normalize_path_text(args.model.strip()).isdigit()
        and current_selected is not None
        and selected_model is not None
        and current_selected.resolve() == selected_model.resolve()
    ):
        report.warnings.append(f"numeric_model_selection_locked_to_current:{args.model}->{rel(selected_model, project)}")
        report.next_steps.append(f"현재 선택 모델이 고정되어 목록 순서 대신 기존 선택 경로를 유지합니다: {rel(selected_model, project)}")
    if (
        args.model
        and normalize_path_text(args.model.strip()).isdigit()
        and selected_model
        and not (
            current_selected is not None
            and current_selected.resolve() == selected_model.resolve()
        )
    ):
        stable_path = rel(selected_model, project)
        report.warnings.append(f"numeric_model_selection_is_order_dependent:{args.model}->{stable_path}")
        report.next_steps.append(f"다음 실행부터는 목록 순서가 바뀌어도 안전하게 실제 경로를 사용하세요: --model {stable_path}")
        report.next_steps.append("이미 준비된 선택 모델을 다시 쓰려면: --model selected")

    if args.sync_runtime:
        runtime_reference = project / "runtest_2.py"
        report.reference_entrypoint = "runtest_2.py"
        if not runtime_reference.is_file():
            report.failures.append("runtest_2_missing")
            report.next_steps.append("먼저 모델 선택으로 runtest_2.py를 생성하세요.")
            return report

        runtime_dirs_changed, runtime_dirs_skipped, runtime_dirs_failures = ensure_runtime_directories(project, args.execute)
        report.prepared_paths.extend(runtime_dirs_changed)
        report.skipped.extend(runtime_dirs_skipped)
        report.failures.extend(runtime_dirs_failures)

        requirements_changed, requirements_skipped, requirements_failures = write_requirements(project, selected_kind, args.execute)
        report.prepared_paths.extend(requirements_changed)
        report.skipped.extend(requirements_skipped)
        report.failures.extend(requirements_failures)

        input_changed, input_skipped, input_failures = write_input_example(project, selected_model, selected_kind, args.execute)
        report.prepared_paths.extend(input_changed)
        report.skipped.extend(input_skipped)
        report.failures.extend(input_failures)

        inference_changed, inference_skipped, inference_failures = write_localservingtest(project, selected_model, selected_kind, runtime_reference, args.execute)
        report.prepared_paths.extend(inference_changed)
        report.skipped.extend(inference_skipped)
        report.failures.extend(inference_failures)

        model_changed, model_skipped, model_failures = write_aiu_model(project, selected_model, selected_kind, args.execute)
        report.prepared_paths.extend(model_changed)
        report.skipped.extend(model_skipped)
        report.failures.extend(model_failures)

        predict_changed, predict_skipped, predict_failures = write_aiu_predict(project, selected_model, selected_kind, args.execute)
        report.prepared_paths.extend(predict_changed)
        report.skipped.extend(predict_skipped)
        report.failures.extend(predict_failures)

        mapping_changed, mapping_skipped, mapping_failures = write_aiu_mapping(project, selected_model, selected_kind, args.execute)
        report.prepared_paths.extend(mapping_changed)
        report.skipped.extend(mapping_skipped)
        report.failures.extend(mapping_failures)

        if args.execute and not report.failures:
            report.next_steps.extend(
                [
                    "후속 변환 완료: 복사된 템플릿 폴더 내부에서 선택 모델 실행/등록에 필요한 연결부를 선택 모델에 맞게 변환했습니다.",
                    "선택 모델 변환 완료: aiu_studio/ 템플릿 복사 -> 선택 모델 경로 및 형식 확인 -> 복사된 템플릿을 선택 모델 형식에 맞게 변환",
                    "다음은 4번 모델 환경변수/패키지 상태 체크입니다.",
                    powershell_python_script(
                        CHECK_ENVIRONMENT_SCRIPT,
                        "--project",
                        powershell_quote_path(project),
                        "--entrypoint",
                        "runtest_2.py",
                    ),
                ]
            )
        elif not report.failures:
            report.next_steps.append("검토 후 --execute를 붙여 runtest_2.py 기준 런타임 폴더/파일을 변환하세요.")
        return report

    reference = find_reference_entrypoint(project, selected_kind)
    report.reference_entrypoint = rel(reference, project) if reference else None
    if reference is None:
        report.failures.append("reference_entrypoint_missing:runtest.py_or_run_test.py")
        report.next_steps.append("워크스페이스 루트에 기존 runtest.py 또는 run_test.py를 넣어주세요.")
        return report

    changed, write_skipped, write_failures = write_runtest_2(project, selected_model, selected_kind, reference, args.execute, args.force)
    report.prepared_paths.extend(changed)
    report.skipped.extend(write_skipped)
    report.failures.extend(write_failures)
    if report.failures:
        return report

    verify_changed, verify_skipped, verify_failures = verify_selected_model_conversion(project, selected_model, selected_kind, models, args.execute)
    report.prepared_paths.extend(verify_changed)
    report.skipped.extend(verify_skipped)
    report.failures.extend(verify_failures)

    if args.execute and not report.failures:
        report.next_steps.extend(
            [
                "자동 준비 완료: 모델 선택 기준 runtest_2.py 변환",
                "선택 모델 변환 완료: aiu_studio/ 템플릿 복사 -> 선택 모델 경로 및 형식 확인 -> 복사된 템플릿을 선택 모델 형식에 맞게 변환",
                "추가 실행: runtest_2.py 기준 런타임 변환",
                powershell_python_script(
                    PREPARE_SELECTED_MODEL_SCRIPT,
                    "--project",
                    powershell_quote_path(project),
                    "--sync-runtime",
                    "--execute",
                ),
                powershell_python_script(
                    CHECK_ENVIRONMENT_SCRIPT,
                    "--project",
                    powershell_quote_path(project),
                    "--entrypoint",
                    "runtest_2.py",
                ),
                "환경 체크 완료 후 5번 원격 MLflow 등록 실행을 진행하세요.",
                "PowerShell에서는 선택 프로젝트 루트로 이동한 뒤 실행하세요.",
                f"cd {powershell_quote_path(project)}",
                "python runtest_2.py",
                "6번 추론 테스트는 5번 원격 MLflow 등록 실행이 성공한 뒤에만 진행합니다.",
                powershell_python_script(
                    VERIFY_MLFLOW_SCRIPT,
                    "--project",
                    powershell_quote_path(project),
                    "--tracking-uri",
                    "<tracking-uri>",
                    "--experiment-name",
                    "<experiment-name>",
                ),
            ]
        )
    elif not report.failures:
        report.next_steps.append("검토 후 --execute를 붙여 기존 runtest.py를 참조한 runtest_2.py만 생성하세요.")
    return report


def print_report(report: PreparedModelReport) -> None:
    print(f"Project: {report.project_path}")
    print(f"Data root: {report.data_root}")
    if report.model_artifact_paths and report.selected_model_path is None:
        data_model_count = sum(1 for path in report.model_artifact_paths if path == "data" or path.startswith("data/"))
        total_model_count = len(report.model_artifact_paths)
        if data_model_count == total_model_count:
            print(f"data 폴더에 {total_model_count}개 모델이 있습니다. 선택해주세요.")
        elif data_model_count:
            print(f"프로젝트에 {total_model_count}개 모델이 있습니다. data 폴더 {data_model_count}개 포함, 선택해주세요.")
        else:
            print(f"현재 프로젝트 루트 바로 아래에 {total_model_count}개 모델이 있습니다. 선택해주세요.")
    print("model_artifact_paths:")
    if report.model_artifact_paths:
        for index, path in enumerate(report.model_artifact_paths, start=1):
            print(f"{index}. {path}")
    else:
        print("- none")
    print("data_file_paths:")
    if report.data_file_paths:
        for index, path in enumerate(report.data_file_paths, start=1):
            print(f"{index}. {path}")
    else:
        print("- none")
    print("entrypoint_paths:")
    if report.entrypoint_paths:
        for index, path in enumerate(report.entrypoint_paths, start=1):
            print(f"{index}. {path}")
    else:
        print("- none")
    print(f"Selected model: {report.selected_model_path or 'missing'}")
    print(f"MODEL_KIND: {report.model_kind or 'missing'}")
    print(f"Reference entrypoint: {report.reference_entrypoint or 'missing'}")
    print(f"Transformed entrypoint: {report.generated_entrypoint}")
    print(f"Execute: {report.execute}")
    if report.required_requirements or report.additional_requirements:
        print("requirements.txt update:")
        if report.required_requirements:
            print("- required:")
            for item in report.required_requirements:
                print(f"  - {item}")
        if report.additional_requirements:
            print("- added for selected model:")
            for item in report.additional_requirements:
                print(f"  - {item}")
        else:
            print("- added for selected model: none")
    if report.prepared_paths:
        print("Prepared:")
        for item in report.prepared_paths:
            print(f"- {item}")
    if report.skipped:
        print("Skipped:")
        for item in report.skipped:
            print(f"- {item}")
    if report.warnings:
        print("Warnings:")
        for warning in report.warnings:
            print(f"- {warning}")
    if report.failures:
        print("Failures:")
        for failure in report.failures:
            print(f"- {failure}")
    print("TODO Guide:")
    model_selected = bool(report.selected_model_path)
    auto_ready = all(
        path in report.prepared_paths
        or f"{path} (refreshed)" in report.prepared_paths
        or any(item.startswith(f"{path} ") for item in report.prepared_paths)
        or (Path(report.project_path) / path).is_file()
        for path in [
            "runtest_2.py",
        ]
    )
    runtime_ready = all(
        (Path(report.project_path) / path).exists()
        for path in [
            "aiu_custom/model.py",
            "aiu_custom/predict.py",
            "aiu_custom/mapping.json",
            "local_serving/localservingtest.py",
            "input_example.json",
            "requirements.txt",
        ]
    )
    if report.model_artifact_paths:
        print("1. 모델 목록 확인 - 완료")
    elif report.entrypoint_paths:
        print("1. 모델 목록 확인 - 실행파일 있음")
    elif report.data_file_paths:
        print("1. 모델 목록 확인 - 데이터만 있음")
    else:
        print("1. 모델 목록 확인 - 모델 없음")
    print("2. 모델 경로로 선택 - 완료" if model_selected else "2. 모델 경로로 선택 - 대기")
    if auto_ready and runtime_ready:
        print("3. 선택 모델 변환 시퀀스 - 완료(runtest_2.py + 런타임 변환)")
    elif auto_ready:
        print("3. 선택 모델 변환 시퀀스 - 진행중(runtest_2.py 완료, 런타임 변환 대기)")
    else:
        print("3. 선택 모델 변환 시퀀스 - 대기")
    if runtime_ready:
        print("4. 모델 환경변수·패키지 상태 체크 - 다음")
    else:
        print("4. 모델 환경변수·패키지 상태 체크 - 3번 선택 모델 변환 시퀀스 완료 후 진행")
    print("5. 원격 MLflow 등록 실행 - 다음")
    print("6. 추론 테스트 - 대기(5번 완료 후)")
    print("7. MLflow 검증 - 대기(6번 완료 후)")
    print("8. 오류 수정 및 재검증 - 오류 시")
    if report.next_steps:
        print("Next steps:")
        for step in report.next_steps:
            print(f"- {step}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Select a current project-root or data/** model artifact and generate workspace-root runtest_2.py without modifying runtest.py.")
    parser.add_argument("--project", default=".", help="model project folder")
    parser.add_argument("--model", help="model index from model_artifact_paths or a project-relative path")
    parser.add_argument("--execute", action="store_true", help="write the selected-model runtest_2.py or sync runtime files when --sync-runtime is used")
    parser.add_argument("--force", action="store_true", help="kept for compatibility; runtest_2.py is refreshed for the selected model")
    parser.add_argument("--sync-runtime", action="store_true", help="read selected model from runtest_2.py and transform runtime folders/files for that model")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    report = build_report(args)
    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print_report(report)
    return 1 if report.failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(130)
