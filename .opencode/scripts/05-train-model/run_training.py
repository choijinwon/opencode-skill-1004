import argparse, json, os, subprocess, sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from common.mlflow_settings import AI_STUDIO_ENV_KEYS, EXPORT_ENV_MAP, parse_setting_env_file
from common.workspace import is_filesystem_root, is_opencode_sample_source, resolve_workspace_project


@dataclass
class EnvVarStatus:
    name: str; status: str


@dataclass
class TrainingReport:
    project_path: str; model_found: bool; selected_sample: str | None; work_path: str
    entrypoint: str | None; command: list[str]; executed: bool; return_code: int | None
    artifacts: list[str] = field(default_factory=list)
    mlflow_summary: dict[str, str] = field(default_factory=dict)
    preflight: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    process_checklist: list[EnvVarStatus] = field(default_factory=list)


def env_values(project: Path) -> dict[str, str]:
    values = parse_setting_env_file(project / ".env")
    return {EXPORT_ENV_MAP[key]: values.get(key, "") for key in AI_STUDIO_ENV_KEYS}


def missing_env(project: Path) -> list[str]:
    values = env_values(project)
    return [key for key, value in values.items() if not value]


def selected_project(project: Path) -> Path:
    configs = sorted(project.glob("*/config/config.json"))
    return configs[-1].parents[1] if configs and not (project / "runtest_2.py").exists() else project


def artifacts(project: Path) -> list[str]:
    names = ["saved_model", "config/config.json", "input_example.json"]
    return [name for name in names if (project / name).exists()]


def build_report(project: Path, entrypoint_name: str | None, execute: bool) -> TrainingReport:
    if is_filesystem_root(project):
        return TrainingReport(str(project), False, None, str(project), None, [], False, None, failures=["drive_root_scan_not_allowed"])
    if is_opencode_sample_source(project):
        return TrainingReport(str(project), False, None, str(project), None, [], False, None, failures=["opencode_sample_source_not_target"])
    work = selected_project(project.resolve())
    entrypoint = work / (entrypoint_name or "runtest_2.py")
    command = [sys.executable, entrypoint.name]
    report = TrainingReport(str(project), (work / "saved_model").exists(), None, str(work), entrypoint.name, command, execute, None, artifacts(work), process_checklist=[EnvVarStatus(key, "set" if value else "missing") for key, value in env_values(work).items()])
    if not entrypoint.exists():
        report.failures.append(f"entrypoint_not_found:{entrypoint.name}")
    for key in missing_env(work):
        report.failures.append(f"missing_env:{key}")
    if not execute:
        report.next_steps.append("검토 후 --execute를 붙여 원격 MLflow 등록을 실행하세요.")
        return report
    if report.failures:
        report.next_steps.append("누락 항목을 수정한 뒤 7번 오류 재실행으로 다시 실행하세요.")
        return report
    env = os.environ.copy()
    env.update(env_values(work))
    completed = subprocess.run(command, cwd=work, env=env, text=True)
    report.return_code = completed.returncode
    if completed.returncode:
        report.failures.append(f"entrypoint_failed:{completed.returncode}")
    else:
        report.mlflow_summary["status"] = "completed"
        report.next_steps.append("등록 실행 완료. 6번 추론 테스트로 진행하세요.")
    return report


def print_report(report: TrainingReport):
    print(f"5번 원격 MLflow 등록: {'실행' if report.executed else '대기'}")
    print(f"작업 폴더: {report.work_path}")
    if report.failures:
        print("실패:")
        for item in report.failures:
            print(f"- {item}")
    for step in report.next_steps:
        print(f"- {step}")


def main():
    parser = argparse.ArgumentParser(description="Step 5: run selected model entrypoint for remote MLflow registration.")
    parser.add_argument("--project", default=".")
    parser.add_argument("--entrypoint", default="runtest_2.py")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(resolve_workspace_project(args.project), args.entrypoint, args.execute)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2)) if args.json else print_report(report)
    return 1 if report.failures and args.execute else 0


if __name__ == "__main__":
    raise SystemExit(main())
