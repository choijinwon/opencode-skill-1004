#!/usr/bin/env python3
from __future__ import annotations

# ---------------------------------------------------------------------------
# 분석용 주석
# ---------------------------------------------------------------------------
# 이 파일은 기존 워크스페이스를 AI Studio 등록 구조에 맞게 보정하는
# 보조 변환 스크립트입니다.
#
# `prepare_selected_model.py`가 모델 선택과 템플릿 복사를 담당한다면,
# 이 파일은 이미 존재하는 entrypoint, requirements, input_example,
# aiu_custom, local_serving 구조를 읽어서 부족한 연결부를 채우는 역할입니다.
# 즉 새 코드를 크게 다시 쓰는 목적이 아니라, 실행/등록에 필요한 부분만
# 최소한으로 맞추는 보정용 스크립트입니다.

import argparse
import ast
import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path


START = "# >>> AI Studio MLflow adapter >>>"
END = "# <<< AI Studio MLflow adapter <<<"

REQUIRED_DIRS = ["aiu_custom", "local_serving", "saved_model"]
REQUIRED_FILES = ["input_example.json", "requirements.txt"]
ENTRYPOINT_HINTS = [
                        "runtest.py",
    "run_test.py",
    "run_model.py",
    "run.py",
    "train.py",
    "main.py",
    "app.py",
    "scripts/train.py",
]

FRAMEWORK_RULES = [
    ("qwen", ["qwen", "AutoModelForCausalLM", "AutoTokenizer"]),
    ("huggingface", ["transformers", "AutoModel", "AutoTokenizer", "pipeline("]),
    ("pytorch", ["import torch", "from torch", "torch.", ".pt", ".pth"]),
    ("tensorflow", ["tensorflow", "keras", ".keras", ".h5", "SavedModel"]),
    ("sklearn", ["sklearn", "scikit-learn", "joblib", ".pkl"]),
    ("xgboost", ["xgboost", ".bst", ".ubj"]),
    ("lightgbm", ["lightgbm"]),
]

REQUIREMENT_BY_FRAMEWORK = {
    "qwen": ["mlflow", "transformers", "torch", "accelerate", "safetensors"],
    "huggingface": ["mlflow", "transformers", "torch", "safetensors"],
    "pytorch": ["mlflow", "torch"],
    "tensorflow": ["mlflow", "tensorflow"],
    "sklearn": ["mlflow", "scikit-learn", "joblib"],
    "xgboost": ["mlflow", "xgboost"],
    "lightgbm": ["mlflow", "lightgbm"],
    "unknown": ["mlflow"],
}


def resolve_workspace_project(raw_project: str) -> Path:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
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


@dataclass
class AdaptReport:
    project_path: str
    entrypoint: str | None
    framework: str
    execute: bool
    planned_changes: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


def read_text(path: Path) -> str:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: 파일 내용을 안전하게 읽고 오류 상황에서는 단계 흐름이 끊기지 않도록 처리합니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def rel(path: Path, base: Path) -> str:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `path`, `base`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def unique_paths(paths: list[Path]) -> list[Path]:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `paths`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 후속 검사/출력에 사용할 목록을 반환합니다.
    """
    unique = []
    seen = set()
    for path in paths:
        key = path.resolve()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def find_entrypoints(project: Path) -> list[Path]:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: 워크스페이스 안에서 조건에 맞는 파일/폴더 후보를 탐색합니다.
    - 입력 기준: 입력값 `project`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 후속 검사/출력에 사용할 목록을 반환합니다.
    """
    found = []
    for name in ENTRYPOINT_HINTS:
        candidate = project / name
        if candidate.is_file():
            found.append(candidate)
    found.extend(path for path in project.glob("*.py") if path.is_file())
    return unique_paths(found)


