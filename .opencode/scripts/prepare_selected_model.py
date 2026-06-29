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
AIU_STUDIO_COPY_IGNORE_DIRS = {"code", "metrics", "tracking"}
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
    "mlruns",
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
    "MODEL_KIND",
    "source_model_path",
    "data_model_path",
    "model_path",
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


def resolve_model_selection(project: Path, models: list[Path], raw: str | None) -> tuple[Path | None, str | None]:
    if not raw:
        return None, "model_selection_required"
    value = normalize_path_text(raw.strip())
    if value.isdigit():
        index = int(value)
        if 1 <= index <= len(models):
            return models[index - 1], None
        return None, f"model_index_out_of_range:{value}"

    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = project / candidate
    candidate = candidate.resolve()
    if not candidate.exists() or not candidate.is_file():
        return None, f"model_path_not_found:{value}"
    return candidate, None


def ensure_under_project(project: Path, model_path: Path) -> bool:
    try:
        model_path.resolve().relative_to(project.resolve())
        return True
    except ValueError:
        return False


def find_reference_entrypoint(project: Path) -> Path | None:
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


def default_mlflow_names(project: Path) -> tuple[str, str]:
    experiment_name = safe_mlflow_name(project.name, "aiu_studio")
    return experiment_name, f"{experiment_name}_model"


def model_profile(project: Path, selected_model: Path, kind: str) -> dict[str, str]:
    details = MODEL_KIND_DETAILS.get(kind, {})
    aiu_relative = aiu_model_relative_path(selected_model, kind)
    return {
        "model_name": selected_model.name,
        "model_suffix": selected_model.suffix.lower(),
        "model_kind": kind,
        "model_relative_path": rel(selected_model, project),
        "aiu_model_relative_path": f"{AIU_STUDIO_DIR_NAME}/{aiu_relative}",
        "model_parent": rel(selected_model.parent, project),
        "required_package": details.get("required_package", "unknown"),
        "load_hint": details.get("load_hint", "custom loader required"),
    }


def aiu_model_relative_path(selected_model: Path, kind: str) -> str:
    return f"models/{kind}/{selected_model.name}"


def runtime_project_path_expr(project: Path, path: Path) -> str:
    relative = rel(path, project)
    aiu_prefix = AIU_STUDIO_DIR_NAME + "/"
    if relative == AIU_STUDIO_DIR_NAME:
        return "AI_STUDIO_DIR"
    if relative.startswith(aiu_prefix):
        return f'AI_STUDIO_DIR / "{relative[len(aiu_prefix):]}"'
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
    converted = rewrite_code_paths_argument(converted)
    return rewrite_model_loader_line(converted, kind, load_hint)


def transform_reference_text(
    reference_text: str,
    injected_block: str,
    replacements: dict[str, str],
    selected_relative: str,
    kind: str,
    load_hint: str,
    required_package: str,
) -> str:
    lines = reference_text.splitlines(keepends=True)
    output: list[str] = []
    inserted = False
    future_import_pattern = re.compile(r"^\s*from\s+__future__\s+import\s+")
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

    for index, line in enumerate(lines):
        if index == insert_at and not inserted:
            output.append(injected_block)
            inserted = True

        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        if stripped.startswith("#") and not re.match(r"^#.*coding[:=]", stripped):
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
            output.append(rewrite_reference_line(line, selected_relative, kind, load_hint, required_package))
            continue

        name, raw_value = match.groups()
        if stripped.rstrip("\n").rstrip().endswith(",") and name in {"CODE_PATHS", "code_paths", "MLFLOW_CODE_PATHS", "mlflow_code_paths"}:
            output.append(rewrite_reference_line(line, selected_relative, kind, load_hint, required_package))
            continue

        expression = replacement_expression(name, replacements)
        if expression is None:
            output.append(rewrite_reference_line(line, selected_relative, kind, load_hint, required_package))
            continue

        if name in MLFLOW_SETTING_NAMES and not indent:
            output.append(f"# AIU Studio preserved original assignment; value is defined in the conversion block above.\n")
            output.append(f"# {line.rstrip()}\n")
            continue
        if name in MLFLOW_SETTING_NAMES:
            output.append(rewrite_reference_line(line, selected_relative, kind, load_hint, required_package))
            continue

        _, comment = split_inline_comment(raw_value)
        converted_comment = converted_assignment_comment(name, selected_relative, kind, load_hint, required_package)
        if converted_comment:
            comment = converted_comment
        output.append(f"{indent}{assignment_line(name, expression, comment)}")

    if not inserted:
        output.insert(0, injected_block)

    if output and not output[-1].endswith("\n"):
        output[-1] += "\n"
    return "".join(output)


