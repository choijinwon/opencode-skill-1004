#!/usr/bin/env python3
"""Run the fixed 7-step AI Studio selected-model flow.

This is intentionally stdlib-only so it can run on a closed-network Windows PC.
By default step 5 verifies the remote MLflow registration gate without calling a
real server. Use --run-remote only when .env has real MLflow values.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


OPENCODE_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = OPENCODE_ROOT / "scripts"
PREPARE_SCRIPT = SCRIPTS_ROOT / "04-train-model" / "prepare_selected_model.py"
ENV_SCRIPT = SCRIPTS_ROOT / "03-environment-check" / "check_environment.py"
RUN_TRAINING_SCRIPT = SCRIPTS_ROOT / "04-train-model" / "run_training.py"
PROCESS_SCRIPT = SCRIPTS_ROOT / "ai_studio_process.py"

REQUIRED_GENERATED_PATHS = [
    "runtest_2.py",
    "aiu_custom/model.py",
    "aiu_custom/predict.py",
    "local_serving/localservingtest.py",
    "config/config.json",
    "input_example.json",
    "requirements.txt",
]


@dataclass
class StepResult:
    index: int
    name: str
    status: str
    detail: str


def ps_path(path: str) -> str:
    return path.replace("/", "\\")


def model_selection_args(raw_model: str) -> list[str]:
    model = raw_model.strip()
    if model.isdigit():
        # Keep compatibility with users typing "--model3" in PowerShell.
        return [f"--model{model}"]
    return ["--model", ps_path(model)]


def run_command(cmd: list[str], cwd: Path, allow_failure: bool = False) -> subprocess.CompletedProcess[str]:
    print(f"[run] cwd={cwd}")
    print("[cmd] " + " ".join(str(part) for part in cmd))
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    if result.returncode != 0 and not allow_failure:
        raise RuntimeError(f"command failed({result.returncode}): {' '.join(str(part) for part in cmd)}")
    return result


def read_env_file(project: Path) -> dict[str, str]:
    env_path = project / ".env"
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def mlflow_env_ready(project: Path) -> bool:
    values = read_env_file(project)
    return all(
        values.get(key, "").strip()
        for key in ["mlflow_tracking_uri", "mlflow_tracking_username", "mlflow_tracking_password"]
    )


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label}: expected text not found: {needle}")


def is_windows_absolute_path(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:[\\/]", value.strip()))


def assert_windows_relative_path(value: str, label: str) -> None:
    if not value:
        raise AssertionError(f"{label}: path is empty")
    if is_windows_absolute_path(value):
        raise AssertionError(f"{label}: must be relative, got absolute path: {value}")
    if "/" in value:
        raise AssertionError(f"{label}: must use Windows backslash path: {value}")


def verify_process_contract() -> None:
    namespace: dict[str, object] = {}
    exec(PROCESS_SCRIPT.read_text(encoding="utf-8"), namespace)
    steps = namespace["AI_STUDIO_PROCESS_STEPS"]
    expected = (
        "모델 목록 확인",
        "모델 선택",
        "환경변수/requirements 갱신",
        "템플릿 변환",
        "원격 MLflow 등록 실행",
        "추론 테스트",
        "오류 재실행",
    )
    if tuple(steps) != expected:
        raise AssertionError(f"7-step process changed: {steps}")


def verify_generated_files(project: Path) -> None:
    missing = [path for path in REQUIRED_GENERATED_PATHS if not (project / path).exists()]
    saved_model_dir = project / "saved_model"
    if not saved_model_dir.is_dir() or not any(saved_model_dir.iterdir()):
        missing.append("saved_model/<selected-model>")
    if missing:
        raise AssertionError("generated files missing: " + ", ".join(missing))

    config = json.loads((project / "config" / "config.json").read_text(encoding="utf-8"))
    model_config = config.get("model", {})
    model_path = str(model_config.get("path") or model_config.get("model_path") or "")
    source_path = str(model_config.get("source_path") or "")
    assert_windows_relative_path(model_path, "config model path")
    assert_windows_relative_path(source_path, "config source path")
    if not model_path.replace("/", "\\").startswith("saved_model\\"):
        raise AssertionError(f"config model path must use saved_model: {model_path}")
    if not source_path:
        raise AssertionError("config source_path is required")

    input_example = json.loads((project / "input_example.json").read_text(encoding="utf-8"))
    input_model_path = str(input_example.get("model_path") or input_example.get("path") or "")
    input_source_path = str(input_example.get("source_path") or "")
    assert_windows_relative_path(input_model_path, "input_example model path")
    assert_windows_relative_path(input_source_path, "input_example source path")
    if not input_model_path.replace("/", "\\").startswith("saved_model\\"):
        raise AssertionError(f"input_example model path must use saved_model: {input_model_path}")

    runtest_text = (project / "runtest_2.py").read_text(encoding="utf-8", errors="ignore")
    if re.search(r"[A-Za-z]:\\", runtest_text):
        raise AssertionError("runtest_2.py must not embed Windows drive absolute paths")
    assert_contains(runtest_text, "os.path.relpath", "MLmodel artifact uri relative path")
    assert_contains(runtest_text, "saved_model", "runtime model path")


def print_summary(results: list[StepResult]) -> None:
    print("")
    print("AI Studio 7단계 테스트 결과")
    for result in results:
        print(f"{result.index}. {result.name}: {result.status} - {result.detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the AI Studio fixed 7-step flow test")
    parser.add_argument("--project", default=".", help="workspace/model project root")
    parser.add_argument("--model", default="3", help="model number or project-relative path")
    parser.add_argument("--run-remote", action="store_true", help="execute real remote MLflow registration")
    parser.add_argument("--skip-inference", action="store_true", help="skip step 6 local inference execution")
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    if not project.exists():
        raise FileNotFoundError(f"project not found: {project}")

    verify_process_contract()
    results: list[StepResult] = []

    # 1. 모델 목록 확인
    step1 = run_command([sys.executable, str(PREPARE_SCRIPT), "--project", str(project), "--verbose"], project, allow_failure=True)
    assert_contains(step1.stdout, "model_artifact_paths:", "step 1 model list")
    results.append(StepResult(1, "모델 목록 확인", "PASS", "model_artifact_paths 출력 확인"))

    # 2. 모델 선택
    step2 = run_command(
        [sys.executable, str(PREPARE_SCRIPT), "--project", str(project), *model_selection_args(args.model), "--execute"],
        project,
    )
    assert_contains(step2.stdout, "준비 결과:", "step 2 prepare result")
    assert_contains(step2.stdout, "완료: 템플릿 복사 후 선택 모델 형식에 맞게 변환", "step 2 conversion")
    results.append(StepResult(2, "모델 선택", "PASS", f"모델 {args.model} 선택 및 자동 준비 성공"))

    # 3. 환경변수/requirements 갱신
    step3 = run_command(
        [sys.executable, str(ENV_SCRIPT), "--project", str(project), "--entrypoint", "runtest_2.py", "--no-fix-packages"],
        project,
        allow_failure=True,
    )
    assert_contains(step3.stdout, "AI Studio TODO Guide - 7단계", "step 3 TODO guide")
    assert_contains(step3.stdout, "[3] 환경변수/requirements 갱신", "step 3 status")
    results.append(StepResult(3, "환경변수/requirements 갱신", "PASS", "TODO 상태 및 requirements 점검 출력 확인"))

    # 4. 템플릿 변환
    verify_generated_files(project)
    results.append(StepResult(4, "템플릿 변환", "PASS", "runtest_2.py/config/input/local_serving/saved_model 검증"))

    # 5. 원격 MLflow 등록 실행
    if args.run_remote:
        if not mlflow_env_ready(project):
            raise AssertionError("--run-remote requires .env mlflow_tracking_uri/username/password")
        step5 = run_command(
            [sys.executable, str(RUN_TRAINING_SCRIPT), "--project", str(project), "--entrypoint", "runtest_2.py", "--execute"],
            project,
        )
        assert_contains(step5.stdout, "원격 MLflow", "step 5 remote registration")
        results.append(StepResult(5, "원격 MLflow 등록 실행", "PASS", "실제 원격 등록 명령 성공"))
    else:
        step5 = run_command([sys.executable, "runtest_2.py"], project, allow_failure=True)
        combined = step5.stdout + step5.stderr
        if mlflow_env_ready(project):
            results.append(StepResult(5, "원격 MLflow 등록 실행", "SKIP", "--run-remote 미지정: 실제 원격 등록 생략"))
        else:
            assert_contains(combined, "missing settings:", "step 5 missing env gate")
            results.append(StepResult(5, "원격 MLflow 등록 실행", "PASS", ".env 미입력 시 실행 차단 확인"))

    # 6. 추론 테스트
    if args.skip_inference:
        results.append(StepResult(6, "추론 테스트", "SKIP", "--skip-inference 지정"))
    else:
        step6 = run_command([sys.executable, str(project / "local_serving" / "localservingtest.py")], project)
        assert_contains(step6.stdout, '"status": "completed"', "step 6 inference status")
        assert_contains(step6.stdout, "saved_model", "step 6 saved_model runtime")
        results.append(StepResult(6, "추론 테스트", "PASS", "saved_model 기준 로컬 추론 성공"))

    # 7. 오류 재실행
    step7 = run_command([sys.executable, str(PREPARE_SCRIPT), "--project", str(project), "--model", "selected", "--execute"], project)
    assert_contains(step7.stdout, "준비 결과:", "step 7 rerun result")
    verify_generated_files(project)
    results.append(StepResult(7, "오류 재실행", "PASS", "selected 모델 재사용 및 재검증 성공"))

    print_summary(results)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(1)