def resolve_entrypoint(project: Path, entrypoint_name: str | None) -> tuple[Path | None, list[Path], str | None]:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: 사용자 입력 경로/대상을 실제 워크스페이스 기준 Path 또는 내부 값으로 확정합니다.
    - 입력 기준: 입력값 `project`, `entrypoint_name`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 여러 값을 tuple로 묶어 반환해 호출부가 상태, 경로, 오류 사유를 함께 판단하게 합니다.
    """
    candidates = find_entrypoints(project)
    if entrypoint_name:
        candidate = Path(entrypoint_name)
        path = candidate if candidate.is_absolute() else project / candidate
        path = path.resolve()
        try:
            path.relative_to(project)
        except ValueError:
            return None, candidates, "entrypoint_outside_project"
        if not path.exists():
            return None, candidates, f"entrypoint_not_found:{entrypoint_name}"
        return path, candidates, None
    if len(candidates) == 1:
        return candidates[0], candidates, None
    if not candidates:
        return None, candidates, "entrypoint_not_found"
    return None, candidates, "entrypoint_ambiguous"


def detect_framework(project: Path, entrypoint: Path | None) -> str:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: 파일 내용과 확장자 근거를 바탕으로 프레임워크/학습 코드/모델 종류를 판별합니다.
    - 입력 기준: 입력값 `project`, `entrypoint`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    texts = []
    if entrypoint is not None:
        texts.append(read_text(entrypoint))
    requirements = project / "requirements.txt"
    if requirements.exists():
        texts.append(read_text(requirements))
    joined = "\n".join(texts)
    lowered = joined.lower()
    for framework, hints in FRAMEWORK_RULES:
        for hint in hints:
            if hint.lower() in lowered:
                return framework
    return "unknown"


def infer_import_packages(entrypoint: Path | None) -> list[str]:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `entrypoint`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 후속 검사/출력에 사용할 목록을 반환합니다.
    """
    if entrypoint is None or not entrypoint.exists():
        return []
    try:
        tree = ast.parse(read_text(entrypoint))
    except SyntaxError:
        return []
    packages = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            packages.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            packages.append(node.module.split(".")[0])
    ignored = {"os", "sys", "json", "pathlib", "typing", "logging", "io", "time", "math", "random", "tempfile"}
    return sorted({name for name in packages if name not in ignored and not name.startswith("_")})


def insertion_index(lines: list[str]) -> int:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `lines`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입 `int` 기준으로 다음 처리 단계에 값을 전달합니다.
    """
    index = 0
    if lines and lines[0].startswith("#!"):
        index = 1
    while index < len(lines) and (not lines[index].strip() or lines[index].startswith("#")):
        index += 1
    if index < len(lines) and lines[index].lstrip().startswith(('"""', "'''")):
        quote = lines[index].lstrip()[:3]
        index += 1
        while index < len(lines):
            if quote in lines[index]:
                index += 1
                break
            index += 1
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("from __future__ import"):
            index += 1
            continue
        if stripped.startswith("import ") or stripped.startswith("from "):
            index += 1
            continue
        if not stripped:
            index += 1
            continue
        break
    return index


