import argparse
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
    "MLFLOW_EXPERIMENT_ID",
]

AI_STUDIO_ENV_KEYS = [
    "mlflow_tracking_url",
    "mlflow_tracking_username",
    "mlflow_tracking_password",
    "mlflow_experiment_name",
    "mlflow_register_model_name",
]

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
    blocked_summary: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


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


def build_report(project: Path) -> EnvironmentReport:
    python_version = platform.python_version()
    deps = dependency_files(project)
    packages = []
    for package in CORE_PACKAGES:
        version = package_version(package)
        packages.append(PackageStatus(package, "set" if version else "missing", version))

    env_vars = [EnvVarStatus(key, env_status(key)) for key in ENV_KEYS]
    ai_env = ai_studio_env_status(project)
    blocked_summary: list[str] = []
    failures: list[str] = []
    next_steps: list[str] = []
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
    if env_status("MLFLOW_TRACKING_URI") == "missing":
        next_steps.append("Confirm local or remote MLFLOW_TRACKING_URI before MLflow verification.")
    if not (project / "ai_studio.env").exists():
        failures.append("missing_env_file:ai_studio.env")
        next_steps.append("Create ai_studio.env with required MLflow settings.")
    for item in ai_env.key_status:
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
        blocked_summary=blocked_summary,
        failures=failures,
        next_steps=next_steps,
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
    if report.ai_studio_env:
        print(f"\nai_studio.env: {report.ai_studio_env.path}")
        for item in report.ai_studio_env.key_status:
            print(f"- {item.name}: {item.status}")
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
