# 2단계 테스트 폴더

이 폴더는 `2. 모델 선택`만 따로 테스트하기 위한 분리 폴더입니다.

포함 파일:
- `scripts/02-model-select/select_model.py`
- `scripts/02-model-select/README.md`
- `skills/02-agent-mlflow-skill-sample-bootstrap/SKILL.md`

PowerShell 실행 예:
```powershell
python .opencode-2모델선택/scripts/02-model-select/select_model.py --project . --model 1
python .opencode-2모델선택/scripts/02-model-select/select_model.py --project . --model data/pytorch_cnn/cnn_model.pt
```

역할:
- 모델 번호/경로 선택
- 최초 선택 모델 고정
- 이후 단계에서 같은 선택 모델 유지
