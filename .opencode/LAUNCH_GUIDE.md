# Launch Guide

```text
OpenCode MLflow Launch

1. 먼저 워크스페이스를 분석합니다.
   model_found: true | false

2. 모델 있음
   루트/data 모델 목록 -> 모델 선택 -> Build에서 ai_studio/ 준비 + 환경변수 체크 + runtest_2.py 생성
   모델 파일은 ai_studio/로 복사하지 않습니다.

3. 모델 없음
   Build에서 샘플 선택: 1 sklearn / 2 pytorch / 3 tensorflow

4. Launch 규칙
   Launch는 읽기 전용입니다. 생성/수정/설치/실행은 Build에서만 합니다.
   secret 값은 set/empty/missing만 표시합니다.
```
