#!/usr/bin/env python3
"""Step 2 wrapper: lock the selected model for the AI Studio flow.

PowerShell users often pass paths with backslashes or Korean Won signs. This
wrapper normalizes only the model selector, then delegates to the canonical
prepare_selected_model.py implementation with --select-only.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path
from types import SimpleNamespace


# ---------------------------------------------------------------------------
# 경로/명령 상수
# ---------------------------------------------------------------------------
# 현재 파일 기준으로 .opencode/scripts 루트에 접근하기 위한 기준 경로입니다.
# 이 파일은 "2차 분석본" 위치에 별도 복사되어 있을 수 있으므로,
# 원본 스크립트와 동일한 상대 위치 규칙을 유지하는 것이 중요합니다.
ROOT = Path(__file__).resolve().parents[2]

# 1차 분석 스크립트 경로입니다.
# 사용자가 "번호로 모델 선택" 했을 때, 현재 표시 목록 기준 번호를 실제 모델 경로로
# 바꾸기 위해 1차 분석 결과를 다시 읽어올 때 사용합니다.
ANALYZE_PROJECT_SCRIPT = ROOT / "scripts" / "01-project-analyze" / "validate_mlflow_project.py"

# 실제 모델 선택/고정/준비 상태 생성 로직이 들어 있는 5차 스크립트 경로입니다.
# 2차 스크립트는 직접 선택 결과를 저장하지 않고, 이 구현체에 위임합니다.
PREPARE_SELECTED_MODEL_SCRIPT = ROOT / "scripts" / "05-train-model" / "prepare_selected_model.py"

# 오류 메시지나 안내 문구에 보여줄 상대경로 문자열입니다.
# 실제 로딩은 위 Path 객체로 하고, 사용자는 아래 문자열 경로로 이해하기 쉽도록 분리합니다.
ANALYZE_PROJECT_COMMAND = ".opencode/scripts/01-project-analyze/validate_mlflow_project.py"
PREPARE_SELECTED_MODEL_COMMAND = ".opencode/scripts/05-train-model/prepare_selected_model.py"

# Windows/PowerShell/한글 키보드 환경에서 자주 섞이는 경로 구분 문자를
# 모두 "/" 기준으로 통일하기 위한 문자 치환표입니다.
# 예:
# - "\"
# - "＼"
# - "￦"
# - "₩"
# 를 모두 "/" 로 바꿉니다.
PATH_SEPARATOR_TRANSLATION = str.maketrans({
    "\\": "/",
    "＼": "/",
    "￦": "/",
    "₩": "/",
})


def normalize_model_selector(value: str) -> str:
    # 사용자가 입력한 모델 선택값을 정규화합니다.
    #
    # 처리 목적:
    # 1) 따옴표 제거
    # 2) selected/current/현재/선택 같은 예약어 유지
    # 3) 숫자 선택(예: 1, 2, 3)은 그대로 유지
    # 4) 경로 입력은 슬래시 형식으로 통일
    #
    # 즉, "번호 선택"과 "상대경로 선택"을 모두 안전하게 받기 위한 전처리 단계입니다.
    """
    분석 주석:
    - 단계 맥락: 2단계 모델 선택: 사용자가 입력한 번호/경로를 선택 모델로 고정하고 이후 단계가 같은 모델을 보도록 합니다.
    - 함수 역할: Windows/PowerShell/한글 키보드 입력처럼 흔들릴 수 있는 문자열을 내부 표준 형식으로 정규화합니다.
    - 입력 기준: 입력값 `value`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    selector = value.strip().strip('"').strip("'")
    if selector.lower() in {"selected", "current", "last", "기존", "현재", "선택"}:
        return selector
    if selector.isdigit():
        return selector
    return re.sub(r"/+", "/", selector.translate(PATH_SEPARATOR_TRANSLATION)).strip("/")