def adapter_block(framework: str) -> str:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: 기존 entrypoint나 템플릿 파일을 AI Studio/MLflow 등록 구조에 맞게 최소 보정합니다.
    - 입력 기준: 입력값 `framework`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    return f'''
{START}
# This block is intentionally generic. Keep model-specific training code below
# unchanged, then call/use these helpers where the model is saved or logged.
import json as _ai_studio_json
import os as _ai_studio_os
from pathlib import Path as _AIStudioPath

AI_STUDIO_PROJECT_DIR = _AIStudioPath(__file__).resolve().parent
AI_STUDIO_DIR = AI_STUDIO_PROJECT_DIR / "ai_studio"
AI_STUDIO_CODE_DIR = AI_STUDIO_DIR / "code"
AI_STUDIO_METRICS_DIR = AI_STUDIO_DIR / "metrics"
AI_STUDIO_TRACKING_DIR = AI_STUDIO_DIR / "tracking"

# 사용자가 직접 입력합니다. password 값은 출력하지 않습니다.
mlflow_tracking_uri = globals().get("mlflow_tracking_uri", "")
mlflow_tracking_username = globals().get("mlflow_tracking_username", "")
mlflow_tracking_password = globals().get("mlflow_tracking_password", "")
mlflow_experiment_name = globals().get("mlflow_experiment_name", "{framework}")
mlflow_register_model_name = globals().get("mlflow_register_model_name", "{framework}_model")


def export_ai_studio_mlflow_env() -> None:
    if not mlflow_tracking_uri:
        raise ValueError("mlflow_tracking_uri_required: set remote MLflow tracking URL before deployment")
    exports = {{
        "MLFLOW_TRACKING_URI": mlflow_tracking_uri,
        "MLFLOW_TRACKING_USERNAME": mlflow_tracking_username,
        "MLFLOW_TRACKING_PASSWORD": mlflow_tracking_password,
        "MLFLOW_EXPERIMENT_NAME": mlflow_experiment_name,
        "MLFLOW_REGISTER_MODEL_NAME": mlflow_register_model_name,
    }}
    for name, value in exports.items():
        if value:
            _ai_studio_os.environ[name] = value


def ensure_ai_studio_dirs() -> None:
    AI_STUDIO_CODE_DIR.mkdir(parents=True, exist_ok=True)
    AI_STUDIO_METRICS_DIR.mkdir(parents=True, exist_ok=True)


def write_ai_studio_summary(payload: dict | None = None) -> _AIStudioPath:
    ensure_ai_studio_dirs()
    summary_path = AI_STUDIO_CODE_DIR / "training_summary.json"
    summary_path.write_text(
        _ai_studio_json.dumps(payload or {{"framework": "{framework}", "status": "completed"}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary_path


def log_ai_studio_tree_to_mlflow(root: _AIStudioPath, artifact_path: str) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if path.is_file():
            relative_parent = path.parent.relative_to(root).as_posix()
            target_path = artifact_path if relative_parent == "." else f"{{artifact_path}}/{{relative_parent}}"
            mlflow.log_artifact(str(path), artifact_path=target_path)


def log_ai_studio_artifacts_to_mlflow() -> None:
    try:
        import mlflow
    except Exception as exc:
        print(f"MLflow import failed; local ai_studio outputs are available. reason={{exc}}")
        return
    export_ai_studio_mlflow_env()
    try:
        mlflow.set_tracking_uri(_ai_studio_os.environ["MLFLOW_TRACKING_URI"])
        mlflow.set_experiment(mlflow_experiment_name)
        with mlflow.start_run(run_name=mlflow_register_model_name):
            log_ai_studio_tree_to_mlflow(AI_STUDIO_CODE_DIR, "ai_studio/code")
            log_ai_studio_tree_to_mlflow(AI_STUDIO_METRICS_DIR, "ai_studio/metrics")
    except Exception as exc:
        print(f"MLflow logging failed; local ai_studio outputs are available. reason={{exc}}")


export_ai_studio_mlflow_env()
ensure_ai_studio_dirs()
{END}
'''.strip()


def model_wrapper_template(framework: str) -> str:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `framework`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    return f'''"""AI Studio pyfunc wrapper template.

Keep the model-specific loading and predict logic here. This file is created
only when missing; it is not meant to overwrite a user's existing wrapper.
"""


class ModelWrapper:
    framework = "{framework}"

    def __init__(self):
        self.model = None

    def load_context(self, context):
        # TODO: load model artifacts from context.artifacts or saved_model/.
        return None

    def predict(self, context, model_input):
        # TODO: replace with model-specific inference logic.
        return model_input
'''


def local_serving_template() -> str:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 별도 입력 없이 현재 파일의 상수, CLI 인자, 또는 워크스페이스 상태를 기준으로 동작합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    return '''import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        payload = self.rfile.read(length).decode("utf-8")
        body = json.dumps({"received": json.loads(payload) if payload else {}}).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8080), Handler).serve_forever()
'''


def write_if_missing(path: Path, text: str, execute: bool, changed: list[str], skipped: list[str]) -> None:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: 생성/변환 결과를 파일로 기록합니다. 기존 파일 보호 여부를 함께 고려합니다.
    - 입력 기준: 입력값 `path`, `text`, `execute`, `changed`, `skipped`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환값보다 파일 생성, 콘솔 출력, 하위 명령 실행 같은 부수 효과가 핵심입니다.
    """
    if path.exists():
        skipped.append(f"exists: {path.name if path.parent == path.parent.parent else path.as_posix()}")
        return
    if execute:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    changed.append(path.as_posix())


def adapt_entrypoint(entrypoint: Path, framework: str, execute: bool, force: bool, changed: list[str], skipped: list[str]) -> None:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: 기존 entrypoint나 템플릿 파일을 AI Studio/MLflow 등록 구조에 맞게 최소 보정합니다.
    - 입력 기준: 입력값 `entrypoint`, `framework`, `execute`, `force`, `changed`, `skipped`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환값보다 파일 생성, 콘솔 출력, 하위 명령 실행 같은 부수 효과가 핵심입니다.
    """
    text = read_text(entrypoint)
    if START in text and END in text and not force:
        skipped.append(f"adapter_exists: {entrypoint}")
        return
    block = adapter_block(framework)
    if START in text and END in text and force:
        next_text = re.sub(re.escape(START) + r".*?" + re.escape(END), block, text, flags=re.DOTALL)
    else:
        lines = text.splitlines()
        index = insertion_index(lines)
        lines[index:index] = ["", block, ""]
        next_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    if execute:
        backup = entrypoint.with_suffix(entrypoint.suffix + ".ai_studio.bak")
        if not backup.exists():
            shutil.copyfile(entrypoint, backup)
            changed.append(backup.as_posix())
        entrypoint.write_text(next_text, encoding="utf-8")
    changed.append(entrypoint.as_posix())


