import json
import subprocess
import sys
from pathlib import Path


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
    analyzer = project_dir / ".opencode" / "scripts" / "validate_mlflow_project.py"

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

    print(f"- 분석 대상: {payload.get('selected_project', str(project_dir))}")
    print(f"- 모델 상태: {'있음' if model_found else '없음 또는 추가 확인 필요'}")

    if evidence or model_artifact_paths:
        print("- 발견 항목:")
        discovered = [str(x) for x in evidence if x]
        discovered.extend(str(path) for path in model_artifact_paths[:6])
        for item in sorted(set(discovered))[:6]:
            print(f"  - {item}")

    if review_items:
        print("- 확인 필요:")
        for item in review_items[:4]:
            print(f"  - {item}")

    print("- 다음 단계:")
    if model_found:
        print("  - 샘플은 사용하지 않고 본인 모델 경로 기준으로 모델 있음 12단계를 진행하세요.")
        print("  - 모델 파일은 data/** 원본 경로에서 직접 읽고 aiu_studio/로 복사하지 않습니다.")
        print("  - 실제 분석/환경 검증/모델 실행은 OpenCode 빌드모드에서 선택해주세요.")
        print("  - 추천 요청: 내 모델 경로 기준으로 MLflow 모델 있음 프로세스 분석해줘.")
    else:
        print("  - 모델이 없으면 sklearn / pytorch / tensorflow 중 하나를 선택해 샘플을 생성할 수 있습니다.")
        print("  - 실제 샘플 복사/모델 생성/검증 실행은 OpenCode 빌드모드에서 선택해주세요.")
        print("  - 추천 요청: 모델이 없으니 sklearn 샘플로 생성해줘.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
