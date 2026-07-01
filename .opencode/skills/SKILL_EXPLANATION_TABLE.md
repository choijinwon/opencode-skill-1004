# AIU Studio Skill Explanation Table

## 1. 스킬 문서 설명

| 번호 | 스킬 문서 | 언제 사용하는지 | 주요 입력 | 하는 일 | 주요 결과 |
|---|---|---|---|---|---|
| 1 | `01-agent-mlflow-skill-project-analyze` | 처음 진입했을 때, 모델 있음/없음 확인이 필요할 때 | 현재 워크스페이스, 프로젝트 루트 | 워크스페이스를 분석하고 모델 파일, 실행 파일, 구조 상태를 확인 | `model_found`, 모델 목록, 점검 결과 |
| 2 | `02-agent-mlflow-skill-sample-bootstrap` | 모델이 없어서 샘플을 복사해야 할 때 | 샘플 종류(`sklearn`, `pytorch`, `tensorflow`), 워크스페이스 루트 | 샘플 또는 템플릿 파일을 워크스페이스로 복사 | 샘플 구조, 기본 템플릿 파일 |
| 3 | `03-agent-mlflow-skill-environment-check` | 모델 선택/템플릿 변환 후 환경 점검이 필요할 때 | `runtest_2.py`, `requirements.txt`, MLflow 입력값 | Python 버전, 패키지, MLflow 입력값, requirements 상태를 점검 | 환경 점검 결과, `requirements.txt` 갱신 |
| 4 | `04-agent-mlflow-skill-train-model` | 모델을 선택하고 실행 준비를 해야 할 때 | 선택 모델 경로, `runtest.py`, 워크스페이스 루트 | `runtest_2.py`를 생성하고 템플릿을 선택 모델 기준으로 변환 | `runtest_2.py`, `aiu_custom/`, `local_serving/`, `saved_model/` |
| 5 | `05-agent-mlflow-skill-inference-test` | MLflow 등록 후 추론 테스트를 해야 할 때 | `local_serving/localservingtest.py`, 입력 예시 | 로컬 추론 입력/출력 스키마와 predict 동작을 확인 | 추론 테스트 결과 |

## 2. 스킬별 핵심 스크립트

| 스킬 문서 | 핵심 스크립트 | 설명 |
|---|---|---|
| `01-agent-mlflow-skill-project-analyze` | `01-project-analyze/validate_mlflow_project.py` | 프로젝트 구조와 모델 존재 여부 분석 |
| `02-agent-mlflow-skill-sample-bootstrap` | `02-sample-bootstrap/bootstrap_sample_project.py` | 샘플/템플릿 복사 |
| `03-agent-mlflow-skill-environment-check` | `03-environment-check/check_environment.py` | 환경변수, 패키지, requirements 점검 |
| `04-agent-mlflow-skill-train-model` | `04-train-model/prepare_selected_model.py` | 모델 선택, `runtest_2.py` 생성, 템플릿 변환 |
| `05-agent-mlflow-skill-inference-test` | `05-inference-test/test_inference.py` | 추론 테스트 실행 |

## 3. 모델 있을 때 스킬 사용 순서

| 순서 | 사용하는 스킬 | 목적 | 대표 실행 |
|---|---|---|---|
| 1 | `01-agent-mlflow-skill-project-analyze` | 워크스페이스 분석 | 프로젝트 분석 |
| 2 | `01-agent-mlflow-skill-project-analyze` | 모델 있음/없음 확인 | `model_found` 확인 |
| 3 | `01-agent-mlflow-skill-project-analyze` | 모델 목록 확인 | 모델 검색/분석 |
| 4 | `04-agent-mlflow-skill-train-model` | 모델 선택 | `prepare_selected_model.py --model ... --execute` |
| 5 | `04-agent-mlflow-skill-train-model` | 모델 확인 | 선택 모델 경로와 `MODEL_KIND` 확인 |
| 6 | `04-agent-mlflow-skill-train-model` | 폴더 복사 | `prepare_selected_model.py --model ... --execute` |
| 7 | `04-agent-mlflow-skill-train-model` | `runtest_2.py` 생성 | `prepare_selected_model.py --model ... --execute` |
| 8 | `04-agent-mlflow-skill-train-model` | 선택 모델 기준 템플릿 변환 | `prepare_selected_model.py --model ... --execute` |
| 9 | `03-agent-mlflow-skill-environment-check` | 환경 점검 | `check_environment.py --entrypoint runtest_2.py` |
| 10 | `04-agent-mlflow-skill-train-model` | MLflow 등록 실행 | `python runtest_2.py` |
| 11 | `05-agent-mlflow-skill-inference-test` | 추론 테스트 | `python local_serving/localservingtest.py` |
| 12 | 실패한 단계의 스킬 | 오류 시 실패 단계부터 재실행 | `Failures` 기준으로 재실행 |

## 4. 사용자 입장에서 보는 간략 설명

| 단계 | 사용자 관점 설명 |
|---|---|
| 1 | 워크스페이스를 분석 |
| 2 | 모델 있음/없음을 확인 |
| 3 | 모델 목록을 확인 |
| 4 | 사용할 모델을 선택 |
| 5 | 선택한 모델 경로와 형식을 확인 |
| 6 | 템플릿 폴더를 현재 워크스페이스 루트로 복사 |
| 7 | `runtest.py`를 참조해서 `runtest_2.py` 생성 |
| 8 | 선택 모델 기준으로 템플릿 변환 |
| 9 | 환경 점검 |
| 10 | MLflow 등록 실행 |
| 11 | 추론 테스트 |
| 12 | 오류가 있으면 실패한 단계부터 다시 실행 |

## 5. 핵심 차이

| 항목 | 설명 |
|---|---|
| `project-analyze` | 분석 전용 |
| `sample-bootstrap` | 복사 전용 |
| `environment-check` | 점검/갱신 전용 |
| `train-model` | 모델 선택, 생성, 변환, 실행 준비 핵심 |
| `inference-test` | 추론 확인 전용 |
