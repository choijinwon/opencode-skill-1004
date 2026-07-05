import argparse
import json
import os
import platform
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path


# 현재 스크립트 파일 기준으로 .opencode 루트에 해당하는 기준 경로입니다.
# 다른 스크립트/샘플 경로를 계산할 때 공통 기준점으로 사용합니다.
ROOT = Path(__file__).resolve().parents[2]

# 사용자가 다음 단계로 바로 실행할 수 있게 안내할 대표 명령 문자열입니다.
# 실제 실행 로직이 아니라, 보고/가이드 메시지에 넣기 위한 "예시 명령" 역할입니다.
PS_PREPARE_MODEL_COMMAND = r"python .opencode/scripts/02-model-select/select_model.py --project . --model <번호|상대경로>"
PS_BOOTSTRAP_COMMAND = r"python .opencode/scripts/04-sample-bootstrap/bootstrap_sample_project.py"

# 실행 파일 후보명입니다.
# 이 프로젝트는 사용자가 run.py, runtest.py, main.py처럼 제각각 다른 이름을
# 사용할 수 있으므로, "정답 파일명"을 강제하지 않습니다.
# 대신 자주 쓰는 파일명을 후보로 모아두고, 현재 워크스페이스 안에 실제로 존재하는지
# 확인해서 엔트리포인트 후보를 추리는 힌트로만 사용합니다.
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

# 환경 설정 파일 후보명입니다.
# 현재는 .env 한 가지만 사용하지만, 이후 확장 가능성을 고려해 리스트로 둡니다.
CONFIG_NAMES = [
    ".env",
                    ]

# 입력 예시 파일 후보명입니다.
# MLflow/KServe/로컬 추론 테스트에서 흔히 쓰는 입력 예시 파일명을 함께 관리합니다.
INPUT_EXAMPLE_NAMES = [
    "input_example.json",
    "sample_input.json",
    "example.json",
]

# 모델 artifact 파일 확장자 후보 목록입니다.
# case 2(Pre-trained 모델 파일만 있음) 판별의 핵심 기준이며,
# 워크스페이스 안에서 이 확장자가 보이면 모델 후보로 취급합니다.
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

# 확장자별 모델 형식 매핑입니다.
# 모델 파일을 찾은 뒤, 어떤 샘플을 참조하고 어떤 연결부를 변환할지 결정할 때 사용합니다.
# 예:
# - .pt / .pth / .ckpt -> pytorch
# - .pkl / .joblib -> sklearn 계열
# - .onnx -> onnx
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
# case 1(학습 코드 있음) 판단은 "파일명이 train.py 인가?"가 아니라,
# 실제 코드 안에 학습/저장 동작이 보이는지를 기준으로 합니다.
#
# 감지 예시:
# - model.fit(...)
# - model.compile(...)
# - torch.save(...)
# - model.save(...)
# - save_model(...)
#
# 즉, 단순 유틸 파일이 아니라 "실제로 모델을 만들거나 저장하는 코드"가 있는지
# 보겠다는 의도입니다.
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
# .py, .ipynb만 보면 대부분의 ML 프로젝트 학습 코드를 포착할 수 있으므로
# 우선 이 두 형식만 대상으로 제한합니다.
CODE_SCAN_SUFFIXES = {".py", ".ipynb"}

# 코드 안의 import/키워드로 프레임워크 흔적을 찾을 때 사용합니다.
# requirements.txt가 없거나 부정확하더라도, 실제 코드에 남은 import/호출 흔적으로
# tensorflow / pytorch / sklearn / xgboost 후보를 보강하기 위한 규칙입니다.
FRAMEWORK_CODE_RULES = [
    ("tensorflow", ["tensorflow", "tf.keras", "keras", ".compile(", ".save(", "saved_model"]),
    ("pytorch", ["torch", "torch.save", "save_pretrained", ".pt", ".pth", ".ckpt"]),
    ("sklearn", ["sklearn", "scikit", "train_test_split", "model.fit("]),
    ("xgboost", ["xgboost", "xgb.", "xgbclassifier", "xgbregressor", "save_model"]),
]

# 모델 산출물로 자주 쓰이는 폴더/파일명 힌트입니다.
# 확장자만으로는 잡히지 않는 디렉터리형/특수형 산출물을 탐지할 때 보조 힌트로 씁니다.
# 예를 들어 TensorFlow SavedModel 폴더나 HuggingFace 계열 파일명을 포착할 수 있습니다.
ARTIFACT_DIR_HINTS = [
    "saved_model",
    "saved_model.pb",
    "variables",
    "tokenizer.json",
    "pytorch_model.bin",
    "model.safetensors",
]

