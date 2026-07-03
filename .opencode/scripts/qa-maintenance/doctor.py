#!/usr/bin/env python3
"""One-page maintenance and QA diagnostic for the OpenCode MLflow workflow.

This script intentionally stays stdlib-only so it can run on closed-network
Windows machines before dependencies are installed. It summarizes package
health, sample scaffold status, MLflow setting status, and output artifacts.
"""
from __future__ import annotations

import argparse
import ast
import importlib.metadata
import json
import os
import platform
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


EXPECTED_PYTHON_VERSION = "3.11.9"
EXPECTED_PACKAGE_VERSIONS = {
    "mlflow": "==3.10.0",
    "torch": "==2.12.1",
    "numpy": "==1.26.4",
    "kserve": "==0.15.0",
    "pandas": "==2.2.3",
}

SKILL_FOLDERS = [
    "01-agent-mlflow-skill-project-analyze",
    "02-agent-mlflow-skill-sample-bootstrap",
    "03-agent-mlflow-skill-environment-check",
    "04-agent-mlflow-skill-train-model",
    "06-agent-mlflow-skill-inference-test",
]

SAMPLE_SPEC_DIRS = [
    "aiu_custom",
    "local_serving",
    "saved_model",
]

SAMPLE_SPEC_FILES = [
    "requirements.txt",
    "input_example.json",
]


def resolve_workspace_project(raw_project: str) -> Path:
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


ENTRYPOINT_CANDIDATES = [
        "runtest_2.py",
                    "runtest.py",
    "run_test.py",
    "run_model.py",
    "run.py",
    "train.py",
    "main.py",
    "app.py",
    "scripts/train.py",
]

SETTING_FILES = [
        "runtest_2.py",
                    "runtest.py",
    "run_test.py",
    "run_model.py",
    "run.py",
    "train.py",
    "main.py",
    "app.py",
]

