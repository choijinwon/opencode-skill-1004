# Launch Guide

```text
OpenCode MLflow Launch

1. 먼저 분석
   어떤 단어로 시작해도 워크스페이스를 먼저 확인합니다.
   결과는 model_found: true 또는 model_found: false로 표시합니다.

2. model_found: true
   프로젝트 루트와 data/** 모델 목록을 보여주고 사용할 모델을 선택합니다.
   모델 파일은 ai_studio/로 복사하지 않습니다.
   기존 runtest.py는 수정하지 않고 runtest_2.py를 생성합니다.
   다음 흐름: 모델 선택 -> runtest_2.py 생성 -> 환경 검증 -> 추론 테스트 -> MLflow 검증

3. model_found: false
   Build 모드에서 샘플을 선택합니다.
   1 sklearn / 2 pytorch / 3 tensorflow
   샘플은 <workspace>/<sample>_sample/ 폴더로 복사합니다.

4. Launch 규칙
   Launch는 읽기 전용입니다.
   파일 생성, 수정, 복사, 설치, 모델 실행은 Build 모드에서만 합니다.

5. 안전 기준
   Bun 사용 금지, 필요 시 npm i 사용
   Windows/native 실행보다 python 스크립트 우선
   secret 값은 출력하지 않고 set/empty/missing만 표시
```
