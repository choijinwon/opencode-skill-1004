# 5단계 테스트 폴더

이 폴더는 `5. 원격 MLflow 등록 실행`만 따로 테스트하기 위한 분리 폴더입니다.

원본 소스:
- `.opencode/scripts/04-train-model/run_training.py`

PowerShell 실행 예:
```powershell
python .opencode/scripts/04-train-model/run_training.py --project . --entrypoint runtest_2.py --execute
```

역할:
- 4단계 결과물 기준 등록 실행
- MLflow 기록/등록
- 실행 전 런타임 재동기화 확인

