# 5단계 train-model 분석 폴더

이 폴더는 `5. train-model` 단계를 따로 읽고 테스트하기 위한 분리 폴더입니다.

포함 파일:
- `scripts/05-train-model/prepare_selected_model.py`
- `scripts/05-train-model/adapt_ai_studio.py`
- `scripts/05-train-model/run_training.py`
- `scripts/05-train-model/README.md`
- `skills/04-agent-mlflow-skill-train-model/SKILL.md`

역할:
- 2단계에서 선택한 모델을 기준으로 작업 폴더를 유지
- 선택 모델 형식에 맞게 템플릿 연결부를 변환
- `runtest_2.py`, `aiu_custom/`, `config/`, `saved_model/`, `input_example.json` 흐름을 점검
- 사용자가 5번을 선택했을 때 원격 MLflow 등록 실행을 수행

PowerShell 실행 예:
```powershell
python .opencode/scripts/05-train-model/prepare_selected_model.py --project . --model selected --execute
python .opencode/scripts/05-train-model/run_training.py --project cnn_model --entrypoint runtest_2.py --execute
```
