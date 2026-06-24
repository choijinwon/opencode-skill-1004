import argparse
import json
import os
import platform
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "samples"

# When no project path is provided, selectable sample projects are inspected in
# this order. They match the bootstrap choices exposed to users.
SAMPLE_PRIORITY = ["sklearn_sample", "pytorch_sample", "tensorflow_sample"]

# The skill pack does not require a fixed file name. These common names are
# used only as hints when detecting a registration or inference entrypoint.
ENTRYPOINT_NAMES = [
    "register_model.py",
    "runtest.py",
    "run_model.py",
    "serve.py",
    "inference.py",
    "predict.py",
    "main.py",
    "app.py",
    "train.py",
]

CONFIG_NAMES = [
    "ai_studio.env",
    "config.json",
    "model_config.json",
    "mlflow_config.json",
    "config.yaml",
    "config.yml",
]

INPUT_EXAMPLE_NAMES = [
    "input_example.json",
    "sample_input.json",
    "example.json",
]

ARTIFACT_SUFFIXES = [
    ".pkl",
    ".joblib",
    ".pt",
    ".pth",
    ".onnx",
    ".h5",
    ".keras",
    ".bst",
    ".ubj",
    ".safetensors",
]

ARTIFACT_DIR_HINTS = [
    "save_model",
    "saved_model.pb",
    "variables",
    "tokenizer.json",
    "pytorch_model.bin",
    "model.safetensors",
]

REQUIRED_DIRS = [
    "aiu_custom",
    "local_serving",
    "save_model",
]

SAMPLE_SPEC_FILES = [
    "requirements.txt",
    "input_example.json",
]

AI_STUDIO_ENV_KEYS = [
    "mlflow_tracking_url",
    "mlflow_tracking_username",
    "mlflow_tracking_password",
    "mlflow_experiment_name",
    "mlflow_register_model_name",
]


