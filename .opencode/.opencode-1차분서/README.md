# 1단계 테스트 폴더

이 폴더는 `1. 프로젝트 분석`만 따로 테스트하기 위한 분리 폴더입니다.

포함 파일:
- `scripts/01-project-analyze/validate_mlflow_project.py`
- `scripts/01-project-analyze/README.md`
- `skills/01-agent-mlflow-skill-project-analyze/SKILL.md`

PowerShell 실행:
```powershell
python .opencode-1차분서/scripts/01-project-analyze/validate_mlflow_project.py --project . --no-write-check
```

역할:
- 현재 워크스페이스 기준 분석
- 모델 목록 확인
- `model_found` 확인
