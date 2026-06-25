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

## When To Use

- 프로젝트 구조 분석 후 실제 실행 가능성을 확인할 때
- Python, virtualenv, dependency, MLflow version을 확인해야 할 때
- 폐쇄망 또는 로컬 환경에서 외부 다운로드 없이 실행 준비 상태를 판단해야 할 때
- MLflow tracking URI, experiment 설정 위치를 확인해야 할 때
- 학습 모델 생성 전에 `ai_studio.env` 필수 설정이 준비되었는지 확인해야 할 때

## Guidance Checks

- Python 실행 파일과 버전을 확인한다.
  - 기대 버전: Python 3.11.9
  - 3.11.9가 아니면 `version_mismatch:python`으로 분류한다.
- virtualenv 또는 conda 환경 사용 여부를 확인한다.
- dependency 파일을 확인한다.
  - `requirements.txt`
  - `pyproject.toml`
  - `environment.yml`
- 핵심 dependency 설치 여부를 확인한다.
  - `mlflow`
  - framework dependency: `sklearn`, `torch`, `tensorflow`, `transformers`
- MLflow version을 확인한다.
- 환경 변수 설정 위치를 확인한다.
  - `MLFLOW_TRACKING_URI`
  - `MLFLOW_TRACKING_USERNAME`
  - `MLFLOW_TRACKING_PASSWORD`
  - `MLFLOW_EXPERIMENT_NAME`
  - `MLFLOW_REGISTER_MODEL_NAME`
  - `MLFLOW_EXPERIMENT_ID`
  - `MLFLOW_EXPERIMENT_PASSWORD`는 올바른 MLflow 인증 환경변수가 아니므로 사용하지 않는다.
- `run_model.py` 또는 `runtest.py`의 MLflow/AI Studio 설정 블록과 필수 값을 확인한다.
  - `mlflow_tracking_url`
  - `mlflow_tracking_username`
  - `mlflow_tracking_password`
  - `mlflow_experiment_name`
  - `mlflow_register_model_name`
- 설정 블록 작성 안내에는 다음 빈 값 형태를 포함한다.
  - `mlflow_tracking_url=`
  - `mlflow_tracking_username=`
  - `mlflow_tracking_password=`
  - `mlflow_experiment_name=`
  - `mlflow_register_model_name=`
- MLflow tracking 값은 사용자가 직접 `run_model.py` 또는 `runtest.py`에 넣도록 안내한다.
  - `runtest.py` 또는 `run_model.py`에서 tracking URL, username, password를 자동 생성하거나 출력하지 않는다.
  - 사용자가 짧은 변수명 `tracking_url`, `username`, `password`로 입력해도 각각 `mlflow_tracking_url`, `mlflow_tracking_username`, `mlflow_tracking_password`로 인식한다.
  - 설정 dict 또는 `os.environ["MLFLOW_TRACKING_URI"] = "..."` 형태로 직접 넣은 값도 입력 완료로 인식한다.
  - `mlflow_tracking_url`이 비어 있으면 로컬 기본 tracking URI를 `file://<project>/ai_studio/artifacts`로 사용해 `mlruns/` 대신 `ai_studio/artifacts/<experiment_id>` 아래에 MLflow run을 만든다.
  - 로컬 기본 tracking URI를 쓸 때는 `MLFLOW_ALLOW_FILE_STORE=true`도 함께 export한다.
  - `run_model.py`는 설정 블록 값을 `MLFLOW_TRACKING_URI`, `MLFLOW_TRACKING_USERNAME`, `MLFLOW_TRACKING_PASSWORD`, `MLFLOW_EXPERIMENT_NAME`, `MLFLOW_REGISTER_MODEL_NAME`으로 export한다.
  - `mlflow_tracking_password` 값은 절대 출력하지 않는다.
  - `mflow_tracking_url` 오타가 있으면 `mlflow_tracking_url`로 수정하도록 안내한다.
  - PyTorch 샘플 기본값은 `mlflow_experiment_name=pytorch_sample`, `mlflow_register_model_name=pytorch_sample_model`이다.
- secret 값은 출력하지 않고 `set`, `empty`, `missing` 상태만 표시한다.
  - `MLFLOW_TRACKING_PASSWORD`와 `mlflow_tracking_password` 값은 절대 출력하지 않는다.
- 로컬/원격 MLflow 중 어떤 tracking target을 쓰는지 확인한다.

## Output

- Python 환경 요약
  - 현재 Python version
  - 기대 Python version: 3.11.9
  - Python version status: `set` 또는 `version_mismatch`
- dependency 파일 존재 여부
- 설치된 핵심 dependency와 version
- MLflow 설치/version 상태
- 환경 변수 설정 상태
- 환경 변수 export 준비 상태
- 소스 직접 입력 필요 값
  - `입력이 필요한 3개 값:` 형식으로 표시한다.
  - 기본 샘플에서 비어 있는 tracking 값은 `mlflow_tracking_url`, `mlflow_tracking_username`, `mlflow_tracking_password`다.
  - `사용자가 직접 소스에 입력` 안내와 대상 파일 `run_model.py` 또는 `runtest.py`를 함께 표시한다.
  - password 실제 값은 출력하지 않는다.
- 체크 단계 TOD Guide
  - 모델 있음: `1. 실행 파일 확정`부터 시작하는 7단계
  - 모델 없음/샘플 복사 후: `1. 환경 검증`부터 시작하는 6단계
- `ai_studio.env` 필수 키 상태
- 로컬/원격 tracking target 판단
- 실행 전 차단 항목
  - 차단 항목 요약
  - Python 버전 차이 예시: `Python 버전 차이 (<현재버전> vs 기대 3.11.9) → 호환성 확인 필요`
- 다음 단계: `agent-mlflow-skill-train-model`

## Failure Classification

- `missing_dependency`: 필요한 패키지가 없음
- `version_mismatch`: 설치 버전이 기대 범위와 다름
  - Python은 정확히 3.11.9를 기대한다.
  - 출력에는 `차단 항목 요약`으로 현재 버전과 기대 버전을 함께 표시한다.
- `missing_env`: 필수 환경 변수가 없음
- `config_error`: 설정 파일은 있으나 읽거나 해석할 수 없음
- `tracking_unreachable`: MLflow tracking server에 접근할 수 없음

## Safety

- secret 값을 로그나 응답에 포함하지 않는다.
- 외부 패키지 설치는 사용자가 명확히 요청한 경우에만 안내하거나 수행한다.
- 폐쇄망에서는 내부 패키지 저장소 정책을 우선 확인해야 한다.
- 폐쇄망에서는 GitHub issue 생성, 외부 crash report, telemetry, bug-report URL 열기를 시도하지 않는다.
- 환경 검증의 차단/경고 항목은 프로세스를 종료시키는 실패가 아니라 보고서 항목으로 출력한다.
- Bun 런타임은 사용하지 않는다. `bun`, `bunx`, `bun install`, `bun run`을 절대 실행하지 않는다.
- JavaScript 패키지 설치가 필요하고 대상 프로젝트에 `package.json`이 있으면 `npm i`만 사용한다.
- Python 샘플/모델 의존성은 `requirements.txt` 기준으로 `python -m pip install -r requirements.txt`를 사용한다.
- Windows에서는 `standaloneExecutable` 경로를 사용하지 않고 워크스페이스 기준 `python ...` 명령으로 스크립트를 직접 실행한다.
- Windows x86_64에서는 native/standalone executable 모델 실행을 기본 경로로 안내하지 않는다. Python entrypoint, `mlflow.pyfunc`, `aiu_custom` wrapper 기반 검증을 우선한다.
