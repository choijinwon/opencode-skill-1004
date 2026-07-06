#!/usr/bin/env python3
from __future__ import annotations

import argparse, ast, importlib.metadata, importlib.util, json, re, shutil, sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from common.mlflow_settings import AI_STUDIO_ENV_KEYS, default_env_text, parse_env_file
from common.workspace import is_absolute_project_arg

ANALYZE_PROJECT_SCRIPT = ROOT / "scripts" / "01-project-analyze" / "validate_mlflow_project.py"
KIND_BY_SUFFIX = {".pkl": "sklearn_pickle", ".joblib": "sklearn_joblib", ".pt": "pytorch", ".pth": "pytorch", ".ckpt": "pytorch", ".onnx": "onnx", ".h5": "tensorflow_h5", ".keras": "tensorflow_keras", ".safetensors": "safetensors", ".bst": "xgboost_bst", ".ubj": "xgboost_ubj"}
REQS = {"pytorch": ["torch==2.7.1", "torchvision==0.22.1", "torchmetrics==1.7.3"], "onnx": ["onnxruntime==1.22.1"], "tensorflow_keras": ["tensorflow==2.19.0"], "tensorflow_h5": ["tensorflow==2.19.0"], "sklearn_pickle": ["joblib==1.5.1", "scikit-learn==1.7.0"], "sklearn_joblib": ["joblib==1.5.1", "scikit-learn==1.7.0"], "safetensors": ["torch==2.7.1", "safetensors==0.5.3"], "xgboost_bst": ["xgboost==3.0.2"], "xgboost_ubj": ["xgboost==3.0.2"]}
IMPORT_PACKAGE = {"PIL": "pillow", "cv2": "opencv-python-headless", "sklearn": "scikit-learn", "yaml": "pyyaml"}
PINNED = {"kserve": "0.15.0", "mlflow": "3.10.0", "numpy": "1.26.4", "pandas": "2.2.3", "pillow": "11.3.0", "opencv-python-headless": "4.12.0.88", "pyyaml": "6.0.2", "scikit-learn": "1.7.0", "torch": "2.7.1", "torchmetrics": "1.7.3", "torchvision": "0.22.1", "tensorflow": "2.19.0", "onnxruntime": "1.22.1", "xgboost": "3.0.2", "joblib": "1.5.1", "matplotlib": "3.10.3", "safetensors": "0.5.3"}
SAMPLE_BY_KIND = {"pytorch": "pytorch_sample", "sklearn_pickle": "sklearn_sample", "sklearn_joblib": "sklearn_sample", "tensorflow_keras": "tensorflow_sample", "tensorflow_h5": "tensorflow_sample", "tensorflow_saved_model": "tensorflow_sample"}
INPUT_BY_KIND = {
    "onnx": "onnx_input",
    "pytorch": "pytorch_input",
    "safetensors": "pytorch_input",
    "sklearn_pickle": "sklearn_input",
    "sklearn_joblib": "sklearn_input",
    "tensorflow_keras": "tensorflow_input",
    "tensorflow_h5": "tensorflow_input",
    "tensorflow_saved_model": "tensorflow_input",
    "xgboost_bst": "xgboost_input",
    "xgboost_ubj": "xgboost_input",
}


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
    required_requirements: list[str] = field(default_factory=lambda: ["mlflow==3.10.0", "kserve==0.15.0"])
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
    return module.build_report(project, "explicit path", write_check=False)


def resolve_selector(project: Path, selector: str) -> str:
    selector = norm(selector)
    if not selector.isdigit():
        return selector
    report = analyze(project)
    paths = list(report.selectable_model_paths or report.training_code_paths + report.model_artifact_paths)
    index = int(selector)
    return norm(paths[index - 1]) if 1 <= index <= len(paths) else selector


def model_kind(path: Path) -> str | None:
    if path.is_dir() and (path / "saved_model.pb").exists():
        return "tensorflow_saved_model"
    if path.suffix.lower() == ".py":
        packages = set(imported_packages(path))
        if {"sklearn", "scikit-learn"} & packages:
            return "sklearn_pickle"
        if {"tensorflow", "keras"} & packages:
            return "tensorflow_keras"
        if "xgboost" in packages:
            return "xgboost_bst"
        if "torch" in packages:
            return "pytorch"
    return KIND_BY_SUFFIX.get(path.suffix.lower())


