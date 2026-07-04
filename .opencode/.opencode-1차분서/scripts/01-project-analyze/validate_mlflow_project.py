import argparse
import json
import os
import platform
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path


# 현재 파일 기준으로 `.opencode-1차분서/` 루트를 찾습니다.
ROOT = Path(__file__).resolve().parents[2]
# 2번 모델 선택 단계로 넘길 때 보여줄 PowerShell 실행 예시입니다.
PS_PREPARE_MODEL_COMMAND = r"python .opencode/scripts/02-model-select/select_model.py --project . --model <번호|상대경로>"
# 모델이 없을 때 샘플 프로젝트를 만드는 다음 단계 실행 예시입니다.
PS_BOOTSTRAP_COMMAND = r"python .opencode/scripts/02-sample-bootstrap/bootstrap_sample_project.py"

# 스킬 팩은 실행 파일명을 강제하지 않습니다.
# 아래 목록은 등록/추론 진입점을 추정할 때 참고하는 대표 파일명 후보입니다.
ENTRYPOINT_NAMES = [
    "register_model.py",
    "runtest_2.py",
    "runtest.py",
    "run_test.py",
    "run_model.py",
    "run.py",
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

CONFIG_NAMES = [
    ".env",
]

# 입력 예시 파일 후보명입니다.
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
    ".ckpt",
    ".csv",
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

# 학습 코드가 있는지 빠르게 판별하기 위한 정규식입니다.
# case 1 기준:
# - .py / .ipynb 안에서
# - model.fit(), model.compile()
# - torch.save(), model.save(), save_model()
# 같은 학습/저장 흐름이 보이면 학습 코드가 있다고 판단합니다.
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

# 학습 코드 스캔 대상 파일 형식입니다.
CODE_SCAN_SUFFIXES = {".py", ".ipynb"}

# 코드 안의 import/키워드로 프레임워크 흔적을 찾을 때 사용합니다.
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

# 분석에서 제외할 폴더 목록입니다.
SCAN_SKIP_DIRS = {
    ".git",
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
    # .opencode 및 .opencode-* 단계 폴더는 번들/분석용 영역이므로 스캔에서 제외합니다.
    return name in SCAN_SKIP_DIRS or name.startswith(".opencode")

# 워크스페이스 하위 폴더 탐색 기본 깊이입니다.
DEFAULT_SCAN_MAX_DEPTH = 8

REQUIRED_DIRS = [
    "aiu_custom",
    "local_serving",
    "saved_model",
]

SAMPLE_SPEC_FILES = [
    "requirements.txt",
    "input_example.json",
]

# AI Studio 실행에 필요한 .env 키입니다.
AI_STUDIO_ENV_KEYS = [
    "mlflow_tracking_uri",
    "mlflow_tracking_username",
    "mlflow_tracking_password",
    "mlflow_experiment_name",
    "mlflow_register_model_name",
]
AUTO_DEFAULT_SETTING_KEYS = {
    "mlflow_experiment_name",
    "mlflow_register_model_name",
}


@dataclass
class Check:
    # 개별 점검 항목 결과를 담습니다.
    name: str
    status: str
    message: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    # 1단계 분석 결과 전체를 담는 리포트 구조입니다.
    selected_project: str
    selection_reason: str
    os: str
    python: str
    checks: list[Check]
    next_steps: list[str]
    model_artifact_paths: list[str] = field(default_factory=list)
    model_found: bool = False
    analysis_case: str = ""
    training_code_paths: list[str] = field(default_factory=list)


def print_markdown_table(headers: list[str], rows: list[list[str]]) -> None:
    # 콘솔 출력용 Markdown 표를 만듭니다.
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        print("| " + " | ".join(str(value) for value in row) + " |")


def read_text(path: Path) -> str:
    # 파일 읽기 실패가 나더라도 분석이 중단되지 않도록 빈 문자열로 처리합니다.
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def safe_exists(path: Path) -> bool:
    # 접근 오류가 나는 경로도 안전하게 검사합니다.
    try:
        return path.exists()
    except OSError:
        return False


def safe_is_file(path: Path) -> bool:
    # 경로가 실제 파일인지 확인합니다.
    # 권한/파일시스템 오류가 나면 예외 대신 False 를 반환합니다.
    try:
        return path.is_file()
    except OSError:
        return False


def safe_is_dir(path: Path) -> bool:
    # 경로가 실제 폴더(디렉터리)인지 확인합니다.
    # 접근 오류가 나더라도 분석이 중단되지 않게 False 로 처리합니다.
    try:
        return path.is_dir()
    except OSError:
        return False


def safe_iterdir(path: Path):
    # 권한/인코딩 문제로 디렉터리 순회가 실패해도 예외를 밖으로 던지지 않습니다.
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
    # base 기준 상대경로를 우선 쓰고, 불가능하면 원본 경로를 그대로 반환합니다.
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def normalize_path_text(value: str) -> str:
    # Windows/한글 키보드 백슬래시 변형 문자를 모두 '/' 기준으로 통일합니다.
    return value.replace("\\", "/").replace("＼", "/").replace("￦", "/").replace("₩", "/")


def artifact_kind(path: Path) -> str | None:
    # 파일 확장자만으로 모델 종류를 빠르게 추정합니다.
    return ARTIFACT_KIND_BY_SUFFIX.get(path.suffix.lower())


def model_sort_key(path: Path, project: Path) -> str:
    # 모델 목록은 워크스페이스 기준 상대경로 알파벳 순서로 고정합니다.
    try:
        relative = path.resolve().relative_to(project.resolve())
    except ValueError:
        relative = path
    return normalize_path_text(str(relative)).lower()


def has_project_markers(path: Path) -> bool:
    # 현재 폴더가 실제 모델 프로젝트처럼 보이는지 기본 흔적을 검사합니다.
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
    if find_artifacts(path, max_depth=DEFAULT_SCAN_MAX_DEPTH):
        return True
    return any(file_path.suffix.lower() in ARTIFACT_SUFFIXES for file_path in safe_iterdir(path) if safe_is_file(file_path))


def score_project(path: Path) -> int:
    # 여러 후보 폴더가 있을 때 우선순위를 정하기 위한 단순 점수입니다.
    score = 0
    if safe_exists(path / "requirements.txt"):
        score += 5
    if any(safe_exists(path / name) for name in ENTRYPOINT_NAMES):
        score += 4
    if find_artifacts(path, max_depth=DEFAULT_SCAN_MAX_DEPTH):
        score += 3
    if any(safe_exists(path / name) for name in CONFIG_NAMES):
        score += 2
    if any(safe_exists(path / name) for name in INPUT_EXAMPLE_NAMES):
        score += 2
    if all(safe_is_dir(path / name) for name in REQUIRED_DIRS):
        score += 2
    return score


def resolve_workspace_project(raw_project: str) -> Path:
    # 사용자가 넘긴 경로를 실제 워크스페이스 프로젝트 루트 기준으로 정규화합니다.
    raw = raw_project.strip()
    if raw in {"<workspace-root>", "<current-project-folder>", "<model-project-folder>"}:
        raw = "."
    elif "<" in raw or ">" in raw:
        raise ValueError("replace placeholder project path before running, for example: --project .")

    project = Path(raw).expanduser().resolve()
    parts = project.parts
    if ".opencode" in parts:
        opencode_index = parts.index(".opencode")
        if opencode_index > 0:
            return Path(*parts[:opencode_index]).resolve()
    return project


def select_project(explicit: str | None) -> tuple[Path, str]:
    # 현재 단계는 사용자가 지정한 프로젝트를 우선 사용하고, 없으면 현재 폴더를 씁니다.
    if explicit:
        project = resolve_workspace_project(explicit)
        return project, "explicit path"

    return resolve_workspace_project("."), "current directory only"


def is_filesystem_root(path: Path) -> bool:
    # 드라이브/파일시스템 루트 전체 검색을 막기 위한 판별입니다.
    return path.parent == path


def is_opencode_sample_source(path: Path) -> bool:
    # .opencode 번들/샘플 원본은 사용자 프로젝트가 아니므로 분석 대상에서 제외합니다.
    parts = path.resolve().parts
    if ".opencode" in parts:
        return True
    for index, part in enumerate(parts[:-1]):
        if part == ".opencode" and parts[index + 1] in {"sample", "samples"}:
            return True
    return False


def iter_files(path: Path, max_depth: int = DEFAULT_SCAN_MAX_DEPTH):
    if is_opencode_sample_source(path):
        return
    # 파일 탐색 범위는 현재 워크스페이스 전체 하위 폴더입니다.
    # 단, .opencode/.venv/node_modules 같은 제외 폴더는 내려가지 않습니다.
    base_depth = len(path.parts)
    for root, dirs, files in os.walk(path, onerror=lambda _error: None):
        root_path = Path(root)
        depth = len(root_path.parts) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = [d for d in dirs if not should_skip_dir_name(d)]
        for file_name in files:
            candidate = root_path / file_name
            if safe_is_file(candidate):
                yield candidate


def is_saved_model_dir(path: Path) -> bool:
    # TensorFlow SavedModel 폴더인지 간단히 판별합니다.
    return safe_is_dir(path) and safe_exists(path / "saved_model.pb")


def iter_artifact_dirs(path: Path, max_depth: int = DEFAULT_SCAN_MAX_DEPTH):
    # 파일형 모델뿐 아니라 디렉터리형 모델도 artifact 후보로 찾습니다.
    if is_opencode_sample_source(path):
        return
    base_depth = len(path.parts)
    for root, dirs, _files in os.walk(path, onerror=lambda _error: None):
        root_path = Path(root)
        depth = len(root_path.parts) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = [d for d in dirs if not should_skip_dir_name(d)]
        if is_saved_model_dir(root_path):
            yield root_path


def find_artifacts(path: Path, max_depth: int = DEFAULT_SCAN_MAX_DEPTH) -> list[Path]:
    # 모델 파일/폴더 후보를 한 번에 모아 정렬된 목록으로 반환합니다.
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
    # 노트북도 학습 코드 탐지 대상이라 셀 내용을 이어붙여 평문화합니다.
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
    # .py 와 .ipynb 를 동일한 방식으로 읽기 위한 헬퍼입니다.
    if path.suffix.lower() == ".ipynb":
        return notebook_text(path)
    return read_text(path)


def iter_code_files(project: Path, max_depth: int = 5):
    # 학습 코드 흔적을 찾을 코드 파일 목록을 안전하게 순회합니다.
    if is_opencode_sample_source(project):
        return
    base_depth = len(project.parts)
    seen: set[Path] = set()
    for root, dirs, files in os.walk(project, onerror=lambda _error: None):
        root_path = Path(root)
        depth = len(root_path.parts) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = [name for name in dirs if not should_skip_dir_name(name)]
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
    # model.fit / model.compile / torch.save 패턴으로 학습 코드 존재를 감지합니다.
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
    # 프레임워크 판별은 추정이 아니라 requirements/artifact/code 흔적을 근거로 합니다.
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
    # requirements.txt 원문과 실제 패키지 줄 목록을 함께 반환합니다.
    req = project / "requirements.txt"
    if not safe_exists(req):
        return None, "", []
    text = read_text(req)
    packages = []
    for line in text.splitlines():
        clean = line.strip()
        if clean and not clean.startswith("#"):
            packages.append(clean)
    return req, text, packages


def check_json_file(path: Path) -> tuple[bool, str]:
    # JSON 파일은 존재 여부와 파싱 가능 여부를 같이 점검합니다.
    if not safe_exists(path):
        return False, "missing"
    try:
        json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        return False, f"invalid json: {exc}"
    except OSError as exc:
        return False, f"read error: {exc}"
    return True, "valid json"


def parse_env_file(path: Path) -> dict[str, str]:
    # .env 는 키 존재 여부 확인용으로만 읽고 secret 값은 출력하지 않습니다.
    values: dict[str, str] = {}
    if not safe_exists(path):
        return values
    for raw_line in read_text(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def check_ai_studio_env(project: Path, code_settings: list[str]) -> Check:
    # AI Studio 실행에 필요한 .env 5개 키가 준비되었는지 검사합니다.
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
    # 여러 후보명 중 가장 먼저 존재하는 파일을 찾습니다.
    for name in names:
        candidate = project / name
        if safe_exists(candidate):
            return candidate
    return None


def unique_paths(paths: list[Path]) -> list[Path]:
    # resolve 기준으로 중복 경로를 제거해 목록을 안정화합니다.
    unique = []
    seen = set()
    for path in paths:
        try:
            key = path.resolve()
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def find_entrypoints(project: Path) -> list[Path]:
    # 일반 실행/등록/추론 엔트리포인트 후보를 수집합니다.
    found = [project / name for name in ENTRYPOINT_NAMES if safe_exists(project / name)]
    found.extend(path for path in safe_glob(project, "*.py") if safe_is_file(path))
    return unique_paths(found)


def find_training_entrypoints(project: Path) -> list[Path]:
    # 학습/등록 흐름과 더 관련 있는 엔트리포인트 후보만 따로 수집합니다.
    found = [project / name for name in TRAINING_ENTRYPOINT_NAMES if safe_exists(project / name)]
    found.extend(path for path in safe_glob(project, "*.py") if safe_is_file(path))
    return unique_paths(found)


def check_aiu_custom(project: Path, entrypoints: list[Path]) -> Check:
    # AI Studio 스타일 pyfunc 등록은 aiu_custom wrapper 존재 여부가 중요합니다.
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
    # 샘플 규격 기준으로 필요한 기본 폴더 3개 존재 여부를 점검합니다.
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
    # 프레임워크 이름을 샘플 폴더 키로 단순 변환합니다.
    if framework in {"sklearn", "pytorch", "tensorflow"}:
        return framework
    return "pytorch"


def sample_spec_missing(project: Path) -> list[str]:
    # 현재 프로젝트가 샘플 규격과 비교해 무엇이 빠졌는지 목록으로 반환합니다.
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
    # 엔트리포인트 후보가 0개/1개/여러 개인지에 따라 다음 액션을 정합니다.
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
    # 샘플 규격 대비 누락된 골격이 있는지 체크합니다.
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
    # 실제로 파일 생성이 가능한 프로젝트인지 임시 파일로 가볍게 검사합니다.
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
    # Windows에서 자주 문제가 되는 공백/경로 길이를 먼저 점검합니다.
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
    # 등록 전에 사전 점검만 수행하는 흐름이 있는지 코드 흔적으로 확인합니다.
    evidence = []
    # 구현마다 이름이 다를 수 있어 prepare/preflight 계열 패턴을 함께 찾습니다.
    patterns = ["--prepare-only", "prepare_only", "preflight", "prepare("]
    for path in entrypoints:
        text = read_text(path)
        matched = [pattern for pattern in patterns if pattern in text]
        if matched:
            evidence.append(f"{path.name}: {', '.join(matched)}")
    return bool(evidence), evidence


def has_register_flow(entrypoints: list[Path]) -> tuple[bool, list[str]]:
    # MLflow 등록 흐름(start_run, log_model 등)이 코드에 보이는지 확인합니다.
    evidence = []
    patterns = ["mlflow.", "log_model", "start_run", "registered_model_name"]
    for path in entrypoints:
        text = read_text(path)
        matched = [pattern for pattern in patterns if pattern in text]
        if matched:
            evidence.append(f"{path.name}: {', '.join(matched)}")
    return bool(evidence), evidence


def find_mlflow_code_settings(entrypoints: list[Path]) -> list[str]:
    # 코드 내부에 MLflow 설정 상수가 직접 들어 있는지 찾아 근거로 남깁니다.
    evidence = []
    setting_names = [
        "mlflow_tracking_uri",
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
    # 1단계 분석 결과를 한 번에 모아 최종 리포트 구조로 만듭니다.
    # 이후 2~7단계로 이어질 수 있게 근거와 next step도 같이 정리합니다.
    checks: list[Check] = []
    project = project.resolve()

    # 1) 먼저 분석 대상 프로젝트 경로가 유효한지 검사합니다.
    #    - 경로가 없으면 바로 중단
    #    - 파일시스템 루트 전체 검색은 차단
    #    - .opencode 번들 원본은 사용자 프로젝트가 아니므로 차단
    if not safe_exists(project):
        checks.append(Check("local model path selection", "block", "selected project path does not exist", ["."]))
        return ValidationReport(".", reason, platform.platform(), sys.version.split()[0], checks, ["Provide a valid --project path."])
    if is_filesystem_root(project):
        checks.append(Check("local model path selection", "block", "drive/root scan is not allowed", ["."]))
        return ValidationReport(".", reason, platform.platform(), sys.version.split()[0], checks, ["선택한 워크스페이스 루트로 이동한 뒤 --project . 로 실행하세요."])
    if is_opencode_sample_source(project):
        checks.append(Check("local model path selection", "block", ".opencode/ is bundled skill source, not a user model project", ["."]))
        return ValidationReport(".", reason, platform.platform(), sys.version.split()[0], checks, ["Use the actual selected model project folder as --project."])

    # 2) 경로가 정상이라면 현재 프로젝트를 분석 대상으로 확정합니다.
    checks.append(Check("local model path selection", "pass", "project selected", [".", reason]))

    # 3) 프로젝트 안의 핵심 단서를 한 번에 수집합니다.
    #    - requirements.txt
    #    - 모델 artifact 파일/폴더
    #    - 학습 코드 흔적
    #    - 프레임워크 후보
    #    - 엔트리포인트 후보
    #    - 설정 파일 / input example 파일
    requirements_path, requirements_text, packages = parse_requirements(project)
    artifacts = find_artifacts(project)
    training_code_paths, training_code_evidence, training_frameworks = detect_training_code(project)
    framework, framework_evidence = detect_framework(project, requirements_text, artifacts, training_frameworks)
    entrypoints = find_entrypoints(project)
    training_entrypoints = find_training_entrypoints(project)
    config_file = find_first_existing(project, CONFIG_NAMES)
    input_example_file = find_first_existing(project, INPUT_EXAMPLE_NAMES)

    # 4) 학습 코드 또는 모델 artifact가 하나라도 있으면 model_found=true 로 판단합니다.
    model_found = bool(training_code_paths or artifacts)

    # 5) 분석 결과를 3가지 케이스로 나눕니다.
    #    - case 1: 학습 코드 있음
    #    - case 2: pre-trained 모델 파일만 있음
    #    - case 3: false (모델/학습 코드 없음)
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

    # 6) 프로젝트 스캔 근거를 모읍니다.
    #    requirements, entrypoint, artifact 일부를 evidence 로 남겨
    #    왜 이렇게 판단했는지 나중에 확인할 수 있게 합니다.
    project_evidence = []
    if requirements_path:
        project_evidence.append(safe_relative(requirements_path, project))
    project_evidence.extend(safe_relative(path, project) for path in entrypoints[:5])
    project_evidence.extend(safe_relative(path, project) for path in artifacts[:5])

    # 7) "현재 프로젝트가 어떤 케이스인지" 체크 결과에 기록합니다.
    checks.append(
        Check(
            "workspace analysis case",
            "pass" if model_found else "warn",
            analysis_message,
            [analysis_case] + analysis_evidence,
        )
    )

    # 8) 전체 스캔 결과와 프레임워크 후보를 체크 결과에 기록합니다.
    checks.append(
        Check(
            "project scan",
            "pass" if entrypoints or artifacts or requirements_path else "warn",
            f"framework candidate: {framework}",
            project_evidence + framework_evidence,
        )
    )

    # 9) 이후 단계에 필요한 세부 점검들을 이어서 수행합니다.
    #    - 실행 파일 후보 확인
    #    - 필수 폴더 확인
    #    - 샘플 규격 비교
    #    - aiu_custom wrapper 확인
    checks.append(check_entrypoint_confirmation(project, training_entrypoints))
    checks.append(check_required_dirs(project))
    checks.append(check_sample_spec(project, framework))
    checks.append(check_aiu_custom(project, entrypoints))

    # 10) requirements.txt 안에 mlflow 의존성이 있는지 확인합니다.
    #     이후 MLflow 등록 가능 여부 판단의 기본 근거가 됩니다.
    mlflow_evidence = []
    has_mlflow_dep = any(re.match(r"(?i)^mlflow([=<>!~ ]|$)", pkg) for pkg in packages)
    if requirements_path:
        mlflow_evidence.append(f"requirements: {safe_relative(requirements_path, project)}")

    # 11) 코드 안에 직접 적힌 MLflow 설정 흔적도 함께 모읍니다.
    code_settings = find_mlflow_code_settings(entrypoints)
    mlflow_evidence.extend(code_settings)

    # 12) MLflow readiness 체크를 기록합니다.
    checks.append(
        Check(
            "MLflow readiness",
            "pass" if has_mlflow_dep else "warn",
            "mlflow dependency found" if has_mlflow_dep else "mlflow dependency is not confirmed",
            mlflow_evidence,
        )
    )

    # MLflow 설정은 코드 상수나 프로젝트 설정 파일에서 확인하는 것을 기본 전제로 둡니다.
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
    # local/remote MLflow 주소는 사용자 환경마다 다르므로 고정값을 가정하지 않습니다.
    if config_file and config_file.suffix == ".json":
        try:
            payload = json.loads(read_text(config_file))
            for key in ["registered_model_name", "experiment_name", "tracking_uri", "tracking_uri"]:
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
        model_found=model_found,
        analysis_case=analysis_case,
        training_code_paths=[safe_relative(path, project) for path in training_code_paths],
    )


def print_model_list(report: ValidationReport):
    # 모델/학습 코드/샘플 선택지는 모두 Markdown Table 형식으로 고정 출력합니다.
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
        print("| No | Path | MODEL_KIND | Location | Status |")
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
    # 기본 출력은 짧은 요약과 목록만 보여주는 간단 모드입니다.
    count = len(report.model_artifact_paths) + len(report.training_code_paths)
    print_markdown_table(
        ["항목", "값"],
        [
            ["현재 단계", "1. 프로젝트 분석"],
            ["model_found", str(report.model_found).lower()],
            ["analysis_case", report.analysis_case or "none"],
            ["발견 개수", str(count)],
        ],
    )
    print()
    print_model_list(report)


def print_verbose_text(report: ValidationReport):
    # 상세 출력은 내부 체크 결과와 next step까지 모두 보여주는 모드입니다.
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


def main():
    # CLI 인자를 받아 분석을 실행하고, 요청한 출력 형식으로 결과를 보여줍니다.
    parser = argparse.ArgumentParser(description="Validate an MLflow model project using the skill pack checklist.")
    parser.add_argument("--project", help="model project path. If omitted, the script auto-selects a candidate.")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON output")
    parser.add_argument("--list", action="store_true", help="print model/sample choices")
    parser.add_argument("--verbose", action="store_true", help="print detailed analysis checks")
    parser.add_argument("--no-write-check", action="store_true", help="skip temporary write permission check")
    parser.add_argument("--strict-exit", action="store_true", help="return non-zero when checks contain warn/block statuses")
    args = parser.parse_args()

    project, reason = select_project(args.project)
    report = build_report(project, reason, write_check=not args.no_write_check)
    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    elif args.list:
        print_model_list(report)
    elif args.verbose:
        print_verbose_text(report)
    else:
        print_text(report)

    if args.strict_exit:
        if any(check.status == "block" for check in report.checks):
            return 2
        if any(check.status == "warn" for check in report.checks):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
