# 4단계 샘플 부트스트랩 분석 폴더

이 폴더는 `4. 샘플 부트스트랩` 단계를 따로 읽고 테스트하기 위한 분리 폴더입니다.

포함 파일:
- `scripts/04-sample-bootstrap/bootstrap_sample_project.py`
- `scripts/04-sample-bootstrap/README.md`
- `skills/02-agent-mlflow-skill-sample-bootstrap/SKILL.md`

역할:
- 모델이 없는 경우 `sklearn`, `pytorch`, `tensorflow` 샘플을 선택해 워크스페이스로 복사
- 기존 모델/데이터가 있는 프로젝트에서는 `data/` 모델 파일을 덮어쓰지 않도록 보호
- `.opencode/samples/*` 샘플 기준으로 필요한 기본 폴더와 파일만 구성

PowerShell 실행 예:
```powershell
python .opencode/scripts/04-sample-bootstrap/bootstrap_sample_project.py --project . --sample pytorch --execute
```