def work_dir(project: Path, model: Path) -> Path:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", model.stem or model.name).strip("._") or "selected_model"
    candidate = project / name
    marker = candidate / ".selected_model_source"
    source = rel(model, project)
    if not candidate.exists() or read_text(marker).strip() in {"", source}:
        return candidate
    parent = re.sub(r"[^A-Za-z0-9_.-]+", "_", model.parent.name).strip("._")
    return project / (f"{parent}_{name}" if parent else name)


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def unique_requirements(lines: list[str]) -> list[str]:
    out, seen = [], set()
    for line in lines:
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        name = requirement_name(clean)
        if name in seen:
            continue
        seen.add(name)
        out.append(clean)
    return out


def requirement_name(line: str) -> str:
    return re.split(r"[<>=!~ ]", line.strip(), maxsplit=1)[0].lower().replace("_", "-")


def read_requirements(path: Path) -> list[str]:
    if not path.exists():
        return []
    return unique_requirements(path.read_text(encoding="utf-8", errors="ignore").splitlines())


def merge_requirements(existing: list[str], updates: list[str]) -> list[str]:
    merged = {requirement_name(line): line for line in unique_requirements(existing)}
    for line in unique_requirements(updates):
        merged[requirement_name(line)] = line
    return list(merged.values())


def pinned_requirement(package: str) -> str | None:
    name = IMPORT_PACKAGE.get(package, package).replace("_", "-")
    try:
        return f"{name}=={importlib.metadata.version(name)}"
    except importlib.metadata.PackageNotFoundError:
        return f"{name}=={PINNED[name]}" if name in PINNED else None


def imported_packages(path: Path) -> list[str]:
    try:
        tree = ast.parse(read_text(path))
    except SyntaxError:
        return []
    stdlib = getattr(sys, "stdlib_module_names", set())
    found: list[str] = []
    for node in ast.walk(tree):
        name = None
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            name = node.module.split(".", 1)[0]
        if name:
            found.append(name)
    return [item for item in found if item not in stdlib and item not in {"aiu_custom"}]


def import_requirements(project: Path, model: Path) -> list[str]:
    data_root = project / "data"
    try:
        relative = model.resolve().relative_to(data_root.resolve())
    except ValueError:
        return []
    if model.suffix == ".py":
        files = [model]
    else:
        folder = data_root / Path(*relative.parts[:-1])
        files = sorted(folder.glob("*.py"))
    packages = []
    for file_path in files:
        packages.extend(imported_packages(file_path))
    return unique_requirements([req for pkg in packages if (req := pinned_requirement(pkg))])


