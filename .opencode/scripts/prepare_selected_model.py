#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


SUPPORTED_MODEL_KINDS = {
    ".pkl": "sklearn_pickle",
    ".joblib": "sklearn_joblib",
    ".pt": "pytorch",
    ".pth": "pytorch",
    ".onnx": "onnx",
    ".keras": "tensorflow_keras",
    ".h5": "tensorflow_h5",
    ".safetensors": "safetensors",
    ".bst": "xgboost_bst",
    ".ubj": "xgboost_ubj",
}

REFERENCE_ENTRYPOINTS = [
    "aiu_studio/runtest.py",
    "aiu_studio/run_test.py",
    "aui_studio/runtest.py",
    "aui_studio/run_test.py",
    "runtest.py",
    "run_test.py",
]
ROOT = Path(__file__).resolve().parents[1]
AIU_STUDIO_DIR_NAME = "aiu_studio"
AIU_STUDIO_SAMPLE_DIR_NAME = "aiu_studio"
AIU_STUDIO_SAMPLE_DIR = ROOT / "samples" / AIU_STUDIO_SAMPLE_DIR_NAME
MODEL_SCAN_SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".opencode",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "ai_studio",
    "aiu_studio",
    "aui_studio",
    "build",
    "dist",
    "env",
    "mlruns",
    "node_modules",
    "venv",
}


@dataclass
class PreparedModelReport:
    project_path: str
    data_root: str
    model_artifact_paths: list[str]
    selected_model_path: str | None
    model_kind: str | None
    reference_entrypoint: str | None
    generated_entrypoint: str
    execute: bool
    copied_template_dirs: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


