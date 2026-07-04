# 4단계 테스트 폴더

이 폴더는 `4. 템플릿 변환`만 따로 테스트하기 위한 분리 폴더입니다.

원본 소스:
- `.opencode/scripts/04-train-model/prepare_selected_model.py`

PowerShell 실행 예:
```powershell
python .opencode/scripts/04-train-model/prepare_selected_model.py --project . --model selected --execute
```

역할:
- 선택 모델 기준 작업 폴더 준비
- `local_serving/` 복사
- `runtest_2.py` 변환
- `aiu_custom/`, `config/config.json`, `input_example.json` 변환
- `requirements.txt` 갱신

