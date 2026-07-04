# 3단계 테스트 폴더

이 폴더는 `3. 환경 검증`만 따로 테스트하기 위한 분리 폴더입니다.

원본 소스:
- `.opencode/scripts/03-environment-check/check_environment.py`
- `.opencode/scripts/03-environment-check/requirements.required.txt`

PowerShell 실행 예:
```powershell
python .opencode/scripts/03-environment-check/check_environment.py --project . --entrypoint runtest_2.py
```

역할:
- `.env` 5개 필수값 상태 확인
- `requirements.txt` 기본 항목 확인
- 선택 모델 기준 추천 패키지 확인

