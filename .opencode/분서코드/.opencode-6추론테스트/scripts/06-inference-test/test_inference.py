import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# 분석용 주석
# ---------------------------------------------------------------------------
# 이 파일은 6단계 "추론 테스트"의 실제 핵심 스크립트 복사본입니다.
#
# 여기서 하는 일은 크게 4가지입니다.
# 1) 선택 모델 작업 폴더에서 input_example.json을 찾습니다.
# 2) inferencetest.py 안의 req_url 값을 읽고 :predict URL인지 확인합니다.
# 3) --execute가 있을 때만 원격 추론 서버로 requests.post를 보냅니다.
# 4) 응답 status_code, JSON/text schema, 실패 원인을 report로 정리합니다.
#
# 중요한 원칙:
# - 6번은 사용자가 명시적으로 선택했을 때만 실행합니다.
# - 로컬 모델 로드는 하지 않고, 원격 :predict URL 호출만 검증합니다.
# - predict_2.py 같은 새 추론 파일은 만들지 않고 inferencetest.py를 기준으로 봅니다.

def resolve_workspace_project(raw_project: str) -> Path:
    """
    분석 주석:
    - 단계 맥락: 6단계 추론 테스트: input_example.json과 inferencetest.py를 확인하고 원격 :predict URL 호출을 검증합니다.
    - 함수 역할: 사용자 입력 경로/대상을 실제 워크스페이스 기준 Path 또는 내부 값으로 확정합니다.
    - 입력 기준: 입력값 `raw_project`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 정규화된 Path 또는 None을 반환해 이후 파일 접근 기준으로 사용합니다.
    """
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
    input_example_path: str | None
    inferencetest_path: str | None
    req_url: str | None
    req_url_status: str
    result_path: str | None
    executed: bool
    status_code: int | None = None
    response_schema: str | None = None
    failures: list[str] = field(default_factory=list)
    output_preview: str | None = None


def load_json(path: Path):
    """
    분석 주석:
    - 단계 맥락: 6단계 추론 테스트: input_example.json과 inferencetest.py를 확인하고 원격 :predict URL 호출을 검증합니다.
    - 함수 역할: 외부 파일, JSON, 모듈, 설정 값을 읽어 현재 단계에서 사용할 수 있게 준비합니다.
    - 입력 기준: 입력값 `path`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입은 코드 흐름에서 결정되며, 호출부가 기대하는 값/상태를 돌려줍니다.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def find_input_example(project: Path) -> Path | None:
    """
    분석 주석:
    - 단계 맥락: 6단계 추론 테스트: input_example.json과 inferencetest.py를 확인하고 원격 :predict URL 호출을 검증합니다.
    - 함수 역할: 워크스페이스 안에서 조건에 맞는 파일/폴더 후보를 탐색합니다.
    - 입력 기준: 입력값 `project`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 정규화된 Path 또는 None을 반환해 이후 파일 접근 기준으로 사용합니다.
    """
    for name in ["input_example.json", "sample_input.json", "example.json"]:
        candidate = project / name
        if candidate.exists():
            return candidate
    return None


def find_inferencetest(project: Path) -> Path | None:
    """
    분석 주석:
    - 단계 맥락: 6단계 추론 테스트: input_example.json과 inferencetest.py를 확인하고 원격 :predict URL 호출을 검증합니다.
    - 함수 역할: 워크스페이스 안에서 조건에 맞는 파일/폴더 후보를 탐색합니다.
    - 입력 기준: 입력값 `project`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 정규화된 Path 또는 None을 반환해 이후 파일 접근 기준으로 사용합니다.
    """
    candidate = project / "inferencetest.py"
    return candidate if candidate.is_file() else None


def literal_assignment(path: Path, name: str) -> str | None:
    """
    분석 주석:
    - 단계 맥락: 6단계 추론 테스트: input_example.json과 inferencetest.py를 확인하고 원격 :predict URL 호출을 검증합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `path`, `name`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
    return None


def validate_predict_url(url: str | None) -> tuple[str | None, str, str | None]:
    """
    분석 주석:
    - 단계 맥락: 6단계 추론 테스트: input_example.json과 inferencetest.py를 확인하고 원격 :predict URL 호출을 검증합니다.
    - 함수 역할: 입력값, URL, 모델 경로, 서버 업로드 경로 등이 허용 조건을 만족하는지 검증합니다.
    - 입력 기준: 입력값 `url`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 여러 값을 tuple로 묶어 반환해 호출부가 상태, 경로, 오류 사유를 함께 판단하게 합니다.
    """
    value = (url or "").strip()
    if not value:
        return None, "missing", "missing_req_url"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return value, "invalid", "invalid_req_url_scheme"
    if not value.rstrip("/").endswith(":predict"):
        return value, "invalid", "req_url_must_end_with_predict"
    return value, "set", None


