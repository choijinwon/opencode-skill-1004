# MLflow 6단계 TODO Skill 설명서

이 문서는 `.opencode/skills`의 MLflow 관련 OpenCode skill과 6단계 TODO 흐름을 설명한다.

기준 대상은 **사용자가 지정한 모델 프로젝트 폴더**다.  
즉, ML 개발자가 실제로 작업 중인 모델 코드 루트 폴더를 의미한다.

예:

```text
/path/to/my-model-project
/path/to/customer-churn-model
/path/to/ai-studio-model
```

## 핵심 목표

ML 개발자가 챗봇을 통해 다음 작업을 순서대로 수행할 수 있게 한다.

```text
1. 환경 검증
2. 샘플 규격 확인/보충
3. 환경 변수 입력/export
4. 패키지 설치
5. 모델 실행 및 원격 MLflow 기록
6. 산출물 확인
```

## 핵심 분기

가장 중요한 판단은 모델 프로젝트 폴더 안에 실행 가능한 모델이 있는지 여부다.

```text
모델이 있음
  -> 사용자가 지정한 모델 프로젝트 폴더를 분석해서 그대로 실행한다.

모델이 없음
  -> 사용자에게 .opencode/samples 아래 샘플 3개 중 하나를 선택하게 한다.
  -> 선택한 샘플 폴더를 워크스페이스 아래로 폴더째 복사한다.
  -> 복사된 샘플로 모델을 생성하고 테스트한다.
```

모델이 발견된 경우에는 샘플 선택 질문을 하지 않는다. 샘플 선택 질문은 `model_found: false`인 경우에만 출력한다.

초기 요청이 넓더라도 항상 아래 순서로 응답한다.

```text
1. 워크스페이스 분석
2. 모델 있음 / 모델 없음 판정
3. 모델 있음이면 기존 모델 진행 가이드
4. 모델 없음이면 sklearn/pytorch/tensorflow 선택 가이드
5. 사용자가 선택하면 샘플 폴더째 복사
6. TODO Guide 6단계로 진행
```

사용자 선택 샘플은 아래 3개만 사용한다.

```text
1. sklearn    - .opencode/samples/sklearn_sample
2. pytorch    - .opencode/samples/pytorch_sample
3. tensorflow - .opencode/samples/tensorflow_sample
```

다른 샘플은 임의로 선택하지 않는다. 선택형 샘플은 `aiu_custom/`, `local_serving/`, `saved_model/` 기본 폴더가 원본에 있어야 한다.

아래 폴더는 폐쇄망에서 사용자가 직접 모델 코드와 데이터를 넣는 기본 모델 슬롯이며, 워크스페이스에 모델이 없을 때 선택해서 폴더째 복사한다.

```text
sklearn_sample/
pytorch_sample/
tensorflow_sample/
```

## 필수 구성

모델 프로젝트 폴더에는 아래 폴더가 필수다.

```text
aiu_custom/
local_serving/
saved_model/
```

아래 폴더는 필수가 아니다.

```text
offline_weather_agent_core/
registry/
```

## ai_studio.env 필수 값

학습 모델 생성 전 `ai_studio.env`가 필요하다.

파일:

```text
ai_studio.env
```

필수 키:

```env
mlflow_tracking_url=""
mlflow_tracking_username=""
mlflow_tracking_password=""
mlflow_experiment_name=""
mlflow_register_model_name=""
```

검증 시 값 자체는 출력하지 않는다. 상태만 표시한다.

```text
set
empty
missing
```

`mlflow_tracking_password` 값도 절대 출력하지 않는다.

## 전체 흐름

```text
Step 0  Sample Bootstrap
        모델이 없으면 사용자에게 sklearn/pytorch/tensorflow 중 하나를 선택하게 한다.
        모델이 있으면 이 단계를 건너뛴다.
        선택한 샘플 폴더를 워크스페이스 아래로 폴더째 복사한다.

Step 1  Project Analyze
        사용자가 지정한 모델 프로젝트 폴더를 분석한다.
        모델이 있으면 기존 프로젝트를 실행 대상으로 정한다.
        모델이 없으면 Step 0 샘플 선택/복사 흐름으로 이동한다.

Step 2  Environment Check
        Python, dependency, MLflow, ai_studio.env 상태를 확인한다.

Step 3  Train Model
        기존 모델을 실행하거나 선택된 샘플로 모델을 생성한다.

Step 4  Inference Test
        생성된 모델을 로드하고 input_example 기반 predict를 검증한다.
```

## Step 1. 프로젝트 구조 분석

Skill:

```text
agent-mlflow-skill-project-analyze
```

### 목적

사용자가 지정한 모델 프로젝트 폴더가 실행 가능한 ML 프로젝트인지 판단한다.

