import argparse
import datetime as dt
import re
from pathlib import Path


SECRET_KEYWORDS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "mlflow_tracking_password",
)


def mask_secret_values(text: str) -> str:
    """프롬프트/결과 안에 secret 형태의 값이 있으면 로그에 남기기 전에 마스킹합니다."""
    masked = text or ""
    for keyword in SECRET_KEYWORDS:
        pattern = re.compile(rf"({re.escape(keyword)}\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE)
        masked = pattern.sub(r"\1***", masked)
    return masked


def table_cell(text: str) -> str:
    """Markdown 표가 깨지지 않도록 줄바꿈과 파이프 문자를 정리합니다."""
    value = mask_secret_values(text).strip()
    value = value.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    value = value.replace("|", "\\|")
    return value or "-"


def log_file_for(project: Path, now: dt.datetime, entry_type: str) -> Path:
    """워크스페이스 기준 .opencode/log/YYYYMMDD/*.md 경로를 만듭니다."""
    date_folder = now.strftime("%Y%m%d")
    file_name = "errors.md" if entry_type == "error" else "prompts.md"
    return project / ".opencode" / "log" / date_folder / file_name


def ensure_log_file(path: Path, now: dt.datetime, entry_type: str) -> None:
    """날짜별 로그 파일이 없으면 기본 Markdown Table 헤더를 생성합니다."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    date_title = now.strftime("%Y-%m-%d")
    title = "Error Log" if entry_type == "error" else "Prompt Log"
    path.write_text(
        f"# {title} - {date_title}\n\n"
        "| Time | Type | Step | Content | Result |\n"
        "|---|---|---|---|---|\n",
        encoding="utf-8",
    )


def append_log(project: Path, entry_type: str, step: str, content: str, result: str) -> Path:
    """프롬프트 또는 작업 히스토리를 오늘 날짜 로그 파일에 한 줄 추가합니다."""
    now = dt.datetime.now()
    path = log_file_for(project, now, entry_type)
    ensure_log_file(path, now, entry_type)
    row = (
        f"| {now.strftime('%H:%M:%S')} "
        f"| {table_cell(entry_type)} "
        f"| {table_cell(step)} "
        f"| {table_cell(content)} "
        f"| {table_cell(result)} |\n"
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(row)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Append Ai Studio prompt/history logs by date.")
    parser.add_argument("--project", default=".", help="workspace root. Default: current directory")
    parser.add_argument("--type", default="prompt", choices=["prompt", "history", "error"], help="log entry type")
    parser.add_argument("--step", default="-", help="Ai Studio step or short context")
    parser.add_argument("--content", default="", help="user prompt or history content")
    parser.add_argument("--result", default="", help="short result summary")
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    written = append_log(project, args.type, args.step, args.content, args.result)
    try:
        display = written.relative_to(project).as_posix()
    except ValueError:
        display = written.as_posix()
    print(f"logged: {display}")


if __name__ == "__main__":
    main()
