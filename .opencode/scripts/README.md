# OpenCode MLflow Scripts

이 폴더는 `.opencode/skills`의 MLflow 흐름을 보조하는 로컬 스크립트를 포함한다. 모델이 있으면 모델 목록 확인부터 시작하는 7단계, 모델이 없으면 샘플 복사 후 6단계로 진행한다.

대상은 사용자가 지정한 모델 프로젝트 폴더다.
사용자 모델 파일은 현재 프로젝트 루트 바로 아래 또는 현재 프로젝트의 `data/**` 하위 트리 어디에나 둘 수 있으며, 자동 준비 시 모델 파일을 템플릿 폴더로 복사하지 않고 선택한 원본 경로에 연결하도록 코드를 변환한다.
`data/` 아래 폴더명은 고정값이 아니며 사용자 프로젝트마다 다를 수 있다.
예: `model.joblib`, `data/<임의폴더>/model.joblib`, `data/sklearn/model.pkl`, `data/checkpoints/model.pt`
모델 있음 흐름에서는 기존 `runtest.py`를 워크스페이스 루트에서 읽기 전용으로 참조하고, 선택 모델 기준 `runtest_2.py`만 생성/갱신한다.
`aiu_custom/`, `local_serving/`, `saved_model/`, `config/`, `requirements.txt`, `input_example.json`은 모델 선택 단계에서 자동 생성하지 않는다.
모델 선택 명령은 1~3번 흐름을 한 번에 수행한다. `--sync-runtime`은 이미 생성된 `runtest_2.py` 기준으로 런타임 파일을 다시 맞출 때만 사용한다.
기존 `runtest.py`는 수정하지 않는다.
선택 모델에 맞는 실행/등록 파일은 `runtest_2.py`로만 변환 생성한다.
Linux 경로에 Windows 구분자(`\`, `＼`, `￦`, `₩`)가 섞이면 생성 파일에서 `/`로 자동 정규화한다.

스킬 목록 기준 스크립트 정리는 `.opencode/scripts/SCRIPT_INDEX.md`를 먼저 본다.
유지보수자는 `.opencode/scripts/MAINTENANCE.md`에서 각 스크립트의 책임, 주요 함수, 수정 포인트, 주의사항을 확인한다.

## Skill Script Map

먼저 이 표만 봅니다. 스킬에서 직접 쓰는 대표 스크립트는 아래 흐름으로 고정합니다.
실제 구현 파일은 스킬 목록 기준 폴더에 있습니다. 실행도 해당 폴더 경로를 직접 사용합니다.
도구가 읽을 수 있는 같은 매핑은 `.opencode/scripts/skill_script_map.json`에 있습니다.
사람이 읽는 상세 정리표는 `.opencode/scripts/SCRIPT_INDEX.md`에 있습니다.

```text
01 Project Analyze
   01-project-analyze/launch_workspace_summary.py     첫 진입 가벼운 요약
   01-project-analyze/validate_mlflow_project.py      상세 분석
   04-train-model/prepare_selected_model.py           모델 목록/선택

02 Sample Bootstrap
   02-sample-bootstrap/bootstrap_sample_project.py    sklearn/pytorch/tensorflow 샘플 복사

03 Environment Check
   03-environment-check/check_environment.py          Python, requirements.txt, MLflow 설정 확인
   03-environment-check/response_speed_check.py       폐쇄망 속도 진단
   03-environment-check/apply_index_ignore.py         인덱싱 제외 적용

04 Train Model / Selected Model Build
   04-train-model/prepare_selected_model.py           runtest.py 참조 + runtest_2.py 변환 생성
   04-train-model/run_training.py                     확정 entrypoint 실행
   04-train-model/adapt_ai_studio.py                  사용자 임의 run.py 보강용 보조 스크립트

05 Inference Test
   05-inference-test/test_inference.py                수동 추론 계약 점검
   generated: local_serving/localservingtest.py

QA / Maintenance
   qa-maintenance/doctor.py                           전체 상태 1페이지 점검
   qa-maintenance/test_local_sample.py                번들 샘플 QA
   SCRIPT_INDEX.md                 스킬 목록 기준 스크립트 정리표
   MAINTENANCE.md                  유지보수 상세 문서
```

## TODO Script Map

사용자에게 보이는 TODO 단계는 아래 스크립트로 연결합니다.

```text
1. 모델 목록 확인                  -> prepare_selected_model.py
2. 모델 선택                       -> prepare_selected_model.py --model <번호|경로>
3. 템플릿 변환                     -> 템플릿 복사 + 복사된 템플릿 기준 연결부 수정
4. 환경변수/requirements 갱신      -> check_environment.py --entrypoint runtest_2.py
5. 학습 실행 및 원격 MLflow 등록   -> python runtest_2.py
6. 추론 테스트                     -> 사용자가 6번 선택 시 python local_serving/localservingtest.py
7. 오류 수정 및 재실행             -> Failures 기준으로 실패한 단계부터 재실행
```

화면에 표시된 모델 번호나 TODO 단계 번호는 숫자 키로 입력하면 바로 선택/실행한다.
모델은 처음 선택한 값으로 고정된다. 이후 다른 숫자를 눌러도 기존 선택 모델을 유지하고, 나머지 단계도 같은 모델 기준으로 진행한다.
고정 기준은 `aiu_custom/mapping.json`의 `model.source_path`다. `runtest_2.py` 안의 모델 경로는 변환 결과물일 뿐 선택 기준으로 사용하지 않는다.

기존 모델 흐름에서 `runtest_2.py`가 있으면 AIU Studio 빌드 모드 숫자 입력은 TODO 단계로 처리한다.

```text
1~3 -> python .opencode/scripts/04-train-model/prepare_selected_model.py --project . --model <번호|경로> --execute
4 -> python .opencode/scripts/03-environment-check/check_environment.py --project . --entrypoint runtest_2.py
5 -> python runtest_2.py
6 -> 사용자가 선택하면 python local_serving/localservingtest.py
7 -> Failures와 오류 메시지 기준으로 수정 후 실패한 단계부터 재실행
```

Windows PowerShell에서는 선택 프로젝트의 실행 폴더로 이동한 뒤 실행한다.

```powershell
cd '<selected-project-path>\aiu_studio'
python runtest_2.py

cd '<selected-project-path>\local_serving'
python localservingtest.py
```

`1~3`은 모델 선택 명령 한 번으로 모델 목록 확인 -> 모델 선택 -> 템플릿 복사와 복사된 템플릿 기준 연결부 수정 흐름으로 진행한다. 이 단계에서 `requirements.txt` 재정의/확인도 함께 처리한다. 필수 패키지 5개는 항상 유지하고, 모델별 추가 패키지만 뒤에 반영한다.
필수 패키지 기준은 `03-environment-check/requirements.required.txt`에서 관리한다.

`9`는 모델 환경변수와 패키지 상태 체크다. 변환된 코드 import 기준 추가 Python 패키지가 필요하면 `requirements.txt`를 업데이트하고, 이때도 필수 패키지 5개는 절대 제거하지 않는다. MLflow 입력값 3개와 자동값 2개는 `set`, `empty`, `missing`, `auto_default` 상태로만 표시한다. secret 값은 출력하지 않는다.

패키지 설치 기준:

```text
JavaScript 프로젝트(package.json 있음) -> npm i
Python 샘플/모델(requirements.txt 있음) -> python -m pip install -r requirements.txt
폐쇄망 WSL(wheelhouse 있음) -> bash .opencode/wsl/install_offline.sh
온라인 WSL(wheelhouse 준비) -> 내부 http:// PyPI 미러 설정 후 bash .opencode/wsl/download_wheels.sh
PyTorch CPU wheel Nexus upstream -> https://download.pytorch.org/whl/cpu
torch SSL 설치 금지 -> https://download.pytorch.org, https://pypi.org 인덱스를 쓰지 않고 wheelhouse 또는 http:// 내부 미러만 사용
Bun 사용 금지 -> opencode Bun 런타임이 파일 트리 오류 처리 중 세그멘테이션 폴트를 낼 수 있으므로 bun, bunx, bun install, bun run 실행하지 않음
```

폐쇄망 WSL 설치 파일은 `.opencode/wsl/`에 있다.

## Closed-Network Response Speed

OpenCode가 폐쇄망 WSL/Windows에서 응답하거나 파일 트리를 인덱싱하는 속도가 느리면 먼저 진단을 실행한다.

```text
python .opencode/scripts/03-environment-check/response_speed_check.py --project .
```

그 다음 ignore 파일을 적용한다.

```text
python .opencode/scripts/03-environment-check/apply_index_ignore.py --project .
```

이 명령은 워크스페이스 루트의 `.ignore`, `.rgignore`, `.gitignore`에 관리 블록을 추가한다. 제외 대상은 `.opencode/`, `.opencode/node_modules/`, `.venv/`, `node_modules/`, `ai_studio/tracking/`, `ai_studio/code/`, `saved_model/`, `datasets/`, `*.pt`, `*.pkl`, `*.safetensors`, `*.bst`, `*.ubj` 같은 스킬 번들/생성물/대용량 모델 파일이다.

자세한 운영 기준은 `.opencode/performance/CLOSED_NETWORK_SPEED.md`를 본다.

## Scripts

### doctor.py

AIU Studio/빌드/skills/sample/env 상태를 한 화면에서 점검한다. 주니어 QA나 폐쇄망 Windows에서 먼저 실행하기 좋다.

```text
python .opencode/scripts/qa-maintenance/doctor.py --workspace . --project .
python .opencode/scripts/qa-maintenance/doctor.py --workspace . --project <model-project-folder> --entrypoint runtest.py
python .opencode/scripts/qa-maintenance/doctor.py --workspace . --project <model-project-folder> --entrypoint run.py
python .opencode/scripts/qa-maintenance/doctor.py --workspace . --project <model-project-folder> --json
```

확인 항목:

```text
1. OpenCode 패키지/opencode.json/01~06 스킬 폴더
2. Python 3.11.9 환경
3. requirements.txt 패키지 설치/버전 상태
4. model_artifact_paths와 MODEL_KIND
5. 실행 파일 확정
6. AIU Studio 코드 적합성
7. MLflow 입력값 3개와 requirements.txt 상태
```

### prepare_selected_model.py

현재 프로젝트 루트 바로 아래와 `data/**` 아래 모델 파일 목록을 만들고, 사용자가 선택한 모델 기준으로 기존 `runtest.py`를 참조해 `runtest_2.py`만 생성/갱신한다.
`runtest_2.py`는 외부 데이터셋을 다운로드하지 않고 MODEL_KIND에 맞는 synthetic `input_example.json`을 생성한다.
기존 `runtest.py`는 수정하지 않고 참조만 한다.
PyTorch/safetensors 모델은 `.opencode/samples/pytorch_sample/` 내부를 참조해서 선택 모델 실행/등록에 필요한 연결부만 안전하게 변환해줘.
선택 모델 경로와 `MODEL_KIND`를 반영한다.
`runtest_2.py` 생성 시퀀스는 `모델 선택 -> 모델 형식 확인 -> 기존 runtest.py 읽기 전용 참조 -> 선택 모델 경로와 MODEL_KIND를 반영한 연결부 변환 -> 변환 결과 검증` 순서로 수행한다.

```text
python .opencode/scripts/04-train-model/prepare_selected_model.py --project <model-project-folder>
python .opencode/scripts/04-train-model/prepare_selected_model.py --project <model-project-folder> --model 1 --execute
python .opencode/scripts/04-train-model/prepare_selected_model.py --project <model-project-folder> --model model.joblib --execute
python .opencode/scripts/04-train-model/prepare_selected_model.py --project <model-project-folder> --model data/<임의폴더>/model.joblib --execute
python .opencode/scripts/04-train-model/prepare_selected_model.py --project <model-project-folder> --model data/torch/model.pt --execute
python .opencode/scripts/04-train-model/prepare_selected_model.py --project <model-project-folder> --model selected --execute
# 보정용: 이미 생성된 runtest_2.py 기준으로 런타임 파일만 다시 맞출 때 사용
python .opencode/scripts/04-train-model/prepare_selected_model.py --project <model-project-folder> --sync-runtime --execute
```

숫자 선택은 현재 출력된 `model_artifact_paths` 순서에 의존한다. 목록이 바뀔 수 있으므로 자동 준비/재실행에는 실제 모델 경로 또는 `--model selected`를 우선 사용한다.

출력 항목:

```text
model_artifact_paths
selected_model_path
MODEL_KIND
reference_entrypoint: runtest.py, run_test.py 중 하나
generated_entrypoint: runtest_2.py
```

지원 모델 형식:

```text
.pkl        -> sklearn_pickle
.joblib     -> sklearn_joblib
.pt, .pth   -> pytorch
.onnx       -> onnx
.keras      -> tensorflow_keras
.h5         -> tensorflow_h5
.safetensors -> safetensors
.bst        -> xgboost_bst
.ubj        -> xgboost_ubj
```

### adapt_ai_studio.py

사용자가 가져온 임의 Python 실행 파일을 AIU Studio/MLflow 연결 형식에 맞게 보강한다. 기본은 dry-run이며, `--execute`를 붙인 경우에만 실제 파일을 수정한다.
실행 파일을 찾지 못하면 자동 생성하지 않는다. 사용자가 실제 학습/모델 생성 Python 파일을 프로젝트에 직접 넣고 `--entrypoint <file>`로 지정해야 한다.
파일 후보가 여러 개일 때도 추측하지 않고 사용자가 직접 지정한다.

```text
python .opencode/scripts/04-train-model/adapt_ai_studio.py --project <model-project-folder> --entrypoint run.py
python .opencode/scripts/04-train-model/adapt_ai_studio.py --project <model-project-folder> --entrypoint run.py --execute
```

수정 방식:

```text
- entrypoint 백업 생성: <file>.ai_studio.bak
- MLflow 입력값 3개, 자동 생성값 2개, MLFLOW_* export helper 삽입
- ai_studio/metrics, ai_studio/code 경로 helper 삽입
- aiu_custom/predict.py, local_serving/serve.py, saved_model/, input_example.json 보충
- requirements.txt가 없으면 프레임워크/Import 기반 최소 패키지 작성
- 루트/data 모델 원본은 복사하거나 이동하지 않음
```

기존 파일은 기본적으로 덮어쓰지 않는다. 이미 adapter block이 있으면 `--force`가 없을 때 건너뛴다.

### validate_mlflow_project.py

모델 프로젝트 폴더를 분석한다.

```text
python .opencode/scripts/01-project-analyze/validate_mlflow_project.py --project <model-project-folder>
python .opencode/scripts/01-project-analyze/validate_mlflow_project.py --project <model-project-folder> --json
```

### bootstrap_sample_project.py

모델 프로젝트 폴더에 실행 가능한 모델이 없을 때, 샘플 3개 중 하나를 선택해 워크스페이스 아래로 샘플 폴더째 복사한다.

선택 가능한 샘플은 원본에 `aiu_custom/`, `local_serving/`, `saved_model/` 기본 폴더가 있어야 한다.

샘플 목록:

```text
python .opencode/scripts/02-sample-bootstrap/bootstrap_sample_project.py --list
```

복사 전 확인:

```text
python .opencode/scripts/02-sample-bootstrap/bootstrap_sample_project.py --project <model-project-folder> --sample sklearn
python .opencode/scripts/02-sample-bootstrap/bootstrap_sample_project.py --project <model-project-folder> --sample pytorch
python .opencode/scripts/02-sample-bootstrap/bootstrap_sample_project.py --project <model-project-folder> --sample tensorflow
```

실제 폴더 복사:

```text
python .opencode/scripts/02-sample-bootstrap/bootstrap_sample_project.py --project <model-project-folder> --sample sklearn --execute
```

기존 모델이 있지만 샘플 규격 폴더/파일이 부족한 경우, 기존 모델 파일을 덮어쓰지 않고 없는 골격만 복사한다.

```text
python .opencode/scripts/02-sample-bootstrap/bootstrap_sample_project.py --project <model-project-folder> --sample pytorch --scaffold-existing --execute
```

복사 대상은 소스 구조 중심이며 `.venv/`, `__pycache__/`, `model/`, `artifacts/ai_studio/`, `ai_studio/`, `mlflow.db` 같은 생성 산출물은 제외한다.

복사 후 `aiu_custom/`, `local_serving/`, `saved_model/` 필수 폴더는 항상 복사된 샘플 폴더 안에 보장한다.

복사 후 다음 단계는 아래 순서로 안내한다.

```text
1. 환경 검증
2. 샘플 규격 확인/보충
3. 환경 변수 입력/export
4. 패키지 설치
5. 모델 실행 및 원격 MLflow 기록
6. 산출물 확인
```

기존 파일이 있을 때 덮어쓰기는 사용자가 명시적으로 요청한 경우에만 사용한다.

```text
python .opencode/scripts/02-sample-bootstrap/bootstrap_sample_project.py --project <model-project-folder> --sample sklearn --execute --force
```

### check_environment.py

Python 3.11.9, dependency, MLflow 3.13.0, 원격 MLflow 서버 version, `ai_studio.env` 상태를 확인한다.
Python 기준 버전은 3.11.9이다. 다른 버전이면 `version_mismatch:python`으로 분류한다.
`requirements.txt`가 있으면 필요한 pip 패키지 목록, 현재 설치 여부, 설치된 버전, 요구 버전, 버전 불일치 여부를 함께 출력한다.
환경검증 화면에는 설치 기준 파일을 `requirements.txt`로 별도 표시한다.
환경검증은 복사 후 변환된 템플릿 파일들 가운데 실제 존재하는 Python 파일들의 import를 확인해 누락된 Python 패키지를 `requirements.txt`에 추가한다. 대표 예시는 `runtest_2.py`, `aiu_custom/model.py`, `aiu_custom/predict.py`, `local_serving/localservingtest.py`다. pip 설치는 자동 실행하지 않고 `python -m pip install -r requirements.txt` 명령만 안내한다.
`mlflow_tracking_url`이 있으면 원격 MLflow 서버의 `/version`을 확인하고, 서버 version과 로컬 `mlflow` 설치 version 및 `requirements.txt` 요구 version이 다르면 불일치로 표시한다.
Python 버전이 다르면 `차단 항목 요약`에 다음 형식으로 표시한다.

```text
1. Python 버전 차이 (<현재버전> vs 기대 3.11.9) → 호환성 확인 필요
```

Secret 값은 출력하지 않고 `set`, `empty`, `missing` 상태만 출력한다.

MLflow 인증용 환경 변수는 다음 이름을 사용한다.

```text
MLFLOW_TRACKING_URI
MLFLOW_TRACKING_USERNAME
MLFLOW_TRACKING_PASSWORD
MLFLOW_EXPERIMENT_NAME
MLFLOW_REGISTER_MODEL_NAME
MLFLOW_EXPERIMENT_ID
```

`MLFLOW_EXPERIMENT_PASSWORD`는 올바른 MLflow 인증 환경변수가 아니다.

학습 모델 생성 필수 파일:

```text
ai_studio.env
```

사용자가 직접 입력할 키:

```text
mlflow_tracking_url
mlflow_tracking_username
mlflow_tracking_password
```

자동 생성되는 키:

```text
mlflow_experiment_name
mlflow_register_model_name
```

작성 예시:

```text
mlflow_tracking_url=http://<tracking-server>
mlflow_tracking_username=
mlflow_tracking_password=
```

`mlflow_experiment_name`, `mlflow_register_model_name`은 선택 모델 파일명에서 확장자를 제거한 이름 기준으로 자동 생성한다. 사용자는 해당 파일의 MLflow/AIU Studio 설정 블록에 tracking URL, username, password만 직접 입력한다.
`mlflow_tracking_url`은 원격 MLflow/리포트 URL만 사용한다. `http://` 또는 `https://`를 입력하고, `file://` 로컬 tracking은 사용하지 않는다.
tracking URL, username, password 중 하나라도 비어 있으면 학습 테스트 실행을 중단한다. 사용자가 값을 직접 입력한 뒤 다시 실행한다.
환경 변수 입력 후 `run_model.py`는 설정 블록 값을 아래 환경 변수로 export한다.

```text
mlflow_tracking_url -> MLFLOW_TRACKING_URI
mlflow_tracking_username -> MLFLOW_TRACKING_USERNAME
mlflow_tracking_password -> MLFLOW_TRACKING_PASSWORD
mlflow_experiment_name -> MLFLOW_EXPERIMENT_NAME
mlflow_register_model_name -> MLFLOW_REGISTER_MODEL_NAME
```

원격 배포 기본값은 `mlflow_tracking_url = ""`이다. 자동 tracking URI나 로컬 테스트용 URI를 넣지 않으므로 사용자가 직접 원격 MLflow/리포트 URL을 입력해야 한다. MLflow artifact는 `artifact_path="ai_studio"` 아래 `ai_studio/code` 구조로 기록하고, 확인용 산출물은 `ai_studio/metrics/`, `ai_studio/code/`에 생성한다.

PyTorch 샘플 기본값은 `mlflow_experiment_name=pytorch_sample`, `mlflow_register_model_name=pytorch_sample_model`이다.
`mlflow_tracking_password` 값은 출력하지 않는다.

```text
python .opencode/scripts/03-environment-check/check_environment.py --project <model-project-folder>
python .opencode/scripts/03-environment-check/check_environment.py --project <model-project-folder> --entrypoint run.py
python .opencode/scripts/03-environment-check/check_environment.py --project <model-project-folder> --json
```

### run_training.py

기존 모델 프로젝트를 실행한다. 모델이 없고 샘플을 가져와야 하면 먼저 `bootstrap_sample_project.py`로 사용자가 선택한 샘플 폴더를 복사한다.

기본값은 안전 모드다. 실제 실행은 `--execute`를 명시해야 한다.
실행 전 `ai_studio.env` 필수 키가 있는지 확인한다.

```text
python .opencode/scripts/04-train-model/run_training.py --project <model-project-folder>
python .opencode/scripts/04-train-model/run_training.py --project <model-project-folder> --execute
```

폐쇄망 모델 선택 샘플:

```text
sklearn
pytorch
tensorflow
```

다른 샘플은 임의로 선택하지 않는다.

### test_local_sample.py

선택형 샘플 자체를 테스트한다.

```text
python .opencode/scripts/qa-maintenance/test_local_sample.py --sample sklearn
python .opencode/scripts/qa-maintenance/test_local_sample.py --sample all
```

### local_serving/localservingtest.py

`prepare_selected_model.py --execute`가 생성하는 선택 모델 기준 추론 테스트 파일이다. 선택 모델 경로, `MODEL_KIND`, `load_selected_model()`이 반영된다.

기본 실행은 화면 출력만 수행하며 프로젝트 루트 `local_serving/` 폴더를 만들지 않는다.

PowerShell에서는 선택 프로젝트의 `local_serving` 폴더로 이동한 뒤 실행한다.

```powershell
cd '<selected-project-path>\local_serving'
python localservingtest.py
```

## Safety

- 실제 학습/추론 실행은 `--execute`가 있을 때만 수행한다.
- secret 값은 출력하지 않는다.
- 샘플 원본은 직접 수정하지 않는다.
- 모델 프로젝트 폴더에 기존 작업 경로가 있으면 기본적으로 덮어쓰지 않는다.
