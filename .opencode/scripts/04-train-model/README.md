# 04 Train Model / Selected Model Build

Skill folder:
`../../skills/04-agent-mlflow-skill-train-model`

Scripts:

- `prepare_selected_model.py`
- `run_training.py`
- `adapt_ai_studio.py`

Root compatibility wrappers:

- `../prepare_selected_model.py`
- `../run_training.py`
- `../adapt_ai_studio.py`

Responsibility:

- 기존 `runtest.py`를 읽기 전용으로 참조
- 선택 모델 기준 `runtest_2.py` 생성
- 3번 추가 시퀀스에서 `--sync-runtime` 실행
- `runtest_2.py` 기준 런타임 폴더/파일 변환
- `03-environment-check/requirements.required.txt` 기준으로 `requirements.txt` 재정의
- 확정 entrypoint 실행
