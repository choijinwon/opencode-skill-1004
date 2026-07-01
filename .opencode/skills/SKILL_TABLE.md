# AIU Studio Skill Table

## 1. 스킬 문서 요약

| 번호 | 스킬 문서 | 목적 | 주요 스크립트 | 주요 결과 |
|---|---|---|---|---|
| 1 | `01-agent-mlflow-skill-project-analyze` | 현재 워크스페이스 분석, 모델 있음/없음 판단 | `01-project-analyze/*` | `model_found`, 모델 목록, 프로젝트 상태 |
| 2 | `02-agent-mlflow-skill-sample-bootstrap` | 샘플/템플릿 복사 | `02-sample-bootstrap/*` | 샘플 파일, 템플릿 파일 |
| 3 | `03-agent-mlflow-skill-environment-check` | Python, 패키지, MLflow 설정 점검 | `03-environment-check/*` | 환경 점검 결과, `requirements.txt` 갱신 |
| 4 | `04-agent-mlflow-skill-train-model` | 모델 선택, `runtest_2.py` 생성, 템플릿 변환, MLflow 등록 실행 | `04-train-model/*` | `runtest_2.py`, `aiu_custom/`, `local_serving/`, `saved_model/` |
| 5 | `05-agent-mlflow-skill-inference-test` | 로컬 추론 테스트 | `05-inference-test/*` | 추론 테스트 결과 |
| 6 | `06-agent-mlflow-skill-mlflow-verify` | MLflow 검증 | `06-mlflow-verify/*` | experiment, run, artifact, registered model 확인 |

## 2. 모델 있을 때 프로세스

| 단계 | 설명 | 실행 스크립트 | 주요 결과물 |
|---|---|---|---|
| 1 | 모델 목록 확인 | `01-project-analyze/*` 또는 모델 검색 로직 | 현재 프로젝트 루트와 `data/**` 모델 목록 |
| 2 | 모델 선택 | `python .opencode/scripts/04-train-model/prepare_selected_model.py --project . --model <번호 또는 경로> --execute` | 선택 모델 고정, `runtest_2.py` 생성 |
| 3 | 선택 모델 환경 변환 | `python .opencode/scripts/04-train-model/prepare_selected_model.py --project . --sync-runtime --execute` | `.opencode/samples/aiu_studio/` 템플릿이 현재 워크스페이스 루트로 복사되고, 선택 모델 기준으로 변환 |
| 4 | 모델 환경변수·패키지 상태 체크 | `python .opencode/scripts/03-environment-check/check_environment.py --project . --entrypoint runtest_2.py` | MLflow 입력값 3개 확인, 자동값 2개 확인, `requirements.txt` 필수 항목 및 추가 패키지 목록 갱신 |
| 5 | 원격 MLflow 등록 실행 | `python runtest_2.py` | MLflow run, artifact, model registration 수행 |
| 6 | 추론 테스트 | `python local_serving/localservingtest.py` | 입력/출력 추론 테스트 |
| 7 | MLflow 검증 | `python .opencode/scripts/06-mlflow-verify/verify_mlflow.py --tracking-uri <tracking-uri> --experiment-name <experiment-name>` | experiment, run, artifact, registered model 결과 확인 |
| 8 | 오류 수정 및 재검증 | 실패한 단계 스크립트 재실행 | `Failures`와 오류 메시지 기준으로 수정 후 실패한 단계부터 다시 실행 |

## 3. 3번 단계 상세

| 항목 | 동작 |
|---|---|
| 템플릿 복사 기준 | `.opencode/samples/aiu_studio/` 내부 템플릿을 현재 워크스페이스 루트로 복사 |
| 복사 제외 | `runtest_2.py`는 템플릿에서 복사하지 않음 |
| 참조 기준 | 기존 `runtest.py`를 읽기 전용으로 참조 |
| 생성 파일 | `runtest_2.py` |
| 변환 대상 예시 | `aiu_custom/predict.py`, `aiu_custom/model.py`, `aiu_custom/mapping.json`, `local_serving/localservingtest.py`, `requirements.txt`, `input_example.json` |
| 모델 파일 복사 | 선택 모델 파일 자체는 복사하지 않음. 현재 프로젝트 안 원본 경로를 그대로 연결 |

## 4. 4번 단계 상세

| 확인 항목 | 설명 |
|---|---|
| Python 버전 | 기대 버전 `3.11.9` 기준 확인 |
| 필수 패키지 | `mlflow==3.10.0`, `torch==2.12.1`, `numpy==1.26.4`, `kserve==0.15.0`, `pandas==2.23` |
| 추가 패키지 | 변환된 코드 import 기준으로 필요한 항목을 `requirements.txt`에 추가 |
| MLflow 입력값 3개 | `mlflow_tracking_url`, `mlflow_tracking_username`, `mlflow_tracking_password` |
| 자동값 2개 | `mlflow_experiment_name`, `mlflow_register_model_name` |
| 표시 정책 | secret 값은 출력하지 않고 `set`, `empty`, `missing` 상태만 표시 |

## 5. 오류 시 재실행 기준

| 오류 위치 | 다시 시작할 단계 |
|---|---|
| 모델 선택/변환 오류 | 2 또는 3 |
| 환경변수/패키지 오류 | 4 |
| MLflow 등록 오류 | 5 |
| 추론 테스트 오류 | 6 |
| MLflow 검증 오류 | 7 |

## 6. 핵심 요약

| 항목 | 요약 |
|---|---|
| 모델 선택 후 핵심 흐름 | 모델 선택 -> `runtest_2.py` 생성 -> 템플릿 복사/변환 -> 환경 점검 -> MLflow 등록 -> 추론 테스트 -> MLflow 검증 |
| 템플릿 복사 위치 | 현재 워크스페이스 루트 |
| 선택 모델 유지 | 한 번 선택한 모델은 이후 단계에서도 그대로 유지 |
| 재검증 방식 | 전체 처음부터 다시 하지 않고 실패한 단계부터 다시 실행 |
