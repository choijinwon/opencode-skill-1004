import argparse
import importlib.util
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


DATA_MODEL_SUFFIXES = {".pkl", ".joblib", ".pt", ".pth", ".onnx", ".h5", ".keras", ".safetensors", ".bst", ".ubj"}
MODEL_SCAN_SKIP_DIRS = {
    ".git",
    ".opencode",
    ".venv",
    "__pycache__",
    "ai_studio",
    "aiu_studio",
    "node_modules",
    "venv",
}


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


@dataclass
class InferenceReport:
    project_path: str
    model_path: str | None
    input_example_path: str | None
    result_path: str | None
    mode: str
    output_type: str | None
    json_serializable: bool
    executed: bool
    failures: list[str] = field(default_factory=list)
    output_preview: str | None = None


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def find_input_example(project: Path) -> Path | None:
    for name in [
        "input_example.json",
        "sample_input.json",
        "example.json",
    ]:
        candidate = project / name
        if candidate.exists():
            return candidate
    return None


def find_model_path_from_generated_entrypoint(project: Path) -> Path | None:
    for entrypoint in [project / "runtest_2.py"]:
        if not entrypoint.exists():
            continue
        text = entrypoint.read_text(encoding="utf-8", errors="ignore")
        patterns = [
            r"SOURCE_MODEL_PATH\s*=\s*PROJECT_DIR\s*/\s*['\"]([^'\"]+)['\"]",
            r"MODEL_PATH\s*=\s*PROJECT_DIR\s*/\s*['\"]([^'\"]+)['\"]",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            candidate = (project / match.group(1)).resolve()
            if candidate.exists():
                return candidate
    return None


def find_model_path(project: Path) -> Path | None:
    selected_model = find_model_path_from_generated_entrypoint(project)
    if selected_model is not None:
        return selected_model
    for root, dirs, files in os.walk(project):
        root_path = Path(root)
        try:
            relative_parts = root_path.relative_to(project).parts
        except ValueError:
            dirs[:] = []
            continue
        if any(part in MODEL_SCAN_SKIP_DIRS for part in relative_parts):
            dirs[:] = []
            continue
        dirs[:] = [dirname for dirname in dirs if dirname not in MODEL_SCAN_SKIP_DIRS]
        for filename in sorted(files):
            path = root_path / filename
            if path.suffix.lower() in DATA_MODEL_SUFFIXES:
                return path
    for name in ["aiu_studio", "ai_studio", "saved_model", "model", "artifacts"]:
        candidate = project / name
        if candidate.exists():
            return candidate
    if (project / "MLmodel").exists():
        return project
    return None


def jsonable(value) -> bool:
    try:
        json.dumps(value, ensure_ascii=False, default=str)
        return True
    except TypeError:
        return False


def preview(value) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text[:1000]


def inference_result_path(project: Path) -> Path:
    return project / "inference_result.json"


def run_pyfunc(model_path: Path, payload):
    import mlflow.pyfunc

    model = mlflow.pyfunc.load_model(str(model_path))
    return model.predict(payload)


def run_aiu_custom(project: Path, payload):
    wrapper_path = project / "aiu_custom" / "model_wrapper.py"
    if not wrapper_path.exists():
        wrapper_path = project / "aiu_custom" / "predict.py"
    if not wrapper_path.exists():
        raise FileNotFoundError("missing_inference_entrypoint: aiu_custom wrapper not found")

    spec = importlib.util.spec_from_file_location("aiu_custom_model_wrapper", wrapper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load wrapper module: {wrapper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    wrapper = module.ModelWrapper()
    return wrapper.predict(None, payload)


def main():
    parser = argparse.ArgumentParser(description="Test local model inference with input_example.json.")
    parser.add_argument("--project", default=".", help="model project folder")
    parser.add_argument("--model-path", help="explicit model path")
    parser.add_argument("--input-example", help="explicit input example JSON path")
    parser.add_argument("--mode", choices=["auto", "pyfunc", "aiu-custom"], default="auto")
    parser.add_argument("--execute", action="store_true", help="actually load model and run predict")
    parser.add_argument("--output", help="optional result JSON file path; no result file is written unless this is set")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    project = resolve_workspace_project(args.project)
    model_path = Path(args.model_path).expanduser().resolve() if args.model_path else find_model_path(project)
    input_path = Path(args.input_example).expanduser().resolve() if args.input_example else find_input_example(project)
    failures: list[str] = []
    result = None
    output_type = None
    serializable = False

    if input_path is None:
        failures.append("missing_input_example")
    if model_path is None and args.mode in {"auto", "pyfunc"}:
        failures.append("model_load_error:model path not found")

    payload = None
    if input_path is not None:
        try:
            payload = load_json(input_path)
        except Exception as exc:
            failures.append(f"schema_error:{exc}")

    mode = args.mode
    if args.execute and not failures:
        try:
            if mode == "auto":
                mode = "pyfunc" if model_path and (model_path / "MLmodel").exists() else "aiu-custom"
            if mode == "pyfunc":
                if model_path is None:
                    raise FileNotFoundError("model_load_error:model path not found")
                result = run_pyfunc(model_path, payload)
            else:
                result = run_aiu_custom(project, payload)
            output_type = type(result).__name__
            serializable = jsonable(result)
            if not serializable:
                failures.append("serialization_error")
        except Exception as exc:
            failures.append(f"predict_error:{exc}")

    output_path = Path(args.output).expanduser().resolve() if args.output else None
    result_path = str(output_path) if output_path else None
    report = InferenceReport(
        project_path=str(project),
        model_path=str(model_path) if model_path else None,
        input_example_path=str(input_path) if input_path else None,
        result_path=result_path,
        mode=mode,
        output_type=output_type,
        json_serializable=serializable,
        executed=args.execute,
        failures=failures,
        output_preview=preview(result) if result is not None else None,
    )
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print(f"Project: {report.project_path}")
        print(f"Model path: {report.model_path or 'missing'}")
        print(f"Input example: {report.input_example_path or 'missing'}")
        print(f"Result path: {report.result_path or 'not written'}")
        print(f"Mode: {report.mode}")
        print(f"Executed: {report.executed}")
        print(f"Output type: {report.output_type or 'none'}")
        print(f"JSON serializable: {report.json_serializable}")
        if report.output_preview:
            print(f"Output preview: {report.output_preview}")
        if report.failures:
            print("Failures:")
            for failure in report.failures:
                print(f"- {failure}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
