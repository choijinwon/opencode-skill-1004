import argparse
import importlib.metadata
import json
import os
import platform
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from common.ai_studio_process import print_markdown_table
from common.mlflow_settings import AI_STUDIO_ENV_KEYS, EXPORT_ENV_MAP, default_env_text, parse_python_string_assignments, parse_setting_env_file
from common.workspace import is_filesystem_root, is_opencode_sample_source, resolve_workspace_project


ENV_KEYS = ["MLFLOW_TRACKING_URI", "MLFLOW_TRACKING_USERNAME", "MLFLOW_TRACKING_PASSWORD", "MLFLOW_EXPERIMENT_NAME", "MLFLOW_REGISTER_MODEL_NAME"]
ENTRYPOINTS = ["runtest_2.py", "runtest.py", "run_test.py", "train.py", "run_model.py", "run.py", "main.py", "app.py", "scripts/train.py"]
REQUIRED_FILE = Path(__file__).resolve().parent / "requirements.required.txt"
KIND_REQUIREMENTS = {
    "sklearn_pickle": ["joblib==1.5.1", "scikit-learn==1.7.0"],
    "sklearn_joblib": ["joblib==1.5.1", "scikit-learn==1.7.0"],
    "pytorch": ["numpy==1.26.4", "torch==2.7.1", "torchvision==0.22.1", "torchmetrics==1.7.3"],
    "onnx": ["onnxruntime==1.22.1"],
    "tensorflow_keras": ["tensorflow==2.19.0"],
    "tensorflow_h5": ["tensorflow==2.19.0"],
    "tensorflow_saved_model": ["tensorflow==2.19.0"],
    "safetensors": ["numpy==1.26.4", "torch==2.7.1", "safetensors==0.5.3"],
    "xgboost_bst": ["xgboost==3.0.2"],
    "xgboost_ubj": ["xgboost==3.0.2"],
}
KIND_PACKAGE = {"pytorch": "torch", "onnx": "onnxruntime", "tensorflow_keras": "tensorflow", "tensorflow_h5": "tensorflow", "tensorflow_saved_model": "tensorflow", "safetensors": "safetensors", "xgboost_bst": "xgboost", "xgboost_ubj": "xgboost", "sklearn_pickle": "joblib", "sklearn_joblib": "joblib"}
KIND_BY_SUFFIX = {".pt": "pytorch", ".pth": "pytorch", ".ckpt": "pytorch", ".onnx": "onnx", ".keras": "tensorflow_keras", ".h5": "tensorflow_h5", ".safetensors": "safetensors", ".bst": "xgboost_bst", ".ubj": "xgboost_ubj", ".pkl": "sklearn_pickle", ".joblib": "sklearn_joblib"}


@dataclass
class PackageStatus:
    name: str; status: str
    version: str | None = None
    required_version: str | None = None


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
    name: str; status: str


@dataclass
class EnvFileStatus:
    path: str
    key_status: list[EnvVarStatus]


@dataclass
class RequirementCandidate:
    package: str; source: str


