import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = ROOT / "samples"
SAMPLES = {
    "sklearn": ("sklearn_sample", "sklearn 모델"),
    "pytorch": ("pytorch_sample", "PyTorch 모델"),
    "tensorflow": ("tensorflow_sample", "TensorFlow/Keras 모델"),
}
SKIP_NAMES = {".DS_Store", "__pycache__", ".venv", "venv", "env", "data", "ai_studio", "mlflow.db"}
REQUIRED_DIRS = ["aiu_custom", "local_serving", "saved_model"]


def table(headers: list[str], rows: list[list[str]]) -> None:
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        print("| " + " | ".join(str(value) for value in row) + " |")


def resolve_project(raw: str) -> Path:
    value = "." if raw.strip() in {"<workspace-root>", "<current-project-folder>", "<model-project-folder>"} else raw
    if "<" in value or ">" in value:
        raise ValueError("placeholder project path를 실제 경로로 바꾸세요. 예: --project .")
    path = Path(value).expanduser().resolve()
    if ".opencode" in path.parts:
        return Path(*path.parts[: path.parts.index(".opencode")]).resolve()
    return path


def is_empty(project: Path) -> bool:
    return not project.exists() or not any(child.name not in {".git", ".gitignore", ".opencode", ".DS_Store"} for child in project.iterdir())


def sample_rows() -> list[dict[str, str]]:
    rows = []
    for key, (folder, label) in SAMPLES.items():
        source = SAMPLES_DIR / folder
        rows.append({"key": key, "label": label, "source_path": str(source), "available": str(source.exists()).lower()})
    return rows


def iter_files(sample: Path):
    for path in sample.rglob("*"):
        relative = path.relative_to(sample)
        if any(part in SKIP_NAMES for part in relative.parts):
            continue
        yield path, relative


def copy_sample(sample: Path, project: Path, execute: bool, force: bool, folder_mode: bool, missing_only: bool) -> tuple[Path, list[str], list[str]]:
    target_root = project / sample.name if folder_mode else project
    copied, skipped = [], []
    if execute:
        target_root.mkdir(parents=True, exist_ok=True)
    for source, relative in iter_files(sample):
        target = target_root / relative
        display = (Path(sample.name) / relative if folder_mode else relative).as_posix()
        if source.is_dir():
            if execute:
                target.mkdir(parents=True, exist_ok=True)
            copied.append(display + "/")
            continue
        if target.exists() and (missing_only or not force):
            skipped.append(display)
            continue
        if execute:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        copied.append(display)
    for name in REQUIRED_DIRS:
        path = target_root / name
        if execute:
            path.mkdir(parents=True, exist_ok=True)
        entry = (Path(sample.name) / name if folder_mode else Path(name)).as_posix() + "/"
        if entry not in copied:
            copied.append(entry)
    return target_root, copied, skipped


def build_report(args) -> dict:
    project = resolve_project(args.project)
    project_empty = is_empty(project)
    sample_key = args.sample
    failures: list[str] = []
    target, copied, skipped = None, [], []
    source = SAMPLES_DIR / SAMPLES[sample_key][0] if sample_key else None
    if not sample_key:
        failures.append("sample_required")
    elif not source or not source.exists():
        failures.append(f"sample_not_found:{sample_key}")
    else:
        target, copied, skipped = copy_sample(source, project, args.execute, args.force, args.copy_mode == "folder", args.scaffold_existing)
    return {
        "project_path": str(project),
        "selected_sample": sample_key,
        "sample_source_path": str(source) if source else None,
        "target_project_path": str(target) if target else None,
        "copy_mode": "scaffold_existing" if args.scaffold_existing else args.copy_mode,
        "execute": args.execute,
        "project_empty": project_empty,
        "copied": copied,
        "skipped": skipped,
        "failures": failures,
        "next_steps": ["3번 환경 검증으로 진행하세요."] if not failures else [],
    }


def print_report(report: dict) -> None:
    if report["failures"]:
        print("실패:")
        for item in report["failures"]:
            print(f"- {item}")
        return
    print(f"샘플: {report['selected_sample']}")
    print(f"대상: {report['target_project_path']}")
    print(f"복사: {len(report['copied'])}개 / 건너뜀: {len(report['skipped'])}개")
    for step in report["next_steps"]:
        print(f"- {step}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 4 fallback: copy a bundled sample scaffold.")
    parser.add_argument("--project", default=".")
    parser.add_argument("--sample", choices=sorted(SAMPLES))
    parser.add_argument("--copy-mode", choices=["folder", "root"], default="root")
    parser.add_argument("--scaffold-existing", action="store_true", help="copy only missing files")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.list:
        rows = sample_rows()
        print(json.dumps(rows, ensure_ascii=False, indent=2)) if args.json else table(["No", "Sample", "Label", "Available"], [[str(i), r["key"], r["label"], r["available"]] for i, r in enumerate(rows, 1)])
        return 0
    report = build_report(args)
    print(json.dumps(report, ensure_ascii=False, indent=2)) if args.json else print_report(report)
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1)
