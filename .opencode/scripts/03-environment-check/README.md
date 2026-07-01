# 03 Environment Check

Skill folder:
`../../skills/03-agent-mlflow-skill-environment-check`

Scripts:

- `check_environment.py`
- `response_speed_check.py`
- `apply_index_ignore.py`

Required files:

- `requirements.required.txt` - every generated workspace `requirements.txt` starts from these required packages

Root compatibility wrappers:

- `../check_environment.py`
- `../response_speed_check.py`
- `../apply_index_ignore.py`

Responsibility:

- Python 버전 확인
- `requirements.txt` 패키지 상태 확인
- MLflow 입력값 3개와 자동값 2개 상태 확인
- 폐쇄망/Windows 응답 속도 진단
- `.opencode/`, `.opencode/node_modules/`, 생성물, 모델 파일 인덱싱 제외 적용
