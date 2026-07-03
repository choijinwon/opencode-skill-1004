# Launch Guide

```text
AI Studio TODO Guide - 7단계

1. 먼저 워크스페이스를 분석합니다.
   model_found: true | false

2. data/ 폴더를 꼭 생성합니다.
   모델은 data/ 폴더에 넣고 시작합니다.

3. 모델 선택
   숫자로 선택 가능:
   1, 2, 3 ...

   자연어로도 선택 가능:
   "첫 번째 모델", "파이토치 모델", "data/... 사용"

   숫자 1번 선택 시 실행:
   python .opencode\scripts\04-train-model\prepare_selected_model.py --project . --model 1 --select-only --execute

   Windows PowerShell에서 현재 워크스페이스 루트 기준 상대경로로 실행합니다.

4. 모델 있음 7단계
   1 모델 목록 확인
   2 모델 선택
   3 환경변수/requirements 갱신
   4 템플릿 변환
   5 원격 MLflow 등록 실행
   6 추론 테스트
   7 오류 재실행
```

모델 목록이 표시된 상태에서 숫자 키를 누르면 TODO 단계가 아니라 모델 번호 선택으로 처리합니다.
secret 값은 출력하지 않고 `set`, `empty`, `missing` 상태만 표시합니다.
