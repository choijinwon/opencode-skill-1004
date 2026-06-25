import argparse
import ast
import importlib.metadata
import json
import os
import platform
import re
import sys
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

MODEL_SETTING_FILES = ["runtest.py", "run_model.py", "run.py"]
ENTRYPOINTS = ["runtest.py", "train.py", "run_model.py", "run.py", "main.py", "app.py", "scripts/train.py"]
SAMPLE_PROJECT_NAMES = {"sklearn_sample", "pytorch_sample", "tensorflow_sample"}
MODEL_MARKERS = ["runtest.py", "train.py", "run_model.py", "predict.py", "input_example.json", "MLmodel"]
ARTIFACT_SUFFIXES = {".pkl", ".joblib", ".pt", ".pth", ".h5", ".keras", ".onnx", ".safetensors"}
ARTIFACT_DIRS = ["ai_studio", "saved_model", "model", "artifacts"]

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

EXPECTED_PYTHON_VERSION = "3.11.9"
REQUIREMENT_OPERATORS = ["==", "!=", ">=", "<=", "~=", ">", "<"]


@dataclass
class PackageStatus:
    name: str
    status: str
    version: str | None = None


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


def requirement_statuses(project: Path) -> list[RequirementStatus]:
    statuses: list[RequirementStatus] = []
    requirements_path = project / "requirements.txt"
    if not requirements_path.exists():
        return statuses
    for raw_line in requirements_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parsed = parse_requirement_line(raw_line)
        if parsed is None:
            continue
        name, required_spec = parsed
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
    return statuses