# 분석에서 제외할 폴더 목록입니다.
# 사용자가 선택한 워크스페이스 안이라도, 아래 폴더들은
# - 번들 스킬 원본
# - 가상환경
# - 빌드 결과물
# - 의존성 캐시
# 성격이 강하므로 분석 대상에서 제외합니다.
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
    # .opencode 및 .opencode-* 단계 폴더는 사용자 모델 프로젝트가 아니라
    # 스킬 번들/실험용 단계 분리 폴더일 가능성이 높습니다.
    # 따라서 모델 탐지, 학습 코드 탐지, artifact 스캔에서 모두 제외합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `name`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 조건 만족 여부를 True/False로 반환해 단계 분기에 사용합니다.
    """
    return name in SCAN_SKIP_DIRS or name.startswith(".opencode")

# 프로젝트 필수 폴더 골격입니다.
# 이후 템플릿 복사/변환이 끝났을 때 기본적으로 있어야 하는 구조를 정의합니다.
REQUIRED_DIRS = [
    "aiu_custom",
    "local_serving",
    "saved_model",
]

# 샘플 규격상 기대하는 공통 파일입니다.
# 모델 종류와 무관하게 공통으로 기대하는 최소 파일만 넣어둡니다.
SAMPLE_SPEC_FILES = [
    "requirements.txt",
    "input_example.json",
]

# AI Studio 실행에 필요한 .env 키입니다.
# tracking URI / 인증 / 실험명 / 등록 모델명까지 총 5개를 필수 기준으로 봅니다.
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
    # name: 점검 항목 이름
    # status: pass / warn / block
    # message: 사람이 읽을 요약 메시지
    # evidence: 그렇게 판단한 근거 목록
    name: str
    status: str
    message: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    # 1단계 분석 결과 전체를 담는 리포트 구조입니다.
    # 이후 CLI 텍스트 출력, JSON 출력, 모델 목록 출력이 모두 이 구조를 공통으로 사용합니다.
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
    # 별도 렌더러 없이도 텍스트/터미널/챗 응답에서 비교적 읽기 쉽도록
    # ASCII 박스 표 대신 Markdown 표 형식으로 통일합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 사용자가 읽는 콘솔 출력을 Markdown Table 또는 짧은 요약 형태로 렌더링합니다.
    - 입력 기준: 입력값 `headers`, `rows`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환값보다 파일 생성, 콘솔 출력, 하위 명령 실행 같은 부수 효과가 핵심입니다.
    """
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        print("| " + " | ".join(str(value) for value in row) + " |")


def read_text(path: Path) -> str:
    # 파일 읽기 실패가 나더라도 분석이 중단되지 않도록 빈 문자열로 처리합니다.
    # 폐쇄망/권한 문제/깨진 인코딩 파일이 있어도 전체 분석이 멈추지 않게 하는 안전장치입니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 파일 내용을 안전하게 읽고 오류 상황에서는 단계 흐름이 끊기지 않도록 처리합니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def safe_exists(path: Path) -> bool:
    # 접근 오류가 나는 경로도 안전하게 검사합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 파일시스템 접근 중 권한/경로 오류가 나도 전체 분석이 중단되지 않도록 보호합니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 조건 만족 여부를 True/False로 반환해 단계 분기에 사용합니다.
    """
    try:
        return path.exists()
    except OSError:
        return False


def safe_is_file(path: Path) -> bool:
    # 경로가 실제 파일인지 확인합니다.
    # 권한/파일시스템 오류가 나면 예외 대신 False 를 반환합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 파일시스템 접근 중 권한/경로 오류가 나도 전체 분석이 중단되지 않도록 보호합니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 조건 만족 여부를 True/False로 반환해 단계 분기에 사용합니다.
    """
    try:
        return path.is_file()
    except OSError:
        return False


def safe_is_dir(path: Path) -> bool:
    # 경로가 실제 폴더(디렉터리)인지 확인합니다.
    # 접근 오류가 나더라도 분석이 중단되지 않게 False 로 처리합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 파일시스템 접근 중 권한/경로 오류가 나도 전체 분석이 중단되지 않도록 보호합니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 조건 만족 여부를 True/False로 반환해 단계 분기에 사용합니다.
    """
    try:
        return path.is_dir()
    except OSError:
        return False


def safe_iterdir(path: Path):
    # 권한/인코딩 문제로 디렉터리 순회가 실패해도 예외를 밖으로 던지지 않습니다.
    # 특정 폴더 하나가 깨져 있어도 나머지 워크스페이스 분석은 계속 진행할 수 있게 합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 파일시스템 접근 중 권한/경로 오류가 나도 전체 분석이 중단되지 않도록 보호합니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입은 코드 흐름에서 결정되며, 호출부가 기대하는 값/상태를 돌려줍니다.
    """
    try:
        yield from path.iterdir()
    except OSError:
        return


