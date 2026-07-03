# MLflow 6단계 TODO Skill 아키텍처

이 문서는 MLflow 6단계 TODO Skill의 구조와 데이터 흐름을 설명한다.

대상은 **사용자가 지정한 모델 프로젝트 폴더**다.  
이 폴더는 ML 개발자가 실제로 작업하는 모델 코드 루트이며, 챗봇은 이 폴더를 기준으로 분석, 실행, 검증을 수행한다.

## 목적

이 아키텍처의 목적은 ML 개발자가 명령어와 MLflow 세부 구조를 몰라도 챗봇을 통해 아래 작업을 끝까지 수행하게 하는 것이다.

```text
모델 프로젝트 분석
실행 환경 검증
학습 또는 모델 export
추론 테스트
MLflow 기록 확인
```

## 상위 구조

```text
사용자
  |
  v
OpenCode Chatbot
  |
  v
.opencode/skills
  |
  v
.opencode/scripts
  |
  v
사용자가 지정한 모델 프로젝트 폴더
  |
  +-- ai_studio.env
  +-- aiu_custom/
  +-- local_serving/
  +-- saved_model/
  +-- input_example.json
  +-- train.py 또는 run_model.py
  |
  v
MLflow Tracking / Model Registry
```

## 핵심 원칙

```text
모델 프로젝트 폴더에 모델이 있으면
  -> 기존 프로젝트를 분석해서 실행한다.
  -> 샘플 선택 질문을 하지 않는다.

모델 프로젝트 폴더에 모델이 없으면
  -> 사용자가 sklearn/pytorch/tensorflow 샘플 3개 중 하나를 선택한다.
  -> 선택한 샘플 폴더를 워크스페이스 아래로 폴더째 복사한다.
  -> 모델을 생성하고 테스트한다.
```

선택형 샘플은 아래 3개만 허용한다.

```text
sklearn    -> .opencode/samples/sklearn_sample
pytorch    -> .opencode/samples/pytorch_sample
tensorflow -> .opencode/samples/tensorflow_sample
```

다른 샘플은 임의로 선택하지 않는다.

아래 폴더는 사용자가 폐쇄망에서 직접 모델 코드와 데이터를 넣는 기본 슬롯이며, 워크스페이스에 모델이 없을 때 선택해서 폴더째 복사한다.

```text
sklearn_sample/
pytorch_sample/
tensorflow_sample/
```

## 필수 프로젝트 계약

모델 프로젝트 폴더는 아래 계약을 만족해야 한다.

```text
<model-project-folder>/
├── ai_studio.env
├── aiu_custom/
├── local_serving/
├── saved_model/
├── input_example.json
└── train.py 또는 run_model.py
```

필수 폴더:

```text
aiu_custom/
local_serving/
saved_model/
```

필수 파일:

```text
ai_studio.env
input_example.json
```

`offline_weather_agent_core/`, `registry/`는 필수 폴더가 아니다.

## ai_studio.env 계약

`ai_studio.env`는 학습 모델 생성과 MLflow 등록에 필요한 설정을 담는다.

필수 키:

```env
mlflow_tracking_uri=""
mlflow_tracking_username=""
mlflow_tracking_password=""
mlflow_experiment_name=""
mlflow_register_model_name=""
```

검증 규칙:

```text
파일 없음
  -> missing_env_file:ai_studio.env

키 없음
  -> missing_env:<key>

키 값이 빈 문자열
  -> empty
  -> 학습 모델 생성 기준에서는 missing_env:<key>

값 존재
  -> set
```

보안 규칙:

```text
mlflow_tracking_password 값은 출력하지 않는다.
secret 값은 로그, 응답, trace에 출력하지 않는다.
상태만 set / empty / missing 으로 표시한다.
```

## 컴포넌트

### Skills

```text
.opencode/skills/
├── agent-mlflow-skill-project-analyze/
├── agent-mlflow-skill-environment-check/
├── agent-mlflow-skill-train-model/
└── agent-mlflow-skill-inference-test/
```

각 Skill은 챗봇이 어떤 기준으로 판단하고 어떤 출력을 해야 하는지 정의한다.

### Scripts

```text
.opencode/scripts/
├── validate_mlflow_project.py
├── bootstrap_sample_project.py
├── check_environment.py
├── run_training.py
├── test_inference.py
└── test_local_sample.py
```

각 Script는 Skill의 판단을 로컬에서 검증할 수 있는 실행 보조 도구다.

## 6단계 TODO 처리 흐름

```text
Step 1 Project Analyze
  |
  |-- validate_mlflow_project.py
  |
  |-- model_found=true
  |     -> 기존 프로젝트 실행 경로 선택
  |
  |-- model_found=false
        -> bootstrap_sample_project.py
        -> sklearn / pytorch / tensorflow 중 사용자 선택
        -> 선택한 샘플 폴더를 워크스페이스 아래로 복사

Step 2 Environment Check
  |
  |-- check_environment.py
  |
  |-- Python / dependency / MLflow 확인
  |-- ai_studio.env 필수 키 확인

Step 3 Train Model
  |
  |-- run_training.py
  |
  |-- 기존 프로젝트 학습 또는 export
  |-- 샘플 기반 모델 생성
  |-- saved_model/ 산출물 확인

Step 4 Inference Test
  |
  |-- test_inference.py
  |
  |-- aiu_custom 또는 local_serving 기반 추론
  |-- input_example.json 기반 predict 검증
```

