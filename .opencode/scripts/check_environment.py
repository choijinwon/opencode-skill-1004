import argparse
import ast
import base64
import importlib.metadata
import json
import os
import platform
import re
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path


ENV_KEYS = [
    "MLFLOW_TRACKING_URI",
    "MLFLOW_TRACKING_USERNAME",
    "MLFLOW_TRACKING_PASSWORD",
    "MLFLOW_EXPERIMENT_NAME",
    "MLFLOW_REGISTER_MODEL_NAME",
    "MLFLOW_EXPERIMENT_ID",
]

AI_STUDIO_ENV_KEYS = [
    "mlflow_tracking_url",
    "mlflow_tracking_username",
    "mlflow_tracking_password",
    "mlflow_experiment_name",
    "mlflow_register_model_name",
]
AUTO_DEFAULT_SETTING_KEYS = {
    "mlflow_experiment_name",
    "mlflow_register_model_name",
}
SSL_BLOCKED_SETTING_KEYS = {
    "mlflow_tracking_url",
}

MODEL_SETTING_FILES = [
    "aiu_studio/runtest_2.py",
    "runtest_2.py",
    "aiu_studio/runtest.py",
    "aiu_studio/run_test.py",
    "aui_studio/runtest.py",
    "aui_studio/run_test.py",
    "runtest.py",
    "run_test.py",
    "run_model.py",
    "run.py",
]
ENTRYPOINTS = [
    "aiu_studio/runtest_2.py",
    "runtest_2.py",
    "aiu_studio/runtest.py",
    "aiu_studio/run_test.py",
    "aui_studio/runtest.py",
    "aui_studio/run_test.py",
    "runtest.py",
    "run_test.py",
    "train.py",
    "run_model.py",
    "run.py",
    "main.py",
    "app.py",
    "scripts/train.py",
]
SAMPLE_PROJECT_NAMES = {"sklearn_sample", "pytorch_sample", "tensorflow_sample"}
MODEL_MARKERS = [
    "aiu_studio/runtest_2.py",
    "runtest_2.py",
    "aiu_studio/runtest.py",
    "aiu_studio/run_test.py",
    "aui_studio/runtest.py",
    "aui_studio/run_test.py",
    "runtest.py",
    "run_test.py",
    "train.py",
    "run_model.py",
    "predict.py",
    "aiu_studio/input_example.json",
    "MLmodel",
]
ARTIFACT_SUFFIXES = {".pkl", ".joblib", ".pt", ".pth", ".h5", ".keras", ".onnx", ".safetensors", ".bst", ".ubj"}
ARTIFACT_DIRS = ["ai_studio", "saved_model", "model", "artifacts"]
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

SETTING_ALIASES = {
    "mlflow_tracking_url": {
        "mlflow_tracking_url",
        "mflow_tracking_url",
        "tracking_url",
        "mlflow_tracking_uri",
        "MLFLOW_TRACKING_URI",
    },
    "mlflow_tracking_username": {
        "mlflow_tracking_username",
        "tracking_username",
        "mlflow_username",
        "username",
        "MLFLOW_TRACKING_USERNAME",
    },
    "mlflow_tracking_password": {
        "mlflow_tracking_password",
        "tracking_password",
        "mlflow_password",
        "password",
        "MLFLOW_TRACKING_PASSWORD",
    },
    "mlflow_experiment_name": {
        "mlflow_experiment_name",
        "experiment_name",
        "MLFLOW_EXPERIMENT_NAME",
    },
    "mlflow_register_model_name": {
        "mlflow_register_model_name",
        "mlflow_register_mdoel_name",
        "register_model_name",
        "registered_model_name",
        "MLFLOW_REGISTER_MODEL_NAME",
    },
}

ALIAS_TO_SETTING = {
    alias: setting_key
    for setting_key, aliases in SETTING_ALIASES.items()
    for alias in aliases
}

EXPORT_ENV_MAP = {
    "mlflow_tracking_url": "MLFLOW_TRACKING_URI",
    "mlflow_tracking_username": "MLFLOW_TRACKING_USERNAME",
    "mlflow_tracking_password": "MLFLOW_TRACKING_PASSWORD",
    "mlflow_experiment_name": "MLFLOW_EXPERIMENT_NAME",
    "mlflow_register_model_name": "MLFLOW_REGISTER_MODEL_NAME",
}

CORE_PACKAGES = [
    "mlflow",
    "scikit-learn",
    "torch",
    "tensorflow",
    "transformers",
]
FRAMEWORK_PACKAGES = {
    "joblib",
    "onnxruntime",
    "safetensors",
    "scikit-learn",
    "tensorflow",
    "torch",
    "transformers",
    "xgboost",
}
MODEL_KIND_REQUIRED_PACKAGE = {
    "sklearn_pickle": "joblib",
    "sklearn_joblib": "joblib",
    "pytorch": "torch",
    "onnx": "onnxruntime",
    "tensorflow_keras": "tensorflow",
    "tensorflow_h5": "tensorflow",
    "safetensors": "safetensors",
    "xgboost_bst": "xgboost",
    "xgboost_ubj": "xgboost",
}