def safe_glob(path: Path, pattern: str):
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 파일시스템 접근 중 권한/경로 오류가 나도 전체 분석이 중단되지 않도록 보호합니다.
    - 입력 기준: 입력값 `path`, `pattern`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입은 코드 흐름에서 결정되며, 호출부가 기대하는 값/상태를 돌려줍니다.
    """
    try:
        yield from path.glob(pattern)
    except OSError:
        return


def safe_relative(path: Path, base: Path) -> str:
    # base 기준 상대경로를 우선 쓰고, 불가능하면 원본 경로를 그대로 반환합니다.
    # 사용자에게는 절대경로보다 워크스페이스 기준 상대경로가 훨씬 읽기 쉬우므로 우선 사용합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 파일시스템 접근 중 권한/경로 오류가 나도 전체 분석이 중단되지 않도록 보호합니다.
    - 입력 기준: 입력값 `path`, `base`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def normalize_path_text(value: str) -> str:
    # Windows/한글 키보드 백슬래시 변형 문자를 모두 '/' 기준으로 통일합니다.
    # 예:
    # - "\" 
    # - "＼"
    # - "￦"
    # - "₩"
    # 를 모두 "/" 로 바꾸어 비교/정렬 시 흔들리지 않게 합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: Windows/PowerShell/한글 키보드 입력처럼 흔들릴 수 있는 문자열을 내부 표준 형식으로 정규화합니다.
    - 입력 기준: 입력값 `value`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    return value.replace("\\", "/").replace("＼", "/").replace("￦", "/").replace("₩", "/")


def artifact_kind(path: Path) -> str | None:
    # 파일 확장자로 모델 형식을 추정합니다.
    # 이후 "어떤 샘플을 참조할지"와 "어떤 패키지를 권장할지"를 정할 때 활용됩니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    return ARTIFACT_KIND_BY_SUFFIX.get(path.suffix.lower())


def model_sort_key(path: Path, project: Path) -> str:
    # 모델 목록은 워크스페이스 기준 상대경로 알파벳 순서로 고정합니다.
    # 번호가 매번 바뀌면 사용자 입장에서 2번을 눌렀는데 다른 모델이 선택되는 문제가 생기므로,
    # 경로 기준 정렬을 고정해 선택 번호의 일관성을 높입니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `path`, `project`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    try:
        relative = path.resolve().relative_to(project.resolve())
    except ValueError:
        relative = path
    return normalize_path_text(str(relative)).lower()


def has_project_markers(path: Path) -> bool:
    # 현재 폴더가 실제 모델 프로젝트인지 빠르게 판별합니다.
    # 단순히 파이썬 파일이 있다고 프로젝트로 보는 것이 아니라,
    # requirements.txt, data/, saved_model/, entrypoint 같은 ML 프로젝트 흔적이
    # 있는지를 기준으로 봅니다.
    # 이렇게 해야 저장소 루트가 우연히 스킬 파일만 많이 가진 상태여도
    # 잘못된 프로젝트로 선택되는 일을 줄일 수 있습니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 특정 파일/폴더/마커가 존재하는지 확인해 다음 단계 분기 판단에 사용합니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 조건 만족 여부를 True/False로 반환해 단계 분기에 사용합니다.
    """
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
    # 여러 후보 폴더가 있을 때 우선순위를 정하기 위한 단순 점수입니다.
    # 점수가 높을수록 "모델 프로젝트일 가능성"이 큰 것으로 보고 우선 탐색합니다.
    # 품질 점수는 아니며, 후보 간 우선순위를 정하는 용도입니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입 `int` 기준으로 다음 처리 단계에 값을 전달합니다.
    """
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


def resolve_workspace_project(raw_project: str) -> Path:
    # 사용자가 넘긴 경로를 실제 워크스페이스 프로젝트 루트 기준으로 정규화합니다.
    # 예:
    # - "." -> 현재 작업 폴더
    # - <workspace-root> 같은 플레이스홀더 -> 실제 현재 프로젝트 루트
    # - .opencode 내부 경로 -> 상위 실제 프로젝트 루트로 보정
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 사용자 입력 경로/대상을 실제 워크스페이스 기준 Path 또는 내부 값으로 확정합니다.
    - 입력 기준: 입력값 `raw_project`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 정규화된 Path 또는 None을 반환해 이후 파일 접근 기준으로 사용합니다.
    """
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
    # 자동으로 다른 드라이브/루트까지 넓게 찾지 않고, 사용자가 선택한 워크스페이스를 존중합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `explicit`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 여러 값을 tuple로 묶어 반환해 호출부가 상태, 경로, 오류 사유를 함께 판단하게 합니다.
    """
    if explicit:
        project = resolve_workspace_project(explicit)
        return project, "explicit path"

    return resolve_workspace_project("."), "current directory only"


def is_filesystem_root(path: Path) -> bool:
    # 드라이브/파일시스템 루트 전체 검색을 막기 위한 판별입니다.
    # 전체 디스크 스캔은 느리고, 사용자 의도와도 다를 가능성이 커서 명시적으로 차단합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 조건 판단용 boolean helper입니다. 큰 흐름의 분기 조건을 명확하게 분리합니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 조건 만족 여부를 True/False로 반환해 단계 분기에 사용합니다.
    """
    return path.parent == path


