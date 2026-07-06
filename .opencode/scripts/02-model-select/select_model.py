#!/usr/bin/env python3
from __future__ import annotations

import argparse, importlib.util, json, re, shutil, sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANALYZE_PROJECT_SCRIPT = ROOT / "scripts" / "01-project-analyze" / "validate_mlflow_project.py"
KIND_BY_SUFFIX = {".pkl": "sklearn_pickle", ".joblib": "sklearn_joblib", ".pt": "pytorch", ".pth": "pytorch", ".ckpt": "pytorch", ".onnx": "onnx", ".h5": "tensorflow_h5", ".keras": "tensorflow_keras", ".safetensors": "safetensors", ".bst": "xgboost_bst", ".ubj": "xgboost_ubj"}
REQS = {"pytorch": ["torch==2.7.1", "torchvision==0.22.1", "torchmetrics==1.7.3"], "onnx": ["onnxruntime==1.22.1"], "tensorflow_keras": ["tensorflow==2.19.0"], "tensorflow_h5": ["tensorflow==2.19.0"], "sklearn_pickle": ["joblib==1.5.1", "scikit-learn==1.7.0"], "sklearn_joblib": ["joblib==1.5.1", "scikit-learn==1.7.0"], "safetensors": ["torch==2.7.1", "safetensors==0.5.3"], "xgboost_bst": ["xgboost==3.0.2"], "xgboost_ubj": ["xgboost==3.0.2"]}


@dataclass
class SelectedReport:
    project_path: str; data_root: str
    model_artifact_paths: list[str] = field(default_factory=list)
    training_code_paths: list[str] = field(default_factory=list)
    data_file_paths: list[str] = field(default_factory=list)
    entrypoint_paths: list[str] = field(default_factory=list)
    selected_model_path: str | None = None
    model_kind: str | None = None
    reference_entrypoint: str | None = None
    generated_entrypoint: str = "runtest_2.py"
    generated_inference_test: str = "inferencetest.py"
    execute: bool = False
    work_project_path: str | None = None
    requested_model_path: str | None = None
    model_selection_locked: bool = False
    locked_model_path: str | None = None
    required_requirements: list[str] = field(default_factory=lambda: ["mlflow", "kserve==0.15.0"])
    additional_requirements: list[str] = field(default_factory=list)
    image_model_recommendations: list[str] = field(default_factory=list)
    prepared_paths: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    selected_python_version: str | None = None
    env_check_status: str | None = None
    env_check_summary: str | None = None
    env_check_command: str | None = None
    env_check_requirements: list[str] = field(default_factory=list)
    env_check_import_packages: list[str] = field(default_factory=list)
    env_check_dry_run_status: str | None = None
    env_check_dry_run_summary: str | None = None


def norm(value: str) -> str:
    return re.sub(r"/+", "/", value.strip().strip("\"'").replace("\\", "/").replace("＼", "/").replace("￦", "/").replace("₩", "/")).strip("/")


