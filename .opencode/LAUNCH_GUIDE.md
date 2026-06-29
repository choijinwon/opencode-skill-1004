# Launch Guide

```text
OpenCode MLflow Launch

1. 먼저 워크스페이스를 분석합니다.
   model_found: true | false
   .opencode/sample(s)는 복사용 원본이라 분석하지 않습니다.

2. 모델 있음
   루트/data 모델 목록을 번호로 보여줍니다.
   사용자는 번호 또는 경로로 사용할 모델을 선택합니다.
   Build에서 자동 준비 실행 1번으로 처리합니다.
   포함 작업: aiu_studio/ 복사 + aiu_studio/models/<MODEL_KIND>/ 모델 복사 + runtest_2.py + predict.py + mapping.json + localservingtest.py
   data/ 원본에는 생성하지 않습니다.

3. 모델 없음
   Build에서 샘플 선택: 1 sklearn / 2 pytorch / 3 tensorflow
```
