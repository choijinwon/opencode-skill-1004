---
name: agent-mlflow-skill-inference-test
description: Use when the user asks "추론 테스트", "input_example.json", "predict.py", "aiu_custom 테스트", "local_serving", or inference test; loads the local model and verifies predict contract and response schema.
license: MIT
compatibility: opencode
metadata:
  flow: ml-workspace-development
  stage: 04-inference-test
  step: 4
---

# Inference Test

## When To Use

- 로컬 학습 또는 모델 artifact 생성 후 실제 추론 가능성을 검증할 때
- `input_example.json`을 사용해 predict가 동작하는지 확인해야 할 때
- `aiu_custom` 기반 MLflow pyfunc wrapper의 `load_context`와 `predict` 계약을 확인해야 할 때
- `local_serving/` 기반 로컬 serving 테스트 구성이 있는지 확인해야 할 때
- 모델 등록 전에 schema, 반환값, 오류를 점검해야 할 때

## Guidance Checks

- 추론 entrypoint 후보를 확인한다.
  - `predict.py`
  - `aiu_custom/model_wrapper.py`
  - `aiu_custom/predict.py`
  - `local_serving/`
  - `run_model.py`
  - serving/test script
- input example을 확인한다.
  - `input_example.json`
  - README 예제
  - test fixture
- 모델 로드 방식을 확인한다.
  - framework native load
  - `mlflow.pyfunc.load_model`
  - custom wrapper load
- `ModelWrapper`가 있으면 다음 계약을 확인한다.
  - `mlflow.pyfunc.PythonModel` 상속 여부
  - `load_context` 구현 여부
  - `predict` 구현 여부
  - artifact/config 참조 경로
- 추론 결과 schema를 확인한다.
  - scalar
  - list
  - dict
  - pandas DataFrame
  - JSON serializable 여부
- 실패 시 모델 로드 실패와 추론 실행 실패를 분리한다.

## Output

- 선택된 추론 entrypoint
- 사용한 input example
- 모델 로드 방식
- 추론 결과 요약
- 응답 schema
- MLflow pyfunc 호환 여부
- 다음 단계: `agent-mlflow-skill-mlflow-verify`

## Failure Classification

- `missing_inference_entrypoint`: 추론 진입점을 찾을 수 없음
- `missing_input_example`: 테스트 입력이 없음
- `model_load_error`: 모델 로드 실패
- `predict_error`: predict 실행 실패
- `schema_error`: 입력 또는 출력 schema가 기대와 다름
- `serialization_error`: 응답을 JSON 등으로 직렬화할 수 없음

## Safety

- secret 또는 개인정보가 포함된 입력 예제를 그대로 출력하지 않는다.
- 추론 결과가 길면 요약하고 schema 중심으로 설명한다.
- 외부 LLM endpoint 호출이 필요한 경우 endpoint와 인증 설정 존재 여부를 먼저 확인한다.