이 단계에서는 원칙적으로 코드를 실행하지 않는다. 파일과 폴더 구조를 읽고 이후 실행 경로를 결정한다.

### 확인 항목

```text
requirements.txt
pyproject.toml
environment.yml
train.py
scripts/train.py
run_model.py
predict.py
input_example.json
ai_studio.env
aiu_custom/
aiu_custom/model_wrapper.py
aiu_custom/predict.py
local_serving/
saved_model/
MLmodel
python_model.pkl
```

### 모델 있음 판단

아래 중 하나 이상이 있으면 모델 프로젝트가 있다고 본다.

```text
학습 entrypoint
  - train.py
  - scripts/train.py

실행/등록 entrypoint
  - run_model.py

추론 entrypoint
  - predict.py

필수 폴더
  - aiu_custom/
  - local_serving/
  - saved_model/

pyfunc wrapper
  - aiu_custom/model_wrapper.py
  - aiu_custom/predict.py

MLflow model
  - MLmodel
  - python_model.pkl

테스트 입력
  - input_example.json
```

모델이 있으면 `.opencode/samples`를 보지 않는다.

출력 예:

```text
model_found: true
selected_project_path: <model-project-folder>
framework: sklearn | pytorch | tensorflow | huggingface | custom_pyfunc | unknown
train_entrypoint: train.py | scripts/train.py | run_model.py | null
inference_entrypoint: predict.py | aiu_custom/model_wrapper.py | local_serving/ | null
required_dirs:
  aiu_custom: set | missing
  local_serving: set | missing
  saved_model: set | missing
input_example_path: input_example.json | null
next_action:
  1. 환경 검증
  2. 샘플 규격 확인/보충
  3. 환경 변수 입력/export
  4. 패키지 설치
  5. 모델 실행 및 원격 MLflow 기록
  6. 산출물 확인
```

### 모델 없음 판단

모델 프로젝트로 볼 근거가 없으면 사용자에게 샘플 3개 중 하나를 선택하게 한다.

선택지:

```text
1. sklearn    - .opencode/samples/sklearn_sample
2. pytorch    - .opencode/samples/pytorch_sample
3. tensorflow - .opencode/samples/tensorflow_sample
```

선택한 샘플은 워크스페이스 아래에 샘플 폴더째 복사한다. 워크스페이스에 기존 파일이 있어도 대상 샘플 폴더가 없으면 복사할 수 있으며, 같은 이름의 샘플 폴더가 있으면 기본적으로 중단한다.

출력 예:

```text
model_found: false
sample_options: sklearn, pytorch, tensorflow
selected_sample: sklearn
sample_source_path: .opencode/samples/sklearn_sample
target_project_path: <model-project-folder>/sklearn_sample
copy_mode: folder
next_action:
  1. 환경 검증
  2. 샘플 규격 확인/보충
  3. 환경 변수 입력/export
  4. 패키지 설치
  5. 모델 실행 및 원격 MLflow 기록
  6. 산출물 확인
```

### Step 1 출력

```text
선택된 프로젝트 경로
model_found 여부
framework 후보와 근거
학습 entrypoint 후보
추론 entrypoint 후보
필수 폴더 존재 여부
input_example 존재 여부
ai_studio.env 존재 여부
모델이 없을 때 선택된 샘플 정보
다음 단계
```

## Step 2. 실행 환경 검증

Skill:

```text
agent-mlflow-skill-environment-check
```

### 목적

Step 1에서 선택된 실행 대상이 실제로 실행 가능한 환경인지 확인한다.

### 확인 항목

```text
Python 실행 파일
Python version
venv 또는 conda 사용 여부
requirements.txt / pyproject.toml / environment.yml
mlflow 설치 여부
mlflow version
framework dependency 설치 여부
ai_studio.env 필수 키 상태
```

### ai_studio.env 검증

아래 키를 확인한다.

```text
mlflow_tracking_url
mlflow_tracking_username
mlflow_tracking_password
mlflow_experiment_name
mlflow_register_model_name
```

값은 출력하지 않고 상태만 출력한다.

```text
set
empty
missing
```

### Step 2 출력

```text
Python 환경 요약
dependency 파일 존재 여부
설치된 핵심 dependency와 version
MLflow 설치/version 상태
ai_studio.env 필수 키 상태
로컬/원격 tracking target 판단
실행 전 차단 항목
다음 단계
```

### 실패 분류

```text
missing_dependency
version_mismatch
missing_env
config_error
tracking_unreachable
```

## Step 3. 로컬 학습 및 모델 생성

Skill:

```text
agent-mlflow-skill-train-model
```

### 목적

로컬에서 학습 또는 export를 실행해 모델 산출물이 생성되는지 확인한다.

### 기존 모델 프로젝트 실행

조건:

```text
model_found: true
```

동작:

