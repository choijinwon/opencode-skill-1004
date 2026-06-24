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
  - `MLFLOW_EXPERIMENT_ID`
  - `MLFLOW_EXPERIMENT_PASSWORD`는 올바른 MLflow 인증 환경변수가 아니므로 사용하지 않는다.
- `ai_studio.env` 파일과 필수 키를 확인한다.
  - `mlflow_tracking_url`
  - `mlflow_tracking_username`
  - `mlflow_tracking_password`
  - `mlflow_experiment_name`
  - `mlflow_register_model_name`
- MLflow tracking 값은 사용자가 직접 `ai_studio.env`에 넣도록 안내한다.
  - `runtest.py` 또는 `run_model.py`에서 tracking URL, username, password를 자동 생성하거나 출력하지 않는다.
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