def json_requirements(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return []
    values = data.get("requirements") or data.get("packages") or data.get("dependencies") or []
    if isinstance(values, dict):
        values = [f"{key}=={value}" if value else str(key) for key, value in values.items()]
    return unique_requirements([str(item) for item in values]) if isinstance(values, list) else []


def data_requirements(project: Path, model: Path) -> list[str]:
    data_root = project / "data"
    try:
        relative = model.resolve().relative_to(data_root.resolve())
    except ValueError:
        return []
    start = len(relative.parts) if model.is_dir() else len(relative.parts) - 1
    dirs = [data_root / Path(*relative.parts[:index]) for index in range(start, -1, -1)]
    for folder in dirs:
        found = read_requirements(folder / "requirements.txt")
        found += json_requirements(folder / "config" / "config.json")
        if found:
            return unique_requirements(found)
    return []


def ensure_env_file(folder: Path) -> Path:
    path = folder / ".env"
    if not path.exists():
        write(path, default_env_text())
        return path
    values = parse_env_file(path)
    missing = [key for key in AI_STUDIO_ENV_KEYS if key not in values]
    if missing:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if text and not text.endswith("\n"):
            text += "\n"
        text += "\n".join(f'{key}=""' for key in missing) + "\n"
        path.write_text(text, encoding="utf-8")
    return path


def ensure_workspace_env(project: Path) -> Path:
    return ensure_env_file(project)


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


def sample_dir(kind: str) -> Path:
    return ROOT / "samples" / SAMPLE_BY_KIND.get(kind, "pytorch_sample")


def copy_if_exists(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return True


def input_schema(kind: str) -> dict:
    return {"name": INPUT_BY_KIND.get(kind, "input"), "shape": [1, 4], "datatype": "FP32"}


def update_input_example(path: Path, kind: str) -> None:
    schema = input_schema(kind)
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="ignore")) if path.exists() else {}
    except json.JSONDecodeError:
        payload = {}
    if isinstance(payload, dict) and isinstance(payload.get("inputs"), list) and payload["inputs"]:
        item = payload["inputs"][0] if isinstance(payload["inputs"][0], dict) else {}
        item.update({key: schema[key] for key in ("name", "datatype")})
        item.setdefault("shape", schema["shape"])
        item.setdefault("data", [[0.0, 0.0, 0.0, 0.0]])
        payload["inputs"][0] = item
    else:
        payload = {"inputs": [{**schema, "data": [[0.0, 0.0, 0.0, 0.0]]}]}
    write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def update_config(path: Path, model: Path, kind: str) -> None:
    config = {}
    if path.exists():
        try:
            config = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            config = {}
    config["data"] = {"input_schema": input_schema(kind)}
    config["model"] = {"path": f"saved_model/{model.name}", "kind": kind}
    write(path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")


def update_runtest(path: Path, work: Path, model: Path, kind: str) -> None:
    text = read_text(path)
    for sample_name in ("pytorch_sample", "sklearn_sample", "tensorflow_sample"):
        text = text.replace(f"{sample_name}_model", f"{work.name}_model").replace(sample_name, work.name)
    constants = (
        f'PROJECT_DIR = Path(__file__).resolve().parent\n'
        f'SELECTED_MODEL_PATH = PROJECT_DIR / "saved_model" / "{model.name}"\n'
        f'MODEL_KIND = "{kind}"\n'
        f'INPUT_EXAMPLE_PATH = PROJECT_DIR / "input_example.json"\n'
        f'CONFIG_PATH = PROJECT_DIR / "config" / "config.json"'
    )
    text = re.sub(r"^PROJECT_DIR\s*=.*$", constants, text, count=1, flags=re.MULTILINE)
    text = re.sub(r'"sample":\s*"[^"]+",', '"model_kind": MODEL_KIND,\n            "selected_model": SELECTED_MODEL_PATH.name,', text)
    text = re.sub(r'mlflow\.log_param\("sample",\s*"[^"]+"\)', 'mlflow.log_param("model_kind", MODEL_KIND)\n            mlflow.log_param("selected_model", SELECTED_MODEL_PATH.name)', text)
    artifact_block = '''mlflow.log_artifact(str(summary_path), artifact_path="ai_studio/code")
            if SELECTED_MODEL_PATH.exists():
                mlflow.log_artifact(str(SELECTED_MODEL_PATH), artifact_path="saved_model")
            if CONFIG_PATH.exists():
                mlflow.log_artifact(str(CONFIG_PATH), artifact_path="config")
            if INPUT_EXAMPLE_PATH.exists():
                mlflow.log_artifact(str(INPUT_EXAMPLE_PATH), artifact_path=".")'''
    text = text.replace('mlflow.log_artifact(str(summary_path), artifact_path="ai_studio/code")', artifact_block)
    env_defaults = {
        "mlflow_tracking_uri": 'os.getenv("MLFLOW_TRACKING_URI", "")',
        "mlflow_tracking_username": 'os.getenv("MLFLOW_TRACKING_USERNAME", "")',
        "mlflow_tracking_password": 'os.getenv("MLFLOW_TRACKING_PASSWORD", "")',
        "mlflow_experiment_name": f'os.getenv("MLFLOW_EXPERIMENT_NAME", "{work.name}")',
        "mlflow_register_model_name": f'os.getenv("MLFLOW_REGISTER_MODEL_NAME", "{work.name}_model")',
    }
    for key, value in env_defaults.items():
        text = re.sub(rf'^{key}\s*=\s*".*"$', f"{key} = {value}", text, flags=re.MULTILINE)
    write(path, text)


def write_wrapper_files(work: Path, model: Path, kind: str) -> None:
    write(work / "aiu_custom" / "model.py", "from .predict import ModelWrapper\n")
    write(work / "aiu_custom" / "predict.py", f'''from pathlib import Path
import mlflow.pyfunc
MODEL_PATH = Path(__file__).resolve().parents[1] / "saved_model" / "{model.name}"
MODEL_KIND = "{kind}"
class ModelWrapper(mlflow.pyfunc.PythonModel):
    def predict(self, context, model_input, params=None):
        return model_input
''')


def runtime_files(work: Path, model: Path, kind: str, requirements: list[str]):
    sample = sample_dir(kind)
    sample_requirements = read_requirements(sample / "requirements.txt")
    base_requirements = [pinned_requirement("mlflow") or "mlflow==3.10.0", pinned_requirement("kserve") or "kserve==0.15.0"]
    write(work / "requirements.txt", "\n".join(unique_requirements([*base_requirements, *sample_requirements, *requirements])) + "\n")
    copy_if_exists(sample / "input_example.json", work / "input_example.json")
    update_input_example(work / "input_example.json", kind)
    copy_if_exists(sample / "inferencetest.py", work / "inferencetest.py")
    if not copy_if_exists(sample / "runtest.py", work / "runtest_2.py"):
        write(work / "runtest_2.py", 'print("runtest_2.py placeholder")\n')
    update_runtest(work / "runtest_2.py", work, model, kind)
    copy_if_exists(sample / "config" / "config.json", work / "config" / "config.json")
    update_config(work / "config" / "config.json", model, kind)
    write_wrapper_files(work, model, kind)
    write(work / "local_serving" / "serve.py", 'print("local serving placeholder")\n')


def build_report(project: Path, selector: str, execute: bool) -> SelectedReport:
    project = project.resolve()
    analysis = analyze(project)
    model_paths = [project / path for path in analysis.model_artifact_paths]
    selector = resolve_selector(project, selector)
    model = (project / selector).resolve()
    kind = model_kind(model) if model.exists() else None
    work = work_dir(project, model) if model.exists() else project
    requirements = unique_requirements([*(data_requirements(project, model) or REQS.get(kind or "", [])), *import_requirements(project, model)])
    report = SelectedReport(str(project), str(project / "data"), analysis.model_artifact_paths, analysis.training_code_paths, selected_model_path=rel(model, project) if model.exists() else None, model_kind=kind, execute=execute, work_project_path=rel(work, project) if model.exists() else None, requested_model_path=selector, locked_model_path=rel(model, project) if model.exists() else None, additional_requirements=requirements, env_check_command="python ../.opencode/scripts/03-environment-check/check_environment.py --project . --entrypoint runtest_2.py")
    if not model.exists():
        report.failures.append(f"model_path_not_found:{selector}")
    elif not kind:
        report.failures.append("unsupported_model_kind")
    elif execute:
        work.mkdir(parents=True, exist_ok=True)
        env_file = ensure_workspace_env(project)
        copy_model(model, work)
        runtime_files(work, model, kind, requirements)
        write(work / ".selected_model_source", rel(model, project) + "\n")
        report.prepared_paths += [rel(env_file, project), rel(work / "requirements.txt", project), "selected_model selected", "runtest_2.py", "aiu_custom/model.py", "aiu_custom/predict.py", "config/config.json transformed for selected model", "input_example.json transformed for selected model", f"saved_model/{model.name}"]
    else:
        report.skipped += [f"{rel(work, project)}:dry_run", "runtime files:dry_run"]
    report.next_steps.append("3번 환경 검증 후 4번 템플릿 변환 확인으로 진행하세요.")
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
    print("환경 파일: .env (워크스페이스 루트 생성/확인)")
    print("패키지 파일: <작업 폴더>/requirements.txt (갱신/확인)")
    print_markdown_table(
        ["Status", "Step", "Action"],
        [
            ["대기", "3", "환경 검증"],
            ["대기", "4", "템플릿 변환 확인"],
            ["대기", "5", "원격 MLflow 등록 실행"],
            ["대기", "6", "추론 테스트"],
            ["대기", "7", "오류 재실행"],
        ],
    )


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
    if is_absolute_project_arg(args.project):
        parser.error("--project는 상대경로만 가능합니다. 예: --project . 또는 --project <선택모델작업폴더>")
    project = Path(args.project)
    ensure_env_file(project)
    report = build_report(project, raw_model, not args.dry_run)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2)) if args.json else print_selected(report)
    return 1 if report.failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1)
