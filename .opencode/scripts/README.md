# OpenCode MLflow Scripts

이 폴더는 `.opencode/skills`의 MLflow 흐름을 보조하는 로컬 스크립트를 포함한다. 모델이 있으면 현재 프로젝트 루트 바로 아래와 `data/**` 모델 목록 확인부터 시작하는 7단계, 모델이 없으면 샘플 복사 후 6단계로 진행한다.

대상은 사용자가 지정한 모델 프로젝트 폴더다.
사용자 모델 파일은 현재 프로젝트 루트 바로 아래 또는 현재 프로젝트의 `data/**` 하위 트리 어디에나 둘 수 있으며, 자동 준비 시 모델 파일을 템플릿 폴더로 복사하지 않고 선택한 원본 경로에 연결하도록 코드를 변환한다.
`data/` 아래 폴더명은 고정값이 아니며 사용자 프로젝트마다 다를 수 있다.
예: `model.joblib`, `data/<임의폴더>/model.joblib`, `data/sklearn/model.pkl`, `data/checkpoints/model.pt`
모델 있음 흐름에서는 `.opencode/samples/aiu_studio/` 내부 파일/폴더를 워크스페이스 루트로 복사한다. `aiu_custom/` 내부 템플릿 파일과 `requirements.txt`도 워크스페이스 루트로 함께 복사된다. 내부 파일 구성은 고정하지 않고 비교/수정하지 않는다.
기존 `runtest.py`는 루트에서 참조하고, 수정하지 않고 복사된 템플릿 파일들을 선택 모델 원본 경로 기준으로 변환/갱신한다.
Linux 경로에 Windows 구분자(`\`, `＼`, `￦`, `₩`)가 섞이면 생성 파일에서 `/`로 자동 정규화한다.

유지보수자는 먼저 `.opencode/scripts/MAINTENANCE.md`를 확인한다. 각 스크립트의 책임, 주요 함수, 수정 포인트, 주의사항을 파일별로 정리해두었다.

## Script Mapping

```text
Step 1  모델 목록 확인
        prepare_selected_model.py
        validate_mlflow_project.py

Step 2  모델 경로로 선택
        prepare_selected_model.py

Step 3  선택 모델 환경 변환
        prepare_selected_model.py

Step 4  모델 환경변수 체크
        check_environment.py
        오류 사항이 있으면 경로/환경변수/패키지/버전 기준 서버 배포 오류사항 목록을 함께 보여준다.

Step 5  원격 MLflow 등록 실행
        runtest_2.py
        input_example.json은 워크스페이스 루트의 input_example.json에 있어야 하며, 상대경로 산출물도 워크스페이스 루트 아래에 생성되도록 실행 시 작업 디렉터리를 프로젝트 루트로 고정한다.

Step 6  추론 스모크 테스트
        local_serving/localservingtest.py

Step 7  MLflow 검증
Step 8  오류 수정 및 재검증
        원격 MLflow 등록, 추론 스모크 테스트, MLflow 검증 중 오류가 있으면 서버 배포 오류사항과 Failures를 기준으로 수정한 뒤 실패한 단계부터 다시 실행한다.
        verify_mlflow.py
```

화면에 표시된 모델 번호나 TOD 단계 번호는 숫자 키로 입력하면 바로 선택/실행한다.

기존 모델 흐름에서 `runtest_2.py`가 있으면 AIU Studio 빌드 모드 숫자 입력은 TOD 단계로 처리한다.

```text
3 -> python .opencode/scripts/prepare_selected_model.py --project . --model selected --execute
4 -> python .opencode/scripts/check_environment.py --project . --entrypoint runtest_2.py
5 -> python runtest_2.py
6 -> python local_serving/localservingtest.py
7 -> python .opencode/scripts/verify_mlflow.py --tracking-uri <tracking-uri> --experiment-name <experiment-name>
```

Windows PowerShell에서는 선택 프로젝트의 실행 폴더로 이동한 뒤 실행한다.

```powershell
cd '<selected-project-path>\aiu_studio'
python runtest_2.py

cd '<selected-project-path>\aiu_studio\local_serving'
python localservingtest.py

cd '<selected-project-path>'
python '<opencode-package-path>\.opencode\scripts\verify_mlflow.py' --project '<selected-project-path>' --tracking-uri <tracking-uri> --experiment-name <experiment-name>
```

`5`는 모델 환경변수 체크이며, MLflow 입력값 3개와 자동값 2개를 `set`, `empty`, `missing`, `auto_default` 상태로만 표시한다. secret 값은 출력하지 않는다.

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
python .opencode/scripts/response_speed_check.py --project .
```

그 다음 ignore 파일을 적용한다.

```text
python .opencode/scripts/apply_index_ignore.py --project .
```

이 명령은 워크스페이스 루트의 `.ignore`, `.rgignore`, `.gitignore`에 관리 블록을 추가한다. 제외 대상은 `.venv/`, `node_modules/`, `ai_studio/tracking/`, `ai_studio/code/`, `saved_model/`, `datasets/`, `*.pt`, `*.pkl`, `*.safetensors`, `*.bst`, `*.ubj` 같은 생성물과 대용량 모델 파일이다. `.opencode` 경로는 제외 패턴에 넣지 않는다.

자세한 운영 기준은 `.opencode/performance/CLOSED_NETWORK_SPEED.md`를 본다.

## Scripts

### doctor.py

AIU Studio/빌드/skills/sample/env 상태를 한 화면에서 점검한다. 주니어 QA나 폐쇄망 Windows에서 먼저 실행하기 좋다.

```text
python .opencode/scripts/doctor.py --workspace . --project .
python .opencode/scripts/doctor.py --workspace . --project <model-project-folder> --entrypoint runtest.py
python .opencode/scripts/doctor.py --workspace . --project <model-project-folder> --entrypoint run.py
python .opencode/scripts/doctor.py --workspace . --project <model-project-folder> --json
```

확인 항목:

```text
1. OpenCode 패키지/opencode.json/01~06 스킬 폴더
2. Python 3.11.9 환경
3. requirements.txt 패키지 설치/버전 상태
4. model_artifact_paths와 MODEL_KIND
5. 실행 파일 확정
6. AIU Studio 코드 적합성
7. 샘플 규격 폴더/파일
8. MLflow 입력값 3개와 자동값 2개 확인/export
9. 루트/data 모델 원본 경로와 모델/메트릭/코드 산출물
```

### prepare_selected_model.py

현재 프로젝트 루트 바로 아래와 `data/**` 아래 모델 파일 목록을 만들고, 사용자가 선택한 모델 기준으로 `.opencode/samples/aiu_studio/` 내부 파일/폴더를 워크스페이스 루트로 복사한 뒤 선택 모델 실행/등록에 필요한 연결부만 안전하게 변환해줘.
`requirements.txt`는 AIU Studio 환경 고정 버전 세트 기준으로 갱신한다. 모든 패키지는 `==`로 고정한다.
`runtest_2.py`는 외부 데이터셋을 다운로드하지 않고 MODEL_KIND에 맞는 synthetic `input_example.json`을 생성한다.
기존 `runtest.py`는 수정하지 않는다.
PyTorch/safetensors 모델은 `.opencode/samples/pytorch_sample/` 내부를 참조해서 선택 모델 실행/등록에 필요한 연결부만 안전하게 변환해줘.
선택 모델 경로와 `MODEL_KIND`를 반영한다.
`runtest_2.py` 생성 시퀀스는 `모델 선택 -> 모델 형식 확인 -> .opencode/samples/aiu_studio/ 내부 파일/폴더를 워크스페이스 루트로 복사 -> samples/pytorch_sample/ 내부 참조(복사 금지) -> 선택 모델 경로와 MODEL_KIND를 반영한 연결부 변환 -> 변환 결과 검증` 순서로 수행한다.

```text
python .opencode/scripts/prepare_selected_model.py --project <model-project-folder>
python .opencode/scripts/prepare_selected_model.py --project <model-project-folder> --model 1 --execute
python .opencode/scripts/prepare_selected_model.py --project <model-project-folder> --model model.joblib --execute
python .opencode/scripts/prepare_selected_model.py --project <model-project-folder> --model data/<임의폴더>/model.joblib --execute
python .opencode/scripts/prepare_selected_model.py --project <model-project-folder> --model data/torch/model.pt --execute
python .opencode/scripts/prepare_selected_model.py --project <model-project-folder> --model selected --execute
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
python .opencode/scripts/adapt_ai_studio.py --project <model-project-folder> --entrypoint run.py
python .opencode/scripts/adapt_ai_studio.py --project <model-project-folder> --entrypoint run.py --execute
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
python .opencode/scripts/validate_mlflow_project.py --project <model-project-folder>
python .opencode/scripts/validate_mlflow_project.py --project <model-project-folder> --json
```

### bootstrap_sample_project.py

모델 프로젝트 폴더에 실행 가능한 모델이 없을 때, 샘플 3개 중 하나를 선택해 워크스페이스 아래로 샘플 폴더째 복사한다.

선택 가능한 샘플은 원본에 `aiu_custom/`, `local_serving/`, `saved_model/` 기본 폴더가 있어야 한다.

샘플 목록:

```text
python .opencode/scripts/bootstrap_sample_project.py --list
```

복사 전 확인:

```text
python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample sklearn
python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample pytorch
python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample tensorflow
```

실제 폴더 복사:

```text
python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample sklearn --execute
```

기존 모델이 있지만 샘플 규격 폴더/파일이 부족한 경우, 기존 모델 파일을 덮어쓰지 않고 없는 골격만 복사한다.

```text
python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample pytorch --scaffold-existing --execute
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
python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample sklearn --execute --force
```

### check_environment.py

Python 3.11.9, dependency, MLflow 3.13.0, 원격 MLflow 서버 version, `ai_studio.env` 상태를 확인한다.
Python 기준 버전은 3.11.9이다. 다른 버전이면 `version_mismatch:python`으로 분류한다.
`requirements.txt`가 있으면 필요한 pip 패키지 목록, 현재 설치 여부, 설치된 버전, 요구 버전, 버전 불일치 여부를 함께 출력한다.
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
`mlflow_tracking_url`은 `http://`, `https://`, `file://`를 사용할 수 있다.
환경 변수 입력 후 `run_model.py`는 설정 블록 값을 아래 환경 변수로 export한다.

```text
mlflow_tracking_url -> MLFLOW_TRACKING_URI
mlflow_tracking_username -> MLFLOW_TRACKING_USERNAME
mlflow_tracking_password -> MLFLOW_TRACKING_PASSWORD
mlflow_experiment_name -> MLFLOW_EXPERIMENT_NAME
mlflow_register_model_name -> MLFLOW_REGISTER_MODEL_NAME
```

원격 배포 기본값은 `mlflow_tracking_url = ""`이다. 자동 tracking URI를 넣지 않으므로 사용자가 직접 원격 MLflow tracking 서버 URL을 입력해야 한다. MLflow artifact는 `artifact_path="ai_studio"` 아래 `ai_studio/code` 구조로 기록하고, 확인용 산출물은 `ai_studio/metrics/`, `ai_studio/code/`에 생성한다.

PyTorch 샘플 기본값은 `mlflow_experiment_name=pytorch_sample`, `mlflow_register_model_name=pytorch_sample_model`이다.
`mlflow_tracking_password` 값은 출력하지 않는다.

```text
python .opencode/scripts/check_environment.py --project <model-project-folder>
python .opencode/scripts/check_environment.py --project <model-project-folder> --entrypoint run.py
python .opencode/scripts/check_environment.py --project <model-project-folder> --json
```

### run_training.py

기존 모델 프로젝트를 실행한다. 모델이 없고 샘플을 가져와야 하면 먼저 `bootstrap_sample_project.py`로 사용자가 선택한 샘플 폴더를 복사한다.

기본값은 안전 모드다. 실제 실행은 `--execute`를 명시해야 한다.
실행 전 `ai_studio.env` 필수 키가 있는지 확인한다.

```text
python .opencode/scripts/run_training.py --project <model-project-folder>
python .opencode/scripts/run_training.py --project <model-project-folder> --execute
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
python .opencode/scripts/test_local_sample.py --sample sklearn
python .opencode/scripts/test_local_sample.py --sample all
```

### local_serving/localservingtest.py

`prepare_selected_model.py --execute`가 생성하는 선택 모델 기준 추론 테스트 파일이다. 선택 모델 경로, `MODEL_KIND`, `load_selected_model()`이 반영된다.

기본 실행은 화면 출력만 수행하며 프로젝트 루트 `local_serving/` 폴더를 만들지 않는다.

PowerShell에서는 선택 프로젝트의 `local_serving` 폴더로 이동한 뒤 실행한다.

```powershell
cd '<selected-project-path>\aiu_studio\local_serving'
python localservingtest.py
```

### verify_mlflow.py

MLflow experiment, run, artifact, registered model 상태를 확인한다.

```text
python .opencode/scripts/verify_mlflow.py --tracking-uri http://127.0.0.1:5000 --experiment-name <name>
python .opencode/scripts/verify_mlflow.py --tracking-uri http://127.0.0.1:5000 --experiment-id <id> --registered-model <model-name>
```

## Safety

- 실제 학습/추론 실행은 `--execute`가 있을 때만 수행한다.
- secret 값은 출력하지 않는다.
- 샘플 원본은 직접 수정하지 않는다.
- 모델 프로젝트 폴더에 기존 작업 경로가 있으면 기본적으로 덮어쓰지 않는다.