def normalize_argv(argv: list[str]) -> list[str]:
    # PowerShell/사용자 입력에서 자주 섞이는 비표준 인자 형태를 정리합니다.
    #
    # 예를 들어 아래 형태들을 보정합니다.
    # - -- model 3        -> --model 3
    # - model 3           -> --model 3 취급
    # - --model3          -> --model 3
    # - execute / 실행    -> 무시
    #
    # 목적은 "사용자가 조금 다르게 입력해도 2번 모델 선택 단계가 최대한 흔들리지 않게"
    # 하는 것입니다.
    """
    분석 주석:
    - 단계 맥락: 2단계 모델 선택: 사용자가 입력한 번호/경로를 선택 모델로 고정하고 이후 단계가 같은 모델을 보도록 합니다.
    - 함수 역할: Windows/PowerShell/한글 키보드 입력처럼 흔들릴 수 있는 문자열을 내부 표준 형식으로 정규화합니다.
    - 입력 기준: 입력값 `argv`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 후속 검사/출력에 사용할 목록을 반환합니다.
    """
    normalized: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--" and index + 1 < len(argv):
            next_arg = argv[index + 1]
            if next_arg in {"model", "project"}:
                normalized.append(f"--{next_arg}")
                index += 2
                continue
        if arg in {"model", "project"}:
            normalized.append(f"--{arg}")
            index += 1
            continue
        if arg in {"execute", "실행"}:
            index += 1
            continue
        match = re.fullmatch(r"--model(.+)", arg)
        if match and match.group(1) and not match.group(1).startswith(("=", "-")):
            normalized.extend(["--model", match.group(1)])
        else:
            normalized.append(arg)
        index += 1
    return normalized