def aiu_injected_block(project: Path, selected_model: Path, kind: str, reference: Path) -> str:
    selected_relative = rel(selected_model, project)
    aiu_model_relative = aiu_model_relative_path(selected_model, kind)
    reference_expr = runtime_project_path_expr(project, reference)
    default_experiment_name, default_register_model_name = default_mlflow_names(project)
    profile = model_profile(project, selected_model, kind)
    details = MODEL_KIND_DETAILS.get(kind, {})
    required_package = details.get("required_package", "unknown")
    load_hint = details.get("load_hint", "custom loader required")
    loader = details.get(
        "loader",
        """def load_selected_model():\n    raise ValueError(f\"unsupported MODEL_KIND: {MODEL_KIND}\")\n""",
    )
    return f'''

# --- AIU Studio selected model conversion ---
# 선택된 모델을 먼저 판별하고, 실행 기준 모델은 aiu_studio/models/ 아래 복사본을 읽습니다.
# MODEL_KIND에 맞는 load_selected_model()을 생성해 선택 모델 기준으로 변환합니다.
# 이 블록은 자동 생성되지만 아래 원본 runtest.py 구조와 주석은 유지합니다.
import os as _aiu_os
from pathlib import Path as _AIUPath

AI_STUDIO_DIR = _AIUPath(__file__).resolve().parent
PROJECT_DIR = AI_STUDIO_DIR.parent
ORIGINAL_MODEL_PATH = PROJECT_DIR / "{selected_relative}"
SOURCE_MODEL_PATH = AI_STUDIO_DIR / "{aiu_model_relative}"
DATA_MODEL_PATH = SOURCE_MODEL_PATH
MODEL_PATH = SOURCE_MODEL_PATH
MODEL_KIND = "{kind}"
MODEL_PROFILE = {json.dumps(profile, ensure_ascii=False, indent=4)}
AIU_REQUIRED_PACKAGE = "{required_package}"
AIU_LOAD_HINT = "{load_hint}"
REFERENCE_ENTRYPOINT = {reference_expr}

# 자주 쓰는 소문자 변수명도 같은 선택 모델을 보도록 맞춥니다.
source_model_path = str(SOURCE_MODEL_PATH)
data_model_path = str(DATA_MODEL_PATH)
model_path = str(MODEL_PATH)

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
# experiment/model name은 프로젝트명 기준으로 자동 생성됩니다.
# password 값은 출력하지 않습니다.
mlflow_tracking_url = ""
mlflow_tracking_username = ""
mlflow_tracking_password = ""
mlflow_experiment_name = "{default_experiment_name}"
mlflow_register_model_name = "{default_register_model_name}"

{loader}

if mlflow_tracking_url.lower().startswith("https://"):
    raise ValueError("ssl_not_allowed: use http:// or file:// for mlflow_tracking_url")

for _aiu_env_name, _aiu_env_value in {{
    "MLFLOW_TRACKING_URI": mlflow_tracking_url,
    "MLFLOW_TRACKING_USERNAME": mlflow_tracking_username,
    "MLFLOW_TRACKING_PASSWORD": mlflow_tracking_password,
    "MLFLOW_EXPERIMENT_NAME": mlflow_experiment_name,
    "MLFLOW_REGISTER_MODEL_NAME": mlflow_register_model_name,
}}.items():
    if _aiu_env_value:
        _aiu_os.environ[_aiu_env_name] = _aiu_env_value
# --- /AIU Studio selected model conversion ---

'''