EXPECTED_PYTHON_VERSION = "3.11.9"
EXPECTED_PACKAGE_VERSIONS = {
    "mlflow": "==3.13.0",
}
REQUIREMENT_OPERATORS = ["==", "!=", ">=", "<=", "~=", ">", "<"]
REMOTE_MLFLOW_VERSION_ENDPOINTS = [
    "version",
    "api/2.0/mlflow/version",
]
REMOTE_MLFLOW_TIMEOUT_SECONDS = 3


@dataclass
class PackageStatus:
    name: str
    status: str
    version: str | None = None
    required_version: str = "any"


@dataclass
class RequirementStatus:
    source: str
    requirement: str
    name: str
    required_version: str
    installed_version: str | None
    status: str


@dataclass
class EnvVarStatus:
    name: str
    status: str


@dataclass
class EnvFileStatus:
    path: str
    key_status: list[EnvVarStatus] = field(default_factory=list)


@dataclass
class RemoteMlflowStatus:
    tracking_uri_status: str
    status: str
    server_version: str | None = None
    local_version: str | None = None
    required_version: str | None = None
    endpoint: str | None = None
    detail: str | None = None


@dataclass
class EnvironmentReport:
    project_path: str
    os: str
    python_executable: str
    python_version: str
    expected_python_version: str
    python_version_status: str
    virtual_env: str
    dependency_files: list[str]
    packages: list[PackageStatus] = field(default_factory=list)
    requirements: list[RequirementStatus] = field(default_factory=list)
    env_vars: list[EnvVarStatus] = field(default_factory=list)
    ai_studio_env: EnvFileStatus | None = None
    model_settings: EnvFileStatus | None = None
    export_ready: list[EnvVarStatus] = field(default_factory=list)
    blocked_summary: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    tod_guide: list[str] = field(default_factory=list)
    source_input_required: list[EnvVarStatus] = field(default_factory=list)
    selected_model_path: str | None = None
    selected_model_kind: str | None = None
    selected_required_package: str | None = None
    selected_package_status: str | None = None
    remote_mlflow: RemoteMlflowStatus | None = None


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_version_parts(value: str) -> tuple[int, ...] | None:
    match = re.match(r"^\s*(\d+(?:\.\d+)*)", value)
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def compare_versions(installed: str, required: str) -> int | None:
    installed_parts = parse_version_parts(installed)
    required_parts = parse_version_parts(required)
    if installed_parts is None or required_parts is None:
        return None
    length = max(len(installed_parts), len(required_parts))
    left = installed_parts + (0,) * (length - len(installed_parts))
    right = required_parts + (0,) * (length - len(required_parts))
    if left == right:
        return 0
    return 1 if left > right else -1


def version_constraint_status(installed: str, required_spec: str) -> str:
    if not required_spec:
        return "installed"
    constraints = [item.strip() for item in required_spec.split(",") if item.strip()]
    unknown = False
    for constraint in constraints:
        operator = next((item for item in REQUIREMENT_OPERATORS if constraint.startswith(item)), None)
        if operator is None:
            unknown = True
            continue
        required = constraint[len(operator) :].strip()
        if operator == "~=":
            unknown = True
            continue
        if operator == "==":
            if installed == required:
                continue
            comparison = compare_versions(installed, required)
            if comparison == 0:
                continue
            return "version_mismatch"
        elif operator == "!=":
            if installed == required:
                return "version_mismatch"
            comparison = compare_versions(installed, required)
            if comparison == 0:
                return "version_mismatch"
        else:
            comparison = compare_versions(installed, required)
            if comparison is None:
                unknown = True
                continue
            if operator == ">=" and comparison < 0:
                return "version_mismatch"
            if operator == ">" and comparison <= 0:
                return "version_mismatch"
            if operator == "<=" and comparison > 0:
                return "version_mismatch"
            if operator == "<" and comparison >= 0:
                return "version_mismatch"
    return "version_unchecked" if unknown else "version_match"


def strip_inline_comment(line: str) -> str:
    if " #" in line:
        return line.split(" #", 1)[0].strip()
    return line.strip()


def parse_requirement_line(raw_line: str) -> tuple[str, str] | None:
    line = strip_inline_comment(raw_line)
    if not line or line.startswith("#"):
        return None
    if line.startswith(("-", "git+", "http://", "https://", "file:")):
        return None
    line = line.split(";", 1)[0].strip()
    match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?\s*(.*)$", line)
    if not match:
        return None
    name = normalize_package_name(match.group(1))
    spec = match.group(2).strip()
    if spec.startswith("@"):
        spec = spec
    return name, spec


