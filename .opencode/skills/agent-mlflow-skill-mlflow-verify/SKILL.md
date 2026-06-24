---
name: agent-mlflow-skill-mlflow-verify
description: Use when the user asks "MLflow 확인", "run 생성 확인", "artifact 확인", "registered model", "Model Registry", or MLflow verify; checks runs, params, metrics, artifacts, pyfunc logging, and registered model status.
license: MIT
compatibility: opencode
metadata:
  flow: ml-workspace-development
  stage: 05-mlflow-verify
  step: 5
---

# MLflow Run And Model Verification

## When To Use

- 학습과 추론 테스트 후 MLflow에 기록이 남았는지 확인할 때
- run, params, metrics, artifacts, model logging 상태를 점검해야 할 때
- Model Registry에 모델 버전이 생성되었는지 확인해야 할 때
- local MLflow와 remote MLflow의 tracking/artifact 위치를 구분해야 할 때

## Guidance Checks

- tracking target을 확인한다.
  - local file store
  - local MLflow server
  - remote MLflow server
- experiment name 또는 experiment id를 확인한다.
- 최근 run 생성 여부를 확인한다.
- run 내부 기록을 확인한다.
  - params
  - metrics
  - tags
  - artifacts
  - model artifact
- pyfunc model logging 여부를 확인한다.
  - `MLmodel`
  - `python_model.pkl`
  - `code/`
  - `artifacts/`
  - signature
  - input example
- Model Registry 등록 여부를 확인한다.
  - registered model name
  - version
  - source URI
  - alias/stage/tag
- GenAI agent인 경우 추가로 확인한다.
  - traces
  - chat sessions
  - prompts
  - judges
  - datasets

## Output

- tracking target 요약
- experiment 정보
- 최근 run 생성 여부
- params/metrics/artifacts 기록 상태
- model artifact 기록 상태
- registered model/version 생성 여부
- MLflow UI에서 확인할 위치
- 남은 차단 항목 또는 후속 작업

## Failure Classification

- `tracking_unreachable`: tracking server 접근 실패
- `experiment_missing`: experiment를 찾을 수 없음
- `run_missing`: 실행 후 run이 생성되지 않음
- `artifact_missing`: run은 있으나 artifact가 없음
- `model_logging_error`: model artifact 구조가 불완전함
- `registry_missing`: registered model 또는 version이 없음
- `permission_error`: 인증 또는 권한 문제로 확인 불가

## Safety

- 인증 정보는 출력하지 않는다.
- remote registry에 등록/삭제/alias 변경은 사용자가 명확히 요청한 경우에만 수행한다.
- artifact root가 sample 내부인지 별도 `ai_studio` 경로인지 구분해서 설명한다.