def generated_runtest_text(project: Path, selected_model: Path, kind: str, reference: Path) -> str:
    reference_text = reference.read_text(encoding="utf-8", errors="ignore")
    selected_relative = rel(selected_model, project)
    aiu_model_relative = aiu_model_relative_path(selected_model, kind)
    default_experiment_name, default_register_model_name = default_mlflow_names(project)
    details = MODEL_KIND_DETAILS.get(kind, {})
    required_package = details.get("required_package", "unknown")
    load_hint = details.get("load_hint", "custom loader required")
    replacements = {
        "SOURCE_MODEL_PATH": f'AI_STUDIO_DIR / "{aiu_model_relative}"',
        "DATA_MODEL_PATH": "SOURCE_MODEL_PATH",
        "MODEL_PATH": "SOURCE_MODEL_PATH",
        "MODEL_KIND": repr(kind),
        "source_model_path": "str(SOURCE_MODEL_PATH)",
        "data_model_path": "str(DATA_MODEL_PATH)",
        "model_path": "str(MODEL_PATH)",
        "MODEL_FILE": "SOURCE_MODEL_PATH",
        "model_file": "str(MODEL_PATH)",
        "CHECKPOINT_PATH": "SOURCE_MODEL_PATH",
        "checkpoint_path": "str(MODEL_PATH)",
        "MODEL_LOAD_HINT": "AIU_LOAD_HINT",
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
    transformed = transform_reference_text(
        reference_text,
        aiu_injected_block(project, selected_model, kind, reference),
        replacements,
        f"{AIU_STUDIO_DIR_NAME}/{aiu_model_relative}",
        kind,
        load_hint,
        required_package,
    )
    return transformed.rstrip() + "\n"


def generated_localservingtest_text(project: Path, selected_model: Path, kind: str, reference: Path) -> str:
    selected_relative = rel(selected_model, project)
    aiu_model_relative = aiu_model_relative_path(selected_model, kind)
    reference_expr = runtime_project_path_expr(project, reference)
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
PROJECT_DIR = AI_STUDIO_DIR.parent
ORIGINAL_MODEL_PATH = PROJECT_DIR / "{selected_relative}"
SOURCE_MODEL_PATH = AI_STUDIO_DIR / "{aiu_model_relative}"
DATA_MODEL_PATH = SOURCE_MODEL_PATH
MODEL_PATH = SOURCE_MODEL_PATH
MODEL_KIND = "{kind}"
MODEL_PROFILE = {json.dumps(profile, ensure_ascii=False, indent=4)}
AIU_REQUIRED_PACKAGE = "{required_package}"
AIU_LOAD_HINT = "{load_hint}"
REFERENCE_ENTRYPOINT = {reference_expr}

# AIU Studio 변환: 선택 모델 복사본 aiu_studio/{aiu_model_relative} 기준 추론 테스트입니다.
# 원본 모델 위치: {selected_relative}
# 모델 파일은 aiu_studio/models/{kind}/ 아래 복사본을 읽습니다.
# MODEL_KIND={kind}, loader={load_hint}

{loader}


def load_input_example():
    for name in ["input_example.json", "sample_input.json", "example.json"]:
        candidate = AI_STUDIO_DIR / name
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return {{}}


def load_aiu_custom_wrapper():
    for relative in ["aiu_custom/model_wrapper.py", "aiu_custom/predict.py"]:
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


def main():
    result = run_inference()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
'''


def generated_predict_text(project: Path, selected_model: Path, kind: str) -> str:
    selected_relative = rel(selected_model, project)
    aiu_model_relative = aiu_model_relative_path(selected_model, kind)
    profile = model_profile(project, selected_model, kind)
    details = MODEL_KIND_DETAILS.get(kind, {})
    required_package = details.get("required_package", "unknown")
    load_hint = details.get("load_hint", "custom loader required")
    loader = details.get(
        "loader",
        """def load_selected_model():\n    raise ValueError(f\"unsupported MODEL_KIND: {MODEL_KIND}\")\n""",
    )
    return f'''from __future__ import annotations

from pathlib import Path


AIU_CUSTOM_DIR = Path(__file__).resolve().parent
AI_STUDIO_DIR = AIU_CUSTOM_DIR.parent
PROJECT_DIR = AI_STUDIO_DIR.parent
ORIGINAL_MODEL_PATH = PROJECT_DIR / "{selected_relative}"
SOURCE_MODEL_PATH = AI_STUDIO_DIR / "{aiu_model_relative}"
DATA_MODEL_PATH = SOURCE_MODEL_PATH
MODEL_PATH = SOURCE_MODEL_PATH
MODEL_KIND = "{kind}"
MODEL_PROFILE = {json.dumps(profile, ensure_ascii=False, indent=4)}
AIU_REQUIRED_PACKAGE = "{required_package}"
AIU_LOAD_HINT = "{load_hint}"

# AIU Studio 변환: 선택 모델 복사본 aiu_studio/{aiu_model_relative} 기준 predict.py입니다.
# 원본 모델 위치: {selected_relative}
# 모델 파일은 aiu_studio/models/{kind}/ 아래 복사본을 읽습니다.
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
            "model_path": str(MODEL_PATH),
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
            "model_path": str(MODEL_PATH),
            "input": payload,
            "inference_error": str(exc),
        }}


def predict(payload):
    return ModelWrapper().predict(None, payload)
