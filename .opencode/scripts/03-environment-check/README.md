# 03 Environment Check

Skill folder:
`../../skills/03-agent-mlflow-skill-environment-check`

Scripts:

- `check_environment.py`

Required files:

- `requirements.required.txt` - every generated selected-model work folder `requirements.txt` starts from these required packages

Responsibility:

- Python 버전 확인
- 선택 모델 작업 폴더 `requirements.txt`가 없으면 생성하고 패키지 상태 확인
- 로컬 dependency 설치는 자동 실행하지 않음
- 선택 모델 작업 폴더 `.env`의 MLflow 5개 값 상태 확인
