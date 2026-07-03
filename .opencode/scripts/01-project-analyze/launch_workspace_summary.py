import json
import subprocess
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from ai_studio_process import AI_STUDIO_PROCESS_STEPS, format_model_selection_hint


MODEL_HINTS = [
            "runtest.py",
    "run_model.py",
    "train.py",
    "predict.py",
    "aiu_custom/",
    "data/",
    "saved_model/",
    "MLmodel",
    "python_model.pkl",
    ".pkl",
    ".joblib",
    ".pt",
    ".pth",
    ".onnx",
    ".h5",
    ".keras",
    ".safetensors",
    ".bst",
    ".ubj",
]


def main() -> int:
    project_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    analyzer_candidates = [
        project_dir / ".opencode" / "scripts" / "01-project-analyze" / "validate_mlflow_project.py",
        project_dir / ".opencode" / "scripts" / "validate_mlflow_project.py",
        Path(__file__).resolve().with_name("validate_mlflow_project.py"),
    ]
    analyzer = next((path for path in analyzer_candidates if path.exists()), analyzer_candidates[0])

    print("[Workspace Analysis]")

    if not analyzer.exists():
        print("- 상태: 분석 스크립트를 찾지 못했습니다.")
        print("- 다음 단계: OpenCode에서 '이 워크스페이스를 분석해줘'라고 요청하세요.")
        return 0

    try:
        result = subprocess.run(
            [sys.executable, str(analyzer), "--project", str(project_dir), "--json"],
            cwd=project_dir,
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except Exception as exc:
        print(f"- 상태: 분석 실패 ({exc})")
        print("- 다음 단계: OpenCode에서 '이 워크스페이스를 분석해줘'라고 요청하세요.")
        return 0

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = None

    if result.returncode != 0 and payload is None:
        print("- 상태: 분석 실패")
        detail = (result.stderr or result.stdout).strip().splitlines()
        if detail:
            print(f"- 사유: {detail[-1][:160]}")
        print("- 다음 단계: OpenCode에서 '이 워크스페이스를 분석해줘'라고 요청하세요.")
        return 0

    if payload is None:
        print("- 상태: 분석 결과 파싱 실패")
        print("- 다음 단계: OpenCode에서 '이 워크스페이스를 분석해줘'라고 요청하세요.")
        return 0

    checks = payload.get("checks", [])
    evidence = []
    review_items = []

    for check in checks:
        status = check.get("status")
        name = check.get("name", "")
        message = check.get("message", "")
        if status == "pass":
            evidence.extend(check.get("evidence", [])[:3])
        elif status in {"warn", "block", "fail"}:
            review_items.append(f"{name}: {message}")

    model_artifact_paths = payload.get("model_artifact_paths") or []
    evidence_text = " ".join(str(item) for item in evidence)
    model_found = bool(model_artifact_paths) or any(hint in evidence_text for hint in MODEL_HINTS)
    if not model_found:
        review_items = [item for item in review_items if not item.startswith("sample spec scaffold:")]

    print(f"- 분석 대상: {payload.get('selected_project', str(project_dir))}")
    print(f"- 모델 상태: {'있음' if model_found else '없음 또는 추가 확인 필요'}")

    if evidence or model_artifact_paths:
        print("- 발견 항목:")
        if model_artifact_paths:
            print(f"  - 모델 후보: {len(model_artifact_paths)}개")
        model_path_set = {str(path) for path in model_artifact_paths}
        discovered = [
            str(x)
            for x in evidence
            if x and str(x) not in model_path_set and not any(str(x).endswith(suffix) for suffix in [".pkl", ".joblib", ".pt", ".pth", ".onnx", ".h5", ".keras", ".safetensors", ".bst", ".ubj"])
        ]
        for item in sorted(set(discovered))[:5]:
            print(f"  - {item}")

    if model_artifact_paths:
        print("- 모델 선택 화면:")
        print(format_model_selection_hint(indent="  "))
        print("  모델 목록은 프로젝트 기준 상대경로 알파벳 순서입니다.")
        print("  숫자키는 TODO 단계가 아니라 아래 모델 번호 선택입니다.")
        for index, path in enumerate(model_artifact_paths[:10], start=1):
            print(f"  {index}. {path}")
        print("  실행 예: python .opencode/scripts/04-train-model/prepare_selected_model.py --project . --model <번호 또는 경로> --execute")

    if review_items:
        print("- 확인 필요:")
        for item in review_items[:4]:
            print(f"  - {item}")

    print("- 다음 단계:")
    if model_found:
        for index, title in enumerate(AI_STUDIO_PROCESS_STEPS, start=1):
            print(f"  {index}. {title}")
    else:
        print("  - 모델이 없으면 sklearn / pytorch / tensorflow 중 하나를 선택해 샘플을 생성할 수 있습니다.")
        print("  - 실제 샘플 복사/모델 생성/검증 실행은 OpenCode ai Studio 빌드 모드에서 선택해주세요.")
        print("  - 추천 요청: 모델이 없으니 sklearn 샘플로 생성해줘.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
