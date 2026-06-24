---
name: agent-mlflow-skill-project-analyze
description: Use when the user asks "분석해줘", "MLflow 5단계", "모델 있음/없음", "워크스페이스 분석", or project structure analysis; analyzes framework, entrypoint, artifact, config, input example, aiu_custom/local_serving/save_model.
license: MIT
compatibility: opencode
metadata:
  flow: ml-workspace-development
  stage: 01-project-analyze
  step: 1
---

# Project Structure Analysis

## When To Use

- 사용자가 지정한 모델 프로젝트 폴더의 ML 프로젝트 구조를 분석해 달라고 요청할 때
- 학습, 추론, MLflow 등록 전에 어떤 파일이 있는지 확인해야 할 때
- 프로젝트가 sklearn, PyTorch, TensorFlow, HuggingFace, custom pyfunc 중 무엇에 가까운지 판단해야 할 때
- `aiu_custom`, `local_serving`, `save_model`, `runtest.py`, `run_model.py`, `input_example.json` 같은 구성 요소가 필요한지 확인해야 할 때
- 사용자가 지정한 모델 프로젝트 폴더에 모델 프로젝트가 없어서 `.opencode/samples` 아래 샘플 4개 중 하나를 선택해 폴더째 복사해야 할 때

## Guidance Checks

- 현재 작업 경로와 사용자가 지정한 프로젝트 경로를 확인한다.
- 핵심 파일 존재 여부를 확인한다.
  - `requirements.txt`, `pyproject.toml`, `environment.yml`
  - `train.py`, `app.py`, `main.py`, `runtest.py`, `run_model.py`
  - `config.json`, `.env.example`, `input_example.json`
  - `aiu_custom/`, `aiu_custom/model_wrapper.py`, `aiu_custom/predict.py`
  - `local_serving/`
  - `save_model/`
  - `artifacts/`, `model/`, `mlruns/`, `aiu_studio/`
- framework 후보를 근거와 함께 분류한다.
  - sklearn: `sklearn`, `.pkl`, `.joblib`, `.fit()`
  - PyTorch: `torch`, `.pt`, `.pth`, `state_dict`
  - TensorFlow/Keras: `tensorflow`, `keras`, `.h5`, `.keras`, `saved_model.pb`
  - HuggingFace: `transformers`, tokenizer files, `model.safetensors`
  - Custom pyfunc: `mlflow.pyfunc.PythonModel`, `aiu_custom`, `ModelWrapper`
- 모델 artifact 후보와 생성 위치를 확인한다.
- 학습 entrypoint와 추론 entrypoint를 분리해서 표시한다.
- 누락 항목은 실패로 단정하지 않고 다음 단계에서 확인할 항목으로 분류한다.

## Initial Workspace Guide

사용자가 아래처럼 넓게 요청하면, 바로 샘플 선택부터 묻지 말고 먼저 워크스페이스를 분석한다.

```text
이 워크스페이스 분석해줘
현재 프로젝트 봐줘
MLflow 5단계로 봐줘
모델 있으면 진행하고 없으면 샘플로 시작해줘
```

첫 응답 흐름은 아래 순서를 따른다.

```text
1. 현재 워크스페이스 경로를 확인한다.
2. 모델 파일, 실행 entrypoint, 필수 폴더를 찾는다.
3. model_found 값을 먼저 결정한다.
4. model_found: true이면 기존 모델 기준 가이드를 출력한다.
5. model_found: false이면 sklearn/pytorch/tensorflow 선택 가이드를 출력한다.
```

초기 분석 응답은 아래 구조를 사용한다. 문장은 자연스럽게 바꿔도 되지만 순서는 유지한다.

```text
워크스페이스를 먼저 분석했습니다.

확인 기준:
- runtest.py, run_model.py, train.py, predict.py
- aiu_custom/
- local_serving/
- save_model/
- input_example.json
- MLmodel, python_model.pkl
- .pkl, .joblib, .pt, .pth, .h5, .keras, .onnx, .safetensors

분석 결과:
- model_found: true | false
- 발견 항목:
- 누락 항목:
- 다음 단계:
```

