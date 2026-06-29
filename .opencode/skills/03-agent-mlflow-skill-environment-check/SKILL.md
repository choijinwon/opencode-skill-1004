---
name: agent-mlflow-skill-environment-check
description: Use when the user asks "환경 검증", "dependency 확인", "MLflow 설치", "ai_studio.env", "API key 위치", or environment check; verifies Python, dependencies, MLflow, env vars, and required AI Studio settings.
license: MIT
compatibility: opencode
metadata:
  flow: ml-workspace-development
  stage: 02-environment-check
  step: 2
---

# Execution Environment Check

## Result First

```text
판단 결과: pass | warn | needs_user_input | blocked
현재 단계: 2. 환경 검증
현재 대상: selected_project_path
핵심 판단: Python 3.11.9, MLflow, dependency, 설정 상태
다음 단계: 샘플 규격 확인/보충 또는 로컬 학습 실행
```

## Workflow

```text
1. 프로젝트 분석
2. 환경 검증
3. 샘플 규격 확인/보충
4. 환경 변수 입력/export
5. 패키지 설치
6. 로컬 학습 모델 실행
7. 산출물 확인
```

## What To Do Now

```text
1. Python 실행 파일과 버전을 확인한다.
2. dependency 파일과 핵심 패키지를 확인한다.
3. MLflow 설치/version을 확인한다.
4. run_model.py, runtest.py 또는 aiu_studio/runtest.py 설정 블록을 확인한다.
5. 비어 있는 값은 사용자가 직접 소스에 입력하도록 안내한다.
```

## Output Contract

```text
반드시 보여줄 값:
- 판단 결과
- Python 현재 version / 기대 version 3.11.9
- dependency 파일 상태
- requirements.txt 필요 패키지 / 설치 여부 / 설치 버전 / 요구 버전 / 버전 불일치
- MLflow 설치/version 상태
- 환경 변수 상태
- 실행 파일명이 다른 경우 --entrypoint <file> 사용 여부
- 입력이 필요한 값
- password는 값 없이 set/empty/missing
- TOD Guide
- 차단 항목 요약
```

상태 출력 UI:

```text
판단 결과: warn
Python: version_mismatch, current=<현재버전>, expected=3.11.9
MLflow: set
Secrets: mlflow_tracking_password=set, value hidden
입력이 필요한 값: mlflow_tracking_url, mlflow_tracking_username, mlflow_tracking_password
```

## Commands

```text
환경 검증:
python .opencode/scripts/check_environment.py --project <selected_project_path>
python .opencode/scripts/check_environment.py --project <selected_project_path> --entrypoint <file>

폐쇄망 WSL 패키지 설치:
bash .opencode/wsl/install_offline.sh

wheelhouse 준비:
export PIP_INDEX_URL=http://<internal-pypi>/simple
bash .opencode/wsl/download_wheels.sh

PyTorch CPU wheel Nexus upstream 참고:
https://download.pytorch.org/whl/cpu

torch SSL 설치 금지:
https://download.pytorch.org, https://pypi.org 인덱스를 사용하지 않는다.
wheelhouse 오프라인 설치 또는 내부 http:// PyPI 미러만 사용한다.

인덱싱 제외 적용:
python .opencode/scripts/apply_index_ignore.py --project .
```

## Artifact Map

```text
local metrics   -> ai_studio/metrics/
local code      -> ai_studio/code/
MLflow artifact -> artifact_path="ai_studio" 아래 code/
tracking store  -> ai_studio/tracking/
```

<details>
<summary>자세한 판단 기준 보기</summary>

```text
pass:
- Python 3.11.9
- MLflow 설치됨
- 핵심 dependency 확인됨
- 필수 MLflow 설정이 소스 또는 환경에 있음

warn:
- Python 버전만 기대값과 다름
- 폐쇄망 설치 준비가 필요하지만 다음 단계 안내 가능

needs_user_input:
- mlflow_tracking_url, username, password 입력 필요
- 실제 entrypoint 확인 필요

blocked:
- 프로젝트 경로 없음
- 실행 파일 없음
- requirements/config를 읽을 수 없음
```

사용자가 직접 입력할 설정:

```text
mlflow_tracking_url
mlflow_tracking_username
mlflow_tracking_password
```

자동 생성되는 설정:

```text
mlflow_experiment_name
mlflow_register_model_name
```

`mlflow_tracking_url`은 `https://`를 사용하지 않는다. SSL은 금지이며 `http://` 또는 `file://`를 사용한다.

</details>

<details>
<summary>문제 해결 보기</summary>

```text
증상: Python 버전 차이
원인: 현재 Python이 3.11.9가 아님
조치: 호환성 경고로 표시하고 필요 시 3.11.9 환경 사용

증상: mlruns 폴더가 생김
원인: tracking URI가 기본값으로 잡힘
조치: 로컬 기본 tracking은 ai_studio/tracking 기준으로 안내

증상: 환경변수를 입력했는데 체크가 안 됨
원인: run_model.py/runtest.py/aiu_studio/runtest.py 설정 블록 또는 export mapping 누락
조치: 소스 설정 블록 값을 확인하고 MLFLOW_* export 상태를 표시

증상: 폐쇄망 설치가 느림
원인: PyPI 다운로드/resolver 지연
조치: .opencode/wsl/wheelhouse 기반 install_offline.sh 우선

증상: torch가 SSL 문제로 설치 불가
원인: pip가 https:// PyPI 또는 https://download.pytorch.org 인덱스를 사용함
조치: SSL 설치 금지. 내부 http:// PyPI 미러로 wheelhouse를 만들거나 별도 PC에서 wheel 파일을 받아 .opencode/wsl/wheelhouse/에 복사한 뒤 install_offline.sh 실행
```

</details>

<details>
<summary>전문가 상세 보기</summary>

허용 alias:

```text
tracking_url -> mlflow_tracking_url
username -> mlflow_tracking_username
password -> mlflow_tracking_password
mflow_tracking_url -> 오타, mlflow_tracking_url로 수정 안내
```

로컬 tracking:

```text
MLFLOW_TRACKING_URI=file://<project>/ai_studio/tracking
MLFLOW_ALLOW_FILE_STORE=true
MLflow artifact는 artifact_path="ai_studio" 아래 code/ 구조로 기록
```

</details>

<details>
<summary>Safety 규칙 보기</summary>

- secret 값을 로그나 응답에 포함하지 않는다.
- `MLFLOW_TRACKING_PASSWORD`와 `mlflow_tracking_password` 값은 절대 출력하지 않는다.
- 폐쇄망에서는 GitHub issue, crash report, telemetry URL을 열지 않는다.
- 환경 검증의 차단/경고 항목은 프로세스를 종료시키는 실패가 아니라 보고서 항목으로 출력한다.
- Bun 런타임은 사용하지 않는다.
- JavaScript 설치가 필요하고 `package.json`이 있으면 `npm i`만 사용한다.
- Windows에서는 `standaloneExecutable` 경로 대신 `python ...` 명령을 사용한다.
- Windows x86_64에서는 native/standalone executable 모델 실행을 기본 경로로 안내하지 않는다.

</details>
