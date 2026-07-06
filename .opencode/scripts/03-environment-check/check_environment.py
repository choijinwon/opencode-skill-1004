import argparse
import ast
import base64
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from common.ai_studio_process import AI_STUDIO_PROCESS_STEPS, format_todo_guide, print_copy_block, print_markdown_table
from common.mlflow_settings import (
    AI_STUDIO_ENV_KEYS,
    EXPORT_ENV_MAP,
    default_env_text,
    parse_env_file,
    parse_python_string_assignments,
    parse_setting_env_file,
    setting_env_file,
    todo_placeholder,
)
from common.selected_model_info import normalize_path_text
from common.workspace import is_filesystem_root, is_opencode_sample_source, resolve_workspace_project, unique_paths

ROOT = Path(__file__).resolve().parents[2]
PREPARE_SELECTED_MODEL_SCRIPT = ROOT / "scripts" / "05-train-model" / "prepare_selected_model.py"
PROJECT_PREPARE_SELECTED_MODEL_SCRIPT = Path(".opencode") / "scripts" / "05-train-model" / "prepare_selected_model.py"

ENV_KEYS = [
    "MLFLOW_TRACKING_URI",
    "MLFLOW_TRACKING_USERNAME",
    "MLFLOW_TRACKING_PASSWORD",
    "MLFLOW_EXPERIMENT_NAME",
    "MLFLOW_REGISTER_MODEL_NAME",
    "MLFLOW_EXPERIMENT_ID",
]

MODEL_SETTING_FILES = [
    "runtest_2.py",
    "runtest.py",
    "run_test.py",
    "run_model.py",
    "run.py",
]
ENTRYPOINTS = [
    "runtest_2.py",
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
    "runtest_2.py",
    "runtest.py",
    "run_test.py",
    "train.py",
    "run_model.py",
    "predict.py",
    "input_example.json",
    "MLmodel",
]