def is_opencode_sample_source(path: Path) -> bool:
    # .opencode 번들/샘플 원본은 사용자 프로젝트가 아니므로 분석 대상에서 제외합니다.
    # 샘플 원본을 스캔해버리면 "사용자 모델"과 "참조용 템플릿"이 섞여 잘못 판정될 수 있습니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 조건 판단용 boolean helper입니다. 큰 흐름의 분기 조건을 명확하게 분리합니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 조건 만족 여부를 True/False로 반환해 단계 분기에 사용합니다.
    """
    parts = path.resolve().parts
    if ".opencode" in parts:
        return True
    for index, part in enumerate(parts[:-1]):
        if part == ".opencode" and parts[index + 1] in {"sample", "samples"}:
            return True
    return False


def iter_files(path: Path, max_depth: int = 4):
    # 파일 탐색 범위는 사용자가 선택한 워크스페이스 하위 전체입니다.
    # 단, .opencode/.venv/node_modules 같은 제외 폴더는 내려가지 않습니다.
    # max_depth는 무한 재귀 탐색으로 인한 속도 저하를 막기 위한 안전장치입니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 파일/폴더 후보를 하나씩 yield하여 큰 워크스페이스도 단계적으로 처리합니다.
    - 입력 기준: 입력값 `path`, `max_depth`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입은 코드 흐름에서 결정되며, 호출부가 기대하는 값/상태를 돌려줍니다.
    """
    if is_opencode_sample_source(path):
        return
    base_depth = len(path.parts)
    for root, dirs, files in os.walk(path, onerror=lambda _error: None):
        root_path = Path(root)
        # 현재 폴더가 워크스페이스 아래 몇 단계 깊이인지 계산합니다.
        # 예를 들어 project/data/a/b 라면 project 대비 depth=3 입니다.
        depth = len(root_path.parts) - base_depth
        # 최대 탐색 깊이에 도달하면 그 아래 하위 폴더는 더 이상 내려가지 않습니다.
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = [d for d in dirs if not should_skip_dir_name(d)]
        for file_name in files:
            candidate = root_path / file_name
            if safe_is_file(candidate):
                yield candidate


def is_saved_model_dir(path: Path) -> bool:
    # TensorFlow SavedModel 폴더인지 간단히 판별합니다.
    # saved_model.pb 파일이 있으면 디렉터리형 모델 artifact로 봅니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 조건 판단용 boolean helper입니다. 큰 흐름의 분기 조건을 명확하게 분리합니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 조건 만족 여부를 True/False로 반환해 단계 분기에 사용합니다.
    """
    return safe_is_dir(path) and safe_exists(path / "saved_model.pb")


def iter_artifact_dirs(path: Path, max_depth: int = 4):
    # 파일형 모델뿐 아니라 디렉터리형 모델도 artifact 후보로 찾습니다.
    # TensorFlow SavedModel처럼 "폴더 자체가 모델"인 경우를 놓치지 않기 위한 보완 탐색입니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 파일/폴더 후보를 하나씩 yield하여 큰 워크스페이스도 단계적으로 처리합니다.
    - 입력 기준: 입력값 `path`, `max_depth`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입은 코드 흐름에서 결정되며, 호출부가 기대하는 값/상태를 돌려줍니다.
    """
    if is_opencode_sample_source(path):
        return
    # 사용자가 선택한 워크스페이스 하위에서 max_depth 깊이까지만 디렉터리형 모델을 탐색합니다.
    base_depth = len(path.parts)
    for root, dirs, _files in os.walk(path, onerror=lambda _error: None):
        root_path = Path(root)
        # 현재 폴더가 워크스페이스 아래 몇 단계 깊이인지 계산합니다.
        depth = len(root_path.parts) - base_depth
        # 최대 탐색 깊이에 도달하면 그 아래 하위 폴더는 더 이상 내려가지 않습니다.
        if depth >= max_depth:
            dirs[:] = []
        # 분석 제외 폴더(.opencode, node_modules 등)는 순회 대상에서 제거합니다.
        dirs[:] = [d for d in dirs if not should_skip_dir_name(d)]
        # 현재 폴더가 TensorFlow SavedModel 구조이면 모델 artifact 디렉터리로 반환합니다.
        if is_saved_model_dir(root_path):
            yield root_path


