# 01 Project Analyze

Skill folder:
`../../skills/01-agent-mlflow-skill-project-analyze`

Scripts:

- `validate_mlflow_project.py`

Responsibility:

- `model_found` 판단
- 현재 프로젝트 루트와 `data/**` 모델 목록 확인
- 모델 선택 진입
- 읽기 전용 분석만 수행
- `.env`, `requirements.txt`, `config/`, `saved_model/`, `aiu_custom/` 생성 금지
