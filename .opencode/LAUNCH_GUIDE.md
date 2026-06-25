# Launch Guide

```text
OpenCode MLflow Launch

1. 먼저 분석
   어떤 단어로 시작해도 현재 워크스페이스를 먼저 확인합니다.
   확인 결과는 model_found: true 또는 model_found: false로 알려줍니다.

2. 모델이 있으면
   사용자 모델 경로를 기준으로 진행합니다.
   run_model.py로 고정하지 않고 실제 로컬 학습/모델 생성 파일을 먼저 확정합니다.
   run.py처럼 Python 파일 하나만 있으면 실행 파일 후보로 봅니다.

   진행 순서
   1. 실행 파일 확정
   2. 환경 검증
   3. 샘플 규격 확인/보충
   4. 환경 변수 입력/export
   5. 패키지 설치
   6. 로컬 학습 모델 실행
   7. 산출물 확인

3. 모델이 없으면
   Build 모드에서 샘플을 선택합니다.

   1 -> sklearn
   2 -> pytorch
   3 -> tensorflow

   샘플은 루트에 파일을 흩뿌리지 않고 아래처럼 폴더째 복사합니다.
   <workspace>/sklearn_sample/
   <workspace>/pytorch_sample/
   <workspace>/tensorflow_sample/

4. Launch 모드 규칙
   Launch 모드는 읽기 전용입니다.
   파일 생성, 수정, 삭제, 복사, 설치, 모델 실행은 Build 모드에서만 합니다.

5. 폐쇄망/Windows 기준
   - Bun 사용 금지: bun, bunx, bun install, bun run
   - JavaScript 설치가 필요하고 package.json이 있으면 npm i 사용
   - WSL wheelhouse가 있으면 bash .opencode/wsl/install_offline.sh 우선
   - 응답/인덱싱이 느리면 python .opencode/scripts/response_speed_check.py --project . 실행
   - 진단 후 python .opencode/scripts/apply_index_ignore.py --project . 실행
   - 전체 점검은 python .opencode/scripts/doctor.py --workspace . --project . 실행
   - Windows standaloneExecutable/native 실행 대신 python 스크립트 우선

추천 첫 요청
- 이 워크스페이스를 MLflow 모델 있음/없음 기준으로 분석해줘.
- 모델이 없으면 Build 모드에서 2번 PyTorch 샘플 생성으로 진행해줘.

보안 규칙
- API key, password, token 값은 출력하지 않습니다.
- secret 값은 set, empty, missing 상태만 표시합니다.
```