## Model Found Flow

사용자가 지정한 모델 프로젝트 폴더에서 학습/추론 가능한 모델 프로젝트가 발견되면 샘플을 선택하지 않는다. 발견된 프로젝트를 기준으로 분석 결과를 만들고, 이후 단계에서 해당 프로젝트를 직접 실행한다.

중요 규칙:

```text
모델 파일 또는 실행 entrypoint가 하나라도 발견되면 사용자에게 샘플 선택 질문을 하지 않는다.
샘플 선택은 model_found: false일 때만 진행한다.
```

모델 프로젝트가 있다고 판단하는 기준은 다음 중 하나 이상이다.

```text
학습 entrypoint 존재: train.py, scripts/train.py
실행/등록 entrypoint 존재: runtest.py, run_model.py
추론 entrypoint 존재: predict.py, app.py, main.py
필수 폴더 존재: aiu_custom/, local_serving/, save_model/
모델 wrapper 존재: aiu_custom/model_wrapper.py, aiu_custom/predict.py
모델 artifact 존재: save_model/, model/, artifacts/, saved_model/, .pkl, .joblib, .pt, .pth, .h5, .keras
MLflow model 존재: MLmodel, python_model.pkl
input example 존재: input_example.json
```

모델이 발견된 경우 출력에는 반드시 다음을 포함한다.

```text
model_found: true
selected_project_path
framework
train_entrypoint
inference_entrypoint
model_artifact_path
input_example_path
next_action: 발견된 프로젝트로 Step 2 환경 검증 후 Step 3 실행
```

모델이 발견된 경우 사용자에게 보여줄 가이드는 아래 방향으로 작성한다.

```text
실행 가능한 모델 구성을 찾았습니다.
샘플은 사용하지 않고 기존 모델 프로젝트 기준으로 진행합니다.

다음 단계:
1. ai_studio.env 확인
2. requirements.txt 또는 pyproject.toml 확인
3. input_example.json 확인
4. runtest.py, run_model.py 또는 train.py 실행 가능 여부 확인
5. MLflow 기록 확인
```

모델이 발견되면 `.opencode/samples`는 참조하지 않는다.

## No Model Found Fallback

사용자가 지정한 모델 프로젝트 폴더에서 학습/추론 가능한 모델 프로젝트를 찾지 못하면 실패로 끝내지 않는다. `.opencode/samples` 아래 샘플 3개 중 하나를 사용자가 선택하게 하고, 선택한 샘플 폴더를 워크스페이스 아래로 폴더째 복사해 모델 생성과 테스트 흐름을 진행할 수 있게 한다.

모델이 없는 경우 사용자에게 반드시 아래처럼 선택을 요청한다.

```text
현재 워크스페이스에서 실행 가능한 모델을 찾지 못했습니다.

아래 샘플 중 하나를 선택해서 워크스페이스에 폴더째 복사할 수 있습니다.

1. sklearn
2. pytorch
3. tensorflow

원하는 샘플 번호 또는 이름을 알려주세요.
```

사용자가 선택하기 전에는 샘플을 복사하지 않는다.

모델이 없는 경우 사용자에게 보여줄 가이드는 아래 방향으로 작성한다.

```text
실행 가능한 모델 구성을 찾지 못했습니다.
기본 모델 샘플로 시작할 수 있습니다.

선택 가능:
1. sklearn
2. pytorch
3. tensorflow

원하는 번호나 이름을 알려주면 해당 샘플 폴더를 워크스페이스에 복사하겠습니다.
```

### Selectable Samples

사용자가 선택할 수 있는 샘플은 아래 3개다.

```text
1. sklearn
   source: .opencode/samples/sklearn_sample
   purpose: 폐쇄망 sklearn 모델 프로젝트 기본 구조

2. pytorch
   source: .opencode/samples/pytorch_sample
   purpose: 폐쇄망 PyTorch 모델 프로젝트 기본 구조

3. tensorflow
   source: .opencode/samples/tensorflow_sample
   purpose: 폐쇄망 TensorFlow/Keras 모델 프로젝트 기본 구조
```

