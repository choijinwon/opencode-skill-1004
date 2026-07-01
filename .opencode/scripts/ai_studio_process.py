"""Fixed AI Studio process contract.

Do not rename, reorder, add, or remove steps without also updating the
official process image and all user-facing documentation.
"""

AI_STUDIO_PROCESS_STEPS = (
    "모델 목록 확인",
    "모델 선택",
    "템플릿 변환",
    "환경변수/requirements 갱신",
    "원격 MLflow 등록 실행",
    "추론 테스트",
    "오류 수정 및 재실행",
)

if len(AI_STUDIO_PROCESS_STEPS) != 7:
    raise RuntimeError("AI Studio process must stay exactly 7 steps")