@dataclass
class EnvironmentReport:
    project_path: str; os: str; python_executable: str; python_version: str
    expected_python_version: str; python_version_status: str; virtual_env: str; dependency_files: list[str]
    packages: list[PackageStatus] = field(default_factory=list)
    requirements: list[RequirementStatus] = field(default_factory=list)
    env_vars: list[EnvVarStatus] = field(default_factory=list)
    ai_studio_env: EnvFileStatus | None = None
    model_settings: EnvFileStatus | None = None
    export_ready: list[EnvVarStatus] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    source_input_required: list[EnvVarStatus] = field(default_factory=list)
    selected_model_path: str | None = None; selected_model_kind: str | None = None
    selected_required_package: str | None = None; selected_package_status: str | None = None
    selected_python_version: str | None = None
    requirement_candidates: list[RequirementCandidate] = field(default_factory=list)
    selected_model_recommendations: list[str] = field(default_factory=list)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def rel(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def package_name(requirement: str) -> str:
    return re.split(r"[<>=!~ ]", requirement.strip(), maxsplit=1)[0].lower().replace("_", "-")


def version_spec(requirement: str) -> str:
    match = re.search(r"([<>=!~]=?.*)$", requirement.strip())
    return match.group(1).strip() if match else "any"


def installed_version(name: str) -> str | None:
    aliases = {"sklearn": "scikit-learn", "cv2": "opencv-python"}
    try:
        return importlib.metadata.version(aliases.get(name, name))
    except importlib.metadata.PackageNotFoundError:
        return None


def requirement_status(installed: str | None, spec: str) -> str:
    if installed is None:
        return "missing"
    if spec in {"", "any"}:
        return "installed"
    if spec.startswith("==") and installed != spec[2:]:
        return "version_mismatch"
    return "installed"


def required_lines() -> list[str]:
    lines = [line.strip() for line in read_text(REQUIRED_FILE).splitlines() if line.strip() and not line.startswith("#")]
    return lines or ["mlflow", "kserve==0.15.0"]


def requirement_lines(project: Path) -> tuple[list[str], list[str]]:
    path = project / "requirements.txt"
    files = ["requirements.txt"] if path.exists() else []
    lines = [line.strip() for line in read_text(path).splitlines() if line.strip() and not line.strip().startswith("#")]
    return files, lines or required_lines()


def ensure_env(project: Path) -> Path:
    path = project / ".env"
    if not path.exists():
        path.write_text(default_env_text(), encoding="utf-8")
    return path


def env_status(path: Path) -> EnvFileStatus:
    values = parse_setting_env_file(path)
    rows = [EnvVarStatus(key, "set" if values.get(key) else "missing") for key in AI_STUDIO_ENV_KEYS]
    return EnvFileStatus(str(path), rows)


def model_settings_status(project: Path, entrypoint: str | None) -> EnvFileStatus | None:
    path = project / entrypoint if entrypoint else next((project / name for name in ENTRYPOINTS if (project / name).exists()), None)
    if path is None or not path.exists():
        return None
    values = parse_python_string_assignments(path)
    return EnvFileStatus(str(path), [EnvVarStatus(key, "set" if values.get(key) else "missing") for key in AI_STUDIO_ENV_KEYS])


def env_vars_from_file(status: EnvFileStatus) -> list[EnvVarStatus]:
    by_key = {item.name: item.status for item in status.key_status}
    return [EnvVarStatus(env_name, by_key.get(key, "missing")) for key, env_name in EXPORT_ENV_MAP.items()]


def selected_model(project: Path, entrypoint: str | None) -> tuple[str | None, str | None]:
    path = project / entrypoint if entrypoint else project / "runtest_2.py"
    values = parse_python_string_assignments(path)
    kind = values.get("MODEL_KIND") or values.get("model_kind")
    model_path = values.get("MODEL_PATH") or values.get("model_path")
    if not model_path:
        saved = sorted((project / "saved_model").glob("*")) if (project / "saved_model").exists() else []
        model_path = rel(saved[0], project) if len(saved) == 1 else None
    if not kind and model_path:
        kind = KIND_BY_SUFFIX.get(Path(model_path).suffix.lower())
    return model_path, kind


def requirement_candidates(kind: str | None, requirements: list[str]) -> list[RequirementCandidate]:
    base = [RequirementCandidate(line, "base") for line in required_lines()]
    selected = [RequirementCandidate(line, "selected_model") for line in KIND_REQUIREMENTS.get(kind or "", []) if package_name(line) not in {package_name(req) for req in requirements}]
    imports = [RequirementCandidate(item.package, "import") for item in selected]
    return base + selected + imports


def build_requirements(project: Path, kind: str | None) -> tuple[list[str], list[RequirementStatus], list[PackageStatus], list[RequirementCandidate]]:
    files, lines = requirement_lines(project)
    merged = list(dict.fromkeys(required_lines() + lines))
    candidates = requirement_candidates(kind, merged)
    for item in candidates:
        if item.source == "selected_model" and item.package not in merged:
            merged.append(item.package)
    reqs: list[RequirementStatus] = []
    packages: list[PackageStatus] = []
    for line in merged:
        name, spec = package_name(line), version_spec(line)
        version = installed_version(name)
        status = requirement_status(version, spec)
        reqs.append(RequirementStatus("requirements.txt" if line in lines else "base", line, name, spec, version, status))
        packages.append(PackageStatus(name, "set" if status == "installed" else status, version, spec))
    return files, reqs, packages, candidates


def blocked(project: Path, message: str, failure: str, step: str) -> EnvironmentReport:
    return EnvironmentReport(str(project), f"{platform.system()} {platform.release()}", sys.executable, platform.python_version(), "MLflow/requirements compatibility", "blocked", os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX") or "not detected", [], failures=[failure], next_steps=[message, step])


def build_report(project: Path, entrypoint_name: str | None = None, selected_python_version: str | None = None) -> EnvironmentReport:
    if is_filesystem_root(project):
        return blocked(project, "드라이브/파일시스템 루트 검색은 허용하지 않습니다.", "drive_root_scan_not_allowed", "선택한 워크스페이스 루트로 이동한 뒤 --project . 로 실행하세요.")
    if is_opencode_sample_source(project):
        return blocked(project, ".opencode/는 번들 스킬 원본이라 분석 대상이 아닙니다.", "opencode_sample_source_not_analysis_target", "실제 모델 프로젝트 폴더를 --project로 지정하세요.")
    project = project.resolve()
    selected_python = selected_python_version or platform.python_version()
    python_status = "set" if platform.python_version().startswith(selected_python) else "selected_version_diff"
    env_file = ensure_env(project)
    ai_env = env_status(env_file)
    settings = model_settings_status(project, entrypoint_name)
    model_path, kind = selected_model(project, entrypoint_name)
    deps, reqs, packages, candidates = build_requirements(project, kind)
    missing_env = [item for item in ai_env.key_status if item.status != "set"]
    bad_packages = [item.name for item in packages if item.status in {"missing", "version_mismatch"}]
    failures = [f"missing_env:{item.name}" for item in missing_env]
    next_steps = []
    if missing_env:
        next_steps.append(".env 5개 필수 입력값을 직접 입력하세요: " + ", ".join(item.name for item in missing_env))
    if bad_packages:
        next_steps.append("패키지 설치는 실행하지 않습니다. requirements.txt 기본 항목과 선택 모델 후보 패키지를 확인하세요.")
    if entrypoint_name and settings is None and entrypoint_name.replace("\\", "/").lstrip("./") == "runtest_2.py":
        next_steps.append("runtest_2.py는 4번 템플릿 변환에서 생성될 수 있습니다.")
    elif entrypoint_name and settings is None:
        failures.append(f"entrypoint_not_found:{entrypoint_name}")
        next_steps.append(f"지정한 실행 파일 경로를 찾지 못했습니다: {entrypoint_name}")
    required_pkg = KIND_PACKAGE.get(kind or "")
    package_status = next((item.status for item in packages if item.name == required_pkg), None)
    return EnvironmentReport(
        str(project), f"{platform.system()} {platform.release()}", sys.executable, platform.python_version(),
        "MLflow/requirements compatibility", python_status, os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX") or "not detected", deps,
        packages=packages, requirements=reqs, env_vars=[EnvVarStatus(key, "set" if os.environ.get(key) else "missing") for key in ENV_KEYS],
        ai_studio_env=ai_env, model_settings=settings, export_ready=env_vars_from_file(ai_env), failures=failures,
        next_steps=next_steps or ["환경 검증 완료. 4번 템플릿 변환으로 진행하세요."], source_input_required=missing_env,
        selected_model_path=model_path, selected_model_kind=kind, selected_required_package=required_pkg, selected_package_status=package_status,
        selected_python_version=selected_python, requirement_candidates=candidates, selected_model_recommendations=KIND_REQUIREMENTS.get(kind or "", []),
    )


def result_status(report: EnvironmentReport) -> str:
    return "차단" if report.failures else "확인"


def print_text(report: EnvironmentReport):
    print(f"3번 환경 검증: {result_status(report)}")
    print(f"Python: {report.python_version} ({report.python_version_status})")
    print(f".env: {report.ai_studio_env.path if report.ai_studio_env else 'missing'}")
    print("다음 단계:")
    for step in report.next_steps:
        print(f"- {step}")


def print_verbose_text(report: EnvironmentReport):
    print_text(report)
    print("\n.env")
    print_markdown_table(["Key", "Status"], [[item.name, item.status] for item in (report.ai_studio_env.key_status if report.ai_studio_env else [])])
    print("\nRequirements")
    print_markdown_table(["Package", "Required", "Installed", "Status"], [[item.name, item.required_version, item.installed_version or "", item.status] for item in report.requirements])
    print("\nCandidates")
    print_markdown_table(["Package", "Source"], [[item.package, item.source] for item in report.requirement_candidates])


def main():
    parser = argparse.ArgumentParser(description="Step 3: check .env and requirements without installing packages.")
    parser.add_argument("--project", default=".", help="model project folder")
    parser.add_argument("--entrypoint", help="runtime file such as runtest_2.py")
    parser.add_argument("--python-version", help="selected Python version")
    parser.add_argument("--fix-packages", action="store_true", help="kept for compatibility; package installation is disabled")
    parser.add_argument("--no-fix-packages", action="store_true", help="kept for compatibility")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    project = resolve_workspace_project(args.project)
    if not project.exists():
        raise FileNotFoundError(f"project folder not found: {project}")
    report = build_report(project, args.entrypoint, args.python_version)
    if args.fix_packages and not args.json:
        print("패키지 자동 설치는 비활성화되어 있습니다.")
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2)) if args.json else print_verbose_text(report) if args.verbose else print_text(report)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