ARTIFACT_SUFFIXES = {".pkl", ".joblib", ".pt", ".pth", ".ckpt", ".h5", ".keras", ".onnx", ".safetensors", ".bst", ".ubj"}
ARTIFACT_DIRS = ["ai_studio", "saved_model", "model", "artifacts"]
MODEL_SCAN_SKIP_DIRS = {
    ".git",
    ".mlflow-local",
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
AUTO_GENERATED_REQUIREMENTS_PACKAGE_NAMES = {
    "joblib",
    "kserve",
    "mlflow",
    "numpy",
    "onnxruntime",
    "pandas",
    "requests",
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
MODEL_KIND_BY_SUFFIX = {
    ".pkl": "sklearn_pickle",
    ".joblib": "sklearn_joblib",
    ".pt": "pytorch",
    ".pth": "pytorch",
    ".ckpt": "pytorch",
    ".onnx": "onnx",
    ".h5": "tensorflow_h5",
    ".keras": "tensorflow_keras",
    ".safetensors": "safetensors",
    ".bst": "xgboost_bst",
    ".ubj": "xgboost_ubj",
}
MODEL_KIND_REQUIREMENT_MAP = {
    "sklearn_pickle": ["joblib==1.5.1", "scikit-learn==1.7.0"],
    "sklearn_joblib": ["joblib==1.5.1", "scikit-learn==1.7.0"],
    "pytorch": ["torch==2.12.1"],
    "onnx": ["onnxruntime"],
    "tensorflow_keras": ["tensorflow"],
    "tensorflow_h5": ["tensorflow"],
    "safetensors": ["safetensors==0.5.3"],
    "xgboost_bst": ["xgboost==3.0.2"],
    "xgboost_ubj": ["xgboost==3.0.2"],
}
MODEL_KIND_MANUAL_REQUIREMENT_MAP = {
    "tensorflow_keras": ["tensorflow==2.19.0"],
    "tensorflow_h5": ["tensorflow==2.19.0"],
    "onnx": ["onnxruntime==1.22.1"],
    "pytorch": ["numpy==1.26.4", "torch==2.7.1", "torchvision==0.22.1", "torchmetrics==1.7.3"],
    "safetensors": ["numpy==1.26.4", "torch==2.7.1", "safetensors==0.5.3"],
    "sklearn_pickle": ["scikit-learn==1.7.0", "joblib==1.5.1"],
    "sklearn_joblib": ["scikit-learn==1.7.0", "joblib==1.5.1"],
    "xgboost_bst": ["xgboost==3.0.2"],
    "xgboost_ubj": ["xgboost==3.0.2"],
}
IMAGE_MODEL_KEYWORDS = (
    "cnn",
    "mnist",
    "fashionmnist",
    "image",
    "vision",
    "resnet",
    "yolo",
    "unet",
    "vit",
    "segmentation",
    "detection",
)
IMAGE_MODEL_KINDS = {
    "pytorch",
    "safetensors",
    "onnx",
    "tensorflow_keras",
    "tensorflow_h5",
    "tensorflow_saved_model",
}
IMAGE_MODEL_MANUAL_REQUIREMENT_MAP = {
    "pytorch": ["pillow==12.3.0", "matplotlib==3.11.0"],
    "safetensors": ["pillow==12.3.0", "matplotlib==3.11.0"],
    "onnx": ["pillow==12.3.0", "matplotlib==3.11.0"],
    "tensorflow_keras": ["pillow==12.3.0", "matplotlib==3.11.0"],
    "tensorflow_h5": ["pillow==12.3.0", "matplotlib==3.11.0"],
    "tensorflow_saved_model": ["pillow==12.3.0", "matplotlib==3.11.0"],
}

PYTHON_COMPATIBILITY_BASELINE = "MLflow/requirements compatibility"
LEGACY_EXPECTED_PYTHON_VERSION = "3.11.9"
REQUIRED_REQUIREMENTS_FILE = Path(__file__).resolve().parent / "requirements.required.txt"
MANDATORY_REQUIREMENT_VERSIONS = {
    "mlflow": "",
    "kserve": "==0.15.0",
}
MANDATORY_REQUIREMENT_NAMES = {"mlflow", "kserve"}


def load_required_requirement_versions() -> dict[str, str]:
    fallback = dict(MANDATORY_REQUIREMENT_VERSIONS)
    if not REQUIRED_REQUIREMENTS_FILE.exists():
        return fallback
    versions: dict[str, str] = {}
    for raw_line in REQUIRED_REQUIREMENTS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not any(operator in line for operator in ("==", "!=", ">=", "<=", "~=", ">", "<")):
            name = line.strip().lower().replace("_", "-")
            if name:
                versions[name] = ""
            continue
        for operator in ("==", "!=", ">=", "<=", "~=", ">", "<"):
            if operator in line:
                name, version = line.split(operator, 1)
                name = name.strip().lower().replace("_", "-")
                if name:
                    versions[name] = f"{operator}{version.strip()}"
                break
    merged = dict(fallback)
    merged.update(versions)
    return merged


EXPECTED_PACKAGE_VERSIONS = load_required_requirement_versions()
def python_compatible_expected_package_versions(python_version: str) -> dict[str, str]:
    versions = dict(EXPECTED_PACKAGE_VERSIONS)
    return versions


def apply_mlflow_environment_version(
    versions: dict[str, str],
    remote_mlflow: "RemoteMlflowStatus | None" = None,
) -> dict[str, str]:
    versions = dict(versions)
    if remote_mlflow and remote_mlflow.server_version:
        versions["mlflow"] = f"=={remote_mlflow.server_version}"
        return versions
    versions["mlflow"] = ""
    return versions
LOCAL_IMPORT_ROOTS = {"aiu_custom"}
REQUIREMENT_SCAN_FILES = [
    "runtest_2.py",
    "aiu_custom/model.py",
    "aiu_custom/predict.py",
    "inferencetest.py",
]
REQUIREMENT_OPERATORS = ["==", "!=", ">=", "<=", "~=", ">", "<"]
IMPORT_REQUIREMENT_MAP = {
    "cv2": "opencv-python",
    "databricks": "databricks-sdk",
    "joblib": "joblib==1.5.1",
    "keras": "tensorflow",
    "kserve": "kserve==0.15.0",
    "matplotlib": "matplotlib",
    "mlflow": "mlflow",
    "numpy": "numpy",
    "onnxruntime": "onnxruntime",
    "pandas": "pandas",
    "PIL": "pillow",
    "requests": "requests==2.32.4",
    "requests_oauthlib": "requests-oauthlib",
    "safetensors": "safetensors==0.5.3",
    "sklearn": "scikit-learn==1.7.0",
    "smart_open": "smart-open",
    "tensorflow": "tensorflow",
    "torch": "torch",
    "torchmetrics": "torchmetrics",
    "torchvision": "torchvision",
    "transformers": "transformers",
    "xgboost": "xgboost==3.0.2",
    "yaml": "pyyaml",
}
REMOTE_MLFLOW_VERSION_ENDPOINTS = [
    "version",
    "api/2.0/mlflow/version",
]
REMOTE_MLFLOW_TIMEOUT_SECONDS = 3
PS_CHECK_ENV_COMMAND = r"python .opencode/scripts/03-environment-check/check_environment.py --project . --entrypoint runtest_2.py"
PS_PREPARE_SELECTED_COMMAND = r"python .opencode/scripts/05-train-model/prepare_selected_model.py --project . --model selected --execute"
PS_RUN_TRAINING_COMMAND = r"python .opencode/scripts/05-train-model/run_training.py --project . --entrypoint runtest_2.py --execute"
PS_INFERENCE_COMMAND = r"python inferencetest.py"


def windows_path_text(path: str | Path) -> str:
    return str(path).replace("/", "\\")


def powershell_quote_text(value: str | Path) -> str:
    return "'" + windows_path_text(value).replace("'", "''") + "'"


def prepare_selected_model_script_for_project(project: Path) -> Path:
    project_local_script = project / PROJECT_PREPARE_SELECTED_MODEL_SCRIPT
    if project_local_script.is_file():
        return PROJECT_PREPARE_SELECTED_MODEL_SCRIPT
    return PROJECT_PREPARE_SELECTED_MODEL_SCRIPT


def powershell_prepare_selected_command(project: Path) -> str:
    script = prepare_selected_model_script_for_project(project)
    return (
        f"python {powershell_quote_text(script)} "
        "--project . --model selected --execute"
    )


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
class RequirementCandidate:
    package: str
    source: str


@dataclass
class PipDryRunPackageResult:
    package: str
    status: str
    detail: str = ""
    requires_python: str | None = None
    alternatives: list[str] = field(default_factory=list)


@dataclass
class PipDryRunStatus:
    selected_python_version: str
    current_python_version: str
    command: str
    status: str
    return_code: int | None = None
    summary: str | None = None
    package_results: list[PipDryRunPackageResult] = field(default_factory=list)
    output_lines: list[str] = field(default_factory=list)


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
    server_deploy_errors: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    tod_guide: list[str] = field(default_factory=list)
    source_input_required: list[EnvVarStatus] = field(default_factory=list)
    selected_model_path: str | None = None
    selected_model_kind: str | None = None
    selected_required_package: str | None = None
    selected_package_status: str | None = None
    remote_mlflow: RemoteMlflowStatus | None = None
    selected_python_version: str | None = None
    requirement_candidates: list[RequirementCandidate] = field(default_factory=list)
    selected_model_recommendations: list[str] = field(default_factory=list)
    image_model_recommendations: list[str] = field(default_factory=list)
    pip_dry_run: PipDryRunStatus | None = None
    requirements_updated: list[str] = field(default_factory=list)
    package_auto_fix_attempted: bool = False
    package_auto_fix_return_code: int | None = None
    template_auto_run_attempted: bool = False
    template_auto_run_return_code: int | None = None
    template_auto_run_output: list[str] = field(default_factory=list)


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def server_deploy_error_items(failures: list[str], blocked_summary: list[str]) -> list[str]:
    if not failures:
        return []

    items: list[str] = []
    for item in blocked_summary:
        if item not in items:
            items.append(item)

    missing_env_names = []
    missing_package_names = []
    version_mismatch_names = []
    for failure in failures:
        if failure.startswith("missing_env:"):
            missing_env_names.append(failure.split(":", 1)[1])
        elif failure.startswith("missing_requirements:"):
            missing_package_names.extend(name for name in failure.split(":", 1)[1].split(",") if name)
        elif failure.startswith("version_mismatch_requirements:"):
            version_mismatch_names.extend(name for name in failure.split(":", 1)[1].split(",") if name)
        elif failure.startswith("missing_dependency:"):
            package_name = failure.split(":", 1)[1]
            if package_name.startswith("selected_model:"):
                items.append("선택 모델 패키지 확인 필요 → " + package_name.split(":", 1)[1])
            else:
                missing_package_names.append(package_name)
        elif failure.startswith("version_mismatch:mlflow"):
            items.append("MLflow 서버/로컬 버전 불일치 → 서버 버전에 맞춰 로컬 mlflow 버전을 조정하세요.")
        elif failure.startswith("selected_python_version_diff:"):
            items.append("현재 Python과 선택 Python 버전이 다름 → requirements 호환성을 확인하세요.")
        elif failure.startswith("entrypoint_not_found:"):
            items.append("실행 파일 경로를 찾을 수 없음 → " + failure.split(":", 1)[1])
        elif failure == "entrypoint_not_found":
            items.append("실행 파일 경로를 찾을 수 없음 → 실제 사용하는 Python 파일을 지정하세요.")
        elif failure == "entrypoint_outside_project":
            items.append("실행 파일 경로 오류 → 선택한 프로젝트 폴더 밖의 파일은 사용할 수 없습니다.")
        elif failure == "selected_model_outside_project":
            items.append("모델 경로 오류 → 선택 모델은 현재 프로젝트 폴더 안에 있어야 합니다.")
        elif failure == "selected_model_config_missing":
            items.append("선택 모델 고정 정보 없음 → config/config.json 기준으로 2~3번을 다시 실행하세요.")
        elif failure.startswith("selected_model_path_missing:"):
            items.append("모델 경로 누락 → config/config.json의 선택 모델 경로를 확인하세요.")
        elif failure.startswith("selected_model_config_path_mismatch:"):
            items.append("모델 경로 불일치 → config/config.json의 모델 경로가 선택 모델과 다릅니다.")
        elif failure.startswith("selected_model_conversion_missing:"):
            items.append("생성 파일 경로를 찾을 수 없음 → " + failure.split(":", 1)[1])
        elif failure.startswith("reference_entrypoint_missing:"):
            items.append("참조 실행 파일 경로를 찾을 수 없음 → runtest.py 또는 run_test.py를 확인하세요.")
        elif failure.startswith("model_py_mapping_loader_missing:"):
            items.append("모델 로더 경로 설정 누락 → aiu_custom/model.py와 config/config.json을 다시 생성하세요.")
        elif failure == "missing_dependency_file":
            items.append("의존성 파일 없음 → requirements.txt, pyproject.toml, environment.yml 중 하나를 확인하세요.")
        elif failure.startswith("missing_model_settings_file:"):
            items.append("MLflow 설정 파일 없음 → 현재 워크스페이스 루트의 .env에 5개 값을 입력하세요.")

    if missing_env_names:
        items.append("환경변수 입력 필요 → " + ", ".join(sorted(set(missing_env_names))))
    if missing_package_names:
        items.append("패키지 확인 필요 → " + ", ".join(sorted(set(missing_package_names))))
    if version_mismatch_names:
        items.append("패키지 버전 불일치 → " + ", ".join(sorted(set(version_mismatch_names))))

    unique_items = []
    for item in items:
        if item not in unique_items:
            unique_items.append(item)
    return unique_items


def normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def unique_preserve_order(items: list[str]) -> list[str]:
    unique_items: list[str] = []
    for item in items:
        if item not in unique_items:
            unique_items.append(item)
    return unique_items


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


def normalize_requirement_file_line(line: str) -> str:
    # requirements.txt에는 torch==...+cpu 같은 wheel local tag를 쓰지 않는다.
    # CPU wheel 선택은 내부 Nexus/pip index 설정에서 처리하고, 파일은 표준 고정 버전만 유지한다.
    return re.sub(
        r"(?i)(==\s*[^,;\s#]+?)\+(cpu|cup|cu\d+)(?=\s*(?:[,;#]|$))",
        r"\1",
        line,
    )


def parse_requirement_line(raw_line: str) -> tuple[str, str] | None:
    line = strip_inline_comment(normalize_requirement_file_line(raw_line))
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


def requirements_guidance_text(expected_package_versions: dict[str, str] | None = None) -> str:
    expected_package_versions = expected_package_versions or EXPECTED_PACKAGE_VERSIONS
    mlflow_spec = expected_package_versions.get("mlflow", "")
    kserve_spec = expected_package_versions.get("kserve", "==0.15.0")
    lines = [
        "# Add project-specific packages below.",
        "# Example: torch==2.7.1",
        f"mlflow{mlflow_spec}",
        f"kserve{kserve_spec}",
    ]
    return "\n".join(lines).rstrip() + "\n"


def selected_model_manual_requirements(model_kind: str | None) -> list[str]:
    if not model_kind:
        return []
    required_names = {normalize_package_name(name) for name in EXPECTED_PACKAGE_VERSIONS}
    return [
        requirement
        for requirement in MODEL_KIND_MANUAL_REQUIREMENT_MAP.get(model_kind, [])
        if normalize_package_name(requirement.split("==", 1)[0]) not in required_names
    ]


def filter_existing_requirement_recommendations(
    requirements: list[str],
    existing_statuses: list["RequirementStatus"],
) -> list[str]:
    existing_names = {
        normalize_package_name(item.name)
        for item in existing_statuses
        if item.source == "requirements.txt"
    }
    return [
        requirement
        for requirement in requirements
        if normalize_package_name(requirement.split("==", 1)[0]) not in existing_names
    ]


def looks_like_image_model(selected_path: str | None, model_kind: str | None) -> bool:
    if not selected_path or model_kind not in IMAGE_MODEL_KINDS:
        return False
    model_text = (
        str(selected_path)
        .replace("\\", "/")
        .replace("＼", "/")
        .replace("￦", "/")
        .replace("₩", "/")
        .lower()
    )
    return any(keyword in model_text for keyword in IMAGE_MODEL_KEYWORDS)


def selected_image_model_manual_requirements(selected_path: str | None, model_kind: str | None) -> list[str]:
    if model_kind not in IMAGE_MODEL_KINDS:
        return []
    return list(IMAGE_MODEL_MANUAL_REQUIREMENT_MAP.get(model_kind or "", []))


def is_legacy_generated_requirements(existing_lines: list[str]) -> bool:
    package_names: list[str] = []
    for line in existing_lines:
        parsed = parse_requirement_line(line)
        if parsed is None:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return False
            continue
        package_names.append(parsed[0])
    if not package_names:
        return False
    return all(name in AUTO_GENERATED_REQUIREMENTS_PACKAGE_NAMES for name in package_names)


def is_stdlib_module(name: str) -> bool:
    root = name.split(".", 1)[0]
    stdlib_names = getattr(sys, "stdlib_module_names", set())
    return root in stdlib_names or root in set(sys.builtin_module_names)


def requirement_package_name(requirement: str) -> str | None:
    parsed = parse_requirement_line(requirement)
    if parsed is None:
        return None
    return parsed[0]


def pin_requirement(requirement: str, expected_package_versions: dict[str, str] | None = None) -> str:
    expected_package_versions = expected_package_versions or EXPECTED_PACKAGE_VERSIONS
    requirement = normalize_requirement_file_line(requirement)
    parsed = parse_requirement_line(requirement)
    if parsed is None:
        return requirement
    name, spec = parsed
    if spec:
        return requirement
    expected = expected_package_versions.get(name)
    if expected:
        return f"{name}{expected}"
    installed = package_version(name)
    if installed:
        return normalize_requirement_file_line(f"{name}=={installed}")
    return requirement


def import_roots_from_file(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return set()
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root:
                    roots.add(root)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".", 1)[0]
            if root:
                roots.add(root)
    return roots


def inferred_requirements_from_imports(project: Path, expected_package_versions: dict[str, str] | None = None) -> list[str]:
    expected_package_versions = expected_package_versions or EXPECTED_PACKAGE_VERSIONS
    requirements: list[str] = []
    seen: set[str] = set()
    for relative in REQUIREMENT_SCAN_FILES:
        path = project / relative
        for root in sorted(import_roots_from_file(path)):
            if root in LOCAL_IMPORT_ROOTS or is_stdlib_module(root):
                continue
            raw_requirement = IMPORT_REQUIREMENT_MAP.get(root)
            if raw_requirement is None:
                continue
            requirement = pin_requirement(raw_requirement, expected_package_versions)
            package_name = requirement_package_name(requirement)
            key = package_name or normalize_package_name(requirement)
            if key in seen:
                continue
            seen.add(key)
            requirements.append(requirement)
    return requirements


def required_requirement_lines(expected_package_versions: dict[str, str] | None = None) -> list[str]:
    expected_package_versions = expected_package_versions or EXPECTED_PACKAGE_VERSIONS
    lines: list[str] = []
    for name, specifier in expected_package_versions.items():
        lines.append(f"{name}{specifier}")
    return lines


def model_kind_requirement_lines(model_kind: str | None, expected_package_versions: dict[str, str] | None = None) -> list[str]:
    if not model_kind:
        return []
    expected_package_versions = expected_package_versions or EXPECTED_PACKAGE_VERSIONS
    requirements = MODEL_KIND_REQUIREMENT_MAP.get(model_kind, [])
    return [pin_requirement(requirement, expected_package_versions) for requirement in requirements]


def selected_allowed_framework_packages(selected_model_requirements: list[str]) -> set[str]:
    allowed: set[str] = set()
    for requirement in selected_model_requirements:
        package_name = requirement_package_name(requirement)
        if package_name:
            allowed.add(package_name)
    return allowed


def should_keep_framework_requirement(package_name: str, selected_allowed_frameworks: set[str] | None) -> bool:
    if selected_allowed_frameworks is None:
        return True
    if package_name not in FRAMEWORK_PACKAGES:
        return True
    return package_name in selected_allowed_frameworks


def update_requirements_from_imports(
    project: Path,
    expected_package_versions: dict[str, str] | None = None,
    selected_model_kind: str | None = None,
) -> list[str]:
    expected_package_versions = expected_package_versions or EXPECTED_PACKAGE_VERSIONS
    requirements_path = project / "requirements.txt"
    changed_requirements: list[str] = []
    required_lines = required_requirement_lines(expected_package_versions)
    required_by_name = {
        package_name: requirement
        for requirement in required_lines
        for package_name in [requirement_package_name(requirement)]
        if package_name is not None
    }

    if not requirements_path.exists():
        requirements_path.write_text(requirements_guidance_text(expected_package_versions), encoding="utf-8")
        return ["requirements.txt created with mlflow/kserve base items"]

    existing_lines = requirements_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    updated_lines: list[str] = []
    seen_names: set[str] = set()

    for line in existing_lines:
        normalized_line = normalize_requirement_file_line(line)
        parsed = parse_requirement_line(normalized_line)
        if parsed is None:
            updated_lines.append(normalized_line)
            continue
        package_name, _specifier = parsed
        required_requirement = required_by_name.get(package_name)
        if required_requirement is not None:
            updated_lines.append(required_requirement)
            seen_names.add(package_name)
            if normalized_line.strip() != required_requirement:
                changed_requirements.append(required_requirement)
            continue
        updated_lines.append(normalized_line)
        seen_names.add(package_name)

    for requirement in required_lines:
        package_name = requirement_package_name(requirement)
        if package_name is None or package_name in seen_names:
            continue
        updated_lines.append(requirement)
        changed_requirements.append(requirement)
        seen_names.add(package_name)

    updated_text = "\n".join(updated_lines).rstrip()
    previous_text = requirements_path.read_text(encoding="utf-8", errors="ignore").rstrip()
    if previous_text == updated_text:
        return []

    requirements_path.write_text(updated_text + "\n", encoding="utf-8")
    return changed_requirements


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


def selected_model_config_candidates(project: Path) -> list[Path]:
    candidates: list[Path] = []
    root_config = project / "config" / "config.json"
    if root_config.is_file():
        candidates.append(root_config)
    if project.is_dir():
        for child in sorted(project.iterdir(), key=lambda path: path.name.lower()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            config_path = child / "config" / "config.json"
            if config_path.is_file():
                candidates.append(config_path)
    return sorted(candidates, key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)


def infer_model_kind_from_path(path_text: str | None) -> str | None:
    if not path_text:
        return None
    suffix = Path(normalize_path_text(path_text)).suffix.lower()
    return MODEL_KIND_BY_SUFFIX.get(suffix)


def selected_model_project(project: Path) -> Path:
    candidates = selected_model_config_candidates(project)
    if not candidates:
        return project
    return candidates[0].parents[1]


def selected_model_status_from_input_example(project: Path) -> tuple[str | None, str | None, str | None, str | None]:
    saved_model_dir = project / "saved_model"
    if not saved_model_dir.is_dir():
        return None, None, None, None
    saved_models = [
        path
        for path in sorted(saved_model_dir.iterdir(), key=lambda item: item.name.lower())
        if path.is_file() or path.is_dir()
        if infer_model_kind_from_path(path.name)
    ]
    if not saved_models:
        return None, None, None, None
    saved_model = saved_models[0]
    workspace_project = project.parent
    data_root = workspace_project / "data"
    source_matches: list[Path] = []
    if data_root.is_dir():
        for path in data_root.rglob(saved_model.name):
            if path.is_file() or path.is_dir():
                source_matches.append(path)
    selected_path = (
        normalize_path_text(os.path.relpath(source_matches[0], workspace_project))
        if len(source_matches) == 1
        else f"saved_model/{saved_model.name}"
    )
    model_kind = infer_model_kind_from_path(saved_model.name)
    required_package = MODEL_KIND_REQUIRED_PACKAGE.get(model_kind) if isinstance(model_kind, str) else None
    normalized_package = normalize_package_name(required_package) if isinstance(required_package, str) else None
    package_status = "set" if normalized_package and package_version(normalized_package) else ("missing" if normalized_package else None)
    return (
        selected_path if isinstance(selected_path, str) else None,
        model_kind if isinstance(model_kind, str) else None,
        normalized_package,
        package_status,
    )


def selected_model_status(project: Path) -> tuple[str | None, str | None, str | None, str | None]:
    candidates = selected_model_config_candidates(project)
    if not candidates:
        return selected_model_status_from_input_example(project)
    config_path = candidates[0]
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return selected_model_status_from_input_example(config_path.parents[1])
    model = payload.get("model") if isinstance(payload, dict) else None
    if not isinstance(model, dict):
        return selected_model_status_from_input_example(config_path.parents[1])
    selected_path = model.get("source_path") or model.get("original_path") or model.get("relative_path") or model.get("model_relative_path") or model.get("runtime_model_path")
    model_kind = model.get("model_kind") or model.get("kind") or infer_model_kind_from_path(
        selected_path if isinstance(selected_path, str) else None
    )
    required_package = model.get("required_package")
    if isinstance(required_package, str) and required_package == "unknown":
        required_package = None
    if isinstance(model_kind, str) and not required_package:
        required_package = MODEL_KIND_REQUIRED_PACKAGE.get(model_kind)
    normalized_package = normalize_package_name(required_package) if isinstance(required_package, str) else None
    package_status = "set" if normalized_package and package_version(normalized_package) else ("missing" if normalized_package else None)
    return (
        selected_path if isinstance(selected_path, str) else None,
        model_kind if isinstance(model_kind, str) else None,
        normalized_package,
        package_status,
    )


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


def normalize_python_version_text(value: str | None, fallback: str) -> str:
    text = (value or "").strip()
    if not text:
        return fallback
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?$", text)
    if not match:
        return fallback
    major, minor, patch = match.group(1), match.group(2), match.group(3)
    if patch is None:
        return f"{major}.{minor}"
    return f"{major}.{minor}.{patch}"


def requirement_candidates(project: Path, expected_package_versions: dict[str, str] | None = None) -> list[RequirementCandidate]:
    expected_package_versions = expected_package_versions or EXPECTED_PACKAGE_VERSIONS
    candidates: list[RequirementCandidate] = []
    seen: set[str] = set()
    for requirement in required_requirement_lines(expected_package_versions):
        package_name = requirement_package_name(requirement)
        if package_name is None or package_name in seen:
            continue
        seen.add(package_name)
        candidates.append(RequirementCandidate(requirement, "base"))
    for requirement in inferred_requirements_from_imports(project, expected_package_versions):
        package_name = requirement_package_name(requirement)
        if package_name is None or package_name in seen:
            continue
        seen.add(package_name)
        candidates.append(RequirementCandidate(requirement, "import"))
    return candidates


def parse_pip_dry_run_output(output: str, requirements_path: Path) -> list[PipDryRunPackageResult]:
    results: list[PipDryRunPackageResult] = []
    current_package: str | None = None
    current_requires: str | None = None
    current_alternatives: list[str] = []
    current_detail: list[str] = []

    def flush_current(status: str = "error") -> None:
        nonlocal current_package, current_requires, current_alternatives, current_detail
        if current_package is None:
            return
        results.append(
            PipDryRunPackageResult(
                package=current_package,
                status=status,
                detail=" ".join(current_detail).strip(),
                requires_python=current_requires,
                alternatives=current_alternatives[:8],
            )
        )
        current_package = None
        current_requires = None
        current_alternatives = []
        current_detail = []

    for raw_line in output.splitlines():
        line = raw_line.strip()
        package_match = re.search(r"Could not find a version that satisfies the requirement ([A-Za-z0-9_.-]+)", line)
        if package_match:
            flush_current()
            current_package = normalize_package_name(package_match.group(1))
            current_detail.append(line)
            continue
        if current_package:
            if "Requires-Python" in line:
                requires_match = re.search(r"Requires-Python\s*([^\s,;]+)", line)
                if requires_match:
                    current_requires = requires_match.group(1)
                current_detail.append(line)
                continue
            versions_match = re.search(r"from versions:\s*(.+)$", line)
            if versions_match:
                current_alternatives = [item.strip() for item in versions_match.group(1).split(",") if item.strip()]
                current_detail.append(line)
                continue
            if line.startswith("ERROR:"):
                current_detail.append(line)
                continue
    flush_current()

    if results:
        return results

    if "Would install" in output or "Requirement already satisfied" in output or "Successfully installed" in output:
        package_results: list[PipDryRunPackageResult] = []
        if requirements_path.exists():
            for raw_line in requirements_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                parsed = parse_requirement_line(raw_line)
                if parsed is None:
                    continue
                package_results.append(PipDryRunPackageResult(package=parsed[0], status="ok"))
        return package_results
    return []


def run_pip_dry_run_check(project: Path, selected_python_version: str) -> PipDryRunStatus:
    requirements_path = project / "requirements.txt"
    current_python_version = platform.python_version()
    command = (
        f"{sys.executable} -m pip install -r requirements.txt --dry-run "
        f"--ignore-installed --python-version {selected_python_version} --only-binary=:all:"
    )
    if not requirements_path.exists():
        return PipDryRunStatus(
            selected_python_version=selected_python_version,
            current_python_version=current_python_version,
            command=command,
            status="missing_requirements",
            summary="requirements.txt not found",
        )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            "requirements.txt",
            "--dry-run",
            "--ignore-installed",
            "--python-version",
            selected_python_version,
            "--only-binary=:all:",
        ],
        cwd=project,
        capture_output=True,
        text=True,
    )
    output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
    package_results = parse_pip_dry_run_output(output, requirements_path)
    summary = "selected Python version dry-run passed" if completed.returncode == 0 else "selected Python version dry-run failed"
    status = "pass" if completed.returncode == 0 else "error"
    if any("Temporary failure" in line or "Connection" in line or "No matching distribution found for" in line for line in output.splitlines()):
        status = "error" if completed.returncode else "pass"
    if any("Failed to establish a new connection" in line or "Name or service not known" in line or "Operation not permitted" in line for line in output.splitlines()):
        status = "unreachable"
        summary = "dry-run skipped: package index unreachable"
    return PipDryRunStatus(
        selected_python_version=selected_python_version,
        current_python_version=current_python_version,
        command=command,
        status=status,
        return_code=completed.returncode,
        summary=summary,
        package_results=package_results,
        output_lines=[line for line in output.splitlines() if line.strip()][:40],
    )


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
    for root, dirs, files in os.walk(project):
        root_path = Path(root)
        try:
            relative_parts = root_path.relative_to(project).parts
        except ValueError:
            dirs[:] = []
            continue
        if any(part in MODEL_SCAN_SKIP_DIRS for part in relative_parts):
            dirs[:] = []
            continue
        dirs[:] = [dirname for dirname in dirs if dirname not in MODEL_SCAN_SKIP_DIRS]
        for filename in files:
            path = root_path / filename
            if path.suffix.lower() in ARTIFACT_SUFFIXES:
                found.append(path)
    return sorted(set(found))


def is_sample_project(project: Path) -> bool:
    return project.name in SAMPLE_PROJECT_NAMES


def find_entrypoint_candidates(project: Path) -> list[Path]:
    found = []
    for name in ENTRYPOINTS:
        candidate = project / name
        if candidate.exists() and candidate.is_file():
            found.append(candidate)
    found.extend(sorted(path for path in project.glob("*.py") if path.is_file()))
    return unique_paths(found)


def ensure_setting_env_file(project: Path) -> Path:
    path = project / ".env"
    if path.exists():
        return path
    path.write_text(default_env_text(), encoding="utf-8")
    return path


def usable_setting_value(value: str | None) -> str | None:
    if value is None or value == "" or todo_placeholder(value):
        return None
    return value


def resolved_mlflow_settings(project: Path, entrypoint_name: str | None = None) -> dict[str, str]:
    values: dict[str, str] = {}

    setting_file = resolve_setting_file(project, entrypoint_name)
    if setting_file is not None and setting_file.exists():
        source_values = parse_python_string_assignments(setting_file)
        for key in AI_STUDIO_ENV_KEYS:
            value = usable_setting_value(source_values.get(key))
            if value is not None:
                values[key] = value

    for setting_key, env_key in EXPORT_ENV_MAP.items():
        value = usable_setting_value(os.environ.get(env_key))
        if value is not None:
            values[setting_key] = value

    env_file_values = parse_setting_env_file(setting_env_file(project))
    for key in AI_STUDIO_ENV_KEYS:
        value = usable_setting_value(env_file_values.get(key))
        if value is not None:
            values[key] = value
    return values


def setting_value_status(key: str, value: str | None, missing_status: str = "missing") -> str:
    if value is None:
        return missing_status
    if value == "":
        return "empty"
    if todo_placeholder(value):
        return "missing"
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
    tracking_uri = settings.get("mlflow_tracking_uri")
    local_version = package_version("mlflow")

    if tracking_uri is None:
        return RemoteMlflowStatus(
            tracking_uri_status="missing",
            status="skipped",
            local_version=local_version,
            detail="mlflow_tracking_uri is missing",
        )
    lowered_tracking_uri = tracking_uri.lower()
    if lowered_tracking_uri.startswith(("file://", "sqlite:")):
        return RemoteMlflowStatus(
            tracking_uri_status="unsupported",
            status="skipped",
            local_version=local_version,
            detail="local file/sqlite tracking URI is not allowed for AI Studio deployment; use remote MLflow/report URL",
        )
    if not lowered_tracking_uri.startswith(("http://", "https://")):
        return RemoteMlflowStatus(
            tracking_uri_status="unsupported",
            status="skipped",
            local_version=local_version,
            detail="tracking URI must start with http:// or https:// for remote version check",
        )
    parsed = urllib.parse.urlparse(tracking_uri)
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        return RemoteMlflowStatus(
            tracking_uri_status="unsupported",
            status="skipped",
            local_version=local_version,
            detail="localhost/127.0.0.1 tracking URI is not allowed for step 5; use remote MLflow/report URL",
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
    path = setting_env_file(project)
    values = parse_setting_env_file(path)
    statuses = []
    for key in AI_STUDIO_ENV_KEYS:
        status = setting_value_status(key, values.get(key) if key in values else None)
        statuses.append(EnvVarStatus(key, status))
    return EnvFileStatus(str(path), statuses)


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
    values = resolved_mlflow_settings(project, entrypoint_name)
    statuses = []
    for setting_key, env_key in EXPORT_ENV_MAP.items():
        value = values.get(setting_key)
        if value:
            status = "set"
        elif env_status(env_key) == "set":
            status = "exported"
        else:
            status = "missing"
        statuses.append(EnvVarStatus(env_key, status))
    return statuses


def source_input_required_status(model_settings: EnvFileStatus | None) -> list[EnvVarStatus]:
    if model_settings is None:
        return [EnvVarStatus(key, "missing") for key in AI_STUDIO_ENV_KEYS]
    required = []
    for item in model_settings.key_status:
        if item.name not in AI_STUDIO_ENV_KEYS:
            continue
        if item.status in {"missing", "empty"}:
            required.append(item)
    return required


def build_report(project: Path, entrypoint_name: str | None = None, selected_python_version: str | None = None) -> EnvironmentReport:
    if is_filesystem_root(project):
        return EnvironmentReport(
            project_path=str(project),
            os=f"{platform.system()} {platform.release()}",
            python_executable=sys.executable,
            python_version=platform.python_version(),
            expected_python_version=PYTHON_COMPATIBILITY_BASELINE,
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
            next_steps=["선택한 워크스페이스 루트로 이동한 뒤 --project . 로 실행하세요."],
            tod_guide=[],
            source_input_required=[],
        )
    if is_opencode_sample_source(project):
        return EnvironmentReport(
            project_path=str(project),
            os=f"{platform.system()} {platform.release()}",
            python_executable=sys.executable,
            python_version=platform.python_version(),
            expected_python_version=PYTHON_COMPATIBILITY_BASELINE,
            python_version_status="blocked",
            virtual_env=os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX") or "not detected",
            dependency_files=[],
            packages=[],
            requirements=[],
            env_vars=[],
            ai_studio_env=None,
            model_settings=None,
            export_ready=[],
            blocked_summary=[".opencode/는 번들 스킬 원본이라 분석 대상이 아닙니다."],
            failures=["opencode_sample_source_not_analysis_target"],
            next_steps=["실제 사용자가 선택한 모델 프로젝트 폴더를 --project로 지정하세요."],
            tod_guide=[],
            source_input_required=[],
        )
    project = selected_model_project(project)
    python_version = platform.python_version()
    selected_python_version = normalize_python_version_text(selected_python_version, python_version)
    selected_path, selected_kind, selected_required_package, selected_package_status = selected_model_status(project)
    model_found = has_model_project(project)
    existing_model_flow = model_found and not is_sample_project(project)
    can_materialize_environment_files = not (existing_model_flow and selected_path is None)
    env_vars = [EnvVarStatus(key, env_status(key)) for key in ENV_KEYS]
    if can_materialize_environment_files:
        ensure_setting_env_file(project)
    ai_env = ai_studio_env_status(project)
    model_settings = model_settings_status(project, entrypoint_name)
    export_ready = export_ready_status(project, entrypoint_name)
    source_input_required = source_input_required_status(ai_env)
    remote_mlflow = check_remote_mlflow_version(project, entrypoint_name)
    effective_expected_package_versions = apply_mlflow_environment_version(
        python_compatible_expected_package_versions(python_version),
        remote_mlflow,
    )
    requirements_updated = []
    if can_materialize_environment_files:
        requirements_updated = update_requirements_from_imports(
            project,
            effective_expected_package_versions,
            selected_kind,
        )
    deps = dependency_files(project)
    requirements = requirement_statuses(project, effective_expected_package_versions)
    dry_run_status = None
    candidates = requirement_candidates(project, effective_expected_package_versions)
    requirement_spec_by_name = {
        item.name: item.required_version
        for item in requirements
    }
    selected_recommendations = selected_model_manual_requirements(selected_kind)
    image_model_recommendations = selected_image_model_manual_requirements(selected_path, selected_kind)
    packages = []
    package_names = unique_preserve_order(
        [
            item.name
            for item in requirements
            if not (existing_model_flow and is_unselected_framework_requirement(item, selected_required_package))
        ]
    )
    if selected_required_package and selected_required_package not in {normalize_package_name(name) for name in package_names}:
        package_names.append(selected_required_package)
    for package in package_names:
        version = package_version(package)
        normalized_package = normalize_package_name(package)
        required_spec = requirement_spec_by_name.get(normalized_package) or effective_expected_package_versions.get(normalized_package, "any")
        status = "missing" if version is None else ("set" if required_spec == "any" else version_constraint_status(version, required_spec))
        packages.append(PackageStatus(package, status, version, required_spec))
    blocked_summary: list[str] = []
    failures: list[str] = []
    next_steps: list[str] = []
    entrypoint_candidates = find_entrypoint_candidates(project)
    setting_file = None
    if model_settings is not None:
        setting_file = display_path(model_settings.path, project)
    entrypoint = setting_file
    if entrypoint is None and len(entrypoint_candidates) == 1:
        entrypoint = str(entrypoint_candidates[0].relative_to(project))
    if existing_model_flow:
        entrypoint_display = entrypoint or "사용자가 실제 사용하는 파일명"
        tod_guide = [
            f"1. {AI_STUDIO_PROCESS_STEPS[0]}: 현재 프로젝트 루트와 data/**에서 사용할 모델 후보를 확인한다.",
            f"2. {AI_STUDIO_PROCESS_STEPS[1]}: Windows PowerShell에서 현재 워크스페이스 루트로 이동한 뒤 select_model.py --model <번호 또는 경로> 로 사용할 모델을 선택한다.",
            f"3. {AI_STUDIO_PROCESS_STEPS[2]}: .env의 원격 MLflow URL을 확인하고, requirements.txt의 mlflow 버전과 kserve 필수 항목만 맞춘다. 나머지 패키지는 사용자가 직접 입력한다.",
            f"4. {AI_STUDIO_PROCESS_STEPS[3]}: .opencode/scripts/05-train-model/templates/pytorch_sample/ 템플릿 복사 후, 복사된 템플릿 기준으로 선택 모델 경로와 모델 형식 연결부를 수정한다.",
            f"5. {AI_STUDIO_PROCESS_STEPS[4]}: python {entrypoint_display} 로 원격 MLflow 서버에 기록/등록한다.",
            f"6. {AI_STUDIO_PROCESS_STEPS[5]}: 자동 실행하지 않고 사용자가 6번을 선택했을 때 inferencetest.py 로 원격 추론 URL을 호출한다.",
            f"7. {AI_STUDIO_PROCESS_STEPS[6]}: 오류가 있으면 실패 단계부터 수정 후 다시 실행한다.",
        ]
        if entrypoint is None:
            if entrypoint_candidates:
                next_steps.append("Entrypoint candidates: " + ", ".join(str(path.relative_to(project)) for path in entrypoint_candidates))
            next_steps.append("실행 파일을 찾지 못했습니다. 사용자가 실제 학습/모델 생성 Python 파일을 프로젝트에 직접 넣고 --entrypoint <file>로 지정하세요.")
        if selected_path is None:
            failures.append("selected_model_config_missing")
            next_steps.append("3번 환경검증은 2번에서 고정한 선택 모델 기준으로 진행합니다. 먼저 2번 모델 선택을 실행하세요.")
    else:
        entrypoint_display = setting_file or "run_model.py, runtest.py 또는 run_test.py"
        tod_guide = [
            "1. 환경 검증: 현재 출력의 Python, dependency, MLflow, 설정 상태를 확인한다.",
            f"2. 샘플 규격 확인/보충: {project}에 복사된 템플릿 폴더 내부 파일들을 확인한다. 대표 예시: aiu_custom/, local_serving/, saved_model/, requirements.txt, input_example.json",
            "3. 환경 변수 입력/export: 현재 워크스페이스 루트의 .env 5개 값을 확인하고 실행 시 MLFLOW_*로 export한다.",
            "4. 패키지 설치: requirements.txt 기준으로 내부 http:// PyPI/Nexus 미러를 사용해 설치한다. SSL/HTTPS 인덱스 직접 설치는 사용하지 않는다.",
            f"5. 모델 실행 및 원격 MLflow 기록: python {entrypoint_display}",
            "6. 산출물 확인: MLflow artifact_path='ai_studio' 아래 ai_studio/code 또는 로컬 ai_studio/metrics, ai_studio/code 생성 여부를 확인한다.",
        ]
    python_version_status = "set" if python_version == selected_python_version else "selected_version_diff"

    if python_version_status == "selected_version_diff":
        blocked_summary.append(f"현재 Python {python_version} / 선택 Python {selected_python_version}")
        failures.append(f"selected_python_version_diff:{python_version}->{selected_python_version}")
        next_steps.append("현재 Python과 사용자가 선택한 Python 버전이 다릅니다. requirements 호환성을 직접 확인하세요.")
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
    if missing_requirements or mismatched_requirements:
        next_steps.append("패키지 설치는 실행하지 않습니다. requirements.txt는 mlflow/kserve 기준만 맞추고 나머지는 사용자가 직접 입력합니다.")
    if remote_mlflow.status == "version_mismatch" and remote_mlflow.server_version:
        next_steps.append(f"원격 MLflow 서버 버전에 맞춰 requirements.txt의 mlflow를 {remote_mlflow.required_version}로 반영했습니다.")
    elif remote_mlflow.status == "missing_local_mlflow" and remote_mlflow.server_version:
        next_steps.append(f"로컬 mlflow 설치 여부와 관계없이 requirements.txt의 mlflow를 {remote_mlflow.required_version}로 반영했습니다.")
    elif remote_mlflow.status == "unreachable":
        next_steps.append("원격 MLflow 서버 버전 확인에 실패했습니다. requirements.txt의 mlflow는 버전 고정 없이 유지합니다.")
    if remote_mlflow.server_version:
        for item in requirements:
            if normalize_package_name(item.name) != "mlflow":
                continue
            if version_constraint_status(remote_mlflow.server_version, item.required_version) == "version_mismatch":
                next_steps.append(f"requirements.txt의 mlflow 요구 버전을 mlflow=={remote_mlflow.server_version}로 변환하세요.")
                break
    tracking_ready = any(item.name == "mlflow_tracking_uri" and item.status == "set" for item in ai_env.key_status)
    if env_status("MLFLOW_TRACKING_URI") == "missing" and not tracking_ready:
        next_steps.append(".env 5개 필수 입력값 중 mlflow_tracking_uri에 원격 MLflow/리포트 URI를 직접 입력하세요.")
    if source_input_required:
        required_names = ", ".join(item.name for item in source_input_required)
        next_steps.append(f".env 5개 필수 입력값을 직접 입력하세요: {required_names}.")
    entrypoint_pending_until_step4 = (
        existing_model_flow
        and selected_path is not None
        and entrypoint_name is not None
        and entrypoint_name.replace("\\", "/").lstrip("./") == "runtest_2.py"
        and not (project / "runtest_2.py").exists()
    )
    if entrypoint_name and model_settings is None and not entrypoint_pending_until_step4:
        failures.append(f"entrypoint_not_found:{entrypoint_name}")
        next_steps.append(f"지정한 실행 파일 경로를 찾지 못했습니다: {entrypoint_name}")
    elif entrypoint_pending_until_step4:
        next_steps.append("runtest_2.py는 4번 템플릿 변환에서 생성됩니다.")
    if not Path(ai_env.path).exists():
        failures.append("missing_model_settings_file:.env")
        if existing_model_flow and entrypoint is None:
            next_steps.append("현재 워크스페이스 루트에 .env 파일을 만들고 MLflow 5개 값을 입력하세요.")
        else:
            next_steps.append("현재 워크스페이스 루트의 .env 파일에 MLflow 5개 값을 입력하세요.")
    setting_source = ai_env
    for item in setting_source.key_status:
        if item.status in {"missing", "empty"}:
            failures.append(f"missing_env:{item.name}")

    virtual_env = os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX") or "not detected"
    return EnvironmentReport(
        project_path=str(project),
        os=f"{platform.system()} {platform.release()}",
        python_executable=sys.executable,
        python_version=python_version,
        expected_python_version=PYTHON_COMPATIBILITY_BASELINE,
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
        server_deploy_errors=server_deploy_error_items(failures, blocked_summary),
        failures=failures,
        next_steps=next_steps,
        tod_guide=tod_guide,
        source_input_required=source_input_required,
        selected_model_path=selected_path,
        selected_model_kind=selected_kind,
        selected_required_package=selected_required_package,
        selected_package_status=selected_package_status,
        remote_mlflow=remote_mlflow,
        selected_python_version=selected_python_version,
        requirement_candidates=candidates,
        selected_model_recommendations=selected_recommendations,
        image_model_recommendations=image_model_recommendations,
        pip_dry_run=dry_run_status,
        requirements_updated=requirements_updated,
    )


def result_status(report: EnvironmentReport) -> str:
    if report.source_input_required:
        return "needs_user_input"
    if report.failures:
        return "warn"
    return "pass"


def status_label(status: str) -> str:
    return {
        "missing": "미설치",
        "version_mismatch": "버전 불일치",
        "version_match": "일치",
        "set": "확인",
    }.get(status, status)


def required_env_input_names(report: EnvironmentReport) -> list[str]:
    return [item.name for item in report.source_input_required if item.name in AI_STUDIO_ENV_KEYS]


def env_setting_description(key: str) -> str:
    return {
        "mlflow_tracking_uri": "원격 MLflow 서버 URI",
        "mlflow_tracking_username": "사용자명",
        "mlflow_tracking_password": "비밀번호 (출력 안 함)",
        "mlflow_experiment_name": "실험 이름",
        "mlflow_register_model_name": "등록 모델 이름",
    }.get(key, "")


def env_setting_rows(report: EnvironmentReport) -> list[list[str]]:
    env_file_status = {
        item.name: item.status
        for item in (report.ai_studio_env.key_status if report.ai_studio_env else [])
    }
    rows: list[list[str]] = []
    for key in AI_STUDIO_ENV_KEYS:
        current_status = env_file_status.get(key, "missing")
        rows.append([key, current_status])
    return rows


def compact_issue_summary(report: EnvironmentReport) -> list[str]:
    issues: list[str] = []
    if report.python_version_status in {"version_mismatch", "compatibility_check", "selected_version_diff"}:
        issues.append(f"현재 Python {report.python_version} / 선택 Python {report.selected_python_version or report.python_version}")
    env_names = required_env_input_names(report)
    if env_names:
        issues.append(".env 입력 필요: " + ", ".join(env_names))
    return issues


def requirement_basis(report: EnvironmentReport, item: RequirementStatus) -> str:
    normalized_name = normalize_package_name(item.name)
    if normalized_name == "mlflow" and report.remote_mlflow:
        if report.remote_mlflow.server_version:
            return "원격 MLflow 서버 버전"
        if report.remote_mlflow.tracking_uri_status == "set":
            return "MLflow 환경 접속 기준"
        if report.remote_mlflow.local_version:
            return "원격 MLflow 서버 버전 확인 필요"
        return "MLflow 환경 기준"
    if normalized_name == "numpy" and report.python_version.startswith("3.13"):
        return "Python 3.13 호환"
    if normalized_name == "kserve":
        return "requirements.txt 필수 유지"
    return "Python/AI Studio 기준"


def selected_model_requirement_rows(report: EnvironmentReport) -> list[list[str]]:
    if report.selected_model_recommendations:
        return [[item] for item in report.selected_model_recommendations]
    if report.selected_model_path or report.selected_model_kind:
        return [["모델 전용 추가 패키지 없음"]]
    return []


def selected_model_info_rows(report: EnvironmentReport) -> list[list[str]]:
    if not report.selected_model_path or not report.selected_model_kind:
        return []
    source_url = normalize_path_text(report.selected_model_path)
    model_name = Path(source_url).name
    return [
        ["model_kind", report.selected_model_kind],
        ["url", f"saved_model/{model_name}"],
        ["path", f"saved_model\\{model_name}"],
        ["source_url", source_url],
        ["source_path", source_url.replace("/", "\\")],
    ]


def pinned_mandatory_requirements(report: EnvironmentReport) -> list[str]:
    requirements: list[str] = []
    if report.remote_mlflow and report.remote_mlflow.server_version:
        requirements.append(f"mlflow=={report.remote_mlflow.server_version}")
    else:
        requirements.append("mlflow")

    requirements.extend(
        f"{item.name}=={item.required_version.lstrip('=')}"
        for item in report.requirements
        if item.name in MANDATORY_REQUIREMENT_NAMES - {"mlflow"}
        if item.required_version and item.required_version not in {"any", "-"}
        if not is_unselected_framework_requirement(item, report.selected_required_package)
    )
    return requirements


def step3_status_text(report: EnvironmentReport) -> str:
    package_issues = package_action_items(report)
    python_issue = report.python_version_status in {"version_mismatch", "compatibility_check", "selected_version_diff"}
    input_names = {item.name for item in report.source_input_required}
    needs_mlflow_input = any(
        name in input_names
        for name in {
            "mlflow_tracking_uri",
            "mlflow_tracking_username",
            "mlflow_tracking_password",
            "mlflow_experiment_name",
            "mlflow_register_model_name",
        }
    )
    if python_issue or needs_mlflow_input or package_issues:
        return "입력 필요"
    return "완료"


def step3_action_text(report: EnvironmentReport) -> str:
    return "환경 검증 완료" if step3_status_text(report) == "완료" else "환경 재검증"


def print_text(report: EnvironmentReport):
    print("\nSecrets 상태 > 환경변수 입력 (필수)")
    print_markdown_table(
        ["Key", "상태"],
        env_setting_rows(report),
    )
    selected_info_rows = selected_model_info_rows(report)
    if selected_info_rows:
        print("\n선택 모델 연결 정보")
        print_markdown_table(["Key", "Value"], selected_info_rows)

    if report.requirements:
        print("\n2. requirements 기본 항목")
        print_markdown_table(
            ["Package", "Required", "기준"],
            [
                [item.name, item.required_version, requirement_basis(report, item)]
                for item in report.requirements
                if item.name in MANDATORY_REQUIREMENT_NAMES
                if not is_unselected_framework_requirement(item, report.selected_required_package)
            ],
        )
    selected_requirement_rows = selected_model_requirement_rows(report)
    if selected_requirement_rows:
        print("\n3. 선택 모델 패키지 후보 (선택 사항)")
        print_markdown_table(
            ["Requirement"],
            selected_requirement_rows,
        )
        selected_requirements = [
            item
            for item in report.selected_model_recommendations
            if item and item != "-"
        ]
        if selected_requirements:
            print("필요한 항목만 사용자가 직접 선택해 requirements.txt에 추가:")
            print_copy_block(selected_requirements)
    if report.image_model_recommendations:
        print("\n3-1. 이미지 모델 패키지 후보 (선택 사항)")
        print_markdown_table(
            ["Package", "Version"],
            [
                [item.split("==", 1)[0], item.split("==", 1)[1] if "==" in item else ""]
                for item in report.image_model_recommendations
            ],
        )
        print("사용자가 직접 선택해 requirements.txt에 추가:")
        print_copy_block(report.image_model_recommendations)
    if report.requirement_candidates:
        print("\nimport 기반 패키지")
        print_markdown_table(
            ["Package", "Source"],
            [[item.package, item.source] for item in report.requirement_candidates],
        )

    print("\n다음 가능 단계")
    print_markdown_table(
        ["Status", "Step", "Action"],
        [
            [step3_status_text(report), "3", step3_action_text(report)],
            ["대기", "4", "템플릿 변환 (사용자 선택)"],
            ["대기", "5", "원격 MLflow 등록 실행"],
            ["대기", "6", "추론 테스트"],
            ["대기", "7", "오류 재실행"],
        ],
    )

def print_verbose_text(report: EnvironmentReport):
    project_root = Path(report.project_path).resolve()
    install_file = "requirements.txt" if "requirements.txt" in report.dependency_files else "missing"
    print("환경 검증 상세 결과")
    print_markdown_table(
        ["항목", "값"],
        [
            ["Project", "."],
            ["Scope", "선택한 워크스페이스 루트 기준"],
            ["현재 Python", report.python_version],
            ["선택 Python", report.selected_python_version or report.python_version],
            ["Python 기준", f"{report.expected_python_version} ({report.python_version_status})"],
            ["requirements.txt", "기본 항목 확인" if install_file == "requirements.txt" else "missing"],
            ["선택 모델", report.selected_model_path or "missing"],
            ["MODEL_KIND", report.selected_model_kind or "missing"],
        ],
    )

    print("\nSecrets 상태 > 환경변수 입력 (필수)")
    print_markdown_table(
        ["Key", "상태"],
        env_setting_rows(report),
    )
    selected_info_rows = selected_model_info_rows(report)
    if selected_info_rows:
        print("\n선택 모델 연결 정보")
        print_markdown_table(["Key", "Value"], selected_info_rows)

    if report.requirements:
        print("\n2. requirements 기본 항목")
        print_markdown_table(
            ["Package", "Required", "기준"],
            [
                [item.name, item.required_version, requirement_basis(report, item)]
                for item in report.requirements
                if item.name in MANDATORY_REQUIREMENT_NAMES
                if not is_unselected_framework_requirement(item, report.selected_required_package)
            ],
        )
    selected_requirement_rows = selected_model_requirement_rows(report)
    if selected_requirement_rows:
        print("\n3. 선택 모델 패키지 후보 (선택 사항)")
        print_markdown_table(
            ["Requirement"],
            selected_requirement_rows,
        )
        selected_requirements = [
            item
            for item in report.selected_model_recommendations
            if item and item != "-"
        ]
        if selected_requirements:
            print("필요한 항목만 사용자가 직접 선택해 requirements.txt에 추가:")
            print_copy_block(selected_requirements)
    if report.image_model_recommendations:
        print("\n3-1. 이미지 모델 패키지 후보 (선택 사항)")
        print_markdown_table(
            ["Package", "Version"],
            [
                [item.split("==", 1)[0], item.split("==", 1)[1] if "==" in item else ""]
                for item in report.image_model_recommendations
            ],
        )
        print("사용자가 직접 선택해 requirements.txt에 추가:")
        print_copy_block(report.image_model_recommendations)
    if report.requirement_candidates:
        print("\nimport 기반 패키지")
        print_markdown_table(
            ["Package", "Source"],
            [[item.package, item.source] for item in report.requirement_candidates],
        )
    if report.remote_mlflow:
        print("\nRemote MLflow server:")
        remote_rows = [
            ["tracking URI", report.remote_mlflow.tracking_uri_status],
            ["status", report.remote_mlflow.status],
            ["server version", report.remote_mlflow.server_version or "unchecked"],
            ["required version", report.remote_mlflow.required_version or "unchecked"],
        ]
        if report.remote_mlflow.server_version:
            remote_rows.append(["requirements transform", "mlflow version follows remote server"])
        elif report.remote_mlflow.tracking_uri_status == "set":
            remote_rows.append(["requirements transform", "remote URL set; mlflow stays unpinned until server version is confirmed"])
        else:
            remote_rows.append(["requirements transform", "remote URL missing; mlflow stays unpinned"])
        print_markdown_table(["항목", "값"], remote_rows)

    if report.ai_studio_env:
        try:
            env_display_path = Path(report.ai_studio_env.path).resolve().relative_to(project_root).as_posix()
        except ValueError:
            env_display_path = Path(report.ai_studio_env.path).name
        print("\n.env 설정")
        print_markdown_table(
            ["Key", "Status", "File"],
            [
                [item.name, item.status, env_display_path]
                for item in report.ai_studio_env.key_status
                if item.name in {
                    "mlflow_tracking_uri",
                    "mlflow_tracking_username",
                    "mlflow_tracking_password",
                    "mlflow_experiment_name",
                    "mlflow_register_model_name",
                }
            ],
        )

    if report.source_input_required:
        source_path = ".env"
        if report.ai_studio_env:
            try:
                source_path = Path(report.ai_studio_env.path).resolve().relative_to(project_root).as_posix()
            except ValueError:
                source_path = Path(report.ai_studio_env.path).name
        print(f"\n입력이 필요한 {len(report.source_input_required)}개 값:")
        print_markdown_table(
            ["Key", "Status", "입력 위치", "비고"],
            [
                [
                    item.name,
                    item.status,
                    source_path,
                    "값은 출력하지 않음" if item.name == "mlflow_tracking_password" else "",
                ]
                for item in report.source_input_required
            ],
        )


def package_action_items(report: EnvironmentReport) -> list[RequirementStatus]:
    return [
        item
        for item in report.requirements
        if item.source == "expected"
        and item.name.lower() in MANDATORY_REQUIREMENT_NAMES
        and not is_unselected_framework_requirement(item, report.selected_required_package)
    ]


def command_project_arg(project: Path) -> str:
    try:
        relative = project.resolve().relative_to(Path.cwd().resolve()).as_posix()
        return relative or "."
    except ValueError:
        return project.as_posix()


def command_script_path(project: Path, script_relative_path: str) -> str:
    project = project.resolve()
    if (project / ".opencode").is_dir():
        return f".opencode/scripts/{script_relative_path}"
    if (project.parent / ".opencode").is_dir():
        return f"../.opencode/scripts/{script_relative_path}"
    return f".opencode/scripts/{script_relative_path}"


def command_project_arg_from_model_folder(project: Path) -> str:
    project = project.resolve()
    if (project.parent / ".opencode").is_dir() and not (project / ".opencode").is_dir():
        return "."
    return command_project_arg(project)


def command_workspace_arg_from_model_folder(project: Path) -> str:
    project = project.resolve()
    if (project.parent / ".opencode").is_dir() and not (project / ".opencode").is_dir():
        return ".."
    return "."


def recheck_command(report: EnvironmentReport) -> str:
    project = Path(report.project_path)
    project_arg = command_project_arg_from_model_folder(project)
    script_path = command_script_path(project, "03-environment-check/check_environment.py")
    command = (
        f"python {script_path} "
        f"--project {project_arg} --entrypoint runtest_2.py"
    )
    if report.selected_python_version:
        command += f" --python-version {report.selected_python_version}"
    return command


def prepare_selected_command(report: EnvironmentReport) -> str:
    project = Path(report.project_path)
    script_path = command_script_path(project, "05-train-model/prepare_selected_model.py")
    project_arg = command_workspace_arg_from_model_folder(project)
    return f"python {script_path} --project {project_arg} --model selected --execute"


def run_training_command(report: EnvironmentReport) -> str:
    project = Path(report.project_path)
    project_arg = command_project_arg_from_model_folder(project)
    script_path = command_script_path(project, "05-train-model/run_training.py")
    return (
        f"python {script_path} "
        f"--project {project_arg} --entrypoint runtest_2.py --execute"
    )


def inference_command(report: EnvironmentReport) -> str:
    project_arg = command_project_arg(Path(report.project_path))
    if project_arg == ".":
        return "python inferencetest.py"
    return f"cd {project_arg} 후 python inferencetest.py"


def print_action_items(report: EnvironmentReport) -> None:
    project_root = Path(report.project_path).resolve()
    package_issues = package_action_items(report)
    python_issue = report.python_version_status in {"version_mismatch", "compatibility_check", "selected_version_diff"}
    actionable_count = 1 if python_issue else 0
    input_names = {item.name for item in report.source_input_required}
    needs_mlflow_input = any(
        name in input_names
        for name in {
            "mlflow_tracking_uri",
            "mlflow_tracking_username",
            "mlflow_tracking_password",
            "mlflow_experiment_name",
            "mlflow_register_model_name",
        }
    )
    if needs_mlflow_input:
        actionable_count += 1
    if actionable_count == 0:
        print("\n처리해야 할 항목: 없음")
        print("\n다시 검증:")
        print_markdown_table(["항목", "명령"], [["다시 검증", recheck_command(report)]])
        print("\n검증 완료 후 실행 가능:")
        print_markdown_table(
            ["Step", "명령/안내"],
            [
                ["4", f"템플릿 변환은 사용자가 선택: {prepare_selected_command(report)}"],
                ["5", f"원격 MLflow 등록 실행: {run_training_command(report)}"],
                ["6", f"추론 테스트는 사용자가 선택할 때만 실행: {inference_command(report)}"],
            ],
        )
        return

    print("\n처리해야 할 항목:")
    action_rows: list[list[str]] = []
    if python_issue:
        action_rows.append([
            "Python 버전",
            "직접 확인 필요",
            f"현재 {report.python_version}; 선택 {report.selected_python_version or report.python_version}",
        ])
    if needs_mlflow_input:
        source_path = ".env"
        if report.ai_studio_env:
            try:
                source_path = Path(report.ai_studio_env.path).resolve().relative_to(project_root).as_posix()
            except ValueError:
                source_path = Path(report.ai_studio_env.path).name
        action_rows.append(
            [
                source_path,
                "직접 입력 필요",
                "mlflow_tracking_uri, mlflow_tracking_username, mlflow_tracking_password, mlflow_experiment_name, mlflow_register_model_name",
            ]
        )
    if action_rows:
        print_markdown_table(["항목", "상태", "조치"], action_rows)

    if package_issues:
        print("\nrequirements.txt 확인 상세:")
        package_rows = []
        for item in package_issues:
            label = "미설치" if item.status == "missing" else "버전 불일치"
            installed = item.installed_version or "missing"
            package_rows.append([item.name, label, item.required_version, installed, requirement_basis(report, item)])
        print_markdown_table(["Package", "로컬 상태", "requirements.txt", "설치 버전", "기준"], package_rows)
    if needs_mlflow_input:
        source_path = ".env"
        if report.ai_studio_env:
            try:
                source_path = Path(report.ai_studio_env.path).resolve().relative_to(project_root).as_posix()
            except ValueError:
                source_path = Path(report.ai_studio_env.path).name
        print("\n.env 직접 입력:")
        print_markdown_table(
            ["Key", "입력 위치", "설명"],
            [
                ["mlflow_tracking_uri", source_path, "원격 MLflow 서버 URI (http://... 또는 https://...)"],
                ["mlflow_tracking_username", source_path, "사용자명"],
                ["mlflow_tracking_password", source_path, "secret, 출력하지 않음"],
                ["mlflow_experiment_name", source_path, "실험 이름"],
                ["mlflow_register_model_name", source_path, "등록 모델 이름"],
            ],
        )
    print("\n다시 검증:")
    print_markdown_table(["항목", "명령"], [["다시 검증", recheck_command(report)]])

    print("\n검증 완료 후 실행 가능:")
    print_markdown_table(
        ["Step", "명령/안내"],
        [
            ["4", f"템플릿 변환: {prepare_selected_command(report)}"],
            ["5", f"원격 MLflow 등록 실행: {run_training_command(report)}"],
            ["6", f"추론 테스트: {inference_command(report)}"],
        ],
    )


def main():
    parser = argparse.ArgumentParser(description="Check local ML project execution environment and .env settings.")
    parser.add_argument("--project", default=".", help="model project folder")
    parser.add_argument("--entrypoint", help="actual local training/model creation file, such as run.py")
    parser.add_argument("--python-version", help="selected Python version to validate requirements against, for example 3.10 or 3.11.9")
    parser.add_argument("--fix-packages", action="store_true", help="deprecated: local package installation is disabled; requirements.txt is only checked")
    parser.add_argument("--no-fix-packages", action="store_true", help="kept for compatibility; package installation is always skipped")
    parser.add_argument("--verbose", action="store_true", help="print detailed package, env, and TODO diagnostics")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    project = resolve_workspace_project(args.project)
    if not project.exists():
        raise FileNotFoundError(f"project folder not found: {project}")

    report = build_report(project, args.entrypoint, args.python_version)
    if args.fix_packages and not args.json:
        print("패키지 자동 설치는 비활성화되어 있습니다. requirements.txt는 mlflow/kserve 기본 항목만 확인합니다.")
    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    elif args.verbose:
        print_verbose_text(report)
    else:
        print_text(report)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