def rel(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def model_kind(path: Path) -> str | None:
    return SUPPORTED_MODEL_KINDS.get(path.suffix.lower())


def scan_model_artifacts(project: Path) -> list[Path]:
    found = []
    for path in project.rglob("*"):
        try:
            relative_parts = path.relative_to(project).parts
        except ValueError:
            continue
        if any(part in MODEL_SCAN_SKIP_DIRS for part in relative_parts):
            continue
        if path.is_file() and model_kind(path):
            found.append(path)
    return sorted(set(found))


def resolve_model_selection(project: Path, models: list[Path], raw: str | None) -> tuple[Path | None, str | None]:
    if not raw:
        return None, "model_selection_required"
    value = raw.strip()
    if value.isdigit():
        index = int(value)
        if 1 <= index <= len(models):
            return models[index - 1], None
        return None, f"model_index_out_of_range:{value}"

    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = project / candidate
    candidate = candidate.resolve()
    if not candidate.exists() or not candidate.is_file():
        return None, f"model_path_not_found:{value}"
    return candidate, None


def ensure_under_project(project: Path, model_path: Path) -> bool:
    try:
        model_path.resolve().relative_to(project.resolve())
        return True
    except ValueError:
        return False


def find_reference_entrypoint(project: Path) -> Path | None:
    for name in REFERENCE_ENTRYPOINTS:
        candidate = project / name
        if candidate.is_file():
            return candidate
    return None


def safe_mlflow_name(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_]+", "_", value).strip("_").lower()
    return normalized or fallback


def default_mlflow_names(project: Path) -> tuple[str, str]:
    experiment_name = safe_mlflow_name(project.name, "aiu_studio")
    return experiment_name, f"{experiment_name}_model"


def copy_aiu_studio_folder(project: Path, execute: bool) -> tuple[list[str], list[str], list[str]]:
    copied: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    target = project / AIU_STUDIO_DIR_NAME
    if target.exists():
        skipped.append(AIU_STUDIO_DIR_NAME + "/")
        return copied, skipped, failures
    if not AIU_STUDIO_SAMPLE_DIR.is_dir():
        failures.append(f"aiu_studio_folder_missing:{AIU_STUDIO_SAMPLE_DIR}")
        return copied, skipped, failures
    if execute:
        shutil.copytree(AIU_STUDIO_SAMPLE_DIR, target)
    copied.append(AIU_STUDIO_DIR_NAME + "/")
    return copied, skipped, failures


def generated_runtest_text(project: Path, selected_model: Path, kind: str, reference: Path) -> str:
    selected_relative = rel(selected_model, project)
    reference_relative = rel(reference, project)
    default_experiment_name, default_register_model_name = default_mlflow_names(project)
    return f'''#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_MODEL_PATH = PROJECT_DIR / "{selected_relative}"
DATA_MODEL_PATH = SOURCE_MODEL_PATH
MODEL_PATH = SOURCE_MODEL_PATH
MODEL_KIND = "{kind}"
REFERENCE_ENTRYPOINT = PROJECT_DIR / "{reference_relative}"
AI_STUDIO_DIR = PROJECT_DIR / "aiu_studio"

# MLflow/AI Studio settings
# tracking URL, username, password는 사용자가 직접 입력합니다.
# experiment/model name은 프로젝트명 기준으로 자동 생성됩니다.
# password 값은 출력하지 않습니다.
mlflow_tracking_url = ""
mlflow_tracking_username = ""
mlflow_tracking_password = ""
mlflow_experiment_name = "{default_experiment_name}"
mlflow_register_model_name = "{default_register_model_name}"


def ensure_ai_studio_dirs() -> None:
    for relative in ["code", "metrics", "tracking"]:
        (AI_STUDIO_DIR / relative).mkdir(parents=True, exist_ok=True)


def export_mlflow_env() -> None:
    import os

    if mlflow_tracking_url.lower().startswith("https://"):
        raise ValueError("ssl_not_allowed: use http:// or file:// for mlflow_tracking_url")

    mapping = {{
        "MLFLOW_TRACKING_URI": mlflow_tracking_url,
        "MLFLOW_TRACKING_USERNAME": mlflow_tracking_username,
        "MLFLOW_TRACKING_PASSWORD": mlflow_tracking_password,
        "MLFLOW_EXPERIMENT_NAME": mlflow_experiment_name,
        "MLFLOW_REGISTER_MODEL_NAME": mlflow_register_model_name,
    }}
    for name, value in mapping.items():
        if value:
            os.environ[name] = value


def load_selected_model():
    if MODEL_KIND in {{"sklearn_pickle", "sklearn_joblib"}}:
        import joblib

        return joblib.load(MODEL_PATH)
    if MODEL_KIND == "pytorch":
        import torch

        return torch.load(MODEL_PATH, map_location="cpu")
    if MODEL_KIND == "onnx":
        import onnxruntime as ort

        return ort.InferenceSession(str(MODEL_PATH))
    if MODEL_KIND in {{"tensorflow_keras", "tensorflow_h5"}}:
        import tensorflow as tf

        return tf.keras.models.load_model(MODEL_PATH)
    if MODEL_KIND == "safetensors":
        from safetensors.torch import load_file

        return load_file(str(MODEL_PATH))
    if MODEL_KIND in {{"xgboost_bst", "xgboost_ubj"}}:
        import xgboost as xgb

        booster = xgb.Booster()
        booster.load_model(str(MODEL_PATH))
        return booster
    raise ValueError(f"unsupported MODEL_KIND: {{MODEL_KIND}}")


def write_selection_summary() -> None:
    ensure_ai_studio_dirs()
    payload = {{
        "model_path": str(MODEL_PATH),
        "source_model_path": str(SOURCE_MODEL_PATH),
        "model_kind": MODEL_KIND,
        "reference_entrypoint": str(REFERENCE_ENTRYPOINT),
        "note": "Model file remains in the project source path and is not copied into aiu_studio/.",
    }}
    (AI_STUDIO_DIR / "code" / "selected_model.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    ensure_ai_studio_dirs()
    export_mlflow_env()
    if not MODEL_PATH.is_file():
        print(f"missing model file: {{MODEL_PATH}}")
        return 1
    write_selection_summary()
    model = load_selected_model()
    print(f"MODEL_PATH={{MODEL_PATH}}")
    print(f"MODEL_KIND={{MODEL_KIND}}")
    print(f"loaded_model_type={{type(model).__name__}}")
    print("secret_status=not_printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def write_runtest_2(project: Path, selected_model: Path, kind: str, reference: Path, execute: bool, force: bool) -> tuple[list[str], list[str], list[str]]:
    target = project / "runtest_2.py"
    changed: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    if target.exists() and not force:
        skipped.append("runtest_2.py")
        if execute:
            failures.append("runtest_2_exists: use --force to overwrite")
        return changed, skipped, failures
    if execute:
        target.write_text(generated_runtest_text(project, selected_model, kind, reference), encoding="utf-8")
    changed.append("runtest_2.py")
    return changed, skipped, failures


def build_report(args: argparse.Namespace) -> PreparedModelReport:
    project = Path(args.project).expanduser().resolve()
    if not project.exists():
        raise FileNotFoundError(f"project folder not found: {project}")

    data_root = project / "data"
    models = scan_model_artifacts(project)
    model_paths = [rel(path, project) for path in models]
    selected_model, selection_error = resolve_model_selection(project, models, args.model)
    selected_kind = model_kind(selected_model) if selected_model else None
    reference = find_reference_entrypoint(project)

    report = PreparedModelReport(
        project_path=str(project),
        data_root=str(data_root),
        model_artifact_paths=model_paths,
        selected_model_path=rel(selected_model, project) if selected_model else None,
        model_kind=selected_kind,
        reference_entrypoint=rel(reference, project) if reference else None,
        generated_entrypoint="runtest_2.py",
        execute=args.execute,
    )

    if not models:
        report.failures.append("model_artifact_paths_empty")
        report.next_steps.append("프로젝트 루트 또는 data/** 아래에 .pkl, .joblib, .pt, .pth, .onnx, .keras, .h5, .safetensors, .bst, .ubj 모델 파일을 넣어주세요.")
    if selection_error:
        report.failures.append(selection_error)
        if models:
            report.next_steps.append("사용할 모델을 번호 또는 경로로 선택하세요. 예: --model 1, --model model.joblib, --model data/torch/model.pt")
    if selected_model and not ensure_under_project(project, selected_model):
        report.failures.append("selected_model_outside_project")
        report.next_steps.append("선택 모델은 <model-project-folder> 아래에 있어야 합니다.")
    if selected_model and selected_kind is None:
        report.failures.append("unsupported_model_suffix")
    if reference is None:
        report.failures.append("reference_entrypoint_missing:runtest.py_or_run_test.py")
        report.next_steps.append("기존 runtest.py 또는 run_test.py를 프로젝트 루트나 aiu_studio/ 아래에 넣어주세요.")

    if report.failures:
        return report

    copied, skipped, copy_failures = copy_aiu_studio_folder(project, args.execute)
    report.copied_template_dirs.extend(copied)
    report.skipped.extend(skipped)
    report.failures.extend(copy_failures)
    if report.failures:
        return report
    changed, write_skipped, write_failures = write_runtest_2(project, selected_model, selected_kind, reference, args.execute, args.force)
    report.copied_template_dirs.extend(changed)
    report.skipped.extend(write_skipped)
    report.failures.extend(write_failures)

    if args.execute and not report.failures:
        report.next_steps.extend(
            [
                "python .opencode/scripts/check_environment.py --project <model-project-folder> --entrypoint runtest_2.py",
                "python runtest_2.py",
                "python .opencode/scripts/test_inference.py --project <model-project-folder>",
                "python .opencode/scripts/verify_mlflow.py --tracking-uri <tracking-uri> --experiment-name <experiment-name>",
            ]
        )
    elif not report.failures:
        report.next_steps.append("검토 후 --execute를 붙여 aiu_studio/ 폴더를 그대로 복사하고 runtest_2.py를 생성하세요.")
    return report


def print_report(report: PreparedModelReport) -> None:
    print(f"Project: {report.project_path}")
    print(f"Data root: {report.data_root}")
    print("model_artifact_paths:")
    if report.model_artifact_paths:
        for index, path in enumerate(report.model_artifact_paths, start=1):
            print(f"{index}. {path}")
    else:
        print("- none")
    print(f"Selected model: {report.selected_model_path or 'missing'}")
    print(f"MODEL_KIND: {report.model_kind or 'missing'}")
    print(f"Reference entrypoint: {report.reference_entrypoint or 'missing'}")
    print(f"Generated entrypoint: {report.generated_entrypoint}")
    print(f"Execute: {report.execute}")
    if report.copied_template_dirs:
        print("Prepared:")
        for item in report.copied_template_dirs:
            print(f"- {item}")
    if report.skipped:
        print("Skipped:")
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Select a project-root or data/** model artifact and generate runtest_2.py without modifying runtest.py.")
    parser.add_argument("--project", default=".", help="model project folder")
    parser.add_argument("--model", help="model index from model_artifact_paths or a project-relative path")
    parser.add_argument("--execute", action="store_true", help="copy aiu_studio/ template folder and create runtest_2.py")
    parser.add_argument("--force", action="store_true", help="overwrite existing runtest_2.py")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    report = build_report(args)
    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print_report(report)
    return 1 if report.failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
