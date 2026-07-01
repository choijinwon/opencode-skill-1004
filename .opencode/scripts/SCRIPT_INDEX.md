# AI Studio Script Index

이 문서는 `.opencode/skills` 01~06 목록에 맞춘 스크립트 정리표입니다.

실제 구현 파일은 스킬 목록 기준 폴더에 둡니다.
기존 실행 명령 호환성을 위해 `.opencode/scripts/` 루트에는 같은 이름의 wrapper를 둡니다.

## 01 Project Analyze

Skill folder:
`01-agent-mlflow-skill-project-analyze`

Primary scripts:

- `01-project-analyze/launch_workspace_summary.py` - 첫 진입 요약, model_found 안내
- `01-project-analyze/validate_mlflow_project.py` - 상세 워크스페이스 분석
- `04-train-model/prepare_selected_model.py` - 모델 목록 확인, 모델 선택

## 02 Sample Bootstrap

Skill folder:
`02-agent-mlflow-skill-sample-bootstrap`

Primary scripts:

- `02-sample-bootstrap/bootstrap_sample_project.py` - 모델 없음 상태에서 sklearn/pytorch/tensorflow 샘플 복사

## 03 Environment Check

Skill folder:
`03-agent-mlflow-skill-environment-check`

Primary scripts:

- `03-environment-check/check_environment.py` - Python, requirements.txt, MLflow 입력값, 패키지 상태 확인

Support scripts:

- `03-environment-check/response_speed_check.py` - 폐쇄망/Windows 응답 속도 및 인덱싱 진단
- `03-environment-check/apply_index_ignore.py` - `.opencode/`, `.opencode/node_modules/`, 생성물, 모델 파일 인덱싱 제외 적용

Required files:

- `03-environment-check/requirements.required.txt` - 생성되는 `requirements.txt`의 필수 5개 패키지 기준

## 04 Train Model / Selected Model Build

Skill folder:
`04-agent-mlflow-skill-train-model`

Primary scripts:

- `04-train-model/prepare_selected_model.py` - `runtest.py` 참조, 선택 모델 기준 `runtest_2.py` 생성, `--sync-runtime` 후속 변환
- `04-train-model/run_training.py` - 확정된 entrypoint 실행

Support scripts:

- `04-train-model/adapt_ai_studio.py` - 사용자 임의 `run.py` 보강용 보조 스크립트

## 05 Inference Test

Skill folder:
`05-agent-mlflow-skill-inference-test`

Primary scripts:

- `05-inference-test/test_inference.py` - 추론 계약 점검

Generated runtime entrypoint:

- `local_serving/localservingtest.py` - `prepare_selected_model.py --sync-runtime --execute`가 프로젝트 루트에 생성

## 06 MLflow Verify

Skill folder:
`06-agent-mlflow-skill-mlflow-verify`

Primary scripts:

- `06-mlflow-verify/verify_mlflow.py` - MLflow run, artifact, registered model 검증

## QA / Maintenance

Scripts:

- `qa-maintenance/doctor.py` - 전체 상태 1페이지 점검
- `qa-maintenance/test_local_sample.py` - 번들 샘플 QA

Documents:

- `README.md` - 사용자/운영용 스크립트 가이드
- `MAINTENANCE.md` - 유지보수 상세 문서
- `SCRIPT_INDEX.md` - 스킬 목록 기준 스크립트 정리표
- `skill_script_map.json` - 도구가 읽는 스킬-스크립트 매핑
