# Ai Studio Skill Table

## 1. 스킬 문서 요약

| 번호 | 스킬 문서 | 목적 | 주요 스크립트 | 주요 결과 |
|---|---|---|---|---|
| 1 | `01-agent-mlflow-skill-project-analyze` | 현재 워크스페이스 분석, 모델 있음/없음 판단 | `01-project-analyze/*` | `model_found`, 모델 목록, 프로젝트 상태 |
| 2 | `02-agent-mlflow-skill-model-select` | 사용할 모델 번호/경로 선택 고정 | `02-model-select/*` | 선택 모델, `MODEL_KIND`, 작업 폴더 |
| 3 | `03-agent-mlflow-skill-environment-check` | Python, 패키지, MLflow 설정 점검 | `03-environment-check/*` | 환경 점검 결과, `requirements.txt` 변환 |
| 4 | `04-agent-mlflow-skill-sample-bootstrap` | 모델 없음 상태에서 샘플/템플릿 복사 | `04-sample-bootstrap/*` | 샘플 파일, 템플릿 파일 |
| 5 | `05-agent-mlflow-skill-train-model` | 템플릿 변환, 원격 MLflow 등록 실행 | `05-train-model/*` | `runtest_2.py`, `aiu_custom/`, `local_serving/`, `saved_model/` |
| 6 | `06-agent-mlflow-skill-inference-test` | 원격 추론 URL 테스트 | `06-inference-test/*` | 추론 테스트 결과 |

## 2. 모델 있을 때 프로세스

| 단계 | 설명 | 실행 스크립트 | 주요 결과물 |
|---|---|---|---|
| 1 | 모델 목록 확인 | `python .opencode/scripts/01-project-analyze/validate_mlflow_project.py --project . --no-write-check` | 현재 프로젝트 루트와 `data/**` 모델 목록 |
| 2 | 모델 선택 | `python .opencode/scripts/02-model-select/select_model.py --project . --model <번호 또는 경로>` | 명시 선택 반영, 이후 단계에서 선택 모델 유지 |
| 3 | 환경 검증 | 사용자가 3번 선택 시 `python .opencode/scripts/03-environment-check/check_environment.py --project . --entrypoint runtest_2.py` | MLflow 입력값 확인, `requirements.txt` 변환 |
| 4 | 템플릿 변환 | 사용자가 4번 선택 시 `python .opencode/scripts/05-train-model/prepare_selected_model.py --project . --model selected --execute` | `local_serving/`, `aiu_custom/`, `config/` 폴더 복사 후, 선택 모델 기준 파일 변환 |
| 5 | 원격 MLflow 등록 실행 | 사용자가 5번 선택 시 `python .opencode/scripts/05-train-model/run_training.py --project <선택모델작업폴더> --entrypoint runtest_2.py --execute` | 선택 모델 작업 폴더에서 재검증/변환 후 원격 MLflow 서버에 기록/등록 |
| 6 | 추론 테스트 | 사용자가 6번 선택 시 `python inferencetest.py` | `input_example.json` 기반 원격 추론 URL 호출 |
| 7 | 오류 재실행 | 사용자가 7번 선택 시 실패한 단계 스크립트 재실행 | `Failures`와 오류 메시지 기준으로 실패한 단계부터 다시 실행 |

## 3. 3번 단계 상세

| 항목 | 동작 |
|---|---|
| Python 버전 | 기대 버전 `3.11.9` 기준 확인 |
| 필수 패키지 | `mlflow`, `kserve==0.15.0` |
| 추가 패키지 | 선택 모델 `MODEL_KIND` 기준으로 추천만 표시하고, 사용자가 필요한 항목만 직접 `requirements.txt`에 추가 |
| `.env` MLflow 5개 값 | `mlflow_tracking_uri`, `mlflow_tracking_username`, `mlflow_tracking_password`, `mlflow_experiment_name`, `mlflow_register_model_name` |
| 원격 URL 조건 | `mlflow_tracking_uri`은 사용자가 직접 입력하며 5번 실행에서는 원격 `http://` 또는 `https://`만 허용 |
| 표시 정책 | secret 값은 출력하지 않고 `set`, `empty`, `missing` 상태만 표시 |

## 4. 4번 단계 상세

| 항목 | 동작 |
|---|---|
| 템플릿 복사 기준 | 선택 모델명 작업 폴더를 만들고 `.opencode/samples/pytorch_sample/`의 `local_serving/`, `aiu_custom/`, `config/` 폴더를 복사 후 다시 읽기 |
| 복사 제외 | `data/`, `runtest_2.py`, `requirements.txt`는 템플릿에서 복사하지 않음 |
| 참조 기준 | 기존 `runtest.py`를 읽기 전용으로 참조 |
| 변환 파일 | `runtest_2.py` |
| 변환 대상 예시 | `aiu_custom/predict.py`, `aiu_custom/model.py`, `config/config.json`, `inferencetest.py`, `input_example.json`, `requirements.txt` |
| 모델 파일 복사 | 선택 모델명 작업 폴더의 `saved_model/` 아래로 복사하고, 변환 코드는 그 복사본을 연결 |

## 5. 오류 시 재실행 기준

| 오류 위치 | 다시 시작할 단계 |
|---|---|
| 분석/모델 목록 오류 | 1 |
| 모델 선택 오류 | 2 |
| 템플릿 변환 오류 | 4 |
| 환경 검증 오류 | 3 |
| MLflow 등록 오류 | 5 |
| 추론 테스트 오류 | 6 |

## 6. 핵심 요약

| 항목 | 요약 |
|---|---|
| 스크립트 경로 기준 | 항상 워크스페이스 루트에서 `--project .` 사용 |
| 모델 경로 기준 | 항상 워크스페이스 상대경로 사용. 예: `data\pytorch_cnn\cnn_model.pt` |
| 모델 선택 후 핵심 흐름 | 모델 목록 확인 -> 모델 선택 후 멈춤 -> 사용자가 선택한 3/4/5/6/7번만 1개씩 실행 |
| 템플릿 복사 위치 | 워크스페이스 루트 아래 선택 모델명 작업 폴더 |
| 선택 모델 유지 | 한 번 선택한 모델은 이후 단계에서도 그대로 유지 |
| 재검증 방식 | 전체 처음부터 다시 하지 않고 실패한 단계부터 다시 실행 |

## 7. 간략 프로세스

| 순서 | 간략 설명 |
|---|---|
| 1 | 모델 목록 확인 |
| 2 | 모델 선택 |
| 3 | 환경 검증 |
| 4 | 템플릿 변환 |
| 5 | 원격 MLflow 등록 실행 |
| 6 | 추론 테스트 |
| 7 | 오류 재실행 |