@dataclass
class Check:
    name: str
    status: str
    message: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    selected_project: str
    selection_reason: str
    os: str
    python: str
    checks: list[Check]
    next_steps: list[str]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def safe_relative(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def has_project_markers(path: Path) -> bool:
    # Treat the current directory as a model project only when it has clear
    # ML project markers. This prevents the repository root from being selected
    # just because it contains the skill pack itself.
    marker_names = {
        "requirements.txt",
        "pyproject.toml",
        "environment.yml",
        "environment.yaml",
        "config.json",
        "input_example.json",
        "register_model.py",
        "runtest.py",
        "run_model.py",
        "train.py",
    }
    if any((path / name).exists() for name in marker_names):
        return True
    direct_artifact_dirs = [path / "ai_studio", path / "save_model", path / "artifacts", path / "model", path / "saved_model"]
    if any(candidate.exists() for candidate in direct_artifact_dirs):
        return True
    return any(file_path.suffix.lower() in ARTIFACT_SUFFIXES for file_path in path.iterdir() if file_path.is_file())


def score_project(path: Path) -> int:
    # The score is intentionally simple and transparent. It is a candidate
    # ranking aid, not a pass/fail quality score.
    score = 0
    if (path / "requirements.txt").exists():
        score += 5
    if any((path / name).exists() for name in ENTRYPOINT_NAMES):
        score += 4
    if find_artifacts(path, max_depth=3):
        score += 3
    if any((path / name).exists() for name in CONFIG_NAMES):
        score += 2
    if any((path / name).exists() for name in INPUT_EXAMPLE_NAMES):
        score += 2
    if all((path / name).is_dir() for name in REQUIRED_DIRS):
        score += 2
    return score


def select_project(explicit: str | None) -> tuple[Path, str]:
    # Priority:
    # 1. explicit user path
    # 2. current directory when it looks like a model project
    # 3. bundled samples, using SAMPLE_PRIORITY as a tie breaker
    if explicit:
        project = Path(explicit).expanduser().resolve()
        return project, "explicit path"

    cwd = Path.cwd().resolve()
    if has_project_markers(cwd):
        return cwd, "current directory has model project markers"

    for name in SAMPLE_PRIORITY:
        candidate = SAMPLES_DIR / name
        if candidate.exists() and score_project(candidate) > 0:
            return candidate.resolve(), f"sample priority: {candidate.name}"

    raise FileNotFoundError("No model project candidate found. Provide --project.")


def iter_files(path: Path, max_depth: int = 4):
    # Limit traversal depth and skip heavy/generated directories so this script
    # remains safe to run in large Windows workspaces.
    base_depth = len(path.parts)
    for root, dirs, files in os.walk(path):
        root_path = Path(root)
        depth = len(root_path.parts) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = [d for d in dirs if d not in {".git", ".venv", "__pycache__", "mlruns"}]
        for file_name in files:
            yield root_path / file_name


def find_artifacts(path: Path, max_depth: int = 4) -> list[Path]:
    artifacts: list[Path] = []
    for file_path in iter_files(path, max_depth=max_depth):
        if file_path.suffix.lower() in ARTIFACT_SUFFIXES:
            artifacts.append(file_path)
        if file_path.name in ARTIFACT_DIR_HINTS:
            artifacts.append(file_path)
    return sorted(set(artifacts))


def detect_framework(project: Path, requirements_text: str, artifacts: list[Path]) -> tuple[str, list[str]]:
    # Framework detection is evidence-based and conservative. Unknown/custom is
    # valid when the project does not expose recognizable dependency or artifact
    # hints.
    evidence: list[str] = []
    lowered = requirements_text.lower()
    artifact_names = " ".join(path.name.lower() for path in artifacts)

    rules = [
        ("tensorflow", ["tensorflow", "keras", ".keras", ".h5", "saved_model.pb"]),
        ("pytorch", ["torch", ".pt", ".pth", "pytorch_model.bin"]),
        ("sklearn", ["scikit-learn", "sklearn", ".pkl", ".joblib"]),
        ("onnx", ["onnx", ".onnx"]),
        ("huggingface", ["transformers", "tokenizer.json", "model.safetensors"]),
        ("xgboost", ["xgboost", ".bst", ".ubj"]),
        ("lightgbm", ["lightgbm"]),
    ]

    for framework, hints in rules:
        matched = [hint for hint in hints if hint in lowered or hint in artifact_names]
        if matched:
            evidence.extend(matched)
            return framework, evidence
    return "unknown/custom", evidence


def parse_requirements(project: Path) -> tuple[Path | None, str, list[str]]:
    req = project / "requirements.txt"
    if not req.exists():
        return None, "", []
    text = read_text(req)
    packages = []
    for line in text.splitlines():
        clean = line.strip()
        if clean and not clean.startswith("#"):
            packages.append(clean)
    return req, text, packages


def check_json_file(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"invalid json: {exc}"
    except OSError as exc:
        return False, f"read error: {exc}"
    return True, "valid json"


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


def check_ai_studio_env(project: Path, code_settings: list[str]) -> Check:
    path = project / "ai_studio.env"
    values = parse_env_file(path)
    evidence = []
    missing = []
    if path.exists():
        evidence.append("ai_studio.env")
    evidence.extend(code_settings)
    for key in AI_STUDIO_ENV_KEYS:
        found_in_env = key in values and values[key] != ""
        found_in_code = any(key in item for item in code_settings)
        if not found_in_env and not found_in_code:
            missing.append(key)
        elif found_in_env:
            evidence.append(f"{key}: set")
    if missing:
        return Check(
            "ai_studio.env required settings",
            "block",
            "required MLflow settings are missing or empty",
            [f"missing_or_empty: {', '.join(missing)}"] + evidence,
        )
    return Check(
        "ai_studio.env required settings",
        "pass",
        "required MLflow settings are available from entrypoint code or ai_studio.env",
        evidence,
    )


def find_first_existing(project: Path, names: list[str]) -> Path | None:
    for name in names:
        candidate = project / name
        if candidate.exists():
            return candidate
    return None


def find_entrypoints(project: Path) -> list[Path]:
    found = [project / name for name in ENTRYPOINT_NAMES if (project / name).exists()]
    found.extend(path for path in iter_files(project, max_depth=2) if path.suffix == ".py")
    return sorted(set(found))


def check_aiu_custom(project: Path, entrypoints: list[Path]) -> Check:
    # AI Studio style pyfunc registration depends on aiu_custom being shipped
    # with the model project because mlflow.pyfunc.log_model uses it through
    # code_paths and ModelWrapper.
    entrypoint_text = "\n".join(read_text(path) for path in entrypoints)
    required = any(
        marker in entrypoint_text
        for marker in ["aiu_custom", "ModelWrapper", "code_paths", "PythonModel"]
    )
    aiu_dir = project / "aiu_custom"
    model_wrapper_file = aiu_dir / "model_wrapper.py"
    predict_file = model_wrapper_file if model_wrapper_file.exists() else aiu_dir / "predict.py"

    if not required and not aiu_dir.exists():
        return Check(
            "AI Studio custom wrapper",
            "pass",
            "aiu_custom is not required by detected entrypoints",
            [],
        )
    if not required and aiu_dir.exists():
        evidence = ["aiu_custom/"]
        if model_wrapper_file.exists():
            evidence.append("aiu_custom/model_wrapper.py")
        elif (aiu_dir / "predict.py").exists():
            evidence.append("aiu_custom/predict.py")
        return Check(
            "AI Studio custom wrapper",
            "pass",
            "aiu_custom scaffold is available; ModelWrapper is not required by detected entrypoints",
            evidence,
        )

    evidence = []
    if aiu_dir.exists():
        evidence.append("aiu_custom/")
    if model_wrapper_file.exists():
        evidence.append("aiu_custom/model_wrapper.py")
    elif predict_file.exists():
        evidence.append("aiu_custom/predict.py")
    predict_text = read_text(predict_file)
    if "ModelWrapper" in predict_text:
        evidence.append("ModelWrapper")
    if "mlflow.pyfunc.PythonModel" in predict_text or "PythonModel" in predict_text:
        evidence.append("PythonModel")

    missing = []
    if not aiu_dir.exists():
        missing.append("aiu_custom/")
    if not predict_file.exists():
        missing.append("aiu_custom/model_wrapper.py or aiu_custom/predict.py")
    if predict_file.exists() and "ModelWrapper" not in predict_text:
        missing.append("ModelWrapper class")

    if missing:
        return Check(
            "AI Studio custom wrapper",
            "block",
            "aiu_custom wrapper is required but incomplete",
            evidence + [f"missing: {item}" for item in missing],
        )
    return Check(
        "AI Studio custom wrapper",
        "pass",
        "aiu_custom wrapper is available",
        evidence,
    )


def check_required_dirs(project: Path) -> Check:
    evidence = []
    missing = []
    for name in REQUIRED_DIRS:
        if (project / name).is_dir():
            evidence.append(f"{name}/")
        else:
            missing.append(f"{name}/")
    if missing:
        return Check(
            "required project folders",
            "block",
            "required folders are missing",
            [f"missing: {', '.join(missing)}"] + evidence,
        )
    return Check(
        "required project folders",
        "pass",
        "required folders are available",
        evidence,
    )


def sample_key_for_framework(framework: str) -> str:
    if framework in {"sklearn", "pytorch", "tensorflow"}:
        return framework
    return "pytorch"


def sample_spec_missing(project: Path) -> list[str]:
    missing = []
    for name in REQUIRED_DIRS:
        if not (project / name).is_dir():
            missing.append(f"{name}/")
    for name in SAMPLE_SPEC_FILES:
        if not (project / name).exists():
            missing.append(name)
    if not find_entrypoints(project):
        missing.append("training entrypoint")
    if not ((project / "aiu_custom" / "predict.py").exists() or (project / "aiu_custom" / "model_wrapper.py").exists()):
        missing.append("aiu_custom/predict.py")
    if not (project / "local_serving" / "serve.py").exists():
        missing.append("local_serving/serve.py")
    return missing


def check_entrypoint_confirmation(project: Path, entrypoints: list[Path]) -> Check:
    evidence = [safe_relative(path, project) for path in entrypoints[:10]]
    if not entrypoints:
        return Check(
            "entrypoint confirmation",
            "warn",
            "training/model creation entrypoint is not confirmed",
            ["사용자에게 실제 사용하는 파일명을 요청하세요."],
        )
    if len(entrypoints) == 1:
        return Check(
            "entrypoint confirmation",
            "pass",
            "single entrypoint candidate found",
            evidence,
        )
    return Check(
        "entrypoint confirmation",
        "warn",
        "multiple entrypoint candidates found; user confirmation is required",
        evidence + ["로컬 학습/모델 생성에 실제로 사용하는 파일명을 확정하세요."],
    )


def check_sample_spec(project: Path, framework: str) -> Check:
    missing = sample_spec_missing(project)
    evidence = [f"sample: {sample_key_for_framework(framework)}"]
    if missing:
        return Check(
            "sample spec scaffold",
            "warn",
            "model exists, but sample-spec folders/files are incomplete",
            evidence + [f"missing: {item}" for item in missing],
        )
    return Check(
        "sample spec scaffold",
        "pass",
        "model project already matches the sample scaffold",
        evidence,
    )


def write_permission_check(project: Path) -> Check:
    try:
        with tempfile.NamedTemporaryFile(prefix=".mlflow_skill_check_", dir=project, delete=True) as handle:
            handle.write(b"ok")
        return Check(
            name="Windows/write permission check",
            status="pass",
            message="project directory is writable",
            evidence=[str(project)],
        )
    except OSError as exc:
        return Check(
            name="Windows/write permission check",
            status="block",
            message=f"project directory is not writable: {exc}",
            evidence=[str(project)],
        )


def windows_path_check(project: Path) -> Check:
    evidence = [str(project)]
    path_text = str(project)
    warnings = []
    if " " in path_text:
        warnings.append("path contains spaces; quote paths in shell commands")
    if len(path_text) > 240:
        warnings.append("path length is near the classic Windows MAX_PATH limit")
    if platform.system().lower() == "windows":
        evidence.append("running on Windows")
    else:
        evidence.append(f"running on {platform.system()}")

    if warnings:
        return Check("Windows/path compatibility", "warn", "; ".join(warnings), evidence)
    return Check("Windows/path compatibility", "pass", "path is compatible with common Windows constraints", evidence)


def has_prepare_only(entrypoints: list[Path]) -> tuple[bool, list[str]]:
    evidence = []
    # --prepare-only is only one possible implementation. "preflight" or a
    # prepare() function can provide the same registration-before-execution check.
    patterns = ["--prepare-only", "prepare_only", "preflight", "prepare("]
    for path in entrypoints:
        text = read_text(path)
        matched = [pattern for pattern in patterns if pattern in text]
        if matched:
            evidence.append(f"{path.name}: {', '.join(matched)}")
    return bool(evidence), evidence


def has_register_flow(entrypoints: list[Path]) -> tuple[bool, list[str]]:
    evidence = []
    patterns = ["mlflow.", "log_model", "start_run", "registered_model_name"]
    for path in entrypoints:
        text = read_text(path)
        matched = [pattern for pattern in patterns if pattern in text]
        if matched:
            evidence.append(f"{path.name}: {', '.join(matched)}")
    return bool(evidence), evidence


def find_mlflow_code_settings(entrypoints: list[Path]) -> list[str]:
    evidence = []
    setting_names = [
        "mlflow_tracking_url",
        "mlflow_tracking_username",
        "mlflow_tracking_password",
        "mlflow_experiment_name",
        "mlflow_register_model_name",
    ]
    for path in entrypoints:
        text = read_text(path)
        matched = [name for name in setting_names if name in text]
        if matched:
            evidence.append(f"{path.name}: {', '.join(matched)}")
    return evidence


def build_report(project: Path, reason: str, write_check: bool) -> ValidationReport:
    # Build the report in the same order as the 7 OpenCode skills:
    # model select -> project check -> mlflow check -> gap guide ->
    # run-model guide -> preflight check -> register guide.
    checks: list[Check] = []
    project = project.resolve()

    if not project.exists():
        checks.append(Check("local model path selection", "block", "selected project path does not exist", [str(project)]))
        return ValidationReport(str(project), reason, platform.platform(), sys.version.split()[0], checks, ["Provide a valid --project path."])

    checks.append(Check("local model path selection", "pass", "project selected", [str(project), reason]))

    requirements_path, requirements_text, packages = parse_requirements(project)
    artifacts = find_artifacts(project)
    framework, framework_evidence = detect_framework(project, requirements_text, artifacts)
    entrypoints = find_entrypoints(project)
    config_file = find_first_existing(project, CONFIG_NAMES)
    input_example_file = find_first_existing(project, INPUT_EXAMPLE_NAMES)

    project_evidence = []
    if requirements_path:
        project_evidence.append(safe_relative(requirements_path, project))
    project_evidence.extend(safe_relative(path, project) for path in entrypoints[:5])
    project_evidence.extend(safe_relative(path, project) for path in artifacts[:5])
    checks.append(
        Check(
            "project scan",
            "pass" if entrypoints or artifacts or requirements_path else "warn",
            f"framework candidate: {framework}",
            project_evidence + framework_evidence,
        )
    )
    checks.append(check_entrypoint_confirmation(project, entrypoints))
    checks.append(check_required_dirs(project))
    checks.append(check_sample_spec(project, framework))
    checks.append(check_aiu_custom(project, entrypoints))

    mlflow_evidence = []
    has_mlflow_dep = any(re.match(r"(?i)^mlflow([=<>!~ ]|$)", pkg) for pkg in packages)
    if requirements_path:
        mlflow_evidence.append(f"requirements: {safe_relative(requirements_path, project)}")
    code_settings = find_mlflow_code_settings(entrypoints)
    mlflow_evidence.extend(code_settings)
    checks.append(
        Check(
            "MLflow readiness",
            "pass" if has_mlflow_dep else "warn",
            "mlflow dependency found" if has_mlflow_dep else "mlflow dependency is not confirmed",
            mlflow_evidence,
        )
    )

    # Code constants and project config files are the expected places to
    # confirm MLflow settings.
    config_ok = False
    if config_file:
        config_ok, config_message = check_json_file(config_file) if config_file.suffix == ".json" else (True, "config file exists")
    else:
        config_message = "config file not found"

    input_ok = False
    if input_example_file:
        input_ok, input_message = check_json_file(input_example_file)
    else:
        input_message = "input example not found"

    gap_status = "pass" if config_file and input_example_file and artifacts else "warn"
    checks.append(
        Check(
            "gap guidance",
            gap_status,
            "missing or review-required items are classified",
            [
                f"config: {config_message}",
                f"input_example: {input_message}",
                f"artifact_count: {len(artifacts)}",
            ],
        )
    )
    checks.append(check_ai_studio_env(project, code_settings))

    register_found, register_evidence = has_register_flow(entrypoints)
    checks.append(
        Check(
            "registration/entrypoint guidance",
            "pass" if register_found else "warn",
            "registration flow evidence found" if register_found else "registration entrypoint is not confirmed",
            register_evidence or [safe_relative(path, project) for path in entrypoints[:5]],
        )
    )

    prepare_found, prepare_evidence = has_prepare_only(entrypoints)
    checks.append(
        Check(
            "prepare-only/preflight check",
            "pass" if prepare_found else "warn",
            "prepare-only or preflight evidence found" if prepare_found else "prepare-only/preflight behavior is not confirmed",
            prepare_evidence,
        )
    )

    local_remote_evidence = []
    # Do not assume a fixed local tracking URI. Each user's local/remote MLflow
    # target should come from their config or environment.
    if config_file and config_file.suffix == ".json":
        try:
            payload = json.loads(config_file.read_text(encoding="utf-8"))
            for key in ["registered_model_name", "experiment_name", "tracking_uri", "tracking_url"]:
                if key in payload:
                    local_remote_evidence.append(f"{key}: present")
        except json.JSONDecodeError:
            pass
    local_remote_evidence.extend(code_settings)
    checks.append(
        Check(
            "local/remote MLflow registration readiness",
            "pass" if local_remote_evidence else "warn",
            "registration settings evidence found" if local_remote_evidence else "tracking/registration settings are not confirmed",
            local_remote_evidence,
        )
    )

    checks.append(windows_path_check(project))
    if write_check:
        checks.append(write_permission_check(project))

    next_steps = []
    if any(check.status == "block" for check in checks):
        next_steps.append("Resolve blocked checks before MLflow registration.")
    if not has_mlflow_dep:
        next_steps.append("Add or confirm mlflow dependency in the project environment.")
    if not artifacts:
        next_steps.append("Run training or provide a model artifact path.")
    if not entrypoints:
        next_steps.append("로컬 학습/모델 생성에 실제로 사용하는 파일명을 알려주세요.")
    elif len(entrypoints) > 1:
        next_steps.append("Entrypoint candidates: " + ", ".join(safe_relative(path, project) for path in entrypoints[:10]))
        next_steps.append("여러 후보 중 실제 사용하는 실행 파일을 확정하세요.")
    missing_spec = sample_spec_missing(project)
    if missing_spec:
        sample_key = sample_key_for_framework(framework)
        next_steps.append(
            f"Sample spec scaffold missing: {', '.join(missing_spec)}."
        )
        next_steps.append(
            f"Copy missing scaffold without overwriting existing model files: python .opencode/scripts/bootstrap_sample_project.py --project {project} --sample {sample_key} --scaffold-existing --execute"
        )
    if not prepare_found:
        next_steps.append("Confirm a prepare-only or preflight behavior before registration.")
    if not local_remote_evidence:
        next_steps.append("Confirm local or remote MLflow tracking settings.")
    if not next_steps:
        next_steps.append("Proceed to local/remote MLflow registration guidance.")

    return ValidationReport(str(project), reason, platform.platform(), sys.version.split()[0], checks, next_steps)


def print_text(report: ValidationReport):
    print(f"Selected project: {report.selected_project}")
    print(f"Selection reason: {report.selection_reason}")
    print(f"OS: {report.os}")
    print(f"Python: {report.python}")
    print()
    for index, check in enumerate(report.checks, start=1):
        print(f"{index}. [{check.status}] {check.name}")
        print(f"   {check.message}")
        for evidence in check.evidence:
            print(f"   - {evidence}")
    print()
    print("Next steps:")
    for step in report.next_steps:
        print(f"- {step}")


def main():
    parser = argparse.ArgumentParser(description="Validate an MLflow model project using the skill pack checklist.")
    parser.add_argument("--project", help="model project path. If omitted, the script auto-selects a candidate.")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON output")
    parser.add_argument("--no-write-check", action="store_true", help="skip temporary write permission check")
    args = parser.parse_args()

    project, reason = select_project(args.project)
    report = build_report(project, reason, write_check=not args.no_write_check)
    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print_text(report)

    if any(check.status == "block" for check in report.checks):
        return 2
    if any(check.status == "warn" for check in report.checks):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
