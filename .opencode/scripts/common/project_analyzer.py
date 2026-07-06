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

from common.ai_studio_process import print_markdown_table
from common.workspace import is_filesystem_root, is_opencode_sample_source, resolve_workspace_project


ENTRYPOINT_NAMES = ["register_model.py", "runtest_2.py", "runtest.py", "run_test.py", "run_model.py", "run.py", "main.py", "app.py", "train.py", "scripts/train.py"]
ARTIFACT_KIND_BY_SUFFIX = {".keras": "tensorflow_keras", ".h5": "tensorflow_h5", ".pt": "pytorch", ".pth": "pytorch", ".ckpt": "pytorch", ".safetensors": "safetensors", ".onnx": "onnx", ".pkl": "sklearn_pickle", ".joblib": "sklearn_joblib", ".bst": "xgboost_bst", ".ubj": "xgboost_ubj"}
ARTIFACT_SUFFIXES = set(ARTIFACT_KIND_BY_SUFFIX)
ARTIFACT_HINT_NAMES = {"saved_model.pb", "tokenizer.json", "pytorch_model.bin", "model.safetensors"}
CODE_SUFFIXES = {".py", ".ipynb"}
SKIP_DIRS = {".git", ".mlflow-local", ".mypy_cache", ".opencode", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__", "ai_studio", "build", "dist", "env", "node_modules", "venv"}
TRAINING_CODE_PATTERN = re.compile(r"\b(model\.(fit|compile|save)|torch\.save|save_model|joblib\.dump|pickle\.dump|xgb\.save_model|save_pretrained)\s*\(", re.IGNORECASE)
FRAMEWORK_RULES = [("tensorflow", ["tensorflow", "tf.keras", "keras", ".keras", ".h5", "saved_model.pb"]), ("pytorch", ["torch", ".pt", ".pth", ".ckpt", "pytorch_model.bin", "model.safetensors"]), ("sklearn", ["scikit-learn", "sklearn", ".pkl", ".joblib"]), ("onnx", ["onnx", ".onnx"]), ("huggingface", ["transformers", "tokenizer.json", "safetensors"]), ("xgboost", ["xgboost", "xgb.", ".bst", ".ubj"])]


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


def safe_bool(method) -> bool:
    try:
        return method()
    except OSError:
        return False


def exists(path: Path) -> bool:
    return safe_bool(path.exists)


def is_file(path: Path) -> bool:
    return safe_bool(path.is_file)


def rel(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def normalize_path_text(value: str) -> str:
    return value.replace("\\", "/").replace("＼", "/").replace("￦", "/").replace("₩", "/")


def unique(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = normalize_path_text(str(path.resolve() if exists(path) else path))
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def walk_project(project: Path, max_depth: int):
    if is_opencode_sample_source(project):
        return
    base_depth = len(project.parts)
    for root, dirs, files in os.walk(project, onerror=lambda _error: None):
        root_path = Path(root)
        if len(root_path.parts) - base_depth >= max_depth:
            dirs[:] = []
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS and not name.startswith(".opencode")]
        yield root_path, files


def select_project(explicit: str | None) -> tuple[Path, str]:
    if explicit:
        return resolve_workspace_project(explicit), "explicit path"
    return resolve_workspace_project("."), "current directory only"


def model_sort_key(path: Path, project: Path) -> str:
    return normalize_path_text(rel(path, project)).lower()


def artifact_kind(path_text: str) -> str:
    path = Path(path_text)
    if path.name == "saved_model" or path.suffix == "":
        return "tensorflow_saved_model" if "saved_model" in path.parts else "unknown"
    return ARTIFACT_KIND_BY_SUFFIX.get(path.suffix.lower(), "unknown")


def find_artifacts(project: Path, max_depth: int = 8) -> list[Path]:
    found: list[Path] = []
    for root, files in walk_project(project, max_depth):
        if exists(root / "saved_model.pb"):
            found.append(root)
        for name in files:
            path = root / name
            if name == "saved_model.pb":
                found.append(root)
            elif path.suffix.lower() in ARTIFACT_SUFFIXES or name in ARTIFACT_HINT_NAMES:
                found.append(path)
    return sorted(unique(found), key=lambda path: model_sort_key(path, project))


def notebook_text(path: Path) -> str:
    raw = read_text(path)
    try:
        cells = json.loads(raw).get("cells", [])
    except (json.JSONDecodeError, AttributeError):
        return raw
    parts: list[str] = []
    for cell in cells if isinstance(cells, list) else []:
        source = cell.get("source", "") if isinstance(cell, dict) else ""
        parts.append("".join(source) if isinstance(source, list) else str(source))
    return "\n".join(parts)


def code_text(path: Path) -> str:
    return notebook_text(path) if path.suffix.lower() == ".ipynb" else read_text(path)


def detect_training_code(project: Path) -> tuple[list[Path], list[str], list[str]]:
    hits: list[Path] = []
    evidence: list[str] = []
    frameworks: list[str] = []
    for root, files in walk_project(project, 5):
        for name in files:
            path = root / name
            if path.suffix.lower() not in CODE_SUFFIXES or not is_file(path):
                continue
            text = code_text(path)
            match = TRAINING_CODE_PATTERN.search(text)
            if not match:
                continue
            hits.append(path)
            evidence.append(f"{rel(path, project)}: {match.group(0).strip()}")
            lowered = text.lower()
            for framework, hints in FRAMEWORK_RULES:
                if framework not in frameworks and any(hint in lowered for hint in hints):
                    frameworks.append(framework)
    return unique(hits), evidence, frameworks


def read_requirements(project: Path) -> tuple[Path | None, str, list[str]]:
    path = project / "requirements.txt"
    if not exists(path):
        return None, "", []
    text = read_text(path)
    packages = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    return path, text, packages


def detect_framework(requirements: str, artifacts: list[Path], training_frameworks: list[str]) -> tuple[str, list[str]]:
    if training_frameworks:
        return training_frameworks[0], [f"training_code: {training_frameworks[0]}"]
    haystack = f"{requirements.lower()} {' '.join(path.name.lower() for path in artifacts)}"
    for framework, hints in FRAMEWORK_RULES:
        matched = [hint for hint in hints if hint in haystack]
        if matched:
            return framework, matched
    return "unknown/custom", []


def find_entrypoints(project: Path) -> list[str]:
    found = [name for name in ENTRYPOINT_NAMES if exists(project / name)]
    try:
        found.extend(path.name for path in project.glob("*.py") if is_file(path))
    except OSError:
        pass
    return list(dict.fromkeys(found))


def check_write(project: Path) -> Check:
    try:
        with tempfile.NamedTemporaryFile(prefix=".mlflow_skill_check_", dir=project, delete=True) as handle:
            handle.write(b"ok")
        return Check("write permission", "pass", "project directory is writable", ["."])
    except OSError as exc:
        return Check("write permission", "block", f"project directory is not writable: {exc}", ["."])


def blocked_report(reason: str, message: str, next_step: str) -> ValidationReport:
    check = Check("local model path selection", "block", message, ["."])
    return ValidationReport(".", reason, platform.platform(), sys.version.split()[0], [check], [next_step])


def build_report(project: Path, reason: str, write_check: bool) -> ValidationReport:
    project = project.resolve()
    if not exists(project):
        return blocked_report(reason, "selected project path does not exist", "Provide a valid --project path.")
    if is_filesystem_root(project):
        return blocked_report(reason, "drive/root scan is not allowed", "선택한 워크스페이스 루트로 이동한 뒤 --project . 로 실행하세요.")
    if is_opencode_sample_source(project):
        return blocked_report(reason, ".opencode/ is bundled skill source, not a user model project", "Use the actual selected model project folder as --project.")

    requirements_path, requirements_text, packages = read_requirements(project)
    artifacts = find_artifacts(project)
    training_paths, training_evidence, training_frameworks = detect_training_code(project)
    framework, framework_evidence = detect_framework(requirements_text, artifacts, training_frameworks)
    entrypoints = find_entrypoints(project)
    model_found = bool(training_paths or artifacts)
    selectable = [rel(path, project) for path in training_paths + artifacts]

    if training_paths:
        case, message, evidence = "case 1: training code", "학습 코드가 감지되었습니다.", training_evidence[:10]
    elif artifacts:
        case, message, evidence = "case 2: pre-trained model artifact", "pre-trained 모델 파일이 감지되었습니다.", [rel(path, project) for path in artifacts[:10]]
    else:
        case, message, evidence = "case 3: false", "학습 코드와 모델 artifact가 없습니다.", ["pytorch_sample", "sklearn_sample", "tensorflow_sample"]

    checks = [
        Check("local model path selection", "pass", "project selected", [".", reason]),
        Check("workspace analysis case", "pass" if model_found else "warn", message, [case] + evidence),
        Check("project scan", "pass" if model_found or requirements_path or entrypoints else "warn", f"framework candidate: {framework}", framework_evidence),
        Check("MLflow readiness", "pass" if any(re.match(r"(?i)^mlflow([=<>!~ ]|$)", pkg) for pkg in packages) else "warn", "mlflow dependency found" if packages else "mlflow dependency is not confirmed", [rel(requirements_path, project)] if requirements_path else []),
    ]
    if write_check:
        checks.append(check_write(project))

    next_steps = (
        [f"Case 1: 학습 코드가 감지되었습니다. framework={framework}, entrypoint={rel(training_paths[0], project)}", "3번 환경 검증 후 4번 템플릿 변환으로 진행하세요."]
        if training_paths else
        ["Case 2: Pre-trained 모델 파일만 감지되었습니다. 모델을 번호 또는 경로로 선택한 뒤 3번 환경 검증으로 진행하세요.", "Run: python .opencode/scripts/02-model-select/select_model.py --project . --model <번호|상대경로>"]
        if artifacts else
        ["Case 3: 모델이 없습니다. 샘플 선택 1 sklearn / 2 pytorch / 3 tensorflow 중 하나를 선택하세요."]
    )
    return ValidationReport(".", reason, platform.platform(), sys.version.split()[0], checks, next_steps, [rel(path, project) for path in artifacts], selectable, model_found, case, [rel(path, project) for path in training_paths])


def print_model_list(report: ValidationReport):
    rows = [(path, "training_code", "file", "선택 가능") for path in report.training_code_paths]
    rows.extend((path, artifact_kind(path), "data", "선택 가능") for path in report.model_artifact_paths)
    if not rows:
        print("| No | Sample |")
        print("|---:|---|")
        for index, sample in enumerate(["sklearn_sample", "pytorch_sample", "tensorflow_sample"], 1):
            print(f"| {index} | {sample} |")
        return
    print("| No | Model Path | MODEL_KIND | Location | Status |")
    print("|---:|---|---|---|---|")
    for index, (path, kind, location, status) in enumerate(rows, 1):
        print(f"| {index} | {path} | {kind} | {location} | {status} |")


def print_text(report: ValidationReport):
    if report.model_found:
        print(f"분석 완료: 모델 있음 ({len(report.selectable_model_paths)}개)")
        print("다음 단계: 사용할 모델 번호를 선택해주세요.")
    else:
        print("분석 완료: 모델 없음")
        print("다음 단계: 샘플을 선택해주세요. 1 sklearn / 2 pytorch / 3 tensorflow")


def print_verbose_text(report: ValidationReport):
    print_markdown_table(["항목", "값"], [["Selected project", report.selected_project], ["Selection reason", report.selection_reason], ["OS", report.os], ["Python", report.python], ["model_found", str(report.model_found).lower()], ["analysis_case", report.analysis_case or "none"]])
    if report.training_code_paths:
        print("Training code paths:")
        print_markdown_table(["No", "Entrypoint Path"], [[str(i), path] for i, path in enumerate(report.training_code_paths, 1)])
    if report.model_artifact_paths:
        print("Model artifact paths:")
        print_markdown_table(["No", "Model Path"], [[str(i), path] for i, path in enumerate(report.model_artifact_paths, 1)])
    print("\nChecks:")
    print_markdown_table(["No", "Status", "Check", "Message", "Evidence"], [[str(i), c.status, c.name, c.message, "; ".join(c.evidence)] for i, c in enumerate(report.checks, 1)])
    print("\nNext steps:")
    print_markdown_table(["No", "Next Step"], [[str(i), step] for i, step in enumerate(report.next_steps, 1)])
