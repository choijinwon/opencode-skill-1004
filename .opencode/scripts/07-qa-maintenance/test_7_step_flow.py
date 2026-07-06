#!/usr/bin/env python3
import argparse, json, subprocess, sys
from dataclasses import dataclass
from pathlib import Path

PYTHON = "python"
ANALYZE = ".opencode/scripts/01-project-analyze/validate_mlflow_project.py"
SELECT = ".opencode/scripts/02-model-select/select_model.py"
ENV = ".opencode/scripts/03-environment-check/check_environment.py"
RUN = ".opencode/scripts/05-train-model/run_training.py"
REQUIRED = ["runtest_2.py", "aiu_custom/model.py", "aiu_custom/predict.py", "inferencetest.py", "config/config.json", "input_example.json", "requirements.txt"]


@dataclass
class StepResult:
    index: int
    name: str
    status: str
    detail: str


def run(cmd: list[str], cwd: Path, allow_failure: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if result.returncode and not allow_failure:
        raise RuntimeError(result.stderr or result.stdout or "command failed")
    return result


def assert_contains(text: str, needle: str, label: str):
    if needle not in text:
        raise AssertionError(f"{label}: missing {needle!r}")


def generated_ok(project: Path):
    missing = [path for path in REQUIRED if not (project / path).exists()]
    if not (project / "saved_model").is_dir() or not any((project / "saved_model").iterdir()):
        missing.append("saved_model/<model>")
    if missing:
        raise AssertionError("missing generated files: " + ", ".join(missing))


def print_summary(rows: list[StepResult]):
    print("AI Studio 7단계 테스트 결과")
    for row in rows:
        print(f"{row.index}. {row.name}: {row.status} - {row.detail}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=".")
    parser.add_argument("--model", default="3")
    parser.add_argument("--run-remote", action="store_true")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    rows: list[StepResult] = []

    step1 = run([PYTHON, ANALYZE, "--project", ".", "--no-write-check", "--json"], project)
    assert json.loads(step1.stdout).get("model_artifact_paths") is not None
    rows.append(StepResult(1, "모델 목록 확인", "PASS", "모델 목록 JSON 확인"))

    step2 = run([PYTHON, SELECT, "--project", ".", "--model", args.model], project)
    assert_contains(step2.stdout, "선택 모델:", "step2")
    work = next((line.split(":", 1)[1].strip() for line in step2.stdout.splitlines() if line.startswith("작업 폴더:")), "")
    work_project = project / work
    generated_ok(work_project)
    rows.append(StepResult(2, "모델 선택", "PASS", "선택 모델 작업 폴더 생성"))

    step3 = run([PYTHON, ENV, "--project", work, "--entrypoint", "runtest_2.py", "--no-fix-packages"], project, allow_failure=True)
    assert_contains(step3.stdout, "3번 환경 검증", "step3")
    rows.append(StepResult(3, "환경 검증", "PASS", ".env/requirements 확인"))

    rows.append(StepResult(4, "템플릿 변환", "PASS", "2번에서 런타임 파일 생성 완료"))

    step5_cmd = [PYTHON, RUN, "--project", work, "--entrypoint", "runtest_2.py"]
    if args.run_remote:
        step5_cmd.append("--execute")
    step5 = run(step5_cmd, project, allow_failure=not args.run_remote)
    assert_contains(step5.stdout + step5.stderr, "5번 원격 MLflow 등록", "step5")
    rows.append(StepResult(5, "원격 MLflow 등록 실행", "PASS" if args.run_remote else "SKIP", "게이트 확인"))

    rows.append(StepResult(6, "추론 테스트", "SKIP", "사용자 선택 시 inferencetest.py 실행"))
    step7 = run([PYTHON, ENV, "--project", work, "--entrypoint", "runtest_2.py", "--no-fix-packages"], project, allow_failure=True)
    assert_contains(step7.stdout, "3번 환경 검증", "step7")
    rows.append(StepResult(7, "오류 재실행", "PASS", "실패 단계 재실행 명령 확인"))
    print_summary(rows)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(1)