def build_report(project: Path, entrypoint_arg: str | None, sample: str, execute: bool, force: bool) -> AdaptReport:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: 여러 검사 결과를 묶어 report, command, TODO guide 같은 최종 출력 구조를 생성합니다.
    - 입력 기준: 입력값 `project`, `entrypoint_arg`, `sample`, `execute`, `force`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입 `AdaptReport` 기준으로 다음 처리 단계에 값을 전달합니다.
    """
    entrypoint, candidates, error = resolve_entrypoint(project, entrypoint_arg)
    framework = detect_framework(project, entrypoint)
    report = AdaptReport(
        project_path=str(project),
        entrypoint=str(entrypoint) if entrypoint else None,
        framework=framework,
        execute=execute,
    )

    if error:
        report.failures.append(error)
        if candidates:
            report.warnings.append("entrypoint candidates: " + ", ".join(rel(path, project) for path in candidates))
        if error == "entrypoint_not_found":
            report.next_steps.append("실행 파일을 찾지 못했습니다. 사용자가 실제 학습/모델 생성 Python 파일을 프로젝트에 직접 넣어주세요.")
            report.next_steps.append("파일을 넣은 뒤 --entrypoint <file>로 다시 실행하세요.")
        elif error == "entrypoint_ambiguous":
            report.next_steps.append("실행 파일 후보가 여러 개입니다. 사용자가 실제 사용하는 파일명을 직접 지정해야 합니다.")
            report.next_steps.append("예: python .opencode/scripts/05-train-model/adapt_ai_studio.py --project . --entrypoint run.py")
        elif error.startswith("entrypoint_not_found:"):
            report.next_steps.append("지정한 실행 파일이 없습니다. 파일명을 확인하거나 해당 Python 파일을 프로젝트에 직접 넣어주세요.")
        else:
            report.next_steps.append("실제 학습/모델 생성 파일을 --entrypoint <file>로 지정하세요.")
        return report

    assert entrypoint is not None
    imports = infer_import_packages(entrypoint)
    required_packages = sorted(set(REQUIREMENT_BY_FRAMEWORK.get(framework, ["mlflow"]) + imports))
    report.planned_changes.extend(
        [
            f"adapt_entrypoint: {rel(entrypoint, project)}",
            "create_if_missing: aiu_custom/predict.py",
            "create_if_missing: local_serving/serve.py",
            "create_if_missing: saved_model/",
            "create_if_missing: input_example.json",
            "create_or_extend_if_missing: requirements.txt",
        ]
    )

    if not execute:
        report.next_steps.append("검토 후 실제 수정하려면 같은 명령에 --execute를 추가하세요.")
        return report

    changed = report.changed_files
    skipped = report.skipped
    for dirname in REQUIRED_DIRS:
        path = project / dirname
        if path.exists():
            skipped.append(f"exists: {dirname}/")
        else:
            path.mkdir(parents=True, exist_ok=True)
            changed.append(path.as_posix())

    write_if_missing(project / "aiu_custom" / "predict.py", model_wrapper_template(framework), execute, changed, skipped)
    write_if_missing(project / "local_serving" / "serve.py", local_serving_template(), execute, changed, skipped)
    write_if_missing(project / "input_example.json", '{\n  "inputs": []\n}\n', execute, changed, skipped)

    requirements = project / "requirements.txt"
    if requirements.exists():
        existing = read_text(requirements)
        additions = [pkg for pkg in required_packages if pkg.lower() not in existing.lower()]
        if additions:
            requirements.write_text(existing.rstrip() + "\n" + "\n".join(additions) + "\n", encoding="utf-8")
            changed.append(requirements.as_posix())
        else:
            skipped.append("requirements already covers inferred packages")
    else:
        requirements.write_text("\n".join(required_packages) + "\n", encoding="utf-8")
        changed.append(requirements.as_posix())

    adapt_entrypoint(entrypoint, framework, execute, force, changed, skipped)
    report.next_steps.extend(
        [
            "수정된 entrypoint의 TODO와 MLflow 설정값 5개를 확인하세요.",
            f"python .opencode/scripts/qa-maintenance/doctor.py --workspace . --project . --entrypoint {rel(entrypoint, project)}",
            f"python .opencode/scripts/03-environment-check/check_environment.py --project . --entrypoint {rel(entrypoint, project)}",
        ]
    )
    return report


def print_markdown_table(headers: list[str], rows: list[list[str]]) -> None:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: 사용자가 읽는 콘솔 출력을 Markdown Table 또는 짧은 요약 형태로 렌더링합니다.
    - 입력 기준: 입력값 `headers`, `rows`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환값보다 파일 생성, 콘솔 출력, 하위 명령 실행 같은 부수 효과가 핵심입니다.
    """
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        print("| " + " | ".join(str(value) for value in row) + " |")


