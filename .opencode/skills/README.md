# OpenCode MLflow Skills

이 폴더는 ML 전문가와 주니어가 같은 흐름으로 MLflow 모델 프로젝트를 점검할 수 있게 돕는 OpenCode skill 모음입니다.

## Workflow

```text
01. Project Analyze
   model_found: true | false 결정
   모델 있음이면 루트/data 모델 목록과 사용할 모델을 먼저 확정

02. Sample Bootstrap
   모델이 없으면 1 sklearn / 2 pytorch / 3 tensorflow 선택

03. Environment Check
   Python 3.11.9, dependency, MLflow 3.13.0, 원격 MLflow 서버 version, 설정 상태 확인

04. Train Model
   선택 모델 기준 runtest_2.py 생성 또는 실제 entrypoint 실행

05. Inference Test
   input_example 기반 predict contract와 schema 확인

06. MLflow Verify
   run, metrics, artifact, registry 상태 확인
```

## Existing Model Process

전제:

- 사용자가 가져온 모델 파일은 현재 프로젝트 루트 바로 아래 또는 현재 프로젝트의 `data/**` 하위 트리 어디에나 둘 수 있다.
- 모델 검색은 현재 `--project` 폴더 안에서만 수행한다. 검색 범위는 현재 프로젝트 루트 바로 아래 모델 파일과 현재 프로젝트 `data/**` 트리다.
- 모델 연결은 선택한 현재 프로젝트 경로 기준 상대경로를 사용한다.
- 상위 폴더, 홈 디렉터리, 드라이브 루트, 임의 하위 폴더, 번들 샘플 폴더를 자동 검색하지 않는다.
- `data/sklearn/model.pkl`, `data/checkpoints/model.pt`처럼 `data/` 아래 폴더명이 달라도 모델로 인식한다.
- 지원 확장자: `.pkl`, `.joblib`, `.pt`, `.pth`, `.onnx`, `.h5`, `.keras`, `.safetensors`, `.bst`, `.ubj`.
- 선택 모델 파일은 템플릿 폴더로 복사하지 않고, 변환된 코드는 선택 모델 원본 경로에 연결한다.
- 모델 선택 단계에서는 기존 `runtest.py`를 읽기 전용으로 참조해 `runtest_2.py`만 생성/갱신한다.
- `aiu_custom/`, `local_serving/`, `saved_model/`, `config/`, `requirements.txt`, `input_example.json`은 모델 선택 단계에서 자동 생성하지 않는다.
- 후속 런타임 변환은 `runtest_2.py`를 기준으로 수행한다.
- 패키지/환경 상태는 다음 환경체크 단계에서 확인하고, 필요 패키지는 안내한다.
- 사용자에게 프로세스를 보여줄 때는 현재 복사/변환 흐름만 보여주고 하위 호환 또는 미사용 경로 설명은 넣지 않는다.
- 복사된 템플릿 파일 구성은 고정하지 않고 비교/수정하지 않는다.
- `data/` 원본에는 새 파일을 생성하지 않는다.
- 기존 `runtest.py`는 워크스페이스 루트에 두고, 읽기 전용으로만 참조한다.
- 기존 `runtest.py` 또는 `run_test.py`는 덮어쓰지 않는다.
- 기존 `runtest.py`는 절대 수정하지 않고 `runtest_2.py`만 선택 모델 기준으로 변환 생성한다.
- `runtest_2.py`는 참조한 `runtest.py` 구조를 기반으로 변환한다.
- 모델 경로/MODEL_KIND/로더는 선택 모델 실행/등록 연결부 기준으로 변환한다.
- 선택된 모델 종류에 맞춰 `load_selected_model()`, `required_package`, `load_hint`를 생성한다.
- 사용자가 직접 입력할 값은 `mlflow_tracking_url`, `mlflow_tracking_username`, `mlflow_tracking_password` 3개다.
- `mlflow_experiment_name`, `mlflow_register_model_name`은 선택 모델 파일명에서 확장자를 제거한 이름 기준으로 자동 생성한다.
- secret 값은 출력하지 않고 `set`, `empty`, `missing` 상태만 확인한다.

```text
Step 1. 모델 목록 확인
        현재 --project 루트 바로 아래와 그 안의 data/**에서 지원 모델 확장자 10개를 검색한다.
Step 2. 모델 경로로 선택
        model_artifact_paths를 번호로 보여주되, 자동 준비에는 실제 경로 선택을 우선한다.
        번호는 현재 출력된 목록 순서에 의존한다. 이미 준비된 선택 모델은 --model selected로 재사용한다.
        선택이 없으면 자동 준비를 진행하지 않고 선택 요청으로 멈춘다.
Step 3. 선택 모델 기준 runtest_2.py 변환
        MODEL_KIND를 먼저 판별한 뒤 기존 runtest.py를 읽기 전용으로 참조한다.
        선택 모델 경로와 MODEL_KIND를 반영해 runtest_2.py만 생성/갱신한다.
        다른 파일이나 폴더는 이 단계에서 자동 생성하지 않는다.
        내부 일치 검증은 runtest_2.py 기준으로만 수행한다.
Step 4. runtest_2.py 기준 런타임 변환 + 모델 환경변수/패키지 상태 체크
        `--sync-runtime`으로 runtest_2.py의 선택 모델 경로와 MODEL_KIND를 읽어 aiu_custom/, local_serving/, saved_model/, config/, requirements.txt, input_example.json을 모델에 맞게 변환/갱신한다.
        입력값 3개와 자동값 2개 상태를 확인한다.
        변환된 코드 import 기준 추가 Python 패키지가 필요하면 requirements.txt 반영 필요 여부와 pip 설치 명령을 안내한다.
Step 5. 원격 MLflow 등록 실행
        runtest_2.py를 먼저 실행해 선택 모델 기준 변환/실행 파일을 확인한다.
Step 6. 추론 테스트
        선택 모델 환경으로 변환된 local serving 입력/출력 스키마를 확인한다.
        이 단계는 실행 확인 단계다. local_serving/ 폴더는 Step 4 런타임 변환에서 생성되어 있어야 한다.
Step 7. MLflow 검증
Step 8. 오류 수정 및 재검증
        원격 MLflow 등록, 추론 테스트, MLflow 검증 중 오류가 있으면 서버 배포 오류사항과 Failures를 기준으로 수정한 뒤 실패한 단계부터 다시 실행한다.
        Run, artifact, registered model 기록을 확인한다.
```