def find_artifacts(path: Path, max_depth: int = 8) -> list[Path]:
    # 모델 파일/폴더 후보를 한 번에 모아 정렬된 목록으로 반환합니다.
    # 중복 제거 후 상대경로 기준 알파벳 순으로 정렬하여
    # 사용자 선택 번호가 최대한 안정적으로 유지되게 합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 워크스페이스 안에서 조건에 맞는 파일/폴더 후보를 탐색합니다.
    - 입력 기준: 입력값 `path`, `max_depth`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 후속 검사/출력에 사용할 목록을 반환합니다.
    """
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
    # .ipynb는 JSON 구조이므로, 코드/마크다운 셀 source를 합쳐 일반 텍스트처럼 검색합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
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
    # 상위 로직은 파일 형식 차이를 신경 쓰지 않고 "코드 텍스트"만 받게 됩니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 파일 내용을 안전하게 읽고 오류 상황에서는 단계 흐름이 끊기지 않도록 처리합니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    if path.suffix.lower() == ".ipynb":
        return notebook_text(path)
    return read_text(path)


def iter_code_files(project: Path, max_depth: int = 5):
    # 학습 코드 흔적을 찾을 코드 파일 목록을 안전하게 순회합니다.
    # 중복 resolve 경로는 제거해서 심볼릭 링크/중복 경로로 같은 파일을 두 번 읽지 않게 합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 파일/폴더 후보를 하나씩 yield하여 큰 워크스페이스도 단계적으로 처리합니다.
    - 입력 기준: 입력값 `project`, `max_depth`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입은 코드 흐름에서 결정되며, 호출부가 기대하는 값/상태를 돌려줍니다.
    """
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
    # 반환값:
    # - hits: 학습 코드로 판단된 파일 목록
    # - evidence: 어떤 패턴 때문에 잡혔는지
    # - frameworks: 코드 흔적으로 추정한 프레임워크 후보
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 파일 내용과 확장자 근거를 바탕으로 프레임워크/학습 코드/모델 종류를 판별합니다.
    - 입력 기준: 입력값 `project`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 여러 값을 tuple로 묶어 반환해 호출부가 상태, 경로, 오류 사유를 함께 판단하게 합니다.
    """
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
    # 우선순위는 대략 다음과 같습니다.
    # 1) 학습 코드에서 직접 드러난 프레임워크
    # 2) requirements.txt 의존성
    # 3) 모델 파일명/확장자
    # 확실한 근거가 없으면 unknown/custom 으로 두는 보수적 전략을 사용합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 파일 내용과 확장자 근거를 바탕으로 프레임워크/학습 코드/모델 종류를 판별합니다.
    - 입력 기준: 입력값 `project`, `requirements_text`, `artifacts`, `training_frameworks`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 여러 값을 tuple로 묶어 반환해 호출부가 상태, 경로, 오류 사유를 함께 판단하게 합니다.
    """
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
    # 반환값:
    # - Path | None: requirements.txt 실제 경로
    # - str: 파일 전체 원문
    # - list[str]: 주석/빈 줄을 제외한 실제 패키지 라인
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 파일 또는 문자열을 읽어 후속 판단에 필요한 구조화된 값으로 변환합니다.
    - 입력 기준: 입력값 `project`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 여러 값을 tuple로 묶어 반환해 호출부가 상태, 경로, 오류 사유를 함께 판단하게 합니다.
    """
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
    # JSON 파일이 실제로 존재하고 파싱 가능한지 확인합니다.
    # 단순 존재 여부만이 아니라 JSON 문법까지 확인해서,
    # 나중에 config/input_example 사용 시 깨진 파일로 인한 실패를 미리 잡습니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 필수 조건을 검사하고 pass/warn/block 같은 상태 판단에 필요한 근거를 만듭니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 여러 값을 tuple로 묶어 반환해 호출부가 상태, 경로, 오류 사유를 함께 판단하게 합니다.
    """
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
    # .env 파일을 단순 key=value 형태로 읽습니다.
    # 이 스크립트는 dotenv 라이브러리를 의존하지 않고,
    # 가장 흔한 "KEY=value" 형태만 가볍게 파싱합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 파일 또는 문자열을 읽어 후속 판단에 필요한 구조화된 값으로 변환합니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 설정/상태 값을 key-value 구조로 반환합니다.
    """
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
    # .env 안에 필수 MLflow 설정값이 모두 들어있는지 검사합니다.
    # 여기서는 "값의 진위/접속 성공"까지는 확인하지 않고,
    # 최소한 비어 있지 않게 채워졌는지만 확인합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 필수 조건을 검사하고 pass/warn/block 같은 상태 판단에 필요한 근거를 만듭니다.
    - 입력 기준: 입력값 `project`, `code_settings`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입 `Check` 기준으로 다음 처리 단계에 값을 전달합니다.
    """
    path = project / ".env"
    values = parse_env_file(path)
    evidence = []
    missing = []
    if safe_exists(path):
        evidence.append(".env")
    for key in AI_STUDIO_ENV_KEYS:
        found_in_env = key in values and values[key] != ""
        # experiment/register 모델명은 비어 있더라도 나중에 자동 기본값을 만들 수 있으므로
        # hard block 대신 auto_default 근거로 남깁니다.
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
    # 후보 이름 중 실제로 존재하는 첫 번째 파일을 찾습니다.
    # 고정 파일명이 아니라 여러 별칭을 허용할 때 쓰는 공통 헬퍼입니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 워크스페이스 안에서 조건에 맞는 파일/폴더 후보를 탐색합니다.
    - 입력 기준: 입력값 `project`, `names`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 정규화된 Path 또는 None을 반환해 이후 파일 접근 기준으로 사용합니다.
    """
    for name in names:
        candidate = project / name
        if safe_exists(candidate):
            return candidate
    return None


def unique_paths(paths: list[Path]) -> list[Path]:
    # resolve 기준으로 중복 경로를 제거합니다.
    # 상대경로/절대경로/심볼릭 링크 차이로 같은 파일이 중복 집계되는 것을 방지합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `paths`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 후속 검사/출력에 사용할 목록을 반환합니다.
    """
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
    # 실행 진입점 후보를 수집합니다.
    # 알려진 파일명 후보 + 루트의 *.py 파일을 함께 모아
    # "무엇이 실행 파일인지" 사용자 확인 전에 대략적인 후보군을 구성합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 워크스페이스 안에서 조건에 맞는 파일/폴더 후보를 탐색합니다.
    - 입력 기준: 입력값 `project`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 후속 검사/출력에 사용할 목록을 반환합니다.
    """
    found = [project / name for name in ENTRYPOINT_NAMES if safe_exists(project / name)]
    found.extend(path for path in safe_glob(project, "*.py") if safe_is_file(path))
    return unique_paths(found)


def find_training_entrypoints(project: Path) -> list[Path]:
    # 학습/등록 쪽 실행 파일 후보를 수집합니다.
    # 추론 전용 파일보다 학습/등록과 더 관련 있는 파일명을 우선 후보로 봅니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 워크스페이스 안에서 조건에 맞는 파일/폴더 후보를 탐색합니다.
    - 입력 기준: 입력값 `project`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 후속 검사/출력에 사용할 목록을 반환합니다.
    """
    found = [project / name for name in TRAINING_ENTRYPOINT_NAMES if safe_exists(project / name)]
    found.extend(path for path in safe_glob(project, "*.py") if safe_is_file(path))
    return unique_paths(found)


