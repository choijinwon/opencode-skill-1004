import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from common.workspace import resolve_workspace_project
from common.mlflow_settings import AI_STUDIO_ENV_KEYS, parse_setting_env_file, todo_placeholder


RUNTIME_FILES = [
    "runtest_2.py",
    "aiu_custom/model.py",
    "aiu_custom/predict.py",
    "config/config.json",
    "input_example.json",
    "inferencetest.py",
    "saved_model",
]


@dataclass
class PrepareReport:
    project_path: str
    model: str
    executed: bool
    work_path: str | None = None
    status: str = "checked"
    prepared_paths: list[str] = field(default_factory=list)
    missing_paths: list[str] = field(default_factory=list)
    missing_env: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


def rel(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def selected_work(project: Path) -> Path | None:
    if (project / "runtest_2.py").exists():
        return project
    candidates = [
        path.parent
        for path in project.glob("*/runtest_2.py")
        if (path.parent / "config" / "config.json").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def workspace_root(project: Path) -> Path:
    if (project / ".opencode").is_dir():
        return project
    if (project.parent / ".opencode").is_dir():
        return project.parent
    return project


def empty_env_keys(root: Path) -> list[str]:
    values = parse_setting_env_file(root / ".env")
    return [key for key in AI_STUDIO_ENV_KEYS if not values.get(key) or todo_placeholder(values.get(key))]


def env_check_command(project: Path, root: Path, work: Path) -> str:
    if project == work and root == project.parent:
        return "python ../.opencode/scripts/03-environment-check/check_environment.py --project . --entrypoint runtest_2.py --no-fix-packages"
    return "python .opencode/scripts/03-environment-check/check_environment.py --project " + rel(work, root) + " --entrypoint runtest_2.py --no-fix-packages"


def build_report(project: Path, model: str, execute: bool) -> PrepareReport:
    project = project.resolve()
    root = workspace_root(project)
    work = selected_work(project)
    report = PrepareReport(".", model, execute, work_path=rel(work, project) if work else None)
    if work is None:
        report.status = "needs_model_select"
        report.next_steps.append("먼저 2번 모델 선택을 실행하세요: python .opencode/scripts/02-model-select/select_model.py --project . --model <번호>")
        return report

    for name in RUNTIME_FILES:
        path = work / name
        (report.prepared_paths if path.exists() else report.missing_paths).append(rel(path, project))
    report.status = "ready" if not report.missing_paths else "incomplete"
    report.missing_env = empty_env_keys(root)
    if report.missing_env:
        report.status = "needs_environment_check"
        report.next_steps.append("3번 환경 검증이 먼저 필요합니다.")
        report.next_steps.append(env_check_command(project, root, work))
        return report
    report.next_steps.append("4번 템플릿 변환은 2번 모델 선택에서 이미 완료되었습니다.")
    report.next_steps.append("다음 단계: python .opencode/scripts/05-train-model/run_training.py --project " + rel(work, project) + " --entrypoint runtest_2.py --execute")
    return report


def print_report(report: PrepareReport) -> None:
    status_text = {"ready": "완료", "needs_environment_check": "환경 검증 필요", "needs_model_select": "모델 선택 필요"}.get(report.status, report.status)
    print("4번 템플릿 변환:", status_text)
    print(f"작업 폴더: {report.work_path or 'missing'}")
    if report.missing_env:
        print("| Status | Step | Action |")
        print("|---|---:|---|")
        print("| 입력 | 3 | 환경 재검증 |")
    if report.prepared_paths:
        print("확인된 파일:")
        for path in report.prepared_paths:
            print(f"- {path}")
    if report.missing_paths:
        print("누락:")
        for path in report.missing_paths:
            print(f"- {path}")
    if report.missing_env:
        print("환경 검증 필요:")
        for key in report.missing_env:
            print(f"- {key}")
    for step in report.next_steps:
        print(f"- {step}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 4 compatibility check for selected model runtime files.")
    parser.add_argument("--project", default=".")
    parser.add_argument("--model", default="selected")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--select-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--sync-runtime", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    report = build_report(resolve_workspace_project(args.project), args.model, args.execute)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2)) if args.json else print_report(report)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1)