이 3개 외의 샘플은 임의로 선택하지 않는다.

선택형 샘플은 원본 폴더에 아래 기본 폴더가 있어야 한다.

```text
aiu_custom/
local_serving/
save_model/
```

아래 폴더는 사용자가 폐쇄망 모델을 직접 넣는 기본 슬롯이며, 워크스페이스에 모델이 없을 때 선택형 폴더 복사 대상으로 사용한다.

```text
sklearn_sample/
pytorch_sample/
tensorflow_sample/
```

### Workspace Copy Rule

기본 복사 방식은 `copy_mode: folder`다. 샘플 내용을 루트에 풀어놓지 않고 샘플 폴더 자체를 복사한다.

```text
<model-project-folder>/sklearn_sample/
<model-project-folder>/pytorch_sample/
<model-project-folder>/tensorflow_sample/
```

워크스페이스에 기존 파일이 있어도 대상 샘플 폴더가 없으면 복사할 수 있다. 같은 이름의 샘플 폴더가 이미 있으면 기본적으로 중단한다. 사용자가 명시적으로 덮어쓰기를 요청한 경우에만 `--force`를 사용한다.

### Selected Sample Handling

선택된 샘플은 원본을 직접 수정하지 않는다. 샘플 폴더 자체를 사용자가 지정한 워크스페이스 아래로 복사한다.

```text
<model-project-folder>/<sample-folder>/aiu_custom/
<model-project-folder>/<sample-folder>/local_serving/
<model-project-folder>/<sample-folder>/save_model/
<model-project-folder>/<sample-folder>/run_model.py
<model-project-folder>/<sample-folder>/requirements.txt
<model-project-folder>/<sample-folder>/input_example.json
```

폴더 복사에서는 실행에 필요하지 않은 생성 산출물을 제외한다.

```text
model/
saved_model/
artifacts/aiu_studio/
.venv/
__pycache__/
mlruns/
aiu_studio/
mlflow.db
```

복사 후 아래 필수 폴더는 항상 복사된 샘플 폴더 안에 있어야 한다. 샘플 원본에 없으면 빈 폴더로 생성한다.

```text
aiu_custom/
local_serving/
save_model/
```

복사는 `agent-mlflow-skill-sample-bootstrap` 스킬과 아래 스크립트를 기준으로 한다.

```text
python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample sklearn --execute
python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample pytorch --execute
python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample tensorflow --execute
```

샘플 선택 결과에는 반드시 다음을 포함한다.

```text
model_found: false
selected_sample
sample_source_path
target_project_path
copy_mode: folder
required_dirs: aiu_custom, local_serving, save_model
next_action:
  1. 환경 검증
  2. 환경 변수 설정
```

## Output

- 선택된 프로젝트 경로
- 모델 프로젝트 발견 여부
- 모델이 있을 때 발견된 학습/추론/model artifact 경로
- 모델이 없을 때 사용자가 선택할 샘플 4개
- 선택된 샘플 원본 경로와 폴더 복사 대상 경로
- 발견된 핵심 파일 목록
- 누락되었거나 확인 필요한 파일 목록
- framework 후보와 판단 근거
- 학습 entrypoint 후보
- 추론 entrypoint 후보
- 모델 artifact 후보
- `aiu_custom` 필요 여부
- 필수 폴더 존재 여부: `aiu_custom/`, `local_serving/`, `save_model/`
- 다음 단계: `agent-mlflow-skill-environment-check`

## Safety

- 이 단계에서는 파일을 수정하지 않는다.
- 모델 artifact를 이동하거나 복사하지 않는다.
- 샘플 원본 디렉터리를 직접 덮어쓰지 않는다.
- 샘플을 폴더째 복사해야 하면 사용자 선택을 먼저 받은 뒤 `agent-mlflow-skill-sample-bootstrap` 기준으로 처리한다.
- 모델이 발견된 경우에는 샘플 선택을 제안하지 않는다.
- credential 값은 출력하지 않는다.
- framework가 불명확하면 `unknown/custom`으로 둔다.
