# 6단계 추론 테스트 분석 폴더

이 폴더는 `6. 추론 테스트` 단계를 따로 읽고 테스트하기 위한 분리 폴더입니다.

포함 파일:
- `scripts/06-inference-test/test_inference.py`
- `scripts/06-inference-test/README.md`
- `skills/06-agent-mlflow-skill-inference-test/SKILL.md`

역할:
- 선택 모델 작업 폴더의 `input_example.json` 확인
- `inferencetest.py`의 `req_url` 확인
- 원격 추론 URL이 `http://...` 또는 `https://...` 이고 `:predict`로 끝나는지 검증
- 사용자가 6번을 선택했을 때만 추론 요청 실행

PowerShell 실행 예:
```powershell
python .opencode/scripts/06-inference-test/test_inference.py --project <선택모델작업폴더> --url http://server/v1/models/model:predict --execute
```