def env_status(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        return "missing"
    if value == "":
        return "empty"
    return "set"


def dependency_files(project: Path) -> list[str]:
    names = ["requirements.txt", "pyproject.toml", "environment.yml", "environment.yaml"]
    return [name for name in names if (project / name).exists()]


def has_model_project(project: Path) -> bool:
    if any((project / name).exists() for name in MODEL_MARKERS):
        return True
    if find_entrypoint_candidates(project):
        return True
    if any((project / name).exists() for name in ARTIFACT_DIRS):
        return True
    return any(path.suffix in ARTIFACT_SUFFIXES for path in project.glob("*") if path.is_file())


def is_sample_project(project: Path) -> bool:
    return project.name in SAMPLE_PROJECT_NAMES


def find_entrypoint_candidates(project: Path) -> list[Path]:
    found = []
    for name in ENTRYPOINTS:
        candidate = project / name
        if candidate.exists() and candidate.is_file():
            found.append(candidate)
    found.extend(sorted(path for path in project.glob("*.py") if path.is_file()))
    return sorted(set(found))


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


def ai_studio_env_status(project: Path) -> EnvFileStatus:
    path = project / "ai_studio.env"
    values = parse_env_file(path)
    statuses = []
    for key in AI_STUDIO_ENV_KEYS:
        if key not in values:
            status = "missing"
        elif values[key] == "":
            status = "empty"
        else:
            status = "set"
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
        if key not in values:
            status = "local_default" if key == "mlflow_tracking_url" else "missing"
        elif values[key] == "":
            status = "local_default" if key == "mlflow_tracking_url" else "empty"
        else:
            status = "set"
        statuses.append(EnvVarStatus(key, status))
    return EnvFileStatus(str(path), statuses)


def export_ready_status(project: Path, entrypoint_name: str | None = None) -> list[EnvVarStatus]:
    path = resolve_setting_file(project, entrypoint_name)
    if path is None or not path.exists():
        return []
    values = parse_python_string_assignments(path)
    statuses = []
    for setting_key, env_key in EXPORT_ENV_MAP.items():
        if values.get(setting_key):
            status = "set"
        elif env_status(env_key) == "set":
            status = "exported"
        elif setting_key == "mlflow_tracking_url":
            status = "local_default"
        else:
            status = "missing"
        statuses.append(EnvVarStatus(env_key, status))
    return statuses


def source_input_required_status(model_settings: EnvFileStatus | None) -> list[EnvVarStatus]:
    if model_settings is None:
        return [EnvVarStatus(key, "missing") for key in AI_STUDIO_ENV_KEYS[:3]]
    required = []
    for item in model_settings.key_status:
        if item.name not in AI_STUDIO_ENV_KEYS[:3]:
            continue
        if item.status in {"missing", "empty"}:
            required.append(item)
    return required


def build_report(project: Path, entrypoint_name: str | None = None) -> EnvironmentReport:
    python_version = platform.python_version()
    deps = dependency_files(project)
    packages = []
    for package in CORE_PACKAGES:
        version = package_version(package)
        packages.append(PackageStatus(package, "set" if version else "missing", version))
    requirements = requirement_statuses(project)

    env_vars = [EnvVarStatus(key, env_status(key)) for key in ENV_KEYS]
    ai_env = ai_studio_env_status(project)
    model_settings = model_settings_status(project, entrypoint_name)
    export_ready = export_ready_status(project, entrypoint_name)
    source_input_required = source_input_required_status(model_settings)
    blocked_summary: list[str] = []
    failures: list[str] = []
    next_steps: list[str] = []
    model_found = has_model_project(project)
    entrypoint_candidates = find_entrypoint_candidates(project)
    setting_file = None
    if model_settings is not None:
        setting_file = Path(model_settings.path).name
    entrypoint = setting_file
    if entrypoint is None and len(entrypoint_candidates) == 1:
        entrypoint = str(entrypoint_candidates[0].relative_to(project))
    existing_model_flow = model_found and not is_sample_project(project)
    if existing_model_flow:
        entrypoint_display = entrypoint or "사용자가 실제 사용하는 파일명"
        tod_guide = [
            "1. 실행 파일 확정: run_model.py로 고정하지 말고 실제 로컬 학습/모델 생성 파일을 확정한다.",
            "2. 환경 검증: 현재 출력의 Python, dependency, MLflow, 설정 상태를 확인한다.",
            f"3. 샘플 규격 확인/보충: {project}의 aiu_custom/, local_serving/, saved_model/, requirements.txt, input_example.json을 확인한다.",
            f"4. 환경 변수 입력/export: {entrypoint_display}의 설정 블록 값을 직접 입력하고 실행 시 MLFLOW_*로 export한다.",
            "5. 패키지 설치: 폐쇄망 WSL은 bash .opencode/wsl/install_offline.sh를 우선 사용하고, wheelhouse가 없으면 온라인 WSL에서 bash .opencode/wsl/download_wheels.sh로 먼저 준비한다.",
            f"6. 로컬 학습 모델 실행: python {entrypoint_display}",
            "7. 산출물 확인: MLflow artifact_path='ai_studio' 아래 ai_studio/code 또는 로컬 ai_studio/metrics, ai_studio/code 생성 여부를 확인한다.",
        ]
        if entrypoint is None:
            if entrypoint_candidates:
                next_steps.append("Entrypoint candidates: " + ", ".join(str(path.relative_to(project)) for path in entrypoint_candidates))
            next_steps.append("실행 파일을 찾지 못했습니다. 사용자가 실제 학습/모델 생성 Python 파일을 프로젝트에 직접 넣고 --entrypoint <file>로 지정하세요.")
            source_input_required = []
    else:
        entrypoint_display = setting_file or "run_model.py 또는 runtest.py"
        tod_guide = [
            "1. 환경 검증: 현재 출력의 Python, dependency, MLflow, 설정 상태를 확인한다.",
            f"2. 샘플 규격 확인/보충: {project}의 aiu_custom/, local_serving/, saved_model/, requirements.txt, input_example.json을 확인한다.",
            f"3. 환경 변수 입력/export: {entrypoint_display}의 설정 블록 값을 직접 입력하고 실행 시 MLFLOW_*로 export한다.",
            "4. 패키지 설치: 폐쇄망 WSL은 bash .opencode/wsl/install_offline.sh를 우선 사용하고, wheelhouse가 없으면 온라인 WSL에서 bash .opencode/wsl/download_wheels.sh로 먼저 준비한다.",
            f"5. 로컬 학습 모델 실행: python {entrypoint_display}",
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
    missing_requirements = [item.name for item in requirements if item.status == "missing"]
    mismatched_requirements = [item.name for item in requirements if item.status == "version_mismatch"]
    if missing_requirements:
        failures.append("missing_requirements:" + ",".join(missing_requirements))
        next_steps.append("Install missing packages from requirements.txt.")
    if mismatched_requirements:
        failures.append("version_mismatch_requirements:" + ",".join(mismatched_requirements))
        next_steps.append("Resolve package version mismatches before model execution.")
    if package_version("mlflow") is None:
        failures.append("missing_dependency:mlflow")
        next_steps.append("Install or activate an environment that includes mlflow.")
    tracking_ready = any(item.name == "MLFLOW_TRACKING_URI" and item.status in {"set", "exported", "local_default"} for item in export_ready)
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
        if item.status in {"missing", "empty"}:
            failures.append(f"missing_env:{item.name}")

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
    )


def print_text(report: EnvironmentReport):
    print(f"Project: {report.project_path}")
    print(f"OS: {report.os}")
    print(f"Python: {report.python_version} ({report.python_executable})")
    print(f"Expected Python: {report.expected_python_version} ({report.python_version_status})")
    print(f"Virtual env: {report.virtual_env}")
    print(f"Dependency files: {', '.join(report.dependency_files) if report.dependency_files else 'missing'}")
    print("\nPackages:")
    for package in report.packages:
        suffix = f" {package.version}" if package.version else ""
        print(f"- {package.name}: {package.status}{suffix}")
    if report.requirements:
        print("\nDependency check from requirements.txt:")
        for item in report.requirements:
            installed = item.installed_version if item.installed_version else "missing"
            print(
                f"- {item.name}: {item.status} "
                f"(required: {item.required_version}, installed: {installed})"
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
        source_path = report.model_settings.path if report.model_settings else "run_model.py 또는 runtest.py"
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