```text
1. selected_project_path를 실행 기준 경로로 사용한다.
2. train_entrypoint 또는 run_model.py를 확인한다.
3. ai_studio.env 필수 키를 확인한다.
4. prepare-only, dry run, smoke test가 있으면 먼저 실행한다.
5. 실제 학습 또는 모델 export를 실행한다.
6. saved_model/에 모델 산출물이 생성되는지 확인한다.
7. Step 4에 model path와 input_example path를 넘긴다.
```

기존 모델 프로젝트가 있으면 선택형 샘플은 사용하지 않는다.

### 샘플 기반 모델 생성

조건:

```text
model_found: false
selected_sample: sklearn | pytorch | tensorflow
```

동작:

```text
1. sample_source_path를 확인한다.
2. target_project_path가 복사된 샘플 폴더인지 확인한다.
3. 샘플 원본은 직접 수정하지 않는다.
4. ai_studio.env 필수 키를 확인한다.
5. prepare-only 또는 smoke test가 있으면 먼저 실행한다.
6. 로컬 학습 또는 모델 export를 실행한다.
7. saved_model/에 모델 산출물이 생성되는지 확인한다.
8. Step 4에 model path와 input_example path를 넘긴다.
```

### 필수 산출물

```text
aiu_custom/
local_serving/
saved_model/
input_example.json
```

`saved_model/`에는 학습 또는 export 결과물이 있어야 한다.

### Step 3 출력

```text
기존 모델 프로젝트 실행 여부
샘플 기반 생성 여부
선택된 학습 entrypoint
선택된 샘플 이름과 프로젝트 루트
학습 실행 방식
생성된 saved_model 산출물
생성되지 않은 필수 산출물
학습 로그 요약
다음 단계
```

### 실패 분류

```text
missing_train_entrypoint
sample_not_found
sample_bootstrap_required
missing_dataset
missing_config
missing_env
artifact_not_created
artifact_invalid
runtime_error
```

## Step 4. 추론 테스트

Skill:

```text
agent-mlflow-skill-inference-test
```

### 목적

생성된 모델이 실제로 로드되고 predict 가능한지 확인한다.

### 확인 항목

```text
추론 entrypoint
  - aiu_custom/model_wrapper.py
  - aiu_custom/predict.py
  - local_serving/
  - predict.py

모델 경로
  - saved_model/

테스트 입력
  - input_example.json
```

### aiu_custom 계약

```text
ModelWrapper 클래스 존재
mlflow.pyfunc.PythonModel 상속
load_context 구현
predict 구현
saved_model/ 참조 경로 정상
```

### Step 4 출력

```text
선택된 추론 entrypoint
사용한 input_example
모델 로드 방식
추론 결과 요약
응답 schema
JSON 직렬화 가능 여부
MLflow pyfunc 호환 여부
다음 단계
```

### 실패 분류

```text
missing_inference_entrypoint
missing_input_example
model_load_error
predict_error
schema_error
serialization_error
```

## 스크립트 매핑

```text
Step 1  프로젝트 구조 분석
        .opencode/scripts/validate_mlflow_project.py

Step 2  실행 환경 검증
        .opencode/scripts/check_environment.py

Step 3  모델 실행 및 원격 MLflow 기록 확인
        .opencode/scripts/run_training.py
        .opencode/scripts/test_local_sample.py

Step 4  추론 테스트
        .opencode/scripts/test_inference.py
```

## 운영 원칙

- 사용자가 지정한 모델 프로젝트 폴더를 먼저 분석한다.
- 모델이 있으면 샘플을 사용하지 않는다.
- 모델이 없고 프로젝트 루트가 비어 있을 때만 sklearn, pytorch, tensorflow 중 하나를 사용자가 선택한다.
- 선택형 샘플 외 다른 샘플은 임의 선택하지 않는다.
- `offline_weather_agent_core/`, `registry/`는 필수 폴더가 아니다.
- `ai_studio.env` 값은 출력하지 않는다.
- `mlflow_tracking_password` 값은 절대 출력하지 않는다.
- 실제 학습/추론 실행은 사용자가 명확히 요청한 경우에만 수행한다.
- 샘플 원본은 직접 수정하지 않는다.
- 외부 다운로드나 원격 등록은 기본 동작으로 가정하지 않는다.

## 최종 확인 질문

6단계 TODO가 끝나면 아래 질문에 답할 수 있어야 한다.

```text
이 모델 프로젝트 폴더는 어떤 ML 프로젝트인가?
필수 폴더 aiu_custom/local_serving/saved_model이 있는가?
ai_studio.env 필수 키가 준비되었는가?
현재 환경에서 실행 가능한가?
학습 또는 export 후 saved_model/에 모델이 생성되는가?
생성된 모델은 실제로 추론 가능한가?
MLflow에 run/model/artifact 기록이 남는가?
```
