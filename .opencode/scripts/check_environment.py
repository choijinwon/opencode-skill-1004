import argparse
import ast
import importlib.metadata
import json
import os
import platform
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

MODEL_SETTING_FILES = ["runtest.py", "run_model.py"]

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


@dataclass
class PackageStatus:
    name: str
    status: str
    version: str | None = None


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
    env_vars: list[EnvVarStatus] = field(default_factory=list)
    ai_studio_env: EnvFileStatus | None = None
    model_settings: EnvFileStatus | None = None
    export_ready: list[EnvVarStatus] = field(default_factory=list)
    blocked_summary: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    tod_guide: list[str] = field(default_factory=list)


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


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


def parse_python_string_assignments(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return values
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                values[target.id] = node.value.value
    return values


def model_settings_status(project: Path) -> EnvFileStatus | None:
    for name in MODEL_SETTING_FILES:
        path = project / name
        if not path.exists():
            continue
        values = parse_python_string_assignments(path)
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
    return None


def export_ready_status(project: Path) -> list[EnvVarStatus]:
    for name in MODEL_SETTING_FILES:
        path = project / name
        if not path.exists():
            continue
        values = parse_python_string_assignments(path)
        statuses = []
        for setting_key, env_key in EXPORT_ENV_MAP.items():
            if values.get(setting_key):
                status = "set"
            elif env_status(env_key) == "set":
                status = "exported"
            else:
                status = "missing"
            statuses.append(EnvVarStatus(env_key, status))
        return statuses
    return []


def build_report(project: Path) -> EnvironmentReport:
    python_version = platform.python_version()
    deps = dependency_files(project)
    packages = []
    for package in CORE_PACKAGES:
        version = package_version(package)
        packages.append(PackageStatus(package, "set" if version else "missing", version))

    env_vars = [EnvVarStatus(key, env_status(key)) for key in ENV_KEYS]
    ai_env = ai_studio_env_status(project)
    model_settings = model_settings_status(project)
    export_ready = export_ready_status(project)
    blocked_summary: list[str] = []
    failures: list[str] = []
    next_steps: list[str] = []
    setting_file = None
    if model_settings is not None:
        setting_file = Path(model_settings.path).name
    entrypoint = setting_file or "run_model.py 또는 runtest.py"
    tod_guide = [
        "1. 환경 검증: 현재 출력의 Python, dependency, MLflow, 설정 상태를 확인한다.",
        f"2. 샘플 폴더 이동: {project}",
        f"3. 환경 변수 입력: {entrypoint}의 MLflow/AI Studio 설정 블록에 필수 값 5개를 직접 입력한다.",
        f"4. 환경 변수 export: {entrypoint} 실행 시 설정 블록 값을 MLFLOW_* 환경변수로 export한다.",
        f"5. 모델 실행: {entrypoint} 기준으로 모델 저장 또는 MLflow artifact 생성을 확인한다.",
    ]
    python_version_status = "set" if python_version == EXPECTED_PYTHON_VERSION else "version_mismatch"

    if python_version_status == "version_mismatch":
        blocked_summary.append(f"Python 버전 차이 ({python_version} vs 기대 {EXPECTED_PYTHON_VERSION}) → 호환성 확인 필요")
        failures.append(f"version_mismatch:python expected {EXPECTED_PYTHON_VERSION} got {python_version}")
        next_steps.append(f"Use Python {EXPECTED_PYTHON_VERSION} for this MLflow workflow.")
    if not deps:
        failures.append("missing_dependency_file")
        next_steps.append("Add or confirm requirements.txt, pyproject.toml, or environment.yml.")
    if package_version("mlflow") is None:
        failures.append("missing_dependency:mlflow")
        next_steps.append("Install or activate an environment that includes mlflow.")
    tracking_ready = any(item.name == "MLFLOW_TRACKING_URI" and item.status in {"set", "exported"} for item in export_ready)
    if env_status("MLFLOW_TRACKING_URI") == "missing" and not tracking_ready:
        next_steps.append("Confirm local or remote MLFLOW_TRACKING_URI before MLflow verification.")
    setting_source = model_settings or ai_env
    if model_settings is None and not (project / "ai_studio.env").exists():
        failures.append("missing_model_settings_file:runtest.py_or_run_model.py")
        next_steps.append("Fill MLflow/AI Studio settings directly in runtest.py or run_model.py.")
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
        env_vars=env_vars,
        ai_studio_env=ai_env,
        model_settings=model_settings,
        export_ready=export_ready,
        blocked_summary=blocked_summary,
        failures=failures,
        next_steps=next_steps,
        tod_guide=tod_guide,
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
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    if not project.exists():
        raise FileNotFoundError(f"project folder not found: {project}")

    report = build_report(project)
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
