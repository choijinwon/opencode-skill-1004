import argparse
import json
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "samples"

SAMPLES = {
    "sklearn": {
        "path": "sklearn_sample",
        "label": "sklearn 모델",
        "description": "폐쇄망에서 사용자가 sklearn 모델 코드와 데이터를 넣는 기본 샘플",
    },
    "pytorch": {
        "path": "pytorch_sample",
        "label": "PyTorch 모델",
        "description": "폐쇄망에서 사용자가 PyTorch 모델 코드와 데이터를 넣는 기본 샘플",
    },
    "tensorflow": {
        "path": "tensorflow_sample",
        "label": "TensorFlow/Keras 모델",
        "description": "폐쇄망에서 사용자가 TensorFlow/Keras 모델 코드와 데이터를 넣는 기본 샘플",
    },
}

IGNORED_NAMES = {
    ".DS_Store",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "mlruns",
    "ai_studio",
    "mlflow.db",
}

GENERATED_ROOT_DIRS = {
    "model",
    "saved_model",
}

GENERATED_PATH_PREFIXES = {
    ("artifacts", "ai_studio"),
}

REQUIRED_PROJECT_DIRS = [
    "aiu_custom",
    "local_serving",
    "save_model",
]

IGNORABLE_PROJECT_ROOT_NAMES = {
    ".git",
    ".gitignore",
    ".opencode",
    ".DS_Store",
}


@dataclass
class BootstrapReport:
    project_path: str
    selected_sample: str | None
    sample_source_path: str | None
    target_project_path: str | None
    copy_mode: str
    execute: bool
    project_empty: bool
    copied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


def list_samples() -> list[dict[str, str]]:
    rows = []
    for key, meta in SAMPLES.items():
        source = SAMPLES_DIR / meta["path"]
        rows.append(
            {
                "key": key,
                "label": meta["label"],
                "description": meta["description"],
                "source_path": str(source),
                "available": str(source.exists()).lower(),
                "required_dirs": str(has_required_dirs(source)).lower(),
            }
        )
    return rows


def has_required_dirs(sample: Path) -> bool:
    return all((sample / name).is_dir() for name in REQUIRED_PROJECT_DIRS)


def is_project_empty(project: Path) -> bool:
    if not project.exists():
        return True
    for child in project.iterdir():
        if child.name not in IGNORABLE_PROJECT_ROOT_NAMES:
            return False
    return True


def should_ignore(path: Path) -> bool:
    parts = path.parts
    if any(part in IGNORED_NAMES for part in parts):
        return True
    if parts and parts[0] in GENERATED_ROOT_DIRS:
        return True
    return any(parts[: len(prefix)] == prefix for prefix in GENERATED_PATH_PREFIXES)


def iter_sample_files(sample: Path, skip_run_model: bool = False):
    for path in sample.rglob("*"):
        relative = path.relative_to(sample)
        if skip_run_model and relative == Path("run_model.py"):
            continue
        if should_ignore(relative):
            continue
        yield path


def copy_sample(sample: Path, project: Path, force: bool, execute: bool, copy_mode: str) -> tuple[Path, list[str], list[str]]:
    target_root = project / sample.name if copy_mode == "folder" else project
    copied: list[str] = []
    skipped: list[str] = []
    skip_run_model = (project / "runtest.py").exists() or (target_root / "runtest.py").exists()

    if target_root.exists() and copy_mode == "folder" and not force:
        raise FileExistsError(f"target_sample_folder_exists:{target_root}")
    if target_root.exists() and copy_mode == "folder" and force and execute:
        shutil.rmtree(target_root)

    for source in iter_sample_files(sample, skip_run_model=skip_run_model):
        relative = source.relative_to(sample)
        target = target_root / relative
        display_relative = Path(sample.name) / relative if copy_mode == "folder" else relative

        if source.is_dir():
            if execute:
                target.mkdir(parents=True, exist_ok=True)
            copied.append(str(display_relative) + "/")
            continue

        if target.exists() and not force:
            skipped.append(str(display_relative))
            continue

        if execute:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        copied.append(str(display_relative))

    for name in REQUIRED_PROJECT_DIRS:
        target = target_root / name
        display_relative = Path(sample.name) / name if copy_mode == "folder" else Path(name)
        if execute:
            target.mkdir(parents=True, exist_ok=True)
        entry = f"{display_relative}/"
        if entry not in copied:
            copied.append(entry)

    return target_root, copied, skipped