def preview(value) -> str:
    """
    분석 주석:
    - 단계 맥락: 6단계 추론 테스트: input_example.json과 inferencetest.py를 확인하고 원격 :predict URL 호출을 검증합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `value`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text[:1000]


def print_markdown_table(headers: list[str], rows: list[list[str]]) -> None:
    """
    분석 주석:
    - 단계 맥락: 6단계 추론 테스트: input_example.json과 inferencetest.py를 확인하고 원격 :predict URL 호출을 검증합니다.
    - 함수 역할: 사용자가 읽는 콘솔 출력을 Markdown Table 또는 짧은 요약 형태로 렌더링합니다.
    - 입력 기준: 입력값 `headers`, `rows`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환값보다 파일 생성, 콘솔 출력, 하위 명령 실행 같은 부수 효과가 핵심입니다.
    """
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        print("| " + " | ".join(str(value) for value in row) + " |")


def response_schema(value) -> str:
    """
    분석 주석:
    - 단계 맥락: 6단계 추론 테스트: input_example.json과 inferencetest.py를 확인하고 원격 :predict URL 호출을 검증합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `value`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    if isinstance(value, dict):
        return "object:" + ",".join(sorted(str(key) for key in value.keys())[:10])
    if isinstance(value, list):
        return f"array:{len(value)}"
    return type(value).__name__


def post_remote_predict(req_url: str, payload):
    """
    분석 주석:
    - 단계 맥락: 6단계 추론 테스트: input_example.json과 inferencetest.py를 확인하고 원격 :predict URL 호출을 검증합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `req_url`, `payload`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환 타입은 코드 흐름에서 결정되며, 호출부가 기대하는 값/상태를 돌려줍니다.
    """
    import requests

    message = json.dumps(payload)
    headers = {"Content-Type": "application/json"}
    response = requests.post(req_url, headers=headers, data=message)
    try:
        body = response.json()
    except ValueError:
        body = {"text": response.text}
    return response.status_code, body


def main():
    """
    분석 주석:
    - 단계 맥락: 6단계 추론 테스트: input_example.json과 inferencetest.py를 확인하고 원격 :predict URL 호출을 검증합니다.
    - 함수 역할: CLI 진입점입니다. 인자를 파싱하고 현재 단계의 전체 실행 순서를 조립합니다.
    - 입력 기준: 별도 입력 없이 현재 파일의 상수, CLI 인자, 또는 워크스페이스 상태를 기준으로 동작합니다.
    - 반환/효과: 반환 타입은 코드 흐름에서 결정되며, 호출부가 기대하는 값/상태를 돌려줍니다.
    """
    parser = argparse.ArgumentParser(description="Step 6: post input_example.json to a remote :predict URL.")
    parser.add_argument("--project", default=".", help="selected model work folder")
    parser.add_argument("--url", help="remote inference URL ending with :predict")
    parser.add_argument("--input-example", help="explicit input example JSON path")
    parser.add_argument("--execute", action="store_true", help="actually send HTTP POST to the remote :predict URL")
    parser.add_argument("--output", help="optional result JSON file path; no result file is written unless this is set")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    project = resolve_workspace_project(args.project)
    input_path = Path(args.input_example).expanduser().resolve() if args.input_example else find_input_example(project)
    inferencetest_path = find_inferencetest(project)
    req_url_from_file = literal_assignment(inferencetest_path, "req_url") if inferencetest_path else None
    req_url, req_url_status, req_url_failure = validate_predict_url(args.url or req_url_from_file)

    failures: list[str] = []
    if input_path is None:
        failures.append("missing_input_example")
    if inferencetest_path is None:
        failures.append("missing_inferencetest_py")
    if req_url_failure:
        failures.append(req_url_failure)

    payload = None
    if input_path is not None:
        try:
            payload = load_json(input_path)
        except Exception as exc:
            failures.append(f"schema_error:{exc}")

    status_code = None
    output = None
    schema = None
    if args.execute and not failures and req_url is not None:
        try:
            status_code, output = post_remote_predict(req_url, payload)
            schema = response_schema(output)
            if status_code >= 400:
                failures.append(f"http_error:{status_code}")
        except Exception as exc:
            failures.append(f"remote_predict_error:{exc}")

    output_path = Path(args.output).expanduser().resolve() if args.output else None
    result_path = str(output_path) if output_path else None
    report = InferenceReport(
        project_path=str(project),
        input_example_path=str(input_path) if input_path else None,
        inferencetest_path=str(inferencetest_path) if inferencetest_path else None,
        req_url=req_url,
        req_url_status=req_url_status,
        result_path=result_path,
        executed=args.execute,
        status_code=status_code,
        response_schema=schema,
        failures=failures,
        output_preview=preview(output) if output is not None else None,
    )
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print("추론 테스트 결과:")
        print_markdown_table(
            ["항목", "값"],
            [
                ["Project", "."],
                ["Input example", report.input_example_path or "missing"],
                ["Inference entrypoint", report.inferencetest_path or "missing"],
                ["req_url status", report.req_url_status],
                ["Result path", report.result_path or "not written"],
                ["Executed", str(report.executed).lower()],
                ["Status code", str(report.status_code) if report.status_code is not None else "none"],
                ["Response schema", report.response_schema or "none"],
            ],
        )
        if report.output_preview:
            print("Output preview:")
            print_markdown_table(["항목", "값"], [["Preview", report.output_preview]])
        if report.failures:
            print("Failures:")
            print_markdown_table(["No", "Failure"], [[str(index), failure] for index, failure in enumerate(report.failures, start=1)])
            if "missing_req_url" in report.failures or "req_url_must_end_with_predict" in report.failures:
                print("조치:")
                print_markdown_table(["No", "Action"], [["1", "inferencetest.py의 req_url 또는 --url에 원격 :predict URL을 입력하세요."]])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
