# OpenCode MLflow Scripts

이 폴더는 `.opencode/skills`의 MLflow 흐름을 보조하는 로컬 스크립트를 포함한다. 모델이 있으면 실행 파일 확정부터 시작하는 7단계, 모델이 없으면 샘플 복사 후 6단계로 진행한다.

대상은 사용자가 지정한 모델 프로젝트 폴더다.

유지보수자는 먼저 `.opencode/scripts/MAINTENANCE.md`를 확인한다. 각 스크립트의 책임, 주요 함수, 수정 포인트, 주의사항을 파일별로 정리해두었다.

## Script Mapping

```text
Step 1  프로젝트 구조 분석 / 실행 파일 확정
        validate_mlflow_project.py
        doctor.py
        bootstrap_sample_project.py

Step 2  실행 환경 검증
        check_environment.py

Step 3  환경 변수 입력/export

Step 4  패키지 설치

Step 5  로컬 학습 실행 및 모델 생성 확인
        run_training.py
        test_local_sample.py

Step 6  산출물 확인
        test_inference.py
        verify_mlflow.py
```

패키지 설치 기준:

```text
JavaScript 프로젝트(package.json 있음) -> npm i
Python 샘플/모델(requirements.txt 있음) -> python -m pip install -r requirements.txt
폐쇄망 WSL(wheelhouse 있음) -> bash .opencode/wsl/install_offline.sh
온라인 WSL(wheelhouse 준비) -> bash .opencode/wsl/download_wheels.sh
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

이 명령은 워크스페이스 루트의 `.ignore`, `.rgignore`, `.gitignore`에 관리 블록을 추가한다. 제외 대상은 `.venv/`, `node_modules/`, `.opencode/wsl/wheelhouse/`, `mlruns/`, `ai_studio/tracking/`, `ai_studio/code/`, `saved_model/`, `datasets/`, `*.pt`, `*.pkl`, `*.safetensors` 같은 생성물과 대용량 모델 파일이다.

자세한 운영 기준은 `.opencode/performance/CLOSED_NETWORK_SPEED.md`를 본다.

## Scripts

### doctor.py

Launch/Build/skills/sample/env 상태를 한 화면에서 점검한다. 주니어 QA나 폐쇄망 Windows에서 먼저 실행하기 좋다.

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
4. 실행 파일 확정
5. AI Studio 코드 적합성
6. 샘플 규격 폴더/파일
7. MLflow 필수 5개 설정값 입력/export
8. 모델/메트릭/코드 산출물
```

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

복사 대상은 소스 구조 중심이며 `.venv/`, `__pycache__/`, `model/`, `artifacts/ai_studio/`, `mlruns/`, `ai_studio/`, `mlflow.db` 같은 생성 산출물은 제외한다.

복사 후 `aiu_custom/`, `local_serving/`, `saved_model/` 필수 폴더는 항상 복사된 샘플 폴더 안에 보장한다.

복사 후 다음 단계는 아래 순서로 안내한다.

```text
1. 환경 검증
2. 샘플 규격 확인/보충
3. 환경 변수 입력/export
4. 패키지 설치
5. 로컬 학습 모델 실행
6. 산출물 확인
```

기존 파일이 있을 때 덮어쓰기는 사용자가 명시적으로 요청한 경우에만 사용한다.

```text
python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample sklearn --execute --force
```

### check_environment.py

Python, dependency, MLflow, `ai_studio.env` 상태를 확인한다.
Python 기준 버전은 3.11.9이다. 다른 버전이면 `version_mismatch:python`으로 분류한다.
`requirements.txt`가 있으면 필요한 pip 패키지 목록, 현재 설치 여부, 설치된 버전, 요구 버전, 버전 불일치 여부를 함께 출력한다.
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

필수 키:

```text
mlflow_tracking_url
mlflow_tracking_username
mlflow_tracking_password
mlflow_experiment_name
mlflow_register_model_name
```

작성 예시:

```text
mlflow_tracking_url=
mlflow_tracking_username=
mlflow_tracking_password=
mlflow_experiment_name=
mlflow_register_model_name=
```

`runtest.py` 또는 `run_model.py`에서 이 값들을 자동 생성하지 않는다. 사용자가 해당 파일의 MLflow/AI Studio 설정 블록에 직접 입력한다.
환경 변수 입력 후 `run_model.py`는 설정 블록 값을 아래 환경 변수로 export한다.

```text
mlflow_tracking_url -> MLFLOW_TRACKING_URI
mlflow_tracking_username -> MLFLOW_TRACKING_USERNAME
mlflow_tracking_password -> MLFLOW_TRACKING_PASSWORD
mlflow_experiment_name -> MLFLOW_EXPERIMENT_NAME
mlflow_register_model_name -> MLFLOW_REGISTER_MODEL_NAME
```

`mlflow_tracking_url`을 비워두면 샘플은 로컬 기본값 `file://<sample>/ai_studio/tracking`를 사용한다. MLflow artifact는 `artifact_path="ai_studio"` 아래 `ai_studio/code` 구조로 기록하고, 로컬 확인용 산출물은 `ai_studio/metrics/`, `ai_studio/code/`에 생성한다. 로컬 file store를 위해 `MLFLOW_ALLOW_FILE_STORE=true`도 함께 설정한다.

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

### test_inference.py

모델 로드와 input example 기반 predict를 테스트한다.

기본값은 안전 모드다. 실제 추론은 `--execute`를 명시해야 한다.

```text
python .opencode/scripts/test_inference.py --project <model-project-folder>
python .opencode/scripts/test_inference.py --project <model-project-folder> --execute
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