def rel(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_analyze_module():
    spec = importlib.util.spec_from_file_location("validate_mlflow_project_impl", ANALYZE_PROJECT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load analyze script: {ANALYZE_PROJECT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def analyze(project: Path):
    module = load_analyze_module()
    selected, reason = module.select_project(str(project))
    return module.build_report(selected, reason, write_check=False)


def resolve_selector(project: Path, selector: str) -> str:
    selector = norm(selector)
    if not selector.isdigit():
        return selector
    report = analyze(project)
    paths = list(report.selectable_model_paths or report.training_code_paths + report.model_artifact_paths)
    index = int(selector)
    return norm(paths[index - 1]) if 1 <= index <= len(paths) else selector


def model_kind(path: Path) -> str | None:
    return "tensorflow_saved_model" if path.is_dir() and (path / "saved_model.pb").exists() else KIND_BY_SUFFIX.get(path.suffix.lower())


def work_dir(project: Path, model: Path) -> Path:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", model.stem or model.name).strip("._") or "selected_model"
    return project / name


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_model(src: Path, work: Path):
    target_dir = work / "saved_model"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / src.name
    if src.is_dir():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src, target)
    else:
        shutil.copy2(src, target)


def runtime_files(work: Path, model: Path, kind: str):
    write(work / "requirements.txt", "\n".join(["mlflow", "kserve==0.15.0", *REQS.get(kind, [])]) + "\n")
    write(work / "input_example.json", json.dumps({"inputs": [{"name": "input", "shape": [1, 4], "datatype": "FP32", "data": [[0, 0, 0, 0]]}]}, ensure_ascii=False, indent=2) + "\n")
    write(work / "config" / "config.json", json.dumps({"data": {"input_schema": {"name": "input", "shape": [1, 4], "datatype": "FP32"}}, "model": {"path": f"saved_model/{model.name}", "kind": kind}}, ensure_ascii=False, indent=2) + "\n")
    write(work / "aiu_custom" / "model.py", "from .predict import ModelWrapper\n")
    write(work / "aiu_custom" / "predict.py", f'''from pathlib import Path
import mlflow.pyfunc
MODEL_PATH = Path(__file__).resolve().parents[1] / "saved_model" / "{model.name}"
MODEL_KIND = "{kind}"
class ModelWrapper(mlflow.pyfunc.PythonModel):
    def predict(self, context, model_input, params=None):
        return model_input
''')
    write(work / "runtest_2.py", '''import os
from pathlib import Path
import mlflow
from aiu_custom.model import ModelWrapper
ROOT = Path(__file__).resolve().parent
def main():
    uri = os.getenv("MLFLOW_TRACKING_URI", "")
    if not uri:
        raise SystemExit("MLFLOW_TRACKING_URI is required")
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT_NAME") or ROOT.name)
    with mlflow.start_run():
        mlflow.log_artifacts(str(ROOT / "saved_model"), artifact_path="saved_model")
        mlflow.log_artifact(str(ROOT / "config" / "config.json"), artifact_path="config")
        mlflow.log_artifact(str(ROOT / "input_example.json"))
        mlflow.pyfunc.log_model(artifact_path="ai_studio", python_model=ModelWrapper(), registered_model_name=os.getenv("MLFLOW_REGISTER_MODEL_NAME") or f"{ROOT.name}_model")
if __name__ == "__main__":
    main()
''')
    write(work / "inferencetest.py", 'req_url=""\nprint("req_url에 :predict 경로를 입력하세요." if not req_url or ":predict" not in req_url else req_url)\n')
    write(work / "local_serving" / "serve.py", 'print("local serving placeholder")\n')


def build_report(project: Path, selector: str, execute: bool) -> SelectedReport:
    project = project.resolve()
    analysis = analyze(project)
    model_paths = [project / path for path in analysis.model_artifact_paths]
    selector = resolve_selector(project, selector)
    model = (project / selector).resolve()
    kind = model_kind(model) if model.exists() else None
    work = work_dir(project, model) if model.exists() else project
    report = SelectedReport(str(project), str(project / "data"), analysis.model_artifact_paths, analysis.training_code_paths, selected_model_path=rel(model, project) if model.exists() else None, model_kind=kind, execute=execute, work_project_path=rel(work, project) if model.exists() else None, requested_model_path=selector, locked_model_path=rel(model, project) if model.exists() else None, additional_requirements=REQS.get(kind or "", []), env_check_command="python ../.opencode/scripts/03-environment-check/check_environment.py --project . --entrypoint runtest_2.py")
    if not model.exists():
        report.failures.append(f"model_path_not_found:{selector}")
    elif not kind:
        report.failures.append("unsupported_model_kind")
    elif execute:
        work.mkdir(parents=True, exist_ok=True)
        copy_model(model, work)
        runtime_files(work, model, kind)
        report.prepared_paths += ["selected_model selected", "runtest_2.py", "aiu_custom/model.py", "aiu_custom/predict.py", "config/config.json transformed for selected model", "input_example.json transformed for selected model", f"saved_model/{model.name}"]
    else:
        report.skipped += [f"{rel(work, project)}:dry_run", "runtime files:dry_run"]
    report.next_steps.append("3번 환경 검증 후 5번 원격 MLflow 등록 실행으로 진행하세요.")
    return report


def print_markdown_table(headers: list[str], rows: list[list[str]]) -> None:
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        print("| " + " | ".join(str(value) for value in row) + " |")


def print_selected(report: SelectedReport) -> None:
    print(f"선택 모델: {report.selected_model_path or 'missing'}")
    print(f"MODEL_KIND: {report.model_kind or 'missing'}")
    print(f"실행 파일: {(report.work_project_path + '/') if report.work_project_path else ''}{report.generated_entrypoint}")
    print(f"작업 폴더: {report.work_project_path or '.'}")
    print_markdown_table(["Status", "Step", "Action"], [["대기", "3", "환경 검증"], ["대기", "5", "원격 MLflow 등록 실행"], ["대기", "6", "추론 테스트"], ["대기", "7", "오류 재실행"]])


def normalize_argv(argv: list[str]) -> list[str]:
    out, i = [], 0
    while i < len(argv):
        arg = argv[i]
        out.append(f"--{arg}" if arg in {"model", "project"} else arg)
        i += 1
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 2: select and prepare model runtime files.")
    parser.add_argument("model_arg", nargs="?")
    parser.add_argument("--project", default=".")
    parser.add_argument("--model")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(normalize_argv(sys.argv[1:]))
    raw_model = args.model or args.model_arg
    if not raw_model:
        parser.error("--model <번호|경로>가 필요합니다.")
    report = build_report(Path(args.project), raw_model, not args.dry_run)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2)) if args.json else print_selected(report)
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
