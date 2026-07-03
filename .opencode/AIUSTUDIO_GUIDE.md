# AI Studio TODO Guide

```text
AI Studio TODO Guide - 7단계

1. 먼저 워크스페이스를 분석합니다.
   model_found: true | false
   .opencode/는 스킬 번들이므로 분석하지 않습니다.

2. 모델 있음
   루트/data 모델 목록을 번호로 보여줍니다.
   사용자는 번호 또는 경로로 사용할 모델을 선택합니다.
   자연어로도 선택할 수 있습니다. 예: "첫 번째 모델", "파이토치 모델", "data/... 모델 사용".
   모델 목록이 보이는 상태에서 숫자 키를 누르면 TODO 단계가 아니라 모델 번호 선택으로 처리합니다.
   모델 선택 직후 자동 준비를 실행합니다.
   실행 명령: python .opencode/scripts/04-train-model/prepare_selected_model.py --project . --model <번호|경로> --execute
   포함 작업: 기존 runtest.py 참조 + 선택 모델 기준 runtest_2.py 변환
   data/ 원본에는 생성하지 않습니다.

3. 모델 없음
   AIU Studio에서 샘플 선택: 1 sklearn / 2 pytorch / 3 tensorflow
   숫자 키 1/2/3을 누르면 해당 샘플을 바로 선택합니다.
   자연어로 "sklearn 샘플", "파이토치 샘플", "tensorflow 샘플"처럼 요청해도 됩니다.
```