## 상세 데이터 흐름

```text
사용자 지정 모델 프로젝트 폴더
  |
  v
Step 1 구조 분석
  |
  +-- 모델 있음
  |     |
  |     v
  |   기존 train.py / run_model.py / aiu_custom 분석
  |
  +-- 모델 없음
        |
        v
      sklearn / pytorch / tensorflow 사용자 선택
        |
        v
      <model-project-folder>/<sample-folder>/ 로 샘플 폴더 복사

Step 2 환경 검증
  |
  v
Python / dependency / ai_studio.env / MLflow 설정 확인
  |
  v
Step 3 학습 또는 export
  |
  v
saved_model/ 산출물 생성
  |
  v
Step 4 추론 테스트
  |
  v
input_example.json -> predict -> output schema 확인
  |
  v
Step 5 MLflow 확인
  |
  v
Run / artifact / pyfunc model / registered model 확인
```

## 폴더 책임

### aiu_custom/

MLflow pyfunc 또는 AI Studio custom model wrapper를 둔다.

권장 구성:

```text
aiu_custom/
├── __init__.py
└── model_wrapper.py
```

역할:

```text
ModelWrapper 제공
mlflow.pyfunc.PythonModel 상속
load_context 구현
predict 구현
saved_model/ 산출물 로드
```

### local_serving/

로컬 serving 테스트 코드를 둔다.

역할:

```text
로컬 API serving 확인
input_example.json 기반 요청 테스트
AI Studio endpoint 전환 전 로컬 검증
```

### saved_model/

학습 또는 export 결과물을 저장한다.

역할:

```text
학습된 모델 파일 저장
export된 모델 파일 저장
추론 테스트 대상 저장
MLflow logging source 후보
```

## Script 책임

### validate_mlflow_project.py

담당 단계:

```text
Step 1 Project Analyze
```

책임:

```text
모델 프로젝트 폴더 구조 분석
필수 폴더 확인
ai_studio.env 확인
framework 후보 판단
entrypoint 후보 판단
모델 있음/없음 판단
```

### check_environment.py

담당 단계:

```text
Step 2 Environment Check
```

책임:

```text
Python version 확인
venv/conda 확인
dependency 확인
MLflow 설치 확인
ai_studio.env 필수 키 확인
secret 값 비노출
```

### run_training.py

담당 단계:

```text
Step 3 Train Model
```

책임:

```text
기존 모델 프로젝트 실행 준비
샘플 기반 모델 생성 준비
--execute 명시 시 실제 실행
saved_model/ 산출물 확인
ai_studio.env 필수 키 확인
```

### test_inference.py

담당 단계:

```text
Step 4 Inference Test
```

책임:

```text
input_example.json 로드
aiu_custom wrapper 로드
MLflow pyfunc load_model 확인
predict 실행
응답 schema 확인
JSON 직렬화 가능 여부 확인
```

## 실패 분류

공통 실패 코드는 아래처럼 사용한다.

```text
missing_required_dir:<name>
missing_env_file:ai_studio.env
missing_env:<key>
missing_dependency
missing_train_entrypoint
sample_not_found
sample_bootstrap_required
artifact_not_created
artifact_invalid
missing_inference_entrypoint
missing_input_example
model_load_error
predict_error
schema_error
tracking_unreachable
experiment_missing
run_missing
artifact_missing
registry_missing
permission_error
```

## 실행 안전 정책

```text
분석은 기본 실행 가능
실제 학습 실행은 --execute 필요
실제 추론 실행은 --execute 필요
샘플 원본은 수정하지 않음
기존 작업 경로 덮어쓰기 전 확인
secret 값 출력 금지
폐쇄망 환경을 기본 전제로 함
외부 다운로드는 기본 동작으로 가정하지 않음
```

## AI Studio 연결 관점

AI Studio에서는 이 구조를 다음 화면으로 옮길 수 있다.

```text
모델 프로젝트 선택 화면
  -> 사용자가 모델 프로젝트 폴더 지정

프로젝트 분석 화면
  -> 필수 폴더, ai_studio.env, entrypoint 확인

환경 검증 화면
  -> Python, dependency, MLflow 설정 확인

학습 실행 화면
  -> train/export 실행 및 saved_model 산출물 확인

추론 테스트 화면
  -> input_example 기반 predict 검증

MLflow 기록 화면
  -> run, artifact, registered model 확인
```

## 최종 상태

6단계 TODO가 끝나면 시스템은 아래 내용을 판단할 수 있어야 한다.

```text
모델 프로젝트 폴더가 유효한가?
필수 폴더가 있는가?
ai_studio.env 필수 키가 있는가?
학습 또는 export가 가능한가?
saved_model/에 모델 산출물이 생성되는가?
input_example 기반 추론이 가능한가?
MLflow에 run/model/artifact 기록이 남는가?
```
