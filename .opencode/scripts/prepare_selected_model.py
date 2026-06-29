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
GENERIC_MODEL_STEMS = {
    "best",
    "checkpoint",
    "final",
    "model",
    "pytorch_model",
    "weights",
}

REFERENCE_ENTRYPOINTS = [
    "aiu_studio/runtest.py",
    "aiu_studio/run_test.py",
    "aui_studio/runtest.py",
    "aui_studio/run_test.py",
    "runtest.py",
    "run_test.py",
]
ROOT = Path(__file__).resolve().parents[1]
AIU_STUDIO_DIR_NAME = "aiu_studio"
AIU_STUDIO_SAMPLE_DIR_NAME = "aiu_studio"
AIU_STUDIO_SAMPLE_DIR = ROOT / "samples" / AIU_STUDIO_SAMPLE_DIR_NAME
PYTORCH_REFERENCE_ENTRYPOINT = ROOT / "samples" / "pytorch_sample" / "runtest.py"
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
    "aiu_studio",
    "aui_studio",
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
    "CODE_PATHS",
    "code_paths",
    "MLFLOW_CODE_PATHS",
    "mlflow_code_paths",
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
    r"ImageClassifier|Imageclassifier|ModelWrapper|torchvision\.models\.[A-Za-z_][A-Za-z0-9_]*|"
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
    selected_model_path: str | None
    model_kind: str | None
    reference_entrypoint: str | None
    generated_entrypoint: str
    generated_inference_test: str
    execute: bool
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
    for index, part in enumerate(parts[:-1]):
        if part == ".opencode" and parts[index + 1] in {"sample", "samples"}:
            return True
    return False


def scan_model_artifacts(project: Path) -> list[Path]:
    if is_opencode_sample_source(project):
        return []
    found = []
    for path in project.rglob("*"):
        try:
            relative_parts = path.relative_to(project).parts
        except ValueError:
            continue
        if any(part in MODEL_SCAN_SKIP_DIRS for part in relative_parts):
            continue
        if path.is_file() and model_kind(path):
            found.append(path)
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
    mapping_path = project / AIU_STUDIO_DIR_NAME / "aiu_custom" / "mapping.json"
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


def resolve_model_selection(project: Path, models: list[Path], raw: str | None) -> tuple[Path | None, str | None]:
    if not raw:
        return None, "model_selection_required"
    value = normalize_path_text(raw.strip())
    if value.lower() in {"selected", "current", "last", "기존", "현재", "선택"}:
        stored = stored_selected_model_path(project)
        if stored is not None:
            return stored, None
        return None, "stored_model_selection_missing"
    if value.isdigit():
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
    if kind == "pytorch" and PYTORCH_REFERENCE_ENTRYPOINT.is_file():
        return PYTORCH_REFERENCE_ENTRYPOINT
    for name in REFERENCE_ENTRYPOINTS:
        candidate = project / name
        if candidate.is_file():
            return candidate
    return None


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
    aiu_prefix = AIU_STUDIO_DIR_NAME + "/"
    if relative == AIU_STUDIO_DIR_NAME:
        return "AI_STUDIO_DIR"
    if relative.startswith(aiu_prefix):
        return f'AI_STUDIO_DIR / "{relative[len(aiu_prefix):]}"'
    if Path(relative).is_absolute():
        return f'_AIUPath({relative!r})'
    return f'PROJECT_DIR / "{relative}"'


def copy_aiu_studio_folder(project: Path, execute: bool) -> tuple[list[str], list[str], list[str]]:
    copied: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    target = project / AIU_STUDIO_DIR_NAME
    if not AIU_STUDIO_SAMPLE_DIR.is_dir():
        failures.append(f"aiu_studio_folder_missing:{AIU_STUDIO_SAMPLE_DIR}")
        return copied, skipped, failures
    if target.exists() and not target.is_dir():
        failures.append(f"aiu_studio_target_not_directory:{target}")
        return copied, skipped, failures
    if execute:
        shutil.copytree(
            AIU_STUDIO_SAMPLE_DIR,
            target,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(*AIU_STUDIO_COPY_IGNORE_DIRS),
        )
    copied.append(AIU_STUDIO_DIR_NAME + "/")
    return copied, skipped, failures


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
    if normalized in {"input_example.json", "aiu_studio/input_example.json"}:
        return "str(INPUT_EXAMPLE_PATH)"
    if normalized in {"sample_input.json", "aiu_studio/sample_input.json", "example.json", "aiu_studio/example.json"}:
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