def check_aiu_custom(project: Path, entrypoints: list[Path]) -> Check:
    # aiu_custom 래퍼가 필요한 프로젝트인지, 필요하다면 골격이 맞는지 검사합니다.
    # AI Studio 스타일의 MLflow pyfunc 등록은 보통 ModelWrapper/PythonModel 래퍼를
    # 사용하므로, 엔트리포인트 코드에 그 흔적이 보이면 aiu_custom 구조를 필수로 봅니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 필수 조건을 검사하고 pass/warn/block 같은 상태 판단에 필요한 근거를 만듭니다.
    - 입력 기준: 입력값 `project`, `entrypoints`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입 `Check` 기준으로 다음 처리 단계에 값을 전달합니다.
    """
    entrypoint_text = "\n".join(read_text(path) for path in entrypoints)
    required = any(
        marker in entrypoint_text
        for marker in ["aiu_custom", "ModelWrapper", "PythonModel"]
    )
    aiu_dir = project / "aiu_custom"
    model_wrapper_file = aiu_dir / "model_wrapper.py"
    predict_file = model_wrapper_file if safe_exists(model_wrapper_file) else aiu_dir / "predict.py"

    # 엔트리포인트에서 aiu_custom을 전혀 참조하지 않고, 폴더도 없으면
    # 현재 프로젝트는 이 래퍼가 필요 없는 형태로 판단합니다.
    if not required and not safe_exists(aiu_dir):
        return Check(
            "AI Studio custom wrapper",
            "pass",
            "aiu_custom is not required by detected entrypoints",
            [],
        )
    # aiu_custom 폴더는 있지만 현재 엔트리포인트에서 직접 요구하지 않는 경우입니다.
    # 즉, 골격은 있어도 "필수"는 아닌 상태로 pass 처리합니다.
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

    # 여기부터는 aiu_custom이 실제로 필요한 경우에만 세부 누락을 점검합니다.
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
    # 필수 폴더 골격이 존재하는지 확인합니다.
    # 이후 템플릿 복사/변환 대상이 되는 핵심 폴더가 빠져 있으면 block 처리합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 필수 조건을 검사하고 pass/warn/block 같은 상태 판단에 필요한 근거를 만듭니다.
    - 입력 기준: 입력값 `project`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입 `Check` 기준으로 다음 처리 단계에 값을 전달합니다.
    """
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
    # 프레임워크 이름을 샘플 키로 단순 매핑합니다.
    # 아직 정확한 전용 샘플이 없는 경우에는 기본값으로 pytorch를 사용합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `framework`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    if framework in {"sklearn", "pytorch", "tensorflow"}:
        return framework
    return "pytorch"


