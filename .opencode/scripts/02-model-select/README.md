# 02 Model Select

2단계 모델 선택 전용 스크립트입니다.

대표 스크립트:
- `select_model.py`

역할:
- 1단계 분석 화면에 나온 모델 목록 번호 또는 상대경로를 선택 모델로 고정
- 번호 선택은 표시된 알파벳 정렬 목록과 동일하게 처리
- 모델 선택만 수행하고 3~7단계는 자동 실행하지 않음

PowerShell 실행 예:
```powershell
& ".opencode/scripts/common/invoke-aistudio-python.ps1" ".opencode/scripts/02-model-select/select_model.py" --project . --model 3 -AutoInstallIfMissing
```
