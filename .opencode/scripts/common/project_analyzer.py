import json
import os
import platform
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from common.mlflow_settings import AI_STUDIO_ENV_KEYS, AUTO_DEFAULT_SETTING_KEYS, parse_env_file
from common.ai_studio_process import print_markdown_table
from common.workspace import is_filesystem_root, is_opencode_sample_source, resolve_workspace_project, unique_paths

PS_PREPARE_MODEL_COMMAND = r"python .opencode/scripts/02-model-select/select_model.py --project . --model <번호|상대경로>"
PS_BOOTSTRAP_COMMAND = r"python .opencode/scripts/04-sample-bootstrap/bootstrap_sample_project.py"

ENTRYPOINT_NAMES = [
    "register_model.py",
    "runtest_2.py",
    "runtest.py",
    "run_test.py",
    "run_model.py",
    "run.py",
    "serve.py",
    "inference.py",
    "predict.py",
    "main.py",
    "app.py",
    "train.py",
]

TRAINING_ENTRYPOINT_NAMES = [
    "register_model.py",
    "runtest_2.py",
    "runtest.py",
    "run_test.py",
    "run_model.py",
    "run.py",
    "main.py",
    "app.py",
    "train.py",
    "scripts/train.py",
]

CONFIG_NAMES = [".env"]

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
    ".ckpt",
    ".onnx",
    ".h5",
    ".keras",
    ".bst",
    ".ubj",
    ".safetensors",
]

ARTIFACT_KIND_BY_SUFFIX = {
    ".keras": "tensorflow_keras",
    ".h5": "tensorflow_h5",
    ".pt": "pytorch",
    ".pth": "pytorch",
    ".ckpt": "pytorch",
    ".safetensors": "safetensors",
    ".onnx": "onnx",
    ".pkl": "sklearn_pickle",
    ".joblib": "sklearn_joblib",
    ".bst": "xgboost_bst",
    ".ubj": "xgboost_ubj",
}

TRAINING_CODE_PATTERN = re.compile(
    r"("
    r"\bmodel\.fit\s*\(|"
    r"\bmodel\.compile\s*\(|"
    r"\btorch\.save\s*\(|"
    r"\bmodel\.save\s*\(|"
    r"\bsave_model\s*\(|"
    r"\bjoblib\.dump\s*\(|"
    r"\bpickle\.dump\s*\(|"
    r"\bxgb\.save_model\s*\(|"
    r"\bsave_pretrained\s*\("
    r")",
    re.IGNORECASE,
)

CODE_SCAN_SUFFIXES = {".py", ".ipynb"}

FRAMEWORK_CODE_RULES = [
    ("tensorflow", ["tensorflow", "tf.keras", "keras", ".compile(", ".save(", "saved_model"]),
    ("pytorch", ["torch", "torch.save", "save_pretrained", ".pt", ".pth", ".ckpt"]),
    ("sklearn", ["sklearn", "scikit", "train_test_split", "model.fit("]),
    ("xgboost", ["xgboost", "xgb.", "xgbclassifier", "xgbregressor", "save_model"]),
]

ARTIFACT_DIR_HINTS = [
    "saved_model",
    "saved_model.pb",
    "variables",
    "tokenizer.json",
    "pytorch_model.bin",
    "model.safetensors",
]

