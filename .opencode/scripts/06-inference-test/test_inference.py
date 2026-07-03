import argparse
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


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


def find_model_path_from_config(project: Path) -> tuple[Path | None, str | None]:
    config_path = project / "config" / "config.json"
    if not config_path.is_file():
        return None, "selected_model_config_missing"
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"selected_model_config_parse_error:{exc.lineno}"
    model = payload.get("model") if isinstance(payload, dict) else None
    if not isinstance(model, dict):
        return None, "selected_model_config_model_missing"
    source_path = model.get("model_relative_path") or model.get("runtime_model_path") or model.get("source_path") or model.get("relative_path")
    if not isinstance(source_path, str) or not source_path.strip():
        return None, "selected_model_config_source_path_missing"
    candidate = Path(source_path)
    if not candidate.is_absolute():
        candidate = project / candidate
    candidate = candidate.resolve()
    if not candidate.exists():
        return None, f"selected_model_config_not_found:{source_path}"
    return candidate, None


def find_model_path(project: Path) -> tuple[Path | None, str | None]:
    selected_model, config_error = find_model_path_from_config(project)
    if selected_model is not None:
        return selected_model, None
    return None, config_error


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
    if args.model_path:
        model_path = Path(args.model_path).expanduser().resolve()
        model_path_error = None
    else:
        model_path, model_path_error = find_model_path(project)
    input_path = Path(args.input_example).expanduser().resolve() if args.input_example else find_input_example(project)
    failures: list[str] = []
    result = None
    output_type = None
    serializable = False

    if input_path is None:
        failures.append("missing_input_example")
    if model_path is None and args.mode in {"auto", "pyfunc"}:
        failures.append(model_path_error or "model_load_error:model path not found")

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
        print("Project: .")
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