def parse_python_literal_assignments(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return {}
    values: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                values[target.id] = value
    return values


def selected_model_status(project: Path) -> tuple[str | None, str | None, str | None, str | None]:
    mapping_path = project / "aiu_studio" / "aiu_custom" / "mapping.json"
    if mapping_path.is_file():
        try:
            payload = json.loads(mapping_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        model = payload.get("model") if isinstance(payload, dict) else None
        if isinstance(model, dict):
            selected_path = model.get("source_path") or model.get("relative_path")
            model_kind = model.get("kind")
            required_package = model.get("required_package")
            if isinstance(required_package, str) and required_package == "unknown":
                required_package = None
            if isinstance(model_kind, str) and not required_package:
                required_package = MODEL_KIND_REQUIRED_PACKAGE.get(model_kind)
            if isinstance(selected_path, str) or isinstance(model_kind, str) or isinstance(required_package, str):
                normalized_package = normalize_package_name(required_package) if isinstance(required_package, str) else None
                package_status = None
                if normalized_package:
                    package_status = "set" if package_version(normalized_package) else "missing"
                return (
                    selected_path if isinstance(selected_path, str) else None,
                    model_kind if isinstance(model_kind, str) else None,
                    normalized_package,
                    package_status,
                )

    runtest_path = project / "aiu_studio" / "runtest_2.py"
    values = parse_python_literal_assignments(runtest_path)
    selected_path = None
    model_kind = values.get("MODEL_KIND")
    if isinstance(model_kind, str):
        required_package = MODEL_KIND_REQUIRED_PACKAGE.get(model_kind)
    else:
        required_package = None
    model_profile = values.get("MODEL_PROFILE")
    if isinstance(model_profile, dict):
        raw_path = model_profile.get("model_relative_path") or model_profile.get("runtime_model_path")
        raw_kind = model_profile.get("model_kind")
        raw_package = model_profile.get("required_package")
        selected_path = raw_path if isinstance(raw_path, str) else None
        model_kind = raw_kind if isinstance(raw_kind, str) else model_kind
        required_package = raw_package if isinstance(raw_package, str) and raw_package != "unknown" else required_package
    normalized_package = normalize_package_name(required_package) if isinstance(required_package, str) else None
    package_status = "set" if normalized_package and package_version(normalized_package) else ("missing" if normalized_package else None)
    return selected_path, model_kind if isinstance(model_kind, str) else None, normalized_package, package_status


def is_unselected_framework_requirement(item: RequirementStatus, selected_required_package: str | None) -> bool:
    if not selected_required_package:
        return False
    selected = normalize_package_name(selected_required_package)
    item_name = normalize_package_name(item.name)
    return item_name in FRAMEWORK_PACKAGES and item_name != selected


def requirement_statuses(project: Path, expected_package_versions: dict[str, str] | None = None) -> list[RequirementStatus]:
    expected_package_versions = expected_package_versions or EXPECTED_PACKAGE_VERSIONS
    statuses: list[RequirementStatus] = []
    seen: set[str] = set()
    requirements_path = project / "requirements.txt"
    if requirements_path.exists():
        for raw_line in requirements_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parsed = parse_requirement_line(raw_line)
            if parsed is None:
                continue
            name, required_spec = parsed
            seen.add(name)
            installed = package_version(name)
            if installed is None:
                status = "missing"
            else:
                status = version_constraint_status(installed, required_spec)
            statuses.append(
                RequirementStatus(
                    source="requirements.txt",
                    requirement=strip_inline_comment(raw_line),
                    name=name,
                    required_version=required_spec or "any",
                    installed_version=installed,
                    status=status,
                )
            )
    for name, required_spec in expected_package_versions.items():
        normalized = normalize_package_name(name)
        if normalized in seen:
            continue
        installed = package_version(normalized)
        status = "missing" if installed is None else version_constraint_status(installed, required_spec)
        statuses.append(
            RequirementStatus(
                source="expected",
                requirement=f"{name}{required_spec}",
                name=normalized,
                required_version=required_spec,
                installed_version=installed,
                status=status,
            )
        )
    return statuses


def env_status(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        return "missing"
    if value == "":
        return "empty"
    return "set"


def display_path(path: str | Path, project: Path) -> str:
    path_obj = Path(path)
    try:
        return str(path_obj.relative_to(project))
    except ValueError:
        return str(path_obj)


def dependency_files(project: Path) -> list[str]:
    names = ["requirements.txt", "pyproject.toml", "environment.yml", "environment.yaml"]
    return [name for name in names if (project / name).exists()]


def is_filesystem_root(path: Path) -> bool:
    return path.parent == path


def is_opencode_sample_source(path: Path) -> bool:
    parts = path.resolve().parts
    for index, part in enumerate(parts[:-1]):
        if part == ".opencode" and parts[index + 1] in {"sample", "samples"}:
            return True
    return False


def has_model_project(project: Path) -> bool:
    if is_opencode_sample_source(project):
        return False
    if any((project / name).exists() for name in MODEL_MARKERS):
        return True
    if find_entrypoint_candidates(project):
        return True
    if any((project / name).exists() for name in ARTIFACT_DIRS):
        return True
    return bool(find_model_artifacts(project))


def find_model_artifacts(project: Path) -> list[Path]:
    if is_opencode_sample_source(project):
        return []
    found: list[Path] = []
    for path in project.rglob("*"):
        try:
            relative_parts = path.relative_to(project).parts
        except ValueError:
            continue
        if any(part in MODEL_SCAN_SKIP_DIRS for part in relative_parts):
            continue
        if path.is_file() and path.suffix.lower() in ARTIFACT_SUFFIXES:
            found.append(path)
    return sorted(set(found))


def is_sample_project(project: Path) -> bool:
    return project.name in SAMPLE_PROJECT_NAMES


def unique_paths(paths: list[Path]) -> list[Path]:
    unique = []
    seen = set()
    for path in paths:
        key = path.resolve()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def find_entrypoint_candidates(project: Path) -> list[Path]:
    found = []
    for name in ENTRYPOINTS:
        candidate = project / name
        if candidate.exists() and candidate.is_file():
            found.append(candidate)
    found.extend(sorted(path for path in project.glob("*.py") if path.is_file()))
    return unique_paths(found)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def usable_setting_value(value: str | None) -> str | None:
    if value is None or value == "" or todo_placeholder(value):
        return None
    return value


def resolved_mlflow_settings(project: Path, entrypoint_name: str | None = None) -> dict[str, str]:
    values: dict[str, str] = {}
    env_file_values = parse_env_file(project / "ai_studio.env")
    for key in AI_STUDIO_ENV_KEYS:
        value = usable_setting_value(env_file_values.get(key))
        if value is not None:
            values[key] = value

    for setting_key, env_key in EXPORT_ENV_MAP.items():
        value = usable_setting_value(os.environ.get(env_key))
        if value is not None:
            values[setting_key] = value

    setting_file = resolve_setting_file(project, entrypoint_name)
    if setting_file is not None and setting_file.exists():
        source_values = parse_python_string_assignments(setting_file)
        for key in AI_STUDIO_ENV_KEYS:
            value = usable_setting_value(source_values.get(key))
            if value is not None:
                values[key] = value
    return values


def ssl_not_allowed(value: str | None) -> bool:
    return bool(value and value.strip().lower().startswith("https://"))


def todo_placeholder(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().lower()
    return normalized in {"{todo}", "todo", "<todo>", "[todo]"}


def setting_value_status(key: str, value: str | None, missing_status: str = "missing") -> str:
    if value is None:
        return "auto_default" if key in AUTO_DEFAULT_SETTING_KEYS else missing_status
    if value == "":
        return "auto_default" if key in AUTO_DEFAULT_SETTING_KEYS else "empty"
    if todo_placeholder(value):
        return "auto_default" if key in AUTO_DEFAULT_SETTING_KEYS else "missing"
    if key in SSL_BLOCKED_SETTING_KEYS and ssl_not_allowed(value):
        return "ssl_not_allowed"
    return "set"


def extract_mlflow_version(payload: str) -> str | None:
    stripped = payload.strip()
    if not stripped:
        return None
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        for key in ["version", "mlflow_version", "server_version"]:
            value = data.get(key)
            if isinstance(value, str):
                return value.strip()
    match = re.search(r"\d+(?:\.\d+){1,3}(?:[A-Za-z0-9_.+-]*)?", stripped)
    return match.group(0) if match else None


def remote_version_status(server_version: str | None, local_version: str | None) -> tuple[str, str | None]:
    if not server_version:
        return "version_unchecked", None
    required_spec = f"=={server_version}"
    if local_version is None:
        return "missing_local_mlflow", required_spec
    return version_constraint_status(local_version, required_spec), required_spec


def check_remote_mlflow_version(project: Path, entrypoint_name: str | None = None) -> RemoteMlflowStatus:
    settings = resolved_mlflow_settings(project, entrypoint_name)
    tracking_uri = settings.get("mlflow_tracking_url")
    local_version = package_version("mlflow")

    if tracking_uri is None:
        return RemoteMlflowStatus(
            tracking_uri_status="missing",
            status="skipped",
            local_version=local_version,
            detail="mlflow_tracking_url is missing",
        )
    if ssl_not_allowed(tracking_uri):
        return RemoteMlflowStatus(
            tracking_uri_status="ssl_not_allowed",
            status="skipped",
            local_version=local_version,
            detail="https tracking URI is not allowed",
        )
    if tracking_uri.lower().startswith("file://"):
        return RemoteMlflowStatus(
            tracking_uri_status="local_file",
            status="skipped",
            local_version=local_version,
            detail="file tracking URI has no remote server version",
        )
    if not tracking_uri.lower().startswith(("http://", "https://")):
        return RemoteMlflowStatus(
            tracking_uri_status="unsupported",
            status="skipped",
            local_version=local_version,
            detail="tracking URI must start with http:// for remote version check",
        )

    username = settings.get("mlflow_tracking_username")
    password = settings.get("mlflow_tracking_password")
    auth_header = None
    if username and password:
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        auth_header = f"Basic {token}"

    base_uri = tracking_uri.rstrip("/")
    last_error = None
    for endpoint_name in REMOTE_MLFLOW_VERSION_ENDPOINTS:
        endpoint = f"{base_uri}/{endpoint_name}"
        headers = {"Accept": "application/json, text/plain"}
        if auth_header:
            headers["Authorization"] = auth_header
        request = urllib.request.Request(endpoint, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=REMOTE_MLFLOW_TIMEOUT_SECONDS) as response:
                payload = response.read(4096).decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            continue
        server_version = extract_mlflow_version(payload)
        if not server_version:
            last_error = ValueError("remote version response did not include a version")
            continue
        status, required_spec = remote_version_status(server_version, local_version)
        return RemoteMlflowStatus(
            tracking_uri_status="set",
            status=status,
            server_version=server_version,
            local_version=local_version,
            required_version=required_spec,
            endpoint=endpoint,
        )

    return RemoteMlflowStatus(
        tracking_uri_status="set",
        status="unreachable",
        local_version=local_version,
        detail=f"remote version check failed: {type(last_error).__name__ if last_error else 'unknown'}",
    )


def ai_studio_env_status(project: Path) -> EnvFileStatus:
    path = project / "ai_studio.env"
    values = parse_env_file(path)
    statuses = []
    for key in AI_STUDIO_ENV_KEYS:
        status = setting_value_status(key, values.get(key) if key in values else None)
        statuses.append(EnvVarStatus(key, status))
    return EnvFileStatus(str(path), statuses)


def literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def target_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        return literal_string(node.slice)
    return None


def record_setting(values: dict[str, str], key: str | None, value: str | None) -> None:
    if key is None or value is None:
        return
    setting_key = ALIAS_TO_SETTING.get(key)
    if setting_key and value:
        values[setting_key] = value


def parse_python_string_assignments(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return values
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = literal_string(node.value)
            for target in node.targets:
                record_setting(values, target_name(target), value)
        elif isinstance(node, ast.AnnAssign):
            record_setting(values, target_name(node.target), literal_string(node.value))
        elif isinstance(node, ast.Dict):
            for key_node, value_node in zip(node.keys, node.values):
                record_setting(values, literal_string(key_node), literal_string(value_node))
    return values


def resolve_setting_file(project: Path, entrypoint_name: str | None = None) -> Path | None:
    if entrypoint_name:
        path = Path(entrypoint_name)
        return path if path.is_absolute() else project / path
    for name in MODEL_SETTING_FILES:
        path = project / name
        if not path.exists():
            continue
        return path
    candidates = find_entrypoint_candidates(project)
    if len(candidates) == 1:
        return candidates[0]
    return None


def model_settings_status(project: Path, entrypoint_name: str | None = None) -> EnvFileStatus | None:
    path = resolve_setting_file(project, entrypoint_name)
    if path is None or not path.exists():
        return None
    values = parse_python_string_assignments(path)
    statuses = []
    for key in AI_STUDIO_ENV_KEYS:
        status = setting_value_status(key, values.get(key) if key in values else None)
        statuses.append(EnvVarStatus(key, status))
    return EnvFileStatus(str(path), statuses)


def export_ready_status(project: Path, entrypoint_name: str | None = None) -> list[EnvVarStatus]:
    path = resolve_setting_file(project, entrypoint_name)
    if path is None or not path.exists():
        return []
    values = parse_python_string_assignments(path)
    statuses = []
    for setting_key, env_key in EXPORT_ENV_MAP.items():
        value = values.get(setting_key)
        env_value = os.environ.get(env_key)
        if ssl_not_allowed(value) or ssl_not_allowed(env_value):
            status = "ssl_not_allowed"
        elif value:
            status = "set"
        elif env_status(env_key) == "set":
            status = "exported"
        elif setting_key in AUTO_DEFAULT_SETTING_KEYS:
            status = "auto_default"
        else:
            status = "missing"
        statuses.append(EnvVarStatus(env_key, status))
    return statuses


def source_input_required_status(model_settings: EnvFileStatus | None) -> list[EnvVarStatus]:
    if model_settings is None:
        return [EnvVarStatus(key, "missing") for key in AI_STUDIO_ENV_KEYS if key not in AUTO_DEFAULT_SETTING_KEYS]
    required = []
    for item in model_settings.key_status:
        if item.name not in AI_STUDIO_ENV_KEYS:
            continue
        if item.status in {"missing", "empty", "ssl_not_allowed"}:
            required.append(item)
    return required


def build_report(project: Path, entrypoint_name: str | None = None) -> EnvironmentReport:
    if is_filesystem_root(project):
        return EnvironmentReport(
            project_path=str(project),
            os=f"{platform.system()} {platform.release()}",
            python_executable=sys.executable,
            python_version=platform.python_version(),
            expected_python_version=EXPECTED_PYTHON_VERSION,
            python_version_status="blocked",
            virtual_env=os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX") or "not detected",
            dependency_files=[],
            packages=[],
            requirements=[],
            env_vars=[],
            ai_studio_env=None,
            model_settings=None,
            export_ready=[],
            blocked_summary=["드라이브/파일시스템 루트 검색은 허용하지 않습니다."],
            failures=["drive_root_scan_not_allowed"],
            next_steps=["현재 모델 프로젝트 폴더에서 실행하거나 --project <current-project-folder>를 지정하세요."],
            tod_guide=[],
            source_input_required=[],
        )
    if is_opencode_sample_source(project):
        return EnvironmentReport(
            project_path=str(project),
            os=f"{platform.system()} {platform.release()}",
            python_executable=sys.executable,
            python_version=platform.python_version(),
            expected_python_version=EXPECTED_PYTHON_VERSION,
            python_version_status="blocked",
            virtual_env=os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX") or "not detected",
            dependency_files=[],
            packages=[],
            requirements=[],
            env_vars=[],
            ai_studio_env=None,
            model_settings=None,
            export_ready=[],
            blocked_summary=[".opencode/sample(s)는 번들 샘플 원본이라 분석 대상이 아닙니다."],
            failures=["opencode_sample_source_not_analysis_target"],
            next_steps=["실제 사용자가 선택한 모델 프로젝트 폴더를 --project로 지정하세요."],
            tod_guide=[],
            source_input_required=[],
        )
    python_version = platform.python_version()
    deps = dependency_files(project)
    selected_path, selected_kind, selected_required_package, selected_package_status = selected_model_status(project)
    env_vars = [EnvVarStatus(key, env_status(key)) for key in ENV_KEYS]
    ai_env = ai_studio_env_status(project)
    model_settings = model_settings_status(project, entrypoint_name)
    export_ready = export_ready_status(project, entrypoint_name)
    source_input_required = source_input_required_status(model_settings)
    remote_mlflow = check_remote_mlflow_version(project, entrypoint_name)
    effective_expected_package_versions = dict(EXPECTED_PACKAGE_VERSIONS)
    if remote_mlflow.server_version:
        effective_expected_package_versions["mlflow"] = f"=={remote_mlflow.server_version}"
    packages = []
    package_names = list(CORE_PACKAGES)
    if selected_required_package and selected_required_package not in {normalize_package_name(name) for name in package_names}:
        package_names.append(selected_required_package)
    for package in package_names:
        version = package_version(package)
        required_spec = effective_expected_package_versions.get(normalize_package_name(package), "any")
        status = "missing" if version is None else ("set" if required_spec == "any" else version_constraint_status(version, required_spec))
        packages.append(PackageStatus(package, status, version, required_spec))
    requirements = requirement_statuses(project, effective_expected_package_versions)
    blocked_summary: list[str] = []
    failures: list[str] = []
    next_steps: list[str] = []
    model_found = has_model_project(project)
    entrypoint_candidates = find_entrypoint_candidates(project)
    setting_file = None
    if model_settings is not None:
        setting_file = display_path(model_settings.path, project)
    entrypoint = setting_file
    if entrypoint is None and len(entrypoint_candidates) == 1:
        entrypoint = str(entrypoint_candidates[0].relative_to(project))
    existing_model_flow = model_found and not is_sample_project(project)
    if existing_model_flow:
        entrypoint_display = entrypoint or "사용자가 실제 사용하는 파일명"
        tod_guide = [
            "1. 모델 목록 확인: 현재 프로젝트 루트 바로 아래와 data/**에서 사용할 모델 후보를 확인한다.",
            "2. 모델 경로로 선택: prepare_selected_model.py --model <경로> 또는 --model selected로 선택한다.",
            "3. 선택 모델 환경 변환: aiu_studio/를 복사하고 모델 형식 확인, 형식별 샘플 참조, runtest_2.py 생성/연결, 실행 코드 변환을 수행한다.",
            f"4. 모델 환경변수 체크: {entrypoint_display}의 MLflow 입력값 3개와 자동값 2개를 set/empty/missing/auto_default/ssl_not_allowed로 확인한다.",
            f"5. 원격 MLflow 배포/등록 실행: python {entrypoint_display} 로 선택 모델을 원격 MLflow 서버에 기록/등록한다.",
            "6. 추론 스모크 테스트: 선택 모델 환경으로 변환된 local serving 입력/출력 스키마를 확인한다.",
            "7. MLflow 검증: Run, artifact, registered model 기록을 확인한다.",
        ]
        if entrypoint is None:
            if entrypoint_candidates:
                next_steps.append("Entrypoint candidates: " + ", ".join(str(path.relative_to(project)) for path in entrypoint_candidates))
            next_steps.append("실행 파일을 찾지 못했습니다. 사용자가 실제 학습/모델 생성 Python 파일을 프로젝트에 직접 넣고 --entrypoint <file>로 지정하세요.")
            source_input_required = []
    else:
        entrypoint_display = setting_file or "run_model.py, runtest.py 또는 aiu_studio/runtest.py"
        tod_guide = [
            "1. 환경 검증: 현재 출력의 Python, dependency, MLflow, 설정 상태를 확인한다.",
            f"2. 샘플 규격 확인/보충: {project}의 aiu_custom/, local_serving/, saved_model/, requirements.txt, aiu_studio/input_example.json을 확인한다.",
            f"3. 환경 변수 입력/export: {entrypoint_display}의 설정 블록 값을 직접 입력하고 실행 시 MLFLOW_*로 export한다.",
            "4. 패키지 설치: 폐쇄망 WSL은 bash .opencode/wsl/install_offline.sh를 우선 사용하고, wheelhouse가 없으면 온라인 WSL에서 bash .opencode/wsl/download_wheels.sh로 먼저 준비한다.",
            f"5. 모델 실행 및 원격 MLflow 기록: python {entrypoint_display}",
            "6. 산출물 확인: MLflow artifact_path='ai_studio' 아래 ai_studio/code 또는 로컬 ai_studio/metrics, ai_studio/code 생성 여부를 확인한다.",
        ]
    python_version_status = "set" if python_version == EXPECTED_PYTHON_VERSION else "version_mismatch"

    if python_version_status == "version_mismatch":
        blocked_summary.append(f"Python 버전 차이 ({python_version} vs 기대 {EXPECTED_PYTHON_VERSION}) → 호환성 확인 필요")
        failures.append(f"version_mismatch:python expected {EXPECTED_PYTHON_VERSION} got {python_version}")
        next_steps.append(f"Use Python {EXPECTED_PYTHON_VERSION} for this MLflow workflow.")
    if not deps:
        failures.append("missing_dependency_file")
        next_steps.append("Add or confirm requirements.txt, pyproject.toml, or environment.yml.")
    blocking_requirements = [
        item
        for item in requirements
        if not (existing_model_flow and is_unselected_framework_requirement(item, selected_required_package))
    ]
    missing_requirements = [item.name for item in blocking_requirements if item.status == "missing"]
    mismatched_requirements = [item.name for item in blocking_requirements if item.status == "version_mismatch"]
    if missing_requirements:
        failures.append("missing_requirements:" + ",".join(missing_requirements))
        next_steps.append("Install missing packages from requirements.txt.")
    if mismatched_requirements:
        failures.append("version_mismatch_requirements:" + ",".join(mismatched_requirements))
        next_steps.append("Resolve package version mismatches before model execution.")
    if package_version("mlflow") is None:
        failures.append("missing_dependency:mlflow")
        next_steps.append("Install or activate an environment that includes mlflow.")
    if remote_mlflow.status == "version_mismatch" and remote_mlflow.server_version:
        failures.append(
            f"version_mismatch:mlflow remote {remote_mlflow.server_version} local {remote_mlflow.local_version or 'missing'}"
        )
        next_steps.append(f"원격 MLflow 서버 버전에 맞춰 로컬/업로드 환경의 mlflow를 {remote_mlflow.required_version}로 설치하세요.")
    elif remote_mlflow.status == "missing_local_mlflow" and remote_mlflow.server_version:
        failures.append(f"missing_dependency:mlflow remote {remote_mlflow.server_version}")
        next_steps.append(f"원격 MLflow 서버 버전에 맞춰 mlflow{remote_mlflow.required_version}를 설치하세요.")
    elif remote_mlflow.status == "unreachable":
        next_steps.append("원격 MLflow 서버 버전 확인에 실패했습니다. 서버 URL/방화벽/인증 정보를 확인하세요.")
    if remote_mlflow.server_version:
        for item in requirements:
            if normalize_package_name(item.name) != "mlflow":
                continue
            if version_constraint_status(remote_mlflow.server_version, item.required_version) == "version_mismatch":
                failures.append(
                    f"version_mismatch_requirements:mlflow remote {remote_mlflow.server_version} not_allowed_by {item.required_version}"
                )
                next_steps.append(f"requirements.txt의 mlflow 요구 버전을 mlflow=={remote_mlflow.server_version}로 수정하세요.")
                break
    tracking_ready = any(item.name == "MLFLOW_TRACKING_URI" and item.status in {"set", "exported"} for item in export_ready)
    if env_status("MLFLOW_TRACKING_URI") == "missing" and not tracking_ready:
        next_steps.append("Confirm local or remote MLFLOW_TRACKING_URI before MLflow verification.")
    if source_input_required:
        required_names = ", ".join(item.name for item in source_input_required)
        next_steps.append(f"사용자가 직접 소스에 입력해야 하는 값: {required_names}.")
    setting_source = model_settings or ai_env
    if model_settings is None and not (project / "ai_studio.env").exists():
        failures.append("missing_model_settings_file:entrypoint_or_ai_studio_env")
        if existing_model_flow and entrypoint is None:
            next_steps.append("실행 파일을 직접 넣고 확정한 뒤 해당 파일의 MLflow/AI Studio 설정 블록에 값을 입력하세요.")
        else:
            next_steps.append("Fill MLflow/AI Studio settings directly in the confirmed entrypoint file.")
    for item in setting_source.key_status:
        if item.status in {"missing", "empty", "ssl_not_allowed"}:
            failures.append(f"missing_env:{item.name}")
            if item.status == "ssl_not_allowed":
                next_steps.append("SSL is not allowed for mlflow_tracking_url. Use http:// or file:// instead of https://.")

    virtual_env = os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX") or "not detected"
    return EnvironmentReport(
        project_path=str(project),
        os=f"{platform.system()} {platform.release()}",
        python_executable=sys.executable,
        python_version=python_version,
        expected_python_version=EXPECTED_PYTHON_VERSION,
        python_version_status=python_version_status,
        virtual_env=virtual_env,
        dependency_files=deps,
        packages=packages,
        requirements=requirements,
        env_vars=env_vars,
        ai_studio_env=ai_env,
        model_settings=model_settings,
        export_ready=export_ready,
        blocked_summary=blocked_summary,
        failures=failures,
        next_steps=next_steps,
        tod_guide=tod_guide,
        source_input_required=source_input_required,
        selected_model_path=selected_path,
        selected_model_kind=selected_kind,
        selected_required_package=selected_required_package,
        selected_package_status=selected_package_status,
        remote_mlflow=remote_mlflow,
    )


def print_text(report: EnvironmentReport):
    print(f"Project: {report.project_path}")
    print(f"OS: {report.os}")
    print(f"Python: {report.python_version} ({report.python_executable})")
    print(f"Expected Python: {report.expected_python_version} ({report.python_version_status})")
    print(f"Virtual env: {report.virtual_env}")
    print(f"Dependency files: {', '.join(report.dependency_files) if report.dependency_files else 'missing'}")
    if report.selected_model_path or report.selected_model_kind or report.selected_required_package:
        print("\nSelected model:")
        print(f"- path: {report.selected_model_path or 'missing'}")
        print(f"- MODEL_KIND: {report.selected_model_kind or 'missing'}")
        print(f"- required package: {report.selected_required_package or 'missing'}")
        print(f"- package status: {report.selected_package_status or 'missing'}")
    print("\nPackages:")
    for package in report.packages:
        suffix = f" {package.version}" if package.version else ""
        expected = f" (expected: {package.required_version})" if package.required_version != "any" else ""
        print(f"- {package.name}: {package.status}{suffix}{expected}")
    if report.remote_mlflow:
        print("\nRemote MLflow server:")
        print(f"- tracking URI: {report.remote_mlflow.tracking_uri_status}")
        print(f"- status: {report.remote_mlflow.status}")
        print(f"- server version: {report.remote_mlflow.server_version or 'unchecked'}")
        print(f"- local version: {report.remote_mlflow.local_version or 'missing'}")
        print(f"- required version: {report.remote_mlflow.required_version or 'unchecked'}")
        if report.remote_mlflow.endpoint:
            print(f"- version endpoint: {report.remote_mlflow.endpoint}")
        if report.remote_mlflow.detail:
            print(f"- detail: {report.remote_mlflow.detail}")
    if report.requirements:
        print("\nDependency check from requirements.txt:")
        for item in report.requirements:
            installed = item.installed_version if item.installed_version else "missing"
            selected_note = ""
            if is_unselected_framework_requirement(item, report.selected_required_package):
                selected_note = ", ignored for selected model"
            print(
                f"- {item.name}: {item.status} "
                f"(required: {item.required_version}, installed: {installed}{selected_note})"
            )
    print("\nEnvironment variables:")
    for item in report.env_vars:
        print(f"- {item.name}: {item.status}")
    if report.ai_studio_env and Path(report.ai_studio_env.path).exists():
        print(f"\nai_studio.env: {report.ai_studio_env.path}")
        for item in report.ai_studio_env.key_status:
            print(f"- {item.name}: {item.status}")
    if report.model_settings:
        print(f"\nModel settings: {report.model_settings.path}")
        for item in report.model_settings.key_status:
            print(f"- {item.name}: {item.status}")
    if report.source_input_required:
        source_path = report.model_settings.path if report.model_settings else "run_model.py, runtest.py 또는 aiu_studio/runtest.py"
        print(f"\n입력이 필요한 {len(report.source_input_required)}개 값:")
        print(f"- 사용자가 직접 소스에 입력: {source_path}")
        for item in report.source_input_required:
            suffix = " (값은 출력하지 않음)" if item.name == "mlflow_tracking_password" else ""
            print(f"- {item.name}: {item.status}{suffix}")
    if report.export_ready:
        print("\nEnvironment export readiness:")
        for item in report.export_ready:
            print(f"- {item.name}: {item.status}")
    if report.tod_guide:
        print("\nTOD Guide:")
        for step in report.tod_guide:
            print(f"- {step}")
    if report.blocked_summary:
        print("\n차단 항목 요약:")
        for index, item in enumerate(report.blocked_summary, start=1):
            print(f"{index}. {item}")
    if report.failures:
        print("\nFailures:")
        for failure in report.failures:
            print(f"- {failure}")
    if report.next_steps:
        print("\nNext steps:")
        for step in report.next_steps:
            print(f"- {step}")


def main():
    parser = argparse.ArgumentParser(description="Check local ML project execution environment and ai_studio.env settings.")
    parser.add_argument("--project", default=".", help="model project folder")
    parser.add_argument("--entrypoint", help="actual local training/model creation file, such as run.py")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    if not project.exists():
        raise FileNotFoundError(f"project folder not found: {project}")

    report = build_report(project, args.entrypoint)
    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print_text(report)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