def load_prepare_module():
    # 5차 준비 스크립트를 import 형태로 동적 로딩합니다.
    #
    # 왜 importlib를 쓰는가?
    # - 별도 프로세스를 또 띄우지 않고
    # - 내부 build_report()/print_report() 같은 함수를 직접 재사용하고
    # - 2차 래퍼가 5차 구현체를 위임 호출하는 구조를 만들기 위해서입니다.
    """
    분석 주석:
    - 단계 맥락: 2단계 모델 선택: 사용자가 입력한 번호/경로를 선택 모델로 고정하고 이후 단계가 같은 모델을 보도록 합니다.
    - 함수 역할: 외부 파일, JSON, 모듈, 설정 값을 읽어 현재 단계에서 사용할 수 있게 준비합니다.
    - 입력 기준: 별도 입력 없이 현재 파일의 상수, CLI 인자, 또는 워크스페이스 상태를 기준으로 동작합니다.
    - 반환/효과: 반환 타입은 코드 흐름에서 결정되며, 호출부가 기대하는 값/상태를 돌려줍니다.
    """
    spec = importlib.util.spec_from_file_location("prepare_selected_model_impl", PREPARE_SELECTED_MODEL_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load prepare script: {PREPARE_SELECTED_MODEL_COMMAND}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_analyze_module():
    # 1차 분석 스크립트를 import 형태로 동적 로딩합니다.
    #
    # 사용 이유:
    # 사용자가 "3번 모델"처럼 번호를 입력했을 때,
    # 현재 워크스페이스에서 실제 3번이 어떤 경로인지 알아내려면
    # 1차 분석의 모델 목록 생성 로직을 그대로 재사용해야 하기 때문입니다.
    """
    분석 주석:
    - 단계 맥락: 2단계 모델 선택: 사용자가 입력한 번호/경로를 선택 모델로 고정하고 이후 단계가 같은 모델을 보도록 합니다.
    - 함수 역할: 외부 파일, JSON, 모듈, 설정 값을 읽어 현재 단계에서 사용할 수 있게 준비합니다.
    - 입력 기준: 별도 입력 없이 현재 파일의 상수, CLI 인자, 또는 워크스페이스 상태를 기준으로 동작합니다.
    - 반환/효과: 반환 타입은 코드 흐름에서 결정되며, 호출부가 기대하는 값/상태를 돌려줍니다.
    """
    spec = importlib.util.spec_from_file_location("validate_mlflow_project_impl", ANALYZE_PROJECT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load analyze script: {ANALYZE_PROJECT_COMMAND}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def resolve_display_number_selector(project: str, selector: str) -> str:
    # 화면에 보이는 "번호 선택"을 실제 모델 경로 선택자로 변환합니다.
    #
    # 동작 흐름:
    # 1) 숫자가 아니면 그대로 반환
    # 2) 숫자면 1차 분석 스크립트로 현재 프로젝트 목록 생성
    # 3) training_code_paths + model_artifact_paths 순서로 표시 목록 구성
    # 4) 사용자가 고른 번호를 실제 상대경로로 치환
    #
    # 이 함수가 중요한 이유:
    # 사용자는 번호로 선택하지만, 이후 단계(5차 준비)는 실제 경로를 알아야
    # "처음 선택한 모델"을 계속 유지할 수 있기 때문입니다.
    """
    분석 주석:
    - 단계 맥락: 2단계 모델 선택: 사용자가 입력한 번호/경로를 선택 모델로 고정하고 이후 단계가 같은 모델을 보도록 합니다.
    - 함수 역할: 사용자 입력 경로/대상을 실제 워크스페이스 기준 Path 또는 내부 값으로 확정합니다.
    - 입력 기준: 입력값 `project`, `selector`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    if not selector.isdigit():
        return selector
    module = load_analyze_module()
    project_path, reason = module.select_project(project)
    report = module.build_report(project_path, reason, write_check=False)
    display_paths = list(report.training_code_paths) + list(report.model_artifact_paths)
    index = int(selector)
    if 1 <= index <= len(display_paths):
        return normalize_model_selector(display_paths[index - 1])
    return selector


def print_markdown_table(headers: list[str], rows: list[list[str]]) -> None:
    # 콘솔 출력용 Markdown 표를 만듭니다.
    # 2차 단계 결과는 사용자가 번호/다음 단계 흐름을 바로 보기 쉬워야 하므로
    # ASCII 박스 표 대신 Markdown 표 형식으로 고정합니다.
    """
    분석 주석:
    - 단계 맥락: 2단계 모델 선택: 사용자가 입력한 번호/경로를 선택 모델로 고정하고 이후 단계가 같은 모델을 보도록 합니다.
    - 함수 역할: 사용자가 읽는 콘솔 출력을 Markdown Table 또는 짧은 요약 형태로 렌더링합니다.
    - 입력 기준: 입력값 `headers`, `rows`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환값보다 파일 생성, 콘솔 출력, 하위 명령 실행 같은 부수 효과가 핵심입니다.
    """
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        print("| " + " | ".join(str(value) for value in row) + " |")


def selected_entrypoint_path(report) -> str:
    # 선택 모델 기준으로 실제 실행 파일 경로를 만들어 반환합니다.
    #
    # report.generated_entrypoint가 있으면 그 값을 우선 사용하고,
    # 없으면 기본값으로 runtest_2.py를 사용합니다.
    # work_project_path가 "." 이 아니면 작업 폴더 하위 경로로 조합해서 보여줍니다.
    """
    분석 주석:
    - 단계 맥락: 2단계 모델 선택: 사용자가 입력한 번호/경로를 선택 모델로 고정하고 이후 단계가 같은 모델을 보도록 합니다.
    - 함수 역할: 현재 단계의 세부 처리 로직을 함수 단위로 분리해 유지보수와 테스트가 쉽도록 합니다.
    - 입력 기준: 입력값 `report`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 사용자 표시, 설정값, 오류 사유 등에 사용할 문자열 또는 None을 반환합니다.
    """
    entrypoint = report.generated_entrypoint or "runtest_2.py"
    if report.work_project_path and report.work_project_path != ".":
        return f"{report.work_project_path.rstrip('/')}/{entrypoint}"
    return entrypoint


def print_selected_entrypoint_only(report) -> None:
    # 성공 시 사용자에게 필요한 핵심 결과만 간단히 출력합니다.
    #
    # 보여주는 정보:
    # - 어떤 모델이 선택되었는지
    # - MODEL_KIND가 무엇인지
    # - 이후 실행 기준 파일이 무엇인지
    # - 작업 폴더가 어디인지
    # - 다음으로 눌러야 할 3~7 단계
    #
    # verbose가 아닐 때는 이 정도만 보여주는 것이 가장 덜 헷갈립니다.
    """
    분석 주석:
    - 단계 맥락: 2단계 모델 선택: 사용자가 입력한 번호/경로를 선택 모델로 고정하고 이후 단계가 같은 모델을 보도록 합니다.
    - 함수 역할: 사용자가 읽는 콘솔 출력을 Markdown Table 또는 짧은 요약 형태로 렌더링합니다.
    - 입력 기준: 입력값 `report`를 기준으로 판단/변환을 수행합니다.
    - 반환/효과: 반환값보다 파일 생성, 콘솔 출력, 하위 명령 실행 같은 부수 효과가 핵심입니다.
    """
    print(f"선택 모델: {report.selected_model_path or 'missing'}")
    print(f"MODEL_KIND: {report.model_kind or 'missing'}")
    print(f"실행 파일: {selected_entrypoint_path(report)}")
    print(f"작업 폴더: {report.work_project_path or '.'}")
    print("다음 가능 단계:")
    print_markdown_table(
        ["Status", "Step", "Action"],
        [
            ["대기", "3", "환경 검증"],
            ["대기", "4", "템플릿 변환 (사용자 선택)"],
            ["대기", "5", "원격 MLflow 등록 실행"],
            ["대기", "6", "추론 테스트"],
            ["대기", "7", "오류 재실행"],
        ],
    )


def main() -> int:
    # 2차 모델 선택 단계의 CLI 진입점입니다.
    #
    # 이 함수가 하는 일:
    # 1) 인자 파싱
    # 2) 사용자가 준 모델 번호/경로 정규화
    # 3) 숫자 선택이면 실제 모델 경로로 치환
    # 4) 4차 prepare_selected_model.py 에 select_only 모드로 위임
    # 5) 결과를 JSON / 간단 출력 / 상세 출력 중 하나로 보여줌
    """
    분석 주석:
    - 단계 맥락: 2단계 모델 선택: 사용자가 입력한 번호/경로를 선택 모델로 고정하고 이후 단계가 같은 모델을 보도록 합니다.
    - 함수 역할: CLI 진입점입니다. 인자를 파싱하고 현재 단계의 전체 실행 순서를 조립합니다.
    - 입력 기준: 별도 입력 없이 현재 파일의 상수, CLI 인자, 또는 워크스페이스 상태를 기준으로 동작합니다.
    - 반환/효과: 반환 타입 `int` 기준으로 다음 처리 단계에 값을 전달합니다.
    """
    parser = argparse.ArgumentParser(description="Step 2: select and lock a model for the AI Studio flow.")
    parser.add_argument("model_arg", nargs="?", help="model number or project-relative path")
    parser.add_argument("--project", default=".", help="workspace/model project folder")
    parser.add_argument("--model", help="model number or project-relative path")
    parser.add_argument("--dry-run", action="store_true", help="show the selected model without writing config/config.json")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--verbose", action="store_true", help="print detailed model list and next steps")
    args = parser.parse_args(normalize_argv(sys.argv[1:]))

    # --model 옵션 또는 위치 인자 둘 중 하나는 반드시 있어야 합니다.
    raw_model = args.model or args.model_arg
    if not raw_model:
        parser.error("2번 모델 선택에는 --model <번호|경로> 또는 위치 인자 <번호|경로>가 필요합니다.")

    # 실제 선택/고정 로직은 5차 준비 스크립트 구현체에 위임합니다.
    module = load_prepare_module()

    # 사용자가 번호로 선택했다면 실제 상대경로로 바꾸고,
    # 경로 입력이었다면 정규화된 경로를 그대로 사용합니다.
    model_selector = resolve_display_number_selector(args.project, normalize_model_selector(raw_model))

    # 5차 준비 스크립트가 기대하는 인자 구조를 SimpleNamespace로 맞춰 전달합니다.
    # 여기서 중요한 고정값:
    # - execute = not dry_run
    # - select_only = True  -> 2차 단계는 "선택 고정"까지만 담당
    # - sync_runtime = False -> 아직 템플릿 변환/런타임 갱신 단계는 아님
    delegated_args = SimpleNamespace(
        project=args.project,
        model=model_selector,
        execute=not args.dry_run,
        force=False,
        select_only=True,
        sync_runtime=False,
        json=args.json,
        verbose=args.verbose,
    )

    # 5차 구현체에서 report를 받아 현재 단계 출력 규칙에 맞게 보여줍니다.
    report = module.build_report(delegated_args)
    if args.json:
        import json

        from dataclasses import asdict

        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    elif not args.verbose and not report.failures:
        # 기본 성공 시에는 핵심 결과만 짧게 보여줍니다.
        print_selected_entrypoint_only(report)
    else:
        # 실패 또는 verbose 요청 시에는 준비 스크립트 쪽 상세 리포트를 그대로 사용합니다.
        module.print_report(report, verbose=args.verbose)

    # 실패 항목이 있으면 종료 코드를 1로 반환해 상위 PowerShell/자동화가 감지할 수 있게 합니다.
    return 1 if report.failures else 0


if __name__ == "__main__":
    # Ctrl+C 등 인터럽트도 종료 코드 130으로 명시 처리합니다.
    # 상위 래퍼에서 "사용자가 중단했다"는 것을 구분하기 쉽습니다.
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