MLFLOW_SOURCE_KEYS = [
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
ENV_EXPORT_MAP = {
    "mlflow_tracking_uri": "MLFLOW_TRACKING_URI",
    "mlflow_tracking_username": "MLFLOW_TRACKING_USERNAME",
    "mlflow_tracking_password": "MLFLOW_TRACKING_PASSWORD",
    "mlflow_experiment_name": "MLFLOW_EXPERIMENT_NAME",
    "mlflow_register_model_name": "MLFLOW_REGISTER_MODEL_NAME",
}

SETTING_ALIASES = {
    "mlflow_tracking_uri": {
        "mlflow_tracking_uri",
        "tracking_uri",
        "MLFLOW_TRACKING_URI",
    },
    "mlflow_tracking_username": {
        "mlflow_tracking_username",
        "tracking_username",
        "mlflow_username",
        "username",
        "MLFLOW_TRACKING_USERNAME",
    },
    "mlflow_tracking_password": {
        "mlflow_tracking_password",
        "tracking_password",
        "mlflow_password",
        "password",
        "MLFLOW_TRACKING_PASSWORD",
    },
    "mlflow_experiment_name": {
        "mlflow_experiment_name",
        "experiment_name",
        "MLFLOW_EXPERIMENT_NAME",
    },
    "mlflow_register_model_name": {
        "mlflow_register_model_name",
        "register_model_name",
        "registered_model_name",
        "MLFLOW_REGISTER_MODEL_NAME",
    },
}

ALIAS_TO_SETTING = {
    alias: key
    for key, aliases in SETTING_ALIASES.items()
    for alias in aliases
}

MODEL_SUFFIXES = {
    ".pkl",
    ".joblib",
    ".pt",
    ".pth",
    ".onnx",
    ".h5",
    ".keras",
    ".safetensors",
    ".bst",
    ".ubj",
}
REQUIREMENT_OPERATORS = ["==", "!=", ">=", "<=", "~=", ">", "<"]

GENERATED_SKIP_DIRS = {
    ".git",
    ".opencode",
    ".venv",
    "__pycache__",
    "ai_studio",
    "node_modules",
}


@dataclass
class DoctorCheck:
    name: str
    status: str
    detail: str
    evidence: list[str] = field(default_factory=list)
    tod: list[str] = field(default_factory=list)


@dataclass
class DoctorReport:
    workspace: str
    project: str
    os: str
    python: str
    expected_python: str
    checks: list[DoctorCheck]
    next_steps: list[str]


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_version_parts(value: str) -> tuple[int, ...] | None:
    match = re.match(r"^\s*(\d+(?:\.\d+)*)", value)
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def compare_versions(installed: str, required: str) -> int | None:
    installed_parts = parse_version_parts(installed)
    required_parts = parse_version_parts(required)
    if installed_parts is None or required_parts is None:
        return None
    length = max(len(installed_parts), len(required_parts))
    left = installed_parts + (0,) * (length - len(installed_parts))
    right = required_parts + (0,) * (length - len(required_parts))
    if left == right:
        return 0
    return 1 if left > right else -1


def version_constraint_status(installed: str, required_spec: str) -> str:
    if not required_spec:
        return "installed"
    constraints = [item.strip() for item in required_spec.split(",") if item.strip()]
    unknown = False
    for constraint in constraints:
        operator = next((item for item in REQUIREMENT_OPERATORS if constraint.startswith(item)), None)
        if operator is None:
            unknown = True
            continue
        required = constraint[len(operator) :].strip()
        if operator == "~=":
            unknown = True
            continue
        if operator == "==":
            comparison = compare_versions(installed, required)
            if installed == required or comparison == 0:
                continue
            return "version_mismatch"
        if operator == "!=":
            comparison = compare_versions(installed, required)
            if installed == required or comparison == 0:
                return "version_mismatch"
            continue
        comparison = compare_versions(installed, required)
        if comparison is None:
            unknown = True
            continue
        if operator == ">=" and comparison < 0:
            return "version_mismatch"
        if operator == ">" and comparison <= 0:
            return "version_mismatch"
        if operator == "<=" and comparison > 0:
            return "version_mismatch"
        if operator == "<" and comparison >= 0:
            return "version_mismatch"
    return "version_unchecked" if unknown else "version_match"


def strip_inline_comment(line: str) -> str:
    if " #" in line:
        return line.split(" #", 1)[0].strip()
    return line.strip()


def parse_requirement_line(raw_line: str) -> tuple[str, str] | None:
    line = strip_inline_comment(raw_line)
    if not line or line.startswith("#"):
        return None
    if line.startswith(("-", "git+", "http://", "https://", "file:")):
        return None
    line = line.split(";", 1)[0].strip()
    match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?\s*(.*)$", line)
    if not match:
        return None
    return normalize_package_name(match.group(1)), match.group(2).strip()


def requirement_rows(project: Path) -> list[tuple[str, str, str | None, str]]:
    rows = []
    seen: set[str] = set()
    path = project / "requirements.txt"
    if path.exists():
        for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parsed = parse_requirement_line(raw_line)
            if parsed is None:
                continue
            name, required_spec = parsed
            seen.add(name)
            installed = package_version(name)
            status = "missing" if installed is None else version_constraint_status(installed, required_spec)
            rows.append((name, required_spec or "any", installed, status))
    for name, required_spec in EXPECTED_PACKAGE_VERSIONS.items():
        normalized = normalize_package_name(name)
        if normalized in seen:
            continue
        installed = package_version(normalized)
        status = "missing" if installed is None else version_constraint_status(installed, required_spec)
        rows.append((normalized, required_spec, installed, status))
    return rows


def rel(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def target_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        return literal_string(node.slice)
    return None


def record_setting(values: dict[str, str], key: str | None, value: str | None) -> None:
    if key is None or value is None:
        return
    setting_key = ALIAS_TO_SETTING.get(key)
    if setting_key:
        values[setting_key] = value


def parse_python_settings(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    try:
        tree = ast.parse(read_text(path))
    except SyntaxError:
        return values
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = literal_string(node.value)
            for target in node.targets:
                record_setting(values, target_name(target), value)
        elif isinstance(node, ast.AnnAssign):
            record_setting(values, target_name(node.target), literal_string(node.value))
        elif isinstance(node, ast.Dict):
            for key_node, value_node in zip(node.keys, node.values):
                record_setting(values, literal_string(key_node), literal_string(value_node))
    return values


def parse_env_settings(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in read_text(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        record_setting(values, key.strip(), value.strip().strip('"').strip("'"))
    return values


def unique_paths(paths: list[Path]) -> list[Path]:
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
    found = []
    for name in ENTRYPOINT_CANDIDATES:
        candidate = project / name
        if candidate.is_file():
            found.append(candidate)
    found.extend(path for path in project.glob("*.py") if path.is_file())
    return unique_paths(found)


def find_setting_file(project: Path, explicit: str | None) -> Path | None:
    if explicit:
        path = (project / explicit).resolve() if not Path(explicit).is_absolute() else Path(explicit).resolve()
        return path if path.exists() else path
    for name in SETTING_FILES:
        path = project / name
        if path.is_file():
            values = parse_python_settings(path)
            if values or name.endswith("runtest.py") or name in {"run_model.py"}:
                return path
    entrypoints = find_entrypoints(project)
    if len(entrypoints) == 1:
        return entrypoints[0]
    return None


def find_model_artifacts(project: Path, max_depth: int = 4) -> list[Path]:
    if is_opencode_sample_source(project):
        return []
    artifacts: list[Path] = []
    base_depth = len(project.parts)
    for root, dirs, files in os.walk(project):
        root_path = Path(root)
        depth = len(root_path.parts) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = [dirname for dirname in dirs if dirname not in GENERATED_SKIP_DIRS]
        for dirname in dirs:
            if dirname in {"saved_model", "model", "models"}:
                artifacts.append(root_path / dirname)
        for filename in files:
            file_path = root_path / filename
            if file_path.suffix.lower() in MODEL_SUFFIXES or filename == "MLmodel":
                artifacts.append(file_path)
    return sorted(set(artifacts))


def is_filesystem_root(path: Path) -> bool:
    return path.parent == path


def is_opencode_sample_source(path: Path) -> bool:
    parts = path.resolve().parts
    if ".opencode" in parts:
        return True
    for index, part in enumerate(parts[:-1]):
        if part == ".opencode" and parts[index + 1] in {"sample", "samples"}:
            return True
    return False


def check_python_version() -> DoctorCheck:
    current = platform.python_version()
    if current == EXPECTED_PYTHON_VERSION:
        return DoctorCheck("환경 검증", "pass", f"Python {current}", [])
    return DoctorCheck(
        "환경 검증",
        "warn",
        f"Python 버전 차이 ({current} vs 기대 {EXPECTED_PYTHON_VERSION})",
        [],
        [f"Python {EXPECTED_PYTHON_VERSION} 환경에서 최종 QA를 실행하세요."],
    )


def check_pip_requirements(project: Path) -> DoctorCheck:
    path = project / "requirements.txt"
    if not path.exists():
        return DoctorCheck(
            "패키지 설치 상태",
            "warn",
            "requirements.txt가 없습니다.",
            ["설치 기준 파일: requirements.txt (missing)"],
            ["사용자 모델의 pip 필요 패키지 목록을 확인하거나 requirements.txt를 추가하세요."],
        )
    rows = requirement_rows(project)
    if not rows:
        return DoctorCheck(
            "패키지 설치 상태",
            "warn",
            "requirements.txt에서 확인 가능한 pip 패키지를 찾지 못했습니다.",
            ["requirements.txt"],
            ["requirements.txt 형식을 확인하세요."],
        )
    missing = [name for name, _, installed, _ in rows if installed is None]
    mismatched = [name for name, _, _, status in rows if status == "version_mismatch"]
    unchecked = [name for name, _, _, status in rows if status == "version_unchecked"]
    evidence = ["설치 기준 파일: requirements.txt"]
    for name, required, installed, status in rows[:20]:
        installed_text = installed or "missing"
        evidence.append(f"{name}: {status} (required: {required}, installed: {installed_text})")
    if missing or mismatched:
        return DoctorCheck(
            "패키지 설치 상태",
            "warn",
            "미설치 또는 버전 불일치 패키지가 있습니다.",
            evidence,
            ["requirements.txt 기준으로 누락/버전 불일치 패키지를 먼저 맞추세요."],
        )
    if unchecked:
        return DoctorCheck(
            "패키지 설치 상태",
            "warn",
            "일부 복잡한 버전 조건은 자동 판정이 필요합니다.",
            evidence,
            ["version_unchecked 항목은 사용자가 설치 버전 호환성을 직접 확인하세요."],
        )
    return DoctorCheck("패키지 설치 상태", "pass", "requirements.txt 패키지가 현재 환경에 설치되어 있습니다.", evidence)


def check_opencode(workspace: Path) -> DoctorCheck:
    config = workspace / ".opencode" / "opencode.json"
    skills_dir = workspace / ".opencode" / "skills"
    evidence = []
    missing = []
    if not config.exists():
        missing.append(".opencode/opencode.json")
    else:
        try:
            json.loads(read_text(config))
            evidence.append(".opencode/opencode.json: valid")
        except json.JSONDecodeError as exc:
            return DoctorCheck(
                "OpenCode 패키지",
                "fail",
                f"opencode.json 형식 오류: line {exc.lineno} {exc.msg}",
                [str(config)],
                ["opencode.json을 먼저 수정하세요."],
            )

    for folder in SKILL_FOLDERS:
        skill = skills_dir / folder / "SKILL.md"
        if skill.exists():
            evidence.append(f"{folder}/SKILL.md")
        else:
            missing.append(f".opencode/skills/{folder}/SKILL.md")

    if missing:
        return DoctorCheck(
            "OpenCode 패키지",
            "warn",
            "필수 패키지 파일 또는 순서형 스킬 폴더가 부족합니다.",
            [f"missing: {item}" for item in missing] + evidence,
            ["스킬 패키지를 다시 복사하거나 누락된 폴더만 보충하세요."],
        )
    return DoctorCheck("OpenCode 패키지", "pass", "opencode.json과 01~06 스킬 폴더가 정상입니다.", evidence)


def check_sample_spec(project: Path, workspace: Path, sample: str) -> DoctorCheck:
    evidence = []
    missing = []
    for dirname in SAMPLE_SPEC_DIRS:
        path = project / dirname
        if path.is_dir():
            evidence.append(f"{dirname}/")
        else:
            missing.append(f"{dirname}/")
    for filename in SAMPLE_SPEC_FILES:
        path = project / filename
        if path.exists():
            evidence.append(filename)
        else:
            missing.append(filename)
    if not ((project / "aiu_custom" / "predict.py").exists() or (project / "aiu_custom" / "model_wrapper.py").exists()):
        missing.append("aiu_custom/predict.py 또는 aiu_custom/model_wrapper.py")
    if not (project / "local_serving" / "serve.py").exists():
        missing.append("local_serving/serve.py")
    if not find_entrypoints(project):
        missing.append("실제 사용하는 Python 실행 파일")

    if missing:
        copy_command = (
            "python .opencode/scripts/02-sample-bootstrap/bootstrap_sample_project.py --project . "
            f"--sample {sample} --scaffold-existing --execute"
        )
        if project == workspace:
            copy_command = f"python .opencode/scripts/02-sample-bootstrap/bootstrap_sample_project.py --project . --sample {sample} --scaffold-existing --execute"
        return DoctorCheck(
            "샘플 규격 확인/보충",
            "warn",
            "모델 프로젝트에 샘플 규격 폴더/파일이 부족합니다.",
            [f"missing: {item}" for item in missing] + evidence,
            [
                "기존 모델 파일은 덮어쓰지 말고 부족한 골격만 복사하세요.",
                copy_command,
            ],
        )
    return DoctorCheck("샘플 규격 확인/보충", "pass", "샘플 규격 폴더/파일이 모두 있습니다.", evidence)


def check_env_settings(project: Path, setting_file_arg: str | None) -> DoctorCheck:
    env_file = project / ".env"
    if not env_file.exists():
        return DoctorCheck(
            "환경 변수 입력/export",
            "warn",
            "MLflow 설정을 읽을 .env 파일을 찾지 못했습니다.",
            [],
            [
                "현재 워크스페이스 루트에 .env 파일을 만들고 MLflow 5개 값을 입력하세요.",
                "필수 키: mlflow_tracking_uri, mlflow_tracking_username, mlflow_tracking_password, mlflow_experiment_name, mlflow_register_model_name",
            ],
        )

    values = parse_env_settings(env_file)
    evidence = [rel(env_file, project)]
    missing = []
    for source_key in MLFLOW_SOURCE_KEYS:
        value = values.get(source_key, "")
        env_key = ENV_EXPORT_MAP[source_key]
        env_value = os.environ.get(env_key)
        if value:
            if source_key == "mlflow_tracking_password":
                evidence.append(f"{source_key}: set (값은 출력하지 않음)")
            else:
                evidence.append(f"{source_key}: set")
        elif env_value:
            evidence.append(f"{source_key}: exported")
        elif source_key in AUTO_DEFAULT_SETTING_KEYS:
            evidence.append(f"{source_key}: auto_default")
        else:
            missing.append(source_key)

    if missing:
        return DoctorCheck(
            "환경 변수 입력/export",
            "warn",
            "필수 MLflow 설정값이 아직 미입력 상태입니다.",
            [f"missing: {item}" for item in missing] + evidence,
            [
                ".env에 tracking URL, username, password, experiment name, register model name을 직접 입력하세요.",
                "mlflow_tracking_uri은 원격 MLflow/리포트 URI(http:// 또는 https://)만 사용합니다.",
                "password 값은 화면에 출력하지 말고 set/missing 상태만 확인하세요.",
            ],
        )
    return DoctorCheck("환경 변수 입력/export", "pass", ".env MLflow 5개 값이 확인됐습니다.", evidence)


def check_ai_studio_code(project: Path, setting_file_arg: str | None) -> DoctorCheck:
    setting_file = find_setting_file(project, setting_file_arg)
    if setting_file is None or not setting_file.exists():
        return DoctorCheck(
            "AI Studio 코드 적합성",
            "warn",
            "검사할 실행 파일을 확정하지 못했습니다.",
            [],
            [
                "실행 파일을 찾지 못했거나 후보가 모호합니다.",
                "사용자가 실제 학습/모델 생성 Python 파일을 직접 넣고 --entrypoint <file>로 지정하세요.",
            ],
        )

    text = read_text(setting_file)
    values = parse_python_settings(setting_file)
    evidence = [rel(setting_file, project)]
    missing = []

    if "mlflow" in text:
        evidence.append("mlflow usage: found")
    else:
        missing.append("mlflow import/use")

    missing_settings = [key for key in MLFLOW_SOURCE_KEYS if not values.get(key) and ENV_EXPORT_MAP[key] not in text]
    if missing_settings:
        missing.append("settings: " + ", ".join(missing_settings))
    else:
        evidence.append("MLflow settings: found")

    export_markers = [env_key for env_key in ENV_EXPORT_MAP.values() if env_key in text]
    if export_markers:
        evidence.append("MLFLOW export/env markers: " + ", ".join(export_markers))
    else:
        missing.append("MLFLOW_* export/env settings")

    if "artifact_path=\"ai_studio\"" in text or "artifact_path='ai_studio'" in text or "ai_studio/code" in text or "ai_studio/metrics" in text:
        evidence.append("AI Studio artifact/output path: found")
    else:
        missing.append("AI Studio artifact/output path")

    if "aiu_custom" in text or "ModelWrapper" in text or (project / "aiu_custom").exists():
        evidence.append("aiu_custom/ModelWrapper marker: found")
    else:
        missing.append("aiu_custom wrapper marker")

    if missing:
        return DoctorCheck(
            "AI Studio 코드 적합성",
            "warn",
            "현재 실행 파일은 AI Studio/MLflow 규격에 맞게 수정이 필요할 수 있습니다.",
            [f"missing: {item}" for item in missing] + evidence,
            [
                f"{rel(setting_file, project)}에 MLflow 설정 블록 5개와 MLFLOW_* export를 추가하세요.",
                "MLflow artifact는 artifact_path=\"ai_studio\" 기준으로 기록되게 맞추세요.",
                "aiu_custom ModelWrapper 사용 여부를 확인하세요.",
            ],
        )
    return DoctorCheck("AI Studio 코드 적합성", "pass", "실행 파일에 AI Studio/MLflow 연동 마커가 있습니다.", evidence)


def check_entrypoint(project: Path, setting_file_arg: str | None) -> DoctorCheck:
    entrypoints = find_entrypoints(project)
    setting_file = find_setting_file(project, setting_file_arg)
    evidence = [rel(path, project) for path in entrypoints[:10]]
    if setting_file and setting_file.exists():
        return DoctorCheck(
            "실행 파일 확정",
            "pass",
            f"실행/설정 파일 후보가 확정됐습니다: {rel(setting_file, project)}",
            evidence or [rel(setting_file, project)],
        )
    if not entrypoints:
        return DoctorCheck(
            "실행 파일 확정",
            "warn",
            "실행 파일 후보가 없습니다.",
            [],
            [
                "실행 파일을 찾지 못했습니다. 사용자가 실제 학습/모델 생성 Python 파일을 프로젝트에 직접 넣어주세요.",
                "파일을 넣은 뒤 --entrypoint <file>로 다시 점검하세요.",
            ],
        )
    if len(entrypoints) == 1:
        return DoctorCheck("실행 파일 확정", "pass", f"단일 실행 파일 후보: {rel(entrypoints[0], project)}", evidence)
    return DoctorCheck(
        "실행 파일 확정",
        "warn",
        "실행 파일 후보가 여러 개입니다.",
        evidence,
        [
            "실행 파일 후보가 여러 개입니다. 사용자가 실제 사용하는 파일명을 직접 지정해야 합니다.",
            "예: python .opencode/scripts/qa-maintenance/doctor.py --workspace . --project <project> --entrypoint run.py",
        ],
    )


def check_model_outputs(project: Path) -> DoctorCheck:
    artifacts = find_model_artifacts(project)
    local_outputs = []
    for name in ["ai_studio/metrics", "ai_studio/code"]:
        path = project / name
        if path.exists():
            local_outputs.append(name)
    evidence = [rel(path, project) for path in artifacts[:10]] + local_outputs
    if artifacts or local_outputs:
        return DoctorCheck("산출물 확인", "pass", "모델/메트릭/코드 산출물 후보가 있습니다.", evidence)
    return DoctorCheck(
        "산출물 확인",
        "warn",
        "모델 산출물 또는 ai_studio 산출물이 아직 보이지 않습니다.",
        [],
        ["모델 실행 및 원격 MLflow 기록 후 ai_studio/metrics, ai_studio/code 또는 모델 파일을 확인하세요."],
    )


def build_next_steps(checks: list[DoctorCheck]) -> list[str]:
    steps: list[str] = []
    for check in checks:
        if check.status in {"warn", "fail"}:
            steps.extend(check.tod)
    deduped = []
    for step in steps:
        if step not in deduped:
            deduped.append(step)
    if not deduped:
        deduped.append("doctor 기준으로 다음 단계 진행 가능: 패키지 설치 -> 모델 실행 및 원격 MLflow 기록 -> 산출물 확인.")
    return deduped


def build_report(workspace: Path, project: Path, sample: str, setting_file: str | None) -> DoctorReport:
    if is_opencode_sample_source(project):
        checks = [
            DoctorCheck(
                ".opencode sample source",
                "fail",
                ".opencode/는 번들 스킬 원본이라 분석 대상이 아닙니다.",
                [str(project)],
                ["실제 사용자가 선택한 모델 프로젝트 폴더를 --project로 지정하세요."],
            )
        ]
        return DoctorReport(
            workspace=str(workspace),
            project=str(project),
            os=f"{platform.system()} {platform.release()}",
            python=platform.python_version(),
            expected_python=EXPECTED_PYTHON_VERSION,
            checks=checks,
            next_steps=build_next_steps(checks),
        )
    checks = [
        check_opencode(workspace),
        check_python_version(),
        check_pip_requirements(project),
        check_entrypoint(project, setting_file),
        check_ai_studio_code(project, setting_file),
        check_sample_spec(project, workspace, sample),
        check_env_settings(project, setting_file),
        check_model_outputs(project),
    ]
    return DoctorReport(
        workspace=str(workspace),
        project=str(project),
        os=f"{platform.system()} {platform.release()}",
        python=platform.python_version(),
        expected_python=EXPECTED_PYTHON_VERSION,
        checks=checks,
        next_steps=build_next_steps(checks),
    )


def print_text(report: DoctorReport) -> None:
    print("OpenCode MLflow Doctor")
    print("Workspace: .")
    print("Project: .")
    print(f"OS: {report.os}")
    print(f"Python: {report.python} (expected {report.expected_python})")
    print("")
    for index, check in enumerate(report.checks, start=1):
        print(f"{index}. [{check.status}] {check.name}")
        print(f"   detail: {check.detail}")
        for item in check.evidence:
            print(f"   - {item}")
        if check.tod:
            print("   TODO:")
            for item in check.tod:
                print(f"   - {item}")
    print("")
    print("Next steps:")
    for item in report.next_steps:
        print(f"- {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one-page OpenCode MLflow workflow diagnostics.")
    parser.add_argument("--workspace", default=".", help="workspace root containing .opencode")
    parser.add_argument("--project", default=".", help="model project folder")
    parser.add_argument("--sample", choices=["sklearn", "pytorch", "tensorflow"], default="pytorch", help="sample scaffold to suggest when files are missing")
    parser.add_argument("--entrypoint", help="actual local training/model creation file, such as runtest.py")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--strict-exit", action="store_true", help="return non-zero on warn/fail")
    args = parser.parse_args()

    workspace = resolve_workspace_project(args.workspace)
    project = resolve_workspace_project(args.project)
    if not workspace.exists():
        raise SystemExit(f"workspace not found: {workspace}")
    if not project.exists():
        raise SystemExit(f"project not found: {project}")
    if is_filesystem_root(project):
        raise SystemExit("drive/root scan is not allowed. Run from the model project folder or pass --project <current-project-folder>.")

    report = build_report(workspace, project, args.sample, args.entrypoint)
    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print_text(report)

    if args.strict_exit:
        if any(check.status == "fail" for check in report.checks):
            return 2
        if any(check.status == "warn" for check in report.checks):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