'''


def generated_mapping_json(project: Path, selected_model: Path, kind: str) -> str:
    selected_relative = rel(selected_model, project)
    aiu_relative = aiu_model_relative_path(selected_model, kind)
    details = MODEL_KIND_DETAILS.get(kind, {})
    mapping = {
        "model": {
            "name": selected_model.name,
            "kind": kind,
            "relative_path": f"{AIU_STUDIO_DIR_NAME}/{aiu_relative}",
            "source_path": selected_relative,
            "aiu_studio_path": f"{AIU_STUDIO_DIR_NAME}/{aiu_relative}",
            "load_hint": details.get("load_hint", "custom loader required"),
            "required_package": details.get("required_package", "unknown"),
        },
        "runtime": {
            "project_dir": "..",
            "aiu_studio_dir": ".",
            "predict_entrypoint": "aiu_custom/predict.py",
            "wrapper_class": "ModelWrapper",
            "local_serving_test": "local_serving/localservingtest.py",
        },
        "policy": {
            "copy_model_to_aiu_studio": True,
            "model_source": "aiu_studio_models_by_model_kind",
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


def write_aiu_predict(project: Path, selected_model: Path, kind: str, execute: bool) -> tuple[list[str], list[str], list[str]]:
    target = project / AIU_STUDIO_DIR_NAME / "aiu_custom" / "predict.py"
    changed: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    existed_before = target.exists()
    if execute:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(generated_predict_text(project, selected_model, kind), encoding="utf-8")
    changed.append("aiu_studio/aiu_custom/predict.py (refreshed)" if existed_before else "aiu_studio/aiu_custom/predict.py")
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


def copy_selected_model_to_aiu(project: Path, selected_model: Path, kind: str, execute: bool) -> tuple[list[str], list[str], list[str]]:
    target = project / AIU_STUDIO_DIR_NAME / aiu_model_relative_path(selected_model, kind)
    changed: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    existed_before = target.exists()
    if execute:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(selected_model, target)
        if not target.is_file():
            failures.append(f"aiu_model_copy_failed:{rel(target, project)}")
            return changed, skipped, failures
    changed.append(f"{rel(target, project)} (refreshed)" if existed_before else rel(target, project))
    return changed, skipped, failures


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

    copied, skipped, copy_failures = copy_aiu_studio_folder(project, args.execute)
    report.prepared_paths.extend(copied)
    report.skipped.extend(skipped)
    report.failures.extend(copy_failures)
    if report.failures:
        return report

    model_copy_changed, model_copy_skipped, model_copy_failures = copy_selected_model_to_aiu(project, selected_model, selected_kind, args.execute)
    report.prepared_paths.extend(model_copy_changed)
    report.skipped.extend(model_copy_skipped)
    report.failures.extend(model_copy_failures)
    if report.failures:
        return report

    reference = find_reference_entrypoint(project)
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
                "자동 준비 완료: 모델 프로젝트 구조 분석 + aiu_studio/ 폴더 복사 + 선택 모델 aiu_studio/models/<MODEL_KIND>/ 복사 + 환경변수 체크 + aiu_studio/runtest_2.py 변환/갱신 + aiu_studio/aiu_custom/predict.py 변환/갱신 + aiu_studio/aiu_custom/mapping.json 변환/갱신 + aiu_studio/local_serving/localservingtest.py 변환/갱신",
                "python aiu_studio/runtest_2.py",
                "python aiu_studio/local_serving/localservingtest.py",
                "추론 테스트 결과는 화면에 출력합니다.",
                "python .opencode/scripts/verify_mlflow.py --tracking-uri <tracking-uri> --experiment-name <experiment-name>",
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
    if report.failures:
        print("Failures:")
        for failure in report.failures:
            print(f"- {failure}")
    print("TOD Guide:")
    model_selected = bool(report.selected_model_path)
    auto_ready = all(
        path in report.prepared_paths or f"{path} (refreshed)" in report.prepared_paths
        for path in [
            f"aiu_studio/models/{report.model_kind}/{Path(report.selected_model_path).name}" if report.selected_model_path and report.model_kind else "",
            "aiu_studio/runtest_2.py",
            "aiu_studio/aiu_custom/predict.py",
            "aiu_studio/aiu_custom/mapping.json",
            "aiu_studio/local_serving/localservingtest.py",
        ]
    )
    print("1. 루트/data 모델 목록 확인 - 완료" if report.model_artifact_paths else "1. 루트/data 모델 목록 확인 - 모델 없음")
    print("2. 사용할 모델 선택 - 완료" if model_selected else "2. 사용할 모델 선택 - 대기")
    print("3. 자동 준비 실행 - 완료" if auto_ready else "3. 자동 준비 실행 - 대기")
    print("4. 환경 검증 - 다음")
    print("5. 모델 환경변수 체크 - 다음")
    print("6. runtest_2.py 실행 - 다음")
    print("7. 로컬 추론 테스트 - 다음")
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