```text
python .opencode/scripts/prepare_selected_model.py --project <model-project-folder>
python .opencode/scripts/prepare_selected_model.py --project <model-project-folder> --model 1 --execute
```

## Folder Order

```text
01-agent-mlflow-skill-project-analyze
02-agent-mlflow-skill-sample-bootstrap
03-agent-mlflow-skill-environment-check
04-agent-mlflow-skill-train-model
05-agent-mlflow-skill-inference-test
06-agent-mlflow-skill-mlflow-verify
```

폴더명은 순서 표시용입니다. 각 `SKILL.md`의 `name:` 값은 기존 호출 호환성을 위해 변경하지 않습니다.

## Script Map

스킬별 대표 스크립트는 아래만 먼저 봅니다. 나머지는 QA/유지보수 보조입니다.
같은 매핑은 `.opencode/scripts/skill_script_map.json`에도 있습니다.

```text
01 Project Analyze
   launch_workspace_summary.py
   validate_mlflow_project.py
   prepare_selected_model.py

02 Sample Bootstrap
   bootstrap_sample_project.py

03 Environment Check
   check_environment.py
   response_speed_check.py
   apply_index_ignore.py

04 Train Model / Selected Model Build
   prepare_selected_model.py
   run_training.py
   adapt_ai_studio.py

05 Inference Test
   local_serving/localservingtest.py
   test_inference.py

06 MLflow Verify
   verify_mlflow.py

QA / Maintenance
   doctor.py
   test_local_sample.py
   MAINTENANCE.md
```

## Doctor

전체 흐름을 한 번에 점검할 때는 doctor를 먼저 실행합니다.

```text
python .opencode/scripts/doctor.py --workspace . --project .
python .opencode/scripts/doctor.py --workspace . --project <model-project-folder> --entrypoint runtest.py
```

doctor는 실행 파일 확정, 샘플 규격, MLflow 입력값 3개와 자동값 2개, 산출물 상태를 한 화면에 보여줍니다.
`requirements.txt`가 있으면 pip 필요 패키지, 현재 설치 여부, 설치된 버전, 요구 버전, 버전 불일치도 함께 보여줍니다.
`run.py`처럼 실행 파일명이 사용자마다 달라도 루트의 단일 `.py` 파일은 자동으로 잡습니다. 여러 후보가 있으면 `--entrypoint <file>`로 확정합니다.
실행 파일을 찾지 못하면 자동 생성하지 않고, 사용자가 실제 학습/모델 생성 Python 파일을 직접 넣도록 안내합니다.

AI Studio/MLflow 연결부를 실제로 보강해야 하면 먼저 dry-run을 실행합니다.

```text
python .opencode/scripts/adapt_ai_studio.py --project <model-project-folder> --entrypoint <file>
python .opencode/scripts/adapt_ai_studio.py --project <model-project-folder> --entrypoint <file> --execute
```

## Common UI Pattern

각 스킬은 `판단 결과`를 먼저 보여주고, 자세한 설명은 접기 영역에 둡니다.

```text
Result First
Workflow
What To Do Now
Output Contract
Commands
Artifact Map
details: 자세한 판단 기준
details: 문제 해결
details: 전문가 상세
details: Safety 규칙
```

## Status Meaning

```text
pass:
  정상 또는 다음 단계 진행 가능

warn:
  진행 가능하지만 호환성/권한/환경 확인 필요

needs_user_input:
  사용자가 값, 파일명, 샘플 선택, 덮어쓰기 여부를 결정해야 함

blocked:
  현재 단계 진행 불가. 원인 해결 필요
```

## Artifact Map

```text
local metrics   -> ai_studio/metrics/
local code      -> ai_studio/code/
MLflow artifact -> artifact_path="ai_studio" 아래 code/
tracking target -> 사용자가 입력한 원격 MLflow tracking 서버
```

## Shared Safety

- Launch 모드는 읽기 전용입니다.
- Build 모드에서만 파일 복사, 수정, 설치, 실행을 수행합니다.
- secret 값은 출력하지 않고 `set`, `empty`, `missing` 상태만 표시합니다.
- Bun은 사용하지 않습니다.
- JavaScript 패키지 설치가 필요하고 `package.json`이 있으면 `npm i`만 사용합니다.
- 폐쇄망 WSL에서는 `.opencode/wsl/install_offline.sh`를 우선 사용합니다.
- torch는 SSL/HTTPS 인덱스로 설치하지 않습니다. wheelhouse 또는 내부 `http://` PyPI 미러만 사용합니다.
- PyTorch CPU wheel의 Nexus proxy upstream 참고 URL은 `https://download.pytorch.org/whl/cpu`입니다.
- Windows에서는 `standaloneExecutable` 또는 native executable 흐름보다 Python script 흐름을 우선합니다.
- 폐쇄망 응답이 느리면 `python .opencode/scripts/response_speed_check.py --project .` 후 `python .opencode/scripts/apply_index_ignore.py --project .`를 실행합니다.