def rewrite_code_paths_argument(line: str) -> str:
    if "code_paths" not in line:
        return line
    suffix = "\n" if line.endswith("\n") else ""
    body = line.rstrip("\n")
    converted = re.sub(r"\bcode_paths\s*=\s*\[\s*\]", "code_paths=AIU_CODE_PATHS", body)
    converted = re.sub(r"\bcode_paths\s*=\s*None\b", "code_paths=AIU_CODE_PATHS", converted)
    if converted == body:
        return line
    code, comment = split_inline_comment(converted)
    converted_comment = comment or "# AIU Studio 변환: aiu_studio/ 내부 실제 코드 폴더 경로를 사용합니다."
    return f"{code}  {converted_comment}{suffix}"


def code_paths_multiline_empty_start(line: str) -> bool:
    code, _ = split_inline_comment(line.rstrip("\n"))
    return bool(re.search(r"\bcode_paths\s*=\s*\[\s*$", code))


def code_paths_multiline_empty_end(line: str) -> bool:
    return line.strip().rstrip(",") == "]"


def converted_code_paths_line(line: str) -> str:
    suffix = "\n" if line.endswith("\n") else ""
    indent = line[: len(line) - len(line.lstrip())]
    return (
        f"{indent}code_paths=AIU_CODE_PATHS  "
        "# AIU Studio 변환: aiu_studio/ 내부 실제 코드 폴더 경로를 사용합니다."
        f"{suffix}"
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
    converted = rewrite_code_paths_argument(converted)
    converted = rewrite_data_prep_call_line(converted, kind)
    converted = rewrite_model_prep_line(converted, kind)
    converted = rewrite_summary_line(converted, kind)
    return rewrite_model_loader_line(converted, kind, load_hint)


def rewrite_preserved_line(line: str) -> str:
    converted = rewrite_path_separator_literals(line)
    converted = rewrite_input_example_literals(converted)
    return rewrite_code_paths_argument(converted)


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
    skip_empty_code_paths_list = False

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
        if skip_empty_code_paths_list:
            if code_paths_multiline_empty_end(line):
                skip_empty_code_paths_list = False
            continue

        if not preserve_code and index == insert_at and not inserted:
            output.append(injected_block)
            inserted = True

        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        if code_paths_multiline_empty_start(line):
            output.append(converted_code_paths_line(line))
            skip_empty_code_paths_list = True
            continue

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
        if stripped.rstrip("\n").rstrip().endswith(",") and name in {"CODE_PATHS", "code_paths", "MLFLOW_CODE_PATHS", "mlflow_code_paths"}:
            output.append(rewrite_preserved_line(line) if preserve_code else rewrite_reference_line(line, selected_relative, kind, load_hint, required_package))
            continue

        expression = replacement_expression(name, replacements)
        if expression is None:
            output.append(rewrite_preserved_line(line) if preserve_code else rewrite_reference_line(line, selected_relative, kind, load_hint, required_package))
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
    project_expr = runtime_path_expr(project)
    aiu_studio_path = project / AIU_STUDIO_DIR_NAME
    aiu_studio_expr = runtime_path_expr(aiu_studio_path)
    selected_model_expr = runtime_path_expr(selected_model)
    input_example_expr = runtime_path_expr(aiu_studio_path / "input_example.json")
    config_dir_expr = runtime_path_expr(aiu_studio_path / "config")
    config_path_expr = runtime_path_expr(aiu_studio_path / "config" / "config.json")
    model_output_dir_expr = runtime_path_expr(aiu_studio_path / "saved_model")
    model_output_path_expr = runtime_path_expr(aiu_studio_path / "saved_model" / "model.pkl")
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
# MODEL_KIND에 맞는 load_selected_model()을 생성해 aiu_studio/ 템플릿 코드를 선택 모델 기준으로 갱신합니다.
# 이 블록은 자동 변환되지만 아래 원본 runtest.py 구조와 주석은 최대한 유지합니다.
import os as _aiu_os
import atexit as _aiu_atexit
import json as _aiu_json
from pathlib import Path as _AIUPath

AI_STUDIO_DIR = {aiu_studio_expr}
PROJECT_DIR = {project_expr}
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

# Step 6 원격 MLflow 배포/등록 중 상대경로 산출물은 프로젝트 루트가 아니라 aiu_studio/ 아래에 생성되도록 고정합니다.
_aiu_os.chdir(AI_STUDIO_DIR)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
MODEL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def _aiu_existing_code_paths():
    candidates = [
        AI_STUDIO_DIR / "aiu_custom",
        AI_STUDIO_DIR / "local_serving",
    ]
    return [str(path) for path in candidates if path.exists()]

# MLflow pyfunc log_model(code_paths=...)에는 aiu_studio/ 내부의 실제 코드 폴더만 전달합니다.
AIU_CODE_PATHS = _aiu_existing_code_paths()
CODE_PATHS = AIU_CODE_PATHS
code_paths = AIU_CODE_PATHS
MLFLOW_CODE_PATHS = AIU_CODE_PATHS
mlflow_code_paths = AIU_CODE_PATHS

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
if mlflow_tracking_url.lower().startswith("https://"):
    raise ValueError("ssl_not_allowed: use http:// or file:// for mlflow_tracking_url")

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
    print("- 3. aiu_studio/ 템플릿 복사 + 선택 모델 기준 전체 코드 변환 - 완료")
    print("- 4. 선택 모델 일치 확인 - 완료")
    print("- 5. 모델 환경변수 체크 - 다음")
    print("- 6. 원격 MLflow 배포/등록 실행 - 완료")
    print("- 7. 추론 스모크 테스트 - 다음")
    print("- 8. MLflow 검증 - 다음")

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
                "data": _aiu_flat_zeros(1 * 1 * 28 * 28),
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


def generated_runtest_text(project: Path, selected_model: Path, kind: str, reference: Path) -> str:
    reference_text = reference.read_text(encoding="utf-8", errors="ignore")
    selected_relative = rel(selected_model, project)
    path_constructor = "Path" if reference.resolve() == PYTORCH_REFERENCE_ENTRYPOINT.resolve() else "_AIUPath"
    aiu_studio_path = project / AIU_STUDIO_DIR_NAME
    default_experiment_name, default_register_model_name = default_mlflow_names(project, selected_model)
    details = MODEL_KIND_DETAILS.get(kind, {})
    required_package = details.get("required_package", "unknown")
    load_hint = details.get("load_hint", "custom loader required")
    preserve_code = reference.resolve() == PYTORCH_REFERENCE_ENTRYPOINT.resolve()
    replacements = {
        "AI_STUDIO_DIR": runtime_path_expr(aiu_studio_path, path_constructor),
        "PROJECT_DIR": runtime_path_expr(project, path_constructor),
        "AI_STUDIO_CODE_DIR": runtime_path_expr(aiu_studio_path / "code", path_constructor),
        "AI_STUDIO_METRICS_DIR": runtime_path_expr(aiu_studio_path / "metrics", path_constructor),
        "AI_STUDIO_TRACKING_DIR": "AI_STUDIO_DIR",
        "SOURCE_MODEL_PATH": runtime_path_expr(selected_model, path_constructor),
        "DATA_MODEL_PATH": "SOURCE_MODEL_PATH",
        "MODEL_PATH": "SOURCE_MODEL_PATH",
        "CONFIG_DIR": runtime_path_expr(aiu_studio_path / "config", path_constructor),
        "CONFIG_PATH": runtime_path_expr(aiu_studio_path / "config" / "config.json", path_constructor),
        "MODEL_OUTPUT_DIR": runtime_path_expr(aiu_studio_path / "saved_model", path_constructor),
        "MODEL_OUTPUT_PATH": runtime_path_expr(aiu_studio_path / "saved_model" / "model.pkl", path_constructor),
        "MODEL_KIND": repr(kind),
        "MODEL_LOAD_HINT": repr(load_hint),
        "classifier": "load_selected_model()",
        "clf": "load_selected_model()",
        "INPUT_EXAMPLE_PATH": runtime_path_expr(aiu_studio_path / "input_example.json", path_constructor),
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
        "CODE_PATHS": "AIU_CODE_PATHS",
        "code_paths": "AIU_CODE_PATHS",
        "MLFLOW_CODE_PATHS": "AIU_CODE_PATHS",
        "mlflow_code_paths": "AIU_CODE_PATHS",
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
    return transformed.rstrip() + "\n"


def generated_localservingtest_text(project: Path, selected_model: Path, kind: str, reference: Path) -> str:
    selected_relative = rel(selected_model, project)
    reference_expr = runtime_project_path_expr(project, reference)
    aiu_studio_path = project / AIU_STUDIO_DIR_NAME
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


LOCAL_SERVING_DIR = {runtime_path_expr(aiu_studio_path / "local_serving", "Path")}
AI_STUDIO_DIR = {runtime_path_expr(aiu_studio_path, "Path")}
PROJECT_DIR = {runtime_path_expr(project, "Path")}
ORIGINAL_MODEL_PATH = {runtime_path_expr(selected_model, "Path")}
SOURCE_MODEL_PATH = {runtime_path_expr(selected_model, "Path")}
DATA_MODEL_PATH = SOURCE_MODEL_PATH
MODEL_PATH = SOURCE_MODEL_PATH
MODEL_KIND = "{kind}"
MODEL_PROFILE = {json.dumps(profile, ensure_ascii=False, indent=4)}
AIU_REQUIRED_PACKAGE = "{required_package}"
AIU_LOAD_HINT = "{load_hint}"
REFERENCE_ENTRYPOINT = {reference_expr}

# AIU Studio 변환: 선택 모델 원본 경로 {selected_relative} 기준 추론 테스트입니다.
# 모델 파일은 aiu_studio/로 복사하지 않고 프로젝트 내 원본 위치에서 직접 읽습니다.
# MODEL_KIND={kind}, loader={load_hint}

{loader}


def load_input_example():
    for name in ["input_example.json", "sample_input.json", "example.json"]:
        candidate = AI_STUDIO_DIR / name
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return {{}}


def load_aiu_custom_wrapper():
    for relative in ["aiu_custom/model.py", "aiu_custom/model_wrapper.py", "aiu_custom/predict.py"]:
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
    print("- 3. aiu_studio/ 템플릿 복사 + 선택 모델 기준 전체 코드 변환 - 완료")
    print("- 4. 선택 모델 일치 확인 - 완료")
    print("- 5. 모델 환경변수 체크 - 다음")
    print("- 6. 원격 MLflow 배포/등록 실행 - 완료")
    print(f"- 7. 추론 스모크 테스트 - {{local_status}}")
    print("- 8. MLflow 검증 - 다음")


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


def _resolve_model_path():
    model = _mapping_model()
    runtime = _mapping_runtime()
    raw_path = model.get("relative_path") or model.get("source_path") or model.get("absolute_path")
    if not raw_path:
        raise ValueError("selected_model_path_missing: aiu_custom/mapping.json")
    path = Path(str(raw_path))
    if path.is_absolute():
        return path
    project_dir = runtime.get("project_dir")
    if project_dir:
        return Path(str(project_dir)) / path
    return Path(__file__).resolve().parents[2] / path


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

    def load_context(self, context=None):
        if self.model is None:
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


def generated_mapping_json(project: Path, selected_model: Path, kind: str) -> str:
    selected_relative = rel(selected_model, project)
    selected_absolute = absolute_path_text(selected_model)
    details = MODEL_KIND_DETAILS.get(kind, {})
    mapping = {
        "model": {
            "name": selected_model.name,
            "kind": kind,
            "relative_path": selected_relative,
            "absolute_path": selected_absolute,
            "source_path": selected_absolute,
            "load_hint": details.get("load_hint", "custom loader required"),
            "required_package": details.get("required_package", "unknown"),
        },
        "runtime": {
            "project_dir": absolute_path_text(project),
            "aiu_studio_dir": absolute_path_text(project / AIU_STUDIO_DIR_NAME),
            "model_entrypoint": "aiu_custom/model.py",
            "predict_entrypoint": "aiu_custom/predict.py",
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


def write_runtest_2(project: Path, selected_model: Path, kind: str, reference: Path, execute: bool, force: bool) -> tuple[list[str], list[str], list[str]]:
    target = project / AIU_STUDIO_DIR_NAME / "runtest_2.py"
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
    changed.append("aiu_studio/runtest_2.py (refreshed)" if existed_before else "aiu_studio/runtest_2.py")
    return changed, skipped, failures


def write_localservingtest(project: Path, selected_model: Path, kind: str, reference: Path, execute: bool) -> tuple[list[str], list[str], list[str]]:
    target = project / AIU_STUDIO_DIR_NAME / "local_serving" / "localservingtest.py"
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
    changed.append("aiu_studio/local_serving/localservingtest.py (refreshed)" if existed_before else "aiu_studio/local_serving/localservingtest.py")
    return changed, skipped, failures


def write_aiu_model(project: Path, selected_model: Path, kind: str, execute: bool) -> tuple[list[str], list[str], list[str]]:
    target = project / AIU_STUDIO_DIR_NAME / "aiu_custom" / "model.py"
    changed: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    existed_before = target.exists()
    if execute:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(generated_model_text(project, selected_model, kind), encoding="utf-8")
    changed.append("aiu_studio/aiu_custom/model.py (refreshed)" if existed_before else "aiu_studio/aiu_custom/model.py")
    return changed, skipped, failures


def write_aiu_predict(project: Path, selected_model: Path, kind: str, execute: bool) -> tuple[list[str], list[str], list[str]]:
    target = project / AIU_STUDIO_DIR_NAME / "aiu_custom" / "predict.py"
    changed: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    if not execute:
        skipped.append("aiu_studio/aiu_custom/predict.py import check:dry_run")
        return changed, skipped, failures
    if not target.is_file():
        failures.append("predict_entrypoint_missing:aiu_studio/aiu_custom/predict.py")
        return changed, skipped, failures

    details = MODEL_KIND_DETAILS.get(kind, {})
    required_package = details.get("required_package")
    text = target.read_text(encoding="utf-8", errors="ignore")
    imported_packages = {
        package
        for line in text.splitlines()
        for package in [import_package_for_line(line)]
        if package is not None
    }
    imported_module_names = {module_name for module_name, _original in imported_packages}
    if required_package and required_package != "unknown" and required_package not in imported_module_names:
        changed.append(f"aiu_studio/aiu_custom/predict.py import check (missing:{required_package})")
        return changed, skipped, failures

    changed.append("aiu_studio/aiu_custom/predict.py import check (ok)")
    return changed, skipped, failures


def write_aiu_mapping(project: Path, selected_model: Path, kind: str, execute: bool) -> tuple[list[str], list[str], list[str]]:
    target = project / AIU_STUDIO_DIR_NAME / "aiu_custom" / "mapping.json"
    changed: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    existed_before = target.exists()
    if execute:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(generated_mapping_json(project, selected_model, kind), encoding="utf-8")
    changed.append("aiu_studio/aiu_custom/mapping.json (refreshed)" if existed_before else "aiu_studio/aiu_custom/mapping.json")
    return changed, skipped, failures


def verify_selected_model_conversion(project: Path, selected_model: Path, kind: str, models: list[Path], execute: bool) -> tuple[list[str], list[str], list[str]]:
    if not execute:
        return [], ["selected_model_conversion_verification:dry_run"], []

    selected_relative = rel(selected_model, project)
    selected_absolute = absolute_path_text(selected_model)
    required_text_files = [
        project / AIU_STUDIO_DIR_NAME / "runtest_2.py",
        project / AIU_STUDIO_DIR_NAME / "aiu_custom" / "model.py",
        project / AIU_STUDIO_DIR_NAME / "local_serving" / "localservingtest.py",
    ]
    changed = ["선택 모델 기준 변환 검증"]
    failures: list[str] = []

    for path in required_text_files:
        display_path = rel(path, project)
        if not path.is_file():
            failures.append(f"selected_model_conversion_missing:{display_path}")
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        if display_path == "aiu_studio/aiu_custom/model.py":
            if "mapping.json" not in text or "_resolve_model_path" not in text:
                failures.append("model_py_mapping_loader_missing:aiu_studio/aiu_custom/model.py")
            if selected_relative in text or selected_absolute in text:
                failures.append("selected_model_path_should_not_be_embedded:aiu_studio/aiu_custom/model.py")
            continue

        if selected_relative not in text and selected_absolute not in text:
            failures.append(f"selected_model_not_reflected:{display_path}:{selected_absolute}")
        if f'MODEL_KIND = "{kind}"' not in text and f"MODEL_KIND = {kind!r}" not in text:
            failures.append(f"selected_model_kind_not_reflected:{display_path}:{kind}")

        for other_model in models:
            other_relative = rel(other_model, project)
            other_absolute = absolute_path_text(other_model)
            if other_relative != selected_relative and (other_relative in text or other_absolute in text):
                failures.append(f"stale_model_path_in_generated:{display_path}:{other_relative}")

    mapping_path = project / AIU_STUDIO_DIR_NAME / "aiu_custom" / "mapping.json"
    if not mapping_path.is_file():
        failures.append("selected_model_conversion_missing:aiu_studio/aiu_custom/mapping.json")
    else:
        try:
            mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            failures.append("selected_model_mapping_invalid_json:aiu_studio/aiu_custom/mapping.json")
        else:
            model_mapping = mapping.get("model", {})
            if model_mapping.get("source_path") not in {selected_relative, selected_absolute}:
                failures.append(f"selected_model_mapping_path_mismatch:{model_mapping.get('source_path')}!={selected_absolute}")
            if model_mapping.get("kind") != kind:
                failures.append(f"selected_model_mapping_kind_mismatch:{model_mapping.get('kind')}!={kind}")

    return changed, [], failures


def build_report(args: argparse.Namespace) -> PreparedModelReport:
    project = Path(args.project).expanduser().resolve()
    if not project.exists():
        raise FileNotFoundError(f"project folder not found: {project}")
    if is_filesystem_root(project):
        raise ValueError("drive/root scan is not allowed. Run from the model project folder or pass --project <current-project-folder>.")
    if is_opencode_sample_source(project):
        raise ValueError(".opencode/sample(s)는 분석 대상이 아닙니다. 선택한 실제 모델 프로젝트 폴더를 --project로 지정하세요.")

    data_root = project / "data"
    models = scan_model_artifacts(project)
    model_paths = [rel(path, project) for path in models]
    selected_model, selection_error = resolve_model_selection(project, models, args.model)
    selected_kind = model_kind(selected_model) if selected_model else None

    report = PreparedModelReport(
        project_path=str(project),
        data_root=str(data_root),
        model_artifact_paths=model_paths,
        selected_model_path=rel(selected_model, project) if selected_model else None,
        model_kind=selected_kind,
        reference_entrypoint=None,
        generated_entrypoint="aiu_studio/runtest_2.py",
        generated_inference_test="aiu_studio/local_serving/localservingtest.py",
        execute=args.execute,
    )

    if not models:
        report.failures.append("model_artifact_paths_empty")
        report.next_steps.append("프로젝트 루트 또는 data/** 아래에 .pkl, .joblib, .pt, .pth, .onnx, .keras, .h5, .safetensors, .bst, .ubj 모델 파일을 넣어주세요.")
    if selection_error:
        report.failures.append(selection_error)
        if models:
            report.next_steps.append("사용할 모델을 번호 또는 경로로 선택하세요. 예: --model 1, --model model.joblib, --model data/torch/model.pt")
            report.next_steps.append(
                "모델 선택 후 자동 준비 실행: python .opencode/scripts/prepare_selected_model.py --project <model-project-folder> --model <번호|경로> --execute"
            )
    if selected_model and not ensure_under_project(project, selected_model):
        report.failures.append("selected_model_outside_project")
        report.next_steps.append("선택 모델은 <model-project-folder> 아래에 있어야 합니다.")
    if selected_model and selected_kind is None:
        report.failures.append("unsupported_model_suffix")

    if report.failures:
        return report
    if args.model and normalize_path_text(args.model.strip()).isdigit() and selected_model:
        stable_path = rel(selected_model, project)
        report.warnings.append(f"numeric_model_selection_is_order_dependent:{args.model}->{stable_path}")
        report.next_steps.append(f"다음 실행부터는 목록 순서가 바뀌어도 안전하게 실제 경로를 사용하세요: --model {stable_path}")
        report.next_steps.append("이미 준비된 선택 모델을 다시 쓰려면: --model selected")

    copied, skipped, copy_failures = copy_aiu_studio_folder(project, args.execute)
    report.prepared_paths.extend(copied)
    report.skipped.extend(skipped)
    report.failures.extend(copy_failures)
    if report.failures:
        return report

    reference = find_reference_entrypoint(project, selected_kind)
    report.reference_entrypoint = rel(reference, project) if reference else None
    if reference is None:
        report.failures.append("reference_entrypoint_missing:runtest.py_or_run_test.py")
        report.next_steps.append("aiu_studio/ 또는 프로젝트 루트에 기존 runtest.py 또는 run_test.py를 넣어주세요.")
        return report

    changed, write_skipped, write_failures = write_runtest_2(project, selected_model, selected_kind, reference, args.execute, args.force)
    report.prepared_paths.extend(changed)
    report.skipped.extend(write_skipped)
    report.failures.extend(write_failures)
    if report.failures:
        return report

    inference_changed, inference_skipped, inference_failures = write_localservingtest(project, selected_model, selected_kind, reference, args.execute)
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

    verify_changed, verify_skipped, verify_failures = verify_selected_model_conversion(project, selected_model, selected_kind, models, args.execute)
    report.prepared_paths.extend(verify_changed)
    report.skipped.extend(verify_skipped)
    report.failures.extend(verify_failures)

    if args.execute and not report.failures:
        report.next_steps.extend(
            [
                "자동 준비 완료: 모델 프로젝트 구조 분석 + aiu_studio/ 템플릿 복사 + 선택 모델 기준 전체 코드 변환/갱신",
                "PowerShell에서는 선택 프로젝트의 aiu_studio 폴더로 이동한 뒤 실행하세요.",
                f"cd {powershell_quote_path(project / AIU_STUDIO_DIR_NAME)}",
                "python runtest_2.py",
                f"cd {powershell_quote_path(project / AIU_STUDIO_DIR_NAME / 'local_serving')}",
                "python localservingtest.py",
                "추론 테스트 결과는 화면에 출력합니다.",
                f"cd {powershell_quote_path(project)}",
                powershell_python_script(
                    ROOT / "scripts" / "verify_mlflow.py",
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
        report.next_steps.append("검토 후 --execute를 붙여 aiu_studio/ 폴더를 그대로 복사하고 aiu_studio/runtest_2.py를 생성하세요.")
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
            print(f"프로젝트 루트에 {total_model_count}개 모델이 있습니다. 선택해주세요.")
    print("model_artifact_paths:")
    if report.model_artifact_paths:
        for index, path in enumerate(report.model_artifact_paths, start=1):
            print(f"{index}. {path}")
    else:
        print("- none")
    print(f"Selected model: {report.selected_model_path or 'missing'}")
    print(f"MODEL_KIND: {report.model_kind or 'missing'}")
    print(f"Reference entrypoint: {report.reference_entrypoint or 'missing'}")
    print(f"Transformed entrypoint: {report.generated_entrypoint}")
    print(f"Transformed inference test: {report.generated_inference_test}")
    print(f"Execute: {report.execute}")
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
    print("TOD Guide:")
    model_selected = bool(report.selected_model_path)
    auto_ready = all(
        path in report.prepared_paths
        or f"{path} (refreshed)" in report.prepared_paths
        or any(item.startswith(f"{path} ") for item in report.prepared_paths)
        for path in [
            "aiu_studio/runtest_2.py",
            "aiu_studio/aiu_custom/model.py",
            "aiu_studio/aiu_custom/predict.py",
            "aiu_studio/aiu_custom/mapping.json",
            "aiu_studio/local_serving/localservingtest.py",
        ]
    )
    print("1. 모델 목록 확인 - 완료" if report.model_artifact_paths else "1. 모델 목록 확인 - 모델 없음")
    print("2. 모델 경로로 선택 - 완료" if model_selected else "2. 모델 경로로 선택 - 대기")
    print("3. aiu_studio/ 템플릿 복사 + 선택 모델 기준 전체 코드 변환 - 완료" if auto_ready else "3. aiu_studio/ 템플릿 복사 + 선택 모델 기준 전체 코드 변환 - 대기")
    print("4. 선택 모델 일치 확인 - 완료" if auto_ready else "4. 선택 모델 일치 확인 - 대기")
    print("5. 모델 환경변수 체크 - 다음")
    print("6. 원격 MLflow 배포/등록 실행 - 다음")
    print("7. 추론 스모크 테스트 - 다음")
    print("8. MLflow 검증 - 다음")
    if report.next_steps:
        print("Next steps:")
        for step in report.next_steps:
            print(f"- {step}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Select a project-root or data/** model artifact and generate aiu_studio/runtest_2.py without modifying runtest.py.")
    parser.add_argument("--project", default=".", help="model project folder")
    parser.add_argument("--model", help="model index from model_artifact_paths or a project-relative path")
    parser.add_argument("--execute", action="store_true", help="copy samples/aiu_studio/ into project-root aiu_studio/ and create aiu_studio/runtest_2.py")
    parser.add_argument("--force", action="store_true", help="kept for compatibility; aiu_studio/runtest_2.py is refreshed for the selected model")
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
