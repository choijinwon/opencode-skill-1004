import argparse
import ast
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "samples"
SAMPLE_OPTIONS = ["sklearn", "pytorch", "tensorflow"]
ENTRYPOINTS = ["runtest.py", "train.py", "run_model.py", "scripts/train.py"]
REQUIRED_DIRS = ["aiu_custom", "local_serving", "save_model"]
ARTIFACT_DIRS = ["save_model", "model", "artifacts", "saved_model"]
ARTIFACT_SUFFIXES = {".pkl", ".joblib", ".pt", ".pth", ".h5", ".keras", ".onnx", ".safetensors"}
AI_STUDIO_ENV_KEYS = [
    "mlflow_tracking_url",
    "mlflow_tracking_username",
    "mlflow_tracking_password",
    "mlflow_experiment_name",
    "mlflow_register_model_name",
]
MODEL_SETTING_FILES = ["runtest.py", "run_model.py"]


@dataclass
class TrainingReport:
    project_path: str
    model_found: bool
    selected_sample: str | None
    work_path: str
    entrypoint: str | None
    command: list[str]
    executed: bool
    return_code: int | None
    artifacts: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


def has_model_project(project: Path) -> bool:
    markers = ["runtest.py", "train.py", "run_model.py", "predict.py", "input_example.json", "MLmodel"]
    if any((project / name).exists() for name in markers):
        return True
    if any((project / name).exists() for name in ARTIFACT_DIRS):
        return True
    return any(path.suffix in ARTIFACT_SUFFIXES for path in project.glob("*") if path.is_file())


def find_entrypoint(project: Path) -> Path | None:
    for name in ENTRYPOINTS:
        candidate = project / name
        if candidate.exists():
            return candidate
    return None


def build_command(python_bin: str, entrypoint: Path, prepare_only: bool) -> list[str]:
    cmd = [python_bin, str(entrypoint)]
    if prepare_only and entrypoint.name in {"run_model.py", "register_model.py"}:
        cmd.append("--prepare-only")
    return cmd


def find_artifacts(project: Path) -> list[str]:
    found: list[str] = []
    for name in ARTIFACT_DIRS:
        path = project / name
        if path.exists():
            found.append(str(path))
    for path in project.rglob("*"):
        if path.is_file() and (path.suffix in ARTIFACT_SUFFIXES or path.name in {"MLmodel", "python_model.pkl"}):
            found.append(str(path))
    return sorted(set(found))


def missing_required_dirs(project: Path) -> list[str]:
    return [name for name in REQUIRED_DIRS if not (project / name).is_dir()]


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


def find_model_settings(project: Path) -> dict[str, str]:
    for name in MODEL_SETTING_FILES:
        path = project / name
        if path.exists():
            return parse_python_string_assignments(path)
    return {}


def missing_ai_studio_env(project: Path) -> list[str]:
    path = project / "ai_studio.env"
    values = find_model_settings(project) or parse_env_file(path)
    missing = []
    if not values:
        missing.append("runtest.py_or_run_model.py_settings")
    for key in AI_STUDIO_ENV_KEYS:
        if key not in values or values[key] == "":
            missing.append(key)
    return missing


def run_command(cmd: list[str], cwd: Path) -> int:
    result = subprocess.run(cmd, cwd=cwd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Run local training for an existing project after ai_studio.env checks.")
    parser.add_argument("--project", default=".", help="user-specified model project folder")
    parser.add_argument("--python", default=sys.executable, help="Python interpreter to use")
    parser.add_argument("--execute", action="store_true", help="actually run the selected command")
    parser.add_argument("--force-sample", action="store_true", help="deprecated; use bootstrap_sample_project.py for sample folder copy")
    parser.add_argument("--prepare-only", action="store_true", help="prefer prepare-only mode when supported")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    if not project.exists():
        raise FileNotFoundError(f"project folder not found: {project}")

    failures: list[str] = []
    next_steps: list[str] = []
    selected_sample = None
    model_found = has_model_project(project)
    work_path = project

    if not model_found:
        failures.append("model_not_found")
        failures.append("sample_bootstrap_required: choose one of sklearn, pytorch, tensorflow and copy the sample folder first")
        next_steps.append("python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample sklearn --execute")

    entrypoint = find_entrypoint(work_path)
    if entrypoint is None:
        failures.append("missing_train_entrypoint")
        cmd = []
    else:
        cmd = build_command(args.python, entrypoint, args.prepare_only)

    return_code = None
    if args.execute and cmd:
        return_code = run_command(cmd, cwd=work_path)
        if return_code != 0:
            failures.append("runtime_error")
    elif cmd:
        next_steps.append("Run again with --execute to start training or model export.")

    artifacts = find_artifacts(work_path)
    missing_dirs = missing_required_dirs(work_path)
    if missing_dirs:
        failures.extend(f"missing_required_dir:{name}" for name in missing_dirs)
    missing_env = missing_ai_studio_env(work_path)
    if missing_env:
        failures.extend(f"missing_env:{name}" for name in missing_env)
    if args.execute and not artifacts:
        failures.append("artifact_not_created")

    report = TrainingReport(
        project_path=str(project),
        model_found=model_found,
        selected_sample=selected_sample,
        work_path=str(work_path),
        entrypoint=str(entrypoint) if entrypoint else None,
        command=cmd,
        executed=args.execute,
        return_code=return_code,
        artifacts=artifacts,
        failures=failures,
        next_steps=next_steps,
    )

    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print(f"Project: {report.project_path}")
        print(f"Work path: {report.work_path}")
        print(f"Model found: {report.model_found}")
        print(f"Selected sample: {report.selected_sample or 'none'}")
        print(f"Entrypoint: {report.entrypoint or 'missing'}")
        print(f"Command: {' '.join(report.command) if report.command else 'none'}")
        print(f"Executed: {report.executed}")
        print(f"Return code: {report.return_code}")
        print("Artifacts:")
        for artifact in report.artifacts:
            print(f"- {artifact}")
        if report.failures:
            print("Failures:")
            for failure in report.failures:
                print(f"- {failure}")
        if report.next_steps:
            print("Next steps:")
            for step in report.next_steps:
                print(f"- {step}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