def build_next_steps(sample_key: str, target_project_path: Path, has_runtest: bool) -> list[str]:
    entrypoint = "runtest.py" if has_runtest else "run_model.py"
    return [
        f"1. 환경 검증: python .opencode/scripts/check_environment.py --project {target_project_path}",
        f"2. 선택한 샘플 폴더로 이동한다: {target_project_path}",
        f"3. 환경 변수 입력: {entrypoint}의 MLflow/AI Studio 설정 블록에 필수 값 5개를 직접 입력한다.",
        f"4. 환경 변수 export: {entrypoint} 실행 시 설정 블록 값을 MLFLOW_* 환경변수로 export한다.",
        f"5. 해당 폴더에 사용자 모델 코드, 데이터, requirements.txt, {entrypoint}를 추가하거나 확인한다.",
        f"6. 로컬 학습/모델 실행: python {entrypoint}",
        "7. ai_studio/model_info.json 또는 MLflow artifact 생성 여부를 확인한다.",
        "8. local_serving/ 또는 aiu_custom/predict.py 기준으로 추론 테스트를 수행한다.",
        "9. MLflow UI에서 traces, chat-sessions, prompts, judges, datasets 기록을 확인한다.",
        f"선택 샘플: {sample_key}",
    ]


def main():
    parser = argparse.ArgumentParser(description="Bootstrap one bundled offline model sample folder into a workspace.")
    parser.add_argument("--project", default=".", help="target workspace root")
    parser.add_argument("--sample", choices=sorted(SAMPLES), help="sample key: sklearn, pytorch, tensorflow")
    parser.add_argument("--copy-mode", choices=["folder", "root"], default="folder", help="copy sample as a folder by default; use root to copy contents directly")
    parser.add_argument("--list", action="store_true", help="list selectable samples")
    parser.add_argument("--execute", action="store_true", help="copy files into the workspace")
    parser.add_argument("--force", action="store_true", help="allow overwriting existing files")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    if args.list:
        rows = list_samples()
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for row in rows:
                print(f"{row['key']}: {row['label']} - {row['description']}")
                print(f"  source: {row['source_path']}")
                print(f"  available: {row['available']}")
        return

    if not args.sample:
        raise ValueError("--sample is required unless --list is used")

    project = Path(args.project).expanduser().resolve()
    sample_meta = SAMPLES[args.sample]
    sample_source = SAMPLES_DIR / sample_meta["path"]
    failures: list[str] = []
    copied: list[str] = []
    skipped: list[str] = []
    target_project_path: Path | None = None

    if not sample_source.exists():
        failures.append(f"sample_not_found:{sample_source}")
    elif not has_required_dirs(sample_source):
        failures.append(f"sample_missing_required_dirs:{','.join(REQUIRED_PROJECT_DIRS)}")

    project_empty = is_project_empty(project)
    if project.exists() and not project.is_dir():
        failures.append(f"project_is_not_directory:{project}")
    if not project_empty and not args.force and args.copy_mode == "root":
        failures.append("project_not_empty")

    if not failures:
        if args.execute:
            project.mkdir(parents=True, exist_ok=True)
        try:
            target_project_path, copied, skipped = copy_sample(
                sample_source,
                project,
                force=args.force,
                execute=args.execute,
                copy_mode=args.copy_mode,
            )
        except Exception as exc:
            failures.append(str(exc))

    report = BootstrapReport(
        project_path=str(project),
        selected_sample=args.sample,
        sample_source_path=str(sample_source),
        target_project_path=str(target_project_path) if target_project_path else None,
        copy_mode=args.copy_mode,
        execute=args.execute,
        project_empty=project_empty,
        copied=copied,
        skipped=skipped,
        failures=failures,
        next_steps=build_next_steps(
            args.sample,
            target_project_path,
            (project / "runtest.py").exists() or (target_project_path / "runtest.py").exists(),
        )
        if not failures and target_project_path
        else [],
    )

    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print(f"Project: {report.project_path}")
        print(f"Selected sample: {report.selected_sample}")
        print(f"Sample source: {report.sample_source_path}")
        print(f"Target project path: {report.target_project_path or 'not prepared'}")
        print(f"Copy mode: {report.copy_mode}")
        print(f"Project empty: {report.project_empty}")
        print(f"Execute: {report.execute}")
        print(f"Copied entries: {len(report.copied)}")
        if report.skipped:
            print("Skipped existing files:")
            for item in report.skipped:
                print(f"- {item}")
        if report.failures:
            print("Failures:")
            for failure in report.failures:
                print(f"- {failure}")
        if report.next_steps:
            print("Next steps:")
            for step in report.next_steps:
                print(f"- {step}")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
