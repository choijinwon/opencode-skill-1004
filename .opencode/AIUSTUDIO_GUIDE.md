# AIU Studio Guide

```text
AIU Studio MLflow Onboarding

1. 먼저 워크스페이스를 분석합니다.
   model_found: true | false
   .opencode/sample(s)는 복사용 원본이라 분석하지 않습니다.

2. 모델 있음
   루트/data 모델 목록을 번호로 보여줍니다.
   사용자는 번호 또는 경로로 사용할 모델을 선택합니다.
   모델 목록이 보이는 상태에서 숫자 키를 누르면 TOD 단계가 아니라 모델 번호 선택으로 처리합니다.
   모델 선택 직후 자동 준비를 실행합니다.
   실행 명령: python .opencode/scripts/prepare_selected_model.py --project . --model <번호|경로> --execute
   포함 작업: 기존 runtest.py 참조 + 선택 모델 기준 runtest_2.py 변환
   data/ 원본에는 생성하지 않습니다.

3. 모델 없음
   AIU Studio에서 샘플 선택: 1 sklearn / 2 pytorch / 3 tensorflow
   숫자 키 1/2/3을 누르면 해당 샘플을 바로 선택합니다.
```