def sample_spec_missing(project: Path) -> list[str]:
    # 샘플 규격 대비 누락된 폴더/파일을 목록으로 반환합니다.
    # 여기서 반환한 값은 "무엇을 복사/보강해야 하는지"를 안내하는 근거가 됩니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `project`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 후속 검사/출력에 사용할 목록을 반환합니다.
    """
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
    # 실행 파일 후보가 하나인지, 여러 개인지, 없는지 확인합니다.
    # 후보가 여러 개면 자동 확정하지 않고, 사용자 확인이 필요하다는 warn을 남깁니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 필수 조건을 검사하고 pass/warn/block 같은 상태 판단에 필요한 근거를 만듭니다.
    - 입력 기준: 입력값 `project`, `entrypoints`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입 `Check` 기준으로 다음 처리 단계에 값을 전달합니다.
    """
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
    # 모델은 있어도 실행 템플릿 골격이 덜 갖춰진 경우가 많아서 별도 warn으로 분리합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 필수 조건을 검사하고 pass/warn/block 같은 상태 판단에 필요한 근거를 만듭니다.
    - 입력 기준: 입력값 `project`, `framework`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입 `Check` 기준으로 다음 처리 단계에 값을 전달합니다.
    """
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
    # 4번 템플릿 변환 단계에서 파일 복사/생성이 필요하므로, 쓰기 가능 여부를 사전 확인합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 생성/변환 결과를 파일로 기록합니다. 기존 파일 보호 여부를 함께 고려합니다.
    - 입력 기준: 입력값 `project`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입 `Check` 기준으로 다음 처리 단계에 값을 전달합니다.
    """
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
    # 특히 PowerShell/배치 환경에서 경로 공백, 긴 경로는 오류 원인이 되기 쉬워 미리 경고합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `project`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입 `Check` 기준으로 다음 처리 단계에 값을 전달합니다.
    """
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
    # 예: --prepare-only, preflight, prepare() 같은 키워드가 있으면
    # "실행 전 준비 단계"가 구현된 것으로 간주합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 특정 파일/폴더/마커가 존재하는지 확인해 다음 단계 분기 판단에 사용합니다.
    - 입력 기준: 입력값 `entrypoints`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 여러 값을 tuple로 묶어 반환해 호출부가 상태, 경로, 오류 사유를 함께 판단하게 합니다.
    """
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
    # MLflow 등록 흐름(start_run, log_model 등)이 코드에 보이는지 확인합니다.
    # 실제 등록 실행 파일이 맞는지 추정할 때 사용하는 근거입니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 특정 파일/폴더/마커가 존재하는지 확인해 다음 단계 분기 판단에 사용합니다.
    - 입력 기준: 입력값 `entrypoints`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 여러 값을 tuple로 묶어 반환해 호출부가 상태, 경로, 오류 사유를 함께 판단하게 합니다.
    """
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
    # .env 외에도 코드 상수/변수명에 설정 흔적이 남아 있으면 준비도 판단에 활용합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 워크스페이스 안에서 조건에 맞는 파일/폴더 후보를 탐색합니다.
    - 입력 기준: 입력값 `entrypoints`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 후속 검사/출력에 사용할 목록을 반환합니다.
    """
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
    #
    # 전체 흐름은 다음과 같이 이어집니다.
    # 1) 프로젝트 경로 자체가 정상인지 확인
    # 2) 모델/학습코드/requirements/entrypoint 흔적 수집
    # 3) case 1 / case 2 / case 3 판정
    # 4) 샘플 규격, .env, MLflow readiness, 등록 가능성 점검
    # 5) 다음 단계 안내(next_steps) 구성
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 여러 검사 결과를 묶어 report, command, TODO guide 같은 최종 출력 구조를 생성합니다.
    - 입력 기준: 입력값 `project`, `reason`, `write_check`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입 `ValidationReport` 기준으로 다음 처리 단계에 값을 전달합니다.
    """
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
    # 둘 다 없으면 아직 모델 프로젝트로 보기 어렵기 때문에 case 3로 내려갑니다.
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
    # 8-1) 이후 단계에서 막히기 쉬운 구조적 체크들을 순서대로 추가합니다.
    checks.append(check_entrypoint_confirmation(project, training_entrypoints))
    checks.append(check_required_dirs(project))
    checks.append(check_sample_spec(project, framework))
    checks.append(check_aiu_custom(project, entrypoints))

    # 9) MLflow 관련 의존성과 설정 흔적을 점검합니다.
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

    # 10) config/input_example/.env 와 같은 실행 보조 파일의 준비 상태를 확인합니다.
    # 실제 모델 파일만 있어도 실행/등록은 못 할 수 있으므로,
    # 부가 설정 파일의 존재와 형식도 함께 점검합니다.
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

    # config, input_example, artifact가 모두 있어야 "실행에 필요한 기본 재료"가
    # 어느 정도 갖춰졌다고 보고 pass 처리합니다.
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

    # 11) 등록 실행 흐름과 prepare/preflight 흐름이 코드상 보이는지 확인합니다.
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
    # 고정 로컬 tracking URI를 가정하지 않습니다.
    # 사용자 환경마다 remote/local MLflow 대상이 다르므로,
    # config/.env/코드 상수에 관련 흔적이 있는지만 확인합니다.
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

    # 12) 마지막으로 Windows 경로 호환성과 쓰기 가능 여부를 확인합니다.
    # 앞의 논리 체크가 통과해도 실제 경로/쓰기 문제로 실패할 수 있어 마지막에 별도 점검합니다.
    checks.append(windows_path_check(project))
    if write_check:
        checks.append(write_permission_check(project))

    # 13) 사용자에게 보여줄 다음 단계 안내를 현재 상태에 맞게 만듭니다.
    # block/warn 여부, case 종류, 누락 항목에 따라 문구가 달라집니다.
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
    # 사용자가 번호로 선택할 때 보기 쉽도록 "No / Path / MODEL_KIND / Location / Status"
    # 형식을 통일합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 사용자가 읽는 콘솔 출력을 Markdown Table 또는 짧은 요약 형태로 렌더링합니다.
    - 입력 기준: 입력값 `report`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입은 코드 흐름에서 결정되며, 호출부가 기대하는 값/상태를 돌려줍니다.
    """
    rows: list[tuple[str, str, str, str]] = []
    for path in report.training_code_paths:
        # 학습 코드 기반 case 1 후보는 실제 "파일"을 선택하는 개념입니다.
        location = "file"
        rows.append((path, "training_code", location, "선택 가능"))
    for path in report.model_artifact_paths:
        suffix = Path(path).suffix.lower()
        kind = ARTIFACT_KIND_BY_SUFFIX.get(suffix, "unknown")
        # artifact 기반 case 2 후보는 모델 파일/폴더이므로 data로 표기합니다.
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
    # 사용자에게 필요한 핵심만 보여주고, 상세한 진단표는 verbose 모드에 맡깁니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 사용자가 읽는 콘솔 출력을 Markdown Table 또는 짧은 요약 형태로 렌더링합니다.
    - 입력 기준: 입력값 `report`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입은 코드 흐름에서 결정되며, 호출부가 기대하는 값/상태를 돌려줍니다.
    """
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
    # 스크립트 개발/디버깅, 유지보수 시 어떤 체크가 왜 warn/block인지 확인할 때 사용합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: 사용자가 읽는 콘솔 출력을 Markdown Table 또는 짧은 요약 형태로 렌더링합니다.
    - 입력 기준: 입력값 `report`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입은 코드 흐름에서 결정되며, 호출부가 기대하는 값/상태를 돌려줍니다.
    """
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
    # --json / --list / --verbose / 기본 출력이 모두 같은 report 객체를 공유합니다.
    """
    분석 주석:
    - 단계 맥락: 1단계 프로젝트 분석: 워크스페이스를 읽기 전용으로 스캔하고 model_found, 모델 목록, case 1/2/3을 판단합니다.
    - 함수 역할: CLI 진입점입니다. 인자를 파싱하고 현재 단계의 전체 실행 순서를 조립합니다.
    - 입력 기준: 별도 입력 없이 현재 파일의 상수, CLI 인자, 또는 워크스페이스 상태를 기준으로 동작합니다.
    - 반환/효과: 반환 타입은 코드 흐름에서 결정되며, 호출부가 기대하는 값/상태를 돌려줍니다.
    """
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