def print_text(report: AdaptReport) -> None:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: 사용자가 읽는 콘솔 출력을 Markdown Table 또는 짧은 요약 형태로 렌더링합니다.
    - 입력 기준: 입력값 `report`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환값보다 파일 생성, 콘솔 출력, 하위 명령 실행 같은 부수 효과가 핵심입니다.
    """
    print("AI Studio Adapter")
    print_markdown_table(
        ["항목", "값"],
        [
            ["Project", "."],
            ["Entrypoint", report.entrypoint or "missing"],
            ["Framework", report.framework],
            ["Execute", str(report.execute).lower()],
        ],
    )
    if report.planned_changes:
        print("\nPlanned changes:")
        print_markdown_table(["No", "Planned Change"], [[str(index), item] for index, item in enumerate(report.planned_changes, start=1)])
    if report.changed_files:
        print("\nChanged files:")
        print_markdown_table(["No", "Changed File"], [[str(index), item] for index, item in enumerate(report.changed_files, start=1)])
    if report.skipped:
        print("\nSkipped:")
        print_markdown_table(["No", "Skipped"], [[str(index), item] for index, item in enumerate(report.skipped, start=1)])
    if report.warnings:
        print("\nWarnings:")
        print_markdown_table(["No", "Warning"], [[str(index), item] for index, item in enumerate(report.warnings, start=1)])
    if report.failures:
        print("\nFailures:")
        print_markdown_table(["No", "Failure"], [[str(index), item] for index, item in enumerate(report.failures, start=1)])
    if report.next_steps:
        print("\nNext steps:")
        print_markdown_table(["No", "Next Step"], [[str(index), item] for index, item in enumerate(report.next_steps, start=1)])


def main() -> int:
    """
    분석 주석:
    - 단계 맥락: 5단계 train-model: 선택 모델 기준 템플릿 변환, 런타임 파일 정합성 확인, 원격 MLflow 등록 실행을 담당합니다.
    - 함수 역할: CLI 진입점입니다. 인자를 파싱하고 현재 단계의 전체 실행 순서를 조립합니다.
    - 입력 기준: 별도 입력 없이 현재 파일의 상수, CLI 인자, 또는 워크스페이스 상태를 기준으로 동작합니다.
    - 반환/효과: 반환 타입 `int` 기준으로 다음 처리 단계에 값을 전달합니다.
    """
    parser = argparse.ArgumentParser(description="Adapt an arbitrary Python model entrypoint for AI Studio/MLflow workflow.")
    parser.add_argument("--project", default=".", help="model project folder")
    parser.add_argument("--entrypoint", help="actual local training/model creation file, such as run.py")
    parser.add_argument("--sample", choices=["sklearn", "pytorch", "tensorflow"], default="pytorch", help="scaffold hint")
    parser.add_argument("--execute", action="store_true", help="apply changes; default is dry-run")
    parser.add_argument("--force", action="store_true", help="replace existing adapter block")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    project = resolve_workspace_project(args.project)
    if not project.exists():
        raise SystemExit(f"project not found: {project}")
    report = build_report(project, args.entrypoint, args.sample, args.execute, args.force)
    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print_text(report)
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