SCAN_SKIP_DIRS = {
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


def should_skip_dir_name(name: str) -> bool:
    return name in SCAN_SKIP_DIRS or name.startswith(".opencode")

REQUIRED_DIRS = [
    "aiu_custom",
    "local_serving",
    "saved_model",
]

SAMPLE_SPEC_FILES = [
    "requirements.txt",
    "input_example.json",
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
    model_artifact_paths: list[str] = field(default_factory=list)
    selectable_model_paths: list[str] = field(default_factory=list)
    model_found: bool = False
    analysis_case: str = ""
    training_code_paths: list[str] = field(default_factory=list)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def safe_call(default, func, *args):
    try:
        return func(*args)
    except OSError:
        return default


def safe_exists(path: Path) -> bool:
    return safe_call(False, path.exists)


def safe_is_file(path: Path) -> bool:
    return safe_call(False, path.is_file)


def safe_is_dir(path: Path) -> bool:
    return safe_call(False, path.is_dir)


def safe_iterdir(path: Path):
    try:
        yield from path.iterdir()
    except OSError:
        return


def safe_glob(path: Path, pattern: str):
    try:
        yield from path.glob(pattern)
    except OSError:
        return


def safe_relative(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def normalize_path_text(value: str) -> str:
    return value.replace("\\", "/").replace("＼", "/").replace("￦", "/").replace("₩", "/")


def artifact_kind(path: Path) -> str | None:
    return ARTIFACT_KIND_BY_SUFFIX.get(path.suffix.lower())


def model_sort_key(path: Path, project: Path) -> str:
    try:
        relative = path.resolve().relative_to(project.resolve())
    except ValueError:
        relative = path
    return normalize_path_text(str(relative)).lower()


def has_project_markers(path: Path) -> bool:
    marker_names = {
        "requirements.txt",
        "pyproject.toml",
        "environment.yml",
        "environment.yaml",
        "input_example.json",
        "register_model.py",
        "runtest.py",
        "run_model.py",
        "train.py",
    }
    if any(safe_exists(path / name) for name in marker_names):
        return True
    direct_artifact_dirs = [path / "ai_studio", path / "data", path / "saved_model", path / "artifacts", path / "model"]
    if any(safe_exists(candidate) for candidate in direct_artifact_dirs):
        return True
    if find_artifacts(path, max_depth=3):
        return True
    return any(file_path.suffix.lower() in ARTIFACT_SUFFIXES for file_path in safe_iterdir(path) if safe_is_file(file_path))


def score_project(path: Path) -> int:
    score = 0
    if safe_exists(path / "requirements.txt"):
        score += 5
    if any(safe_exists(path / name) for name in ENTRYPOINT_NAMES):
        score += 4
    if find_artifacts(path, max_depth=3):
        score += 3
    if any(safe_exists(path / name) for name in CONFIG_NAMES):
        score += 2
    if any(safe_exists(path / name) for name in INPUT_EXAMPLE_NAMES):
        score += 2
    if all(safe_is_dir(path / name) for name in REQUIRED_DIRS):
        score += 2
    return score


def select_project(explicit: str | None) -> tuple[Path, str]:
    if explicit:
        project = resolve_workspace_project(explicit)
        return project, "explicit path"

    return resolve_workspace_project("."), "current directory only"


def walk_project(path: Path, max_depth: int):
    if is_opencode_sample_source(path):
        return
    base_depth = len(path.parts)
    for root, dirs, files in os.walk(path, onerror=lambda _error: None):
        root_path = Path(root)
        depth = len(root_path.parts) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = [d for d in dirs if not should_skip_dir_name(d)]
        yield root_path, files


def iter_files(path: Path, max_depth: int = 4):
    for root_path, files in walk_project(path, max_depth):
        for file_name in files:
            candidate = root_path / file_name
            if safe_is_file(candidate):
                yield candidate


def is_saved_model_dir(path: Path) -> bool:
    return safe_is_dir(path) and safe_exists(path / "saved_model.pb")


def iter_artifact_dirs(path: Path, max_depth: int = 4):
    for root_path, _files in walk_project(path, max_depth):
        if is_saved_model_dir(root_path):
            yield root_path


def find_artifacts(path: Path, max_depth: int = 8) -> list[Path]:
    artifacts: list[Path] = []
    artifacts.extend(iter_artifact_dirs(path, max_depth=max_depth))
    for file_path in iter_files(path, max_depth=max_depth):
        if file_path.suffix.lower() in ARTIFACT_SUFFIXES:
            artifacts.append(file_path)
        if file_path.name == "saved_model.pb":
            artifacts.append(file_path.parent)
        elif file_path.name in ARTIFACT_DIR_HINTS:
            artifacts.append(file_path)
    return sorted(set(artifacts), key=lambda item: model_sort_key(item, path))


def notebook_text(path: Path) -> str:
    try:
        payload = json.loads(read_text(path))
    except json.JSONDecodeError:
        return read_text(path)
    cells = payload.get("cells") if isinstance(payload, dict) else None
    if not isinstance(cells, list):
        return read_text(path)
    parts: list[str] = []
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            parts.append("".join(str(item) for item in source))
        elif isinstance(source, str):
            parts.append(source)
    return "\n".join(parts)


def read_code_text(path: Path) -> str:
    if path.suffix.lower() == ".ipynb":
        return notebook_text(path)
    return read_text(path)


def iter_code_files(project: Path, max_depth: int = 5):
    seen: set[Path] = set()
    for root_path, files in walk_project(project, max_depth):
        for file_name in files:
            candidate = root_path / file_name
            if candidate.suffix.lower() not in CODE_SCAN_SUFFIXES:
                continue
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if resolved in seen or not safe_is_file(candidate):
                continue
            seen.add(resolved)
            yield candidate


def detect_training_code(project: Path) -> tuple[list[Path], list[str], list[str]]:
    hits: list[Path] = []
    evidence: list[str] = []
    frameworks: list[str] = []
    for path in iter_code_files(project):
        text = read_code_text(path)
        match = TRAINING_CODE_PATTERN.search(text)
        if not match:
            continue
        hits.append(path)
        evidence.append(f"{safe_relative(path, project)}: {match.group(0).strip()}")
        lowered = text.lower()
        for framework, hints in FRAMEWORK_CODE_RULES:
            if framework in frameworks:
                continue
            if any(hint in lowered for hint in hints):
                frameworks.append(framework)
    return unique_paths(hits), evidence, frameworks


def detect_framework(project: Path, requirements_text: str, artifacts: list[Path], training_frameworks: list[str]) -> tuple[str, list[str]]:
    evidence: list[str] = []
    if training_frameworks:
        framework = training_frameworks[0]
        evidence.append(f"training_code: {framework}")
        return framework, evidence

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
    if not safe_exists(req):
        return None, "", []
    text = read_text(req)
    packages = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    return req, text, packages


def check_json_file(path: Path) -> tuple[bool, str]:
    if not safe_exists(path):
        return False, "missing"
    try:
        json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        return False, f"invalid json: {exc}"
    except OSError as exc:
        return False, f"read error: {exc}"
    return True, "valid json"


def check_ai_studio_env(project: Path, code_settings: list[str]) -> Check:
    path = project / ".env"
    values = parse_env_file(path)
    evidence = []
    missing = []
    if safe_exists(path):
        evidence.append(".env")
    for key in AI_STUDIO_ENV_KEYS:
        found_in_env = key in values and values[key] != ""
        if key in AUTO_DEFAULT_SETTING_KEYS and not found_in_env:
            evidence.append(f"{key}: auto_default")
            continue
        if not found_in_env:
            missing.append(key)
        elif found_in_env:
            evidence.append(f"{key}: set")
    if missing:
        return Check(
            ".env required settings",
            "block",
            "required MLflow settings are missing or empty",
            [f"missing_or_empty: {', '.join(missing)}"] + evidence,
        )
    return Check(
        ".env required settings",
        "pass",
        "required MLflow settings are available from .env",
        evidence,
    )


def find_first_existing(project: Path, names: list[str]) -> Path | None:
    return next((project / name for name in names if safe_exists(project / name)), None)


def named_entrypoints(project: Path, names: list[str]) -> list[Path]:
    found = [project / name for name in names if safe_exists(project / name)]
    found.extend(path for path in safe_glob(project, "*.py") if safe_is_file(path))
    return unique_paths(found)


def find_entrypoints(project: Path) -> list[Path]:
    return named_entrypoints(project, ENTRYPOINT_NAMES)


def find_training_entrypoints(project: Path) -> list[Path]:
    return named_entrypoints(project, TRAINING_ENTRYPOINT_NAMES)


def check_aiu_custom(project: Path, entrypoints: list[Path]) -> Check:
    entrypoint_text = "\n".join(read_text(path) for path in entrypoints)
    required = any(
        marker in entrypoint_text
        for marker in ["aiu_custom", "ModelWrapper", "PythonModel"]
    )
    aiu_dir = project / "aiu_custom"
    model_wrapper_file = aiu_dir / "model_wrapper.py"
    predict_file = model_wrapper_file if safe_exists(model_wrapper_file) else aiu_dir / "predict.py"

    if not required and not safe_exists(aiu_dir):
        return Check(
            "AI Studio custom wrapper",
            "pass",
            "aiu_custom is not required by detected entrypoints",
            [],
        )
    if not required and safe_exists(aiu_dir):
        evidence = ["aiu_custom/"]
        if safe_exists(model_wrapper_file):
            evidence.append("aiu_custom/model_wrapper.py")
        elif safe_exists(aiu_dir / "predict.py"):
            evidence.append("aiu_custom/predict.py")
        return Check(
            "AI Studio custom wrapper",
            "pass",
            "aiu_custom scaffold is available; ModelWrapper is not required by detected entrypoints",
            evidence,
        )

    evidence = []
    if safe_exists(aiu_dir):
        evidence.append("aiu_custom/")
    if safe_exists(model_wrapper_file):
        evidence.append("aiu_custom/model_wrapper.py")
    elif safe_exists(predict_file):
        evidence.append("aiu_custom/predict.py")
    predict_text = read_text(predict_file)
    if "ModelWrapper" in predict_text:
        evidence.append("ModelWrapper")
    if "mlflow.pyfunc.PythonModel" in predict_text or "PythonModel" in predict_text:
        evidence.append("PythonModel")

    missing = []
    if not safe_exists(aiu_dir):
        missing.append("aiu_custom/")
    if not safe_exists(predict_file):
        missing.append("aiu_custom/model_wrapper.py or aiu_custom/predict.py")
    if safe_exists(predict_file) and "ModelWrapper" not in predict_text:
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
        if safe_is_dir(project / name):
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
        if not safe_is_dir(project / name):
            missing.append(f"{name}/")
    for name in SAMPLE_SPEC_FILES:
        if not safe_exists(project / name):
            missing.append(name)
    if not find_training_entrypoints(project):
        missing.append("training entrypoint")
    if not (safe_exists(project / "aiu_custom" / "predict.py") or safe_exists(project / "aiu_custom" / "model_wrapper.py")):
        missing.append("aiu_custom/predict.py")
    if not safe_exists(project / "local_serving" / "serve.py"):
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
        evidence + ["실제 사용하는 Python 실행 파일명을 확정하세요."],
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
            evidence=["."],
        )
    except OSError as exc:
        return Check(
            name="Windows/write permission check",
            status="block",
            message=f"project directory is not writable: {exc}",
            evidence=["."],
        )


def windows_path_check(project: Path) -> Check:
    evidence = ["."]
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
    return entrypoint_pattern_evidence(entrypoints, ["--prepare-only", "prepare_only", "preflight", "prepare("])


def entrypoint_pattern_evidence(entrypoints: list[Path], patterns: list[str]) -> tuple[bool, list[str]]:
    evidence = []
    for path in entrypoints:
        text = read_text(path)
        matched = [pattern for pattern in patterns if pattern in text]
        if matched:
            evidence.append(f"{path.name}: {', '.join(matched)}")
    return bool(evidence), evidence


def has_register_flow(entrypoints: list[Path]) -> tuple[bool, list[str]]:
    return entrypoint_pattern_evidence(entrypoints, ["mlflow.", "log_model", "start_run", "registered_model_name"])


def find_mlflow_code_settings(entrypoints: list[Path]) -> list[str]:
    setting_names = [
        "mlflow_tracking_uri",
        "mlflow_tracking_username",
        "mlflow_tracking_password",
        "mlflow_experiment_name",
        "mlflow_register_model_name",
    ]
    return entrypoint_pattern_evidence(entrypoints, setting_names)[1]


def build_report(project: Path, reason: str, write_check: bool) -> ValidationReport:
    checks: list[Check] = []
    project = project.resolve()

    if not safe_exists(project):
        checks.append(Check("local model path selection", "block", "selected project path does not exist", ["."]))
        return ValidationReport(".", reason, platform.platform(), sys.version.split()[0], checks, ["Provide a valid --project path."])
    if is_filesystem_root(project):
        checks.append(Check("local model path selection", "block", "drive/root scan is not allowed", ["."]))
        return ValidationReport(".", reason, platform.platform(), sys.version.split()[0], checks, ["선택한 워크스페이스 루트로 이동한 뒤 --project . 로 실행하세요."])
    if is_opencode_sample_source(project):
        checks.append(Check("local model path selection", "block", ".opencode/ is bundled skill source, not a user model project", ["."]))
        return ValidationReport(".", reason, platform.platform(), sys.version.split()[0], checks, ["Use the actual selected model project folder as --project."])

    checks.append(Check("local model path selection", "pass", "project selected", [".", reason]))

    requirements_path, requirements_text, packages = parse_requirements(project)
    artifacts = find_artifacts(project)
    training_code_paths, training_code_evidence, training_frameworks = detect_training_code(project)
    framework, framework_evidence = detect_framework(project, requirements_text, artifacts, training_frameworks)
    entrypoints = find_entrypoints(project)
    training_entrypoints = find_training_entrypoints(project)
    config_file = find_first_existing(project, CONFIG_NAMES)
    input_example_file = find_first_existing(project, INPUT_EXAMPLE_NAMES)

    model_found = bool(training_code_paths or artifacts)

    if training_code_paths:
        analysis_case = "case 1: training code"
        analysis_message = "py/ipynb 파일에서 model.fit(), model.compile(), save 계열 학습 로직이 감지되었습니다. 해당 프레임워크 템플릿 변환 안내로 진행합니다."
        analysis_evidence = training_code_evidence[:10]
    elif artifacts:
        analysis_case = "case 2: pre-trained model artifact"
        analysis_message = "pth, pkl, h5, onnx, SavedModel 폴더 등 pre-trained 모델 파일만 감지되었습니다. 모델 선택 흐름으로 진행합니다."
        analysis_evidence = [safe_relative(path, project) for path in artifacts[:10]]
    else:
        analysis_case = "case 3: false"
        analysis_message = "학습 코드와 모델 artifact가 없습니다. pytorch_sample / sklearn_sample / tensorflow_sample 중 하나를 선택하는 흐름으로 진행합니다."
        analysis_evidence = [
            "pytorch_sample",
            "sklearn_sample",
            "tensorflow_sample",
        ]

    project_evidence = []
    if requirements_path:
        project_evidence.append(safe_relative(requirements_path, project))
    project_evidence.extend(safe_relative(path, project) for path in entrypoints[:5])
    project_evidence.extend(safe_relative(path, project) for path in artifacts[:5])

    checks.append(
        Check(
            "workspace analysis case",
            "pass" if model_found else "warn",
            analysis_message,
            [analysis_case] + analysis_evidence,
        )
    )

    checks.append(
        Check(
            "project scan",
            "pass" if entrypoints or artifacts or requirements_path else "warn",
            f"framework candidate: {framework}",
            project_evidence + framework_evidence,
        )
    )
    checks.append(check_entrypoint_confirmation(project, training_entrypoints))
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

    if config_file:
        _config_ok, config_message = check_json_file(config_file) if config_file.suffix == ".json" else (True, "config file exists")
    else:
        config_message = "config file not found"

    if input_example_file:
        _input_ok, input_message = check_json_file(input_example_file)
    else:
        input_message = "input example not found"

    selectable_paths = [safe_relative(path, project) for path in training_code_paths]
    selectable_paths.extend(safe_relative(path, project) for path in artifacts)

    gap_status = "pass" if config_file and input_example_file and (artifacts or training_code_paths) else "warn"
    checks.append(
        Check(
            "gap guidance",
            gap_status,
            "missing or review-required items are classified",
            [
                f"config: {config_message}",
                f"input_example: {input_message}",
                f"selectable_model_count: {len(selectable_paths)}",
                f"artifact_count: {len(artifacts)}",
                f"training_code_count: {len(training_code_paths)}",
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
    if config_file and config_file.suffix == ".json":
        try:
            payload = json.loads(read_text(config_file))
            for key in ["registered_model_name", "experiment_name", "tracking_uri"]:
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
    if training_code_paths:
        entrypoint = safe_relative(training_code_paths[0], project)
        next_steps.append(f"Case 1: 학습 코드가 감지되었습니다. framework={framework}, entrypoint={entrypoint}")
        next_steps.append("3번 환경 검증 후 4번 템플릿 변환에서 해당 프레임워크 기준으로 연결부를 변환하세요.")
    elif artifacts:
        next_steps.append("Case 2: Pre-trained 모델 파일만 감지되었습니다. 모델을 번호 또는 경로로 선택한 뒤 3번 환경 검증으로 진행하세요.")
        next_steps.append(f"Run: {PS_PREPARE_MODEL_COMMAND}")
    else:
        next_steps.append("Case 3: 모델이 없습니다. 샘플 선택 1 sklearn / 2 pytorch / 3 tensorflow 중 하나를 선택하세요.")
    if any(check.status == "block" for check in checks):
        next_steps.append("Resolve blocked checks before MLflow registration.")
    if not has_mlflow_dep:
        next_steps.append("Add or confirm mlflow dependency in the project environment.")
    if not artifacts and not training_code_paths:
        next_steps.append("Run training or provide a model artifact path.")
    if not training_entrypoints:
        next_steps.append("실제 사용하는 Python 실행 파일명을 알려주세요.")
    elif len(training_entrypoints) > 1:
        next_steps.append("Entrypoint candidates: " + ", ".join(safe_relative(path, project) for path in training_entrypoints[:10]))
        next_steps.append("여러 후보 중 실제 사용하는 실행 파일을 확정하세요.")
    missing_spec = sample_spec_missing(project)
    if missing_spec:
        sample_key = sample_key_for_framework(framework)
        next_steps.append(
            f"Sample spec scaffold missing: {', '.join(missing_spec)}."
        )
        next_steps.append(
            f"Copy missing scaffold without overwriting existing model files: {PS_BOOTSTRAP_COMMAND} --project . --sample {sample_key} --scaffold-existing --execute"
        )
    if not prepare_found:
        next_steps.append("Confirm a prepare-only or preflight behavior before registration.")
    if not local_remote_evidence:
        next_steps.append(".env에 원격 MLflow/리포트 URI, username, password를 직접 입력하세요.")
    if not next_steps:
        next_steps.append("Proceed to local/remote MLflow registration guidance.")

    return ValidationReport(
        ".",
        reason,
        platform.platform(),
        sys.version.split()[0],
        checks,
        next_steps,
        model_artifact_paths=[safe_relative(path, project) for path in artifacts],
        selectable_model_paths=selectable_paths,
        model_found=model_found,
        analysis_case=analysis_case,
        training_code_paths=[safe_relative(path, project) for path in training_code_paths],
    )


def print_model_list(report: ValidationReport):
    rows: list[tuple[str, str, str, str]] = []
    for path in report.training_code_paths:
        location = "file"
        rows.append((path, "training_code", location, "선택 가능"))
    for path in report.model_artifact_paths:
        suffix = Path(path).suffix.lower()
        kind = ARTIFACT_KIND_BY_SUFFIX.get(suffix, "unknown")
        location = "data"
        rows.append((path, kind, location, "선택 가능"))
    if rows:
        print("| No | Model Path | MODEL_KIND | Location | Status |")
        print("|---:|---|---|---|---|")
        for index, (path, kind, location, status) in enumerate(rows, start=1):
            print(f"| {index} | {path} | {kind} | {location} | {status} |")
        return
    print("| No | Sample |")
    print("|---:|---|")
    print("| 1 | sklearn_sample |")
    print("| 2 | pytorch_sample |")
    print("| 3 | tensorflow_sample |")


def print_text(report: ValidationReport):
    count = len(report.selectable_model_paths) or (len(report.model_artifact_paths) + len(report.training_code_paths))
    if report.model_found:
        print(f"분석 완료: 모델 있음 ({count}개)")
        print("다음 단계: 사용할 모델 번호를 선택해주세요.")
        return
    print("분석 완료: 모델 없음")
    print("다음 단계: 샘플을 선택해주세요. 1 sklearn / 2 pytorch / 3 tensorflow")


def print_verbose_text(report: ValidationReport):
    print_markdown_table(
        ["항목", "값"],
        [
            ["Selected project", report.selected_project],
            ["Selection reason", report.selection_reason],
            ["OS", report.os],
            ["Python", report.python],
            ["model_found", str(report.model_found).lower()],
            ["analysis_case", report.analysis_case or "none"],
        ],
    )
    if report.analysis_case:
        pass
    if report.training_code_paths:
        print("Training code paths:")
        print_markdown_table(["No", "Entrypoint Path"], [[str(index), path] for index, path in enumerate(report.training_code_paths, start=1)])
    if report.model_artifact_paths:
        print("Model artifact paths:")
        print_markdown_table(["No", "Model Path"], [[str(index), path] for index, path in enumerate(report.model_artifact_paths, start=1)])
    print()
    check_rows = []
    for index, check in enumerate(report.checks, start=1):
        evidence = "; ".join(check.evidence) if check.evidence else ""
        check_rows.append([str(index), check.status, check.name, check.message, evidence])
    print_markdown_table(["No", "Status", "Check", "Message", "Evidence"], check_rows)
    print()
    print("Next steps:")
    print_markdown_table(["No", "Next Step"], [[str(index), step] for index, step in enumerate(report.next_steps, start=1)])
