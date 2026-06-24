# OpenCode Skills

이 폴더는 ML 개발자가 사용자가 지정한 모델 프로젝트 폴더를 대상으로 챗봇을 통해 모델 개발과 MLflow 기록 확인을 진행할 수 있도록 돕는 OpenCode skill을 포함합니다.

```text
Step 1  agent-mlflow-skill-project-analyze
Step 2  agent-mlflow-skill-environment-check
Step 3  agent-mlflow-skill-train-model
Step 4  agent-mlflow-skill-inference-test
Step 5  agent-mlflow-skill-mlflow-verify
```

## Goal

사용자가 직접 명령을 많이 알지 못해도 다음 흐름을 챗봇으로 점검할 수 있게 한다.

```text
프로젝트 구조 분석
실행 환경 검증
로컬 학습 실행
모델 생성 확인
추론 테스트
MLflow Run 생성 확인
```

상세 설명은 [MLFLOW_5_STEP_GUIDE.md](./MLFLOW_5_STEP_GUIDE.md)를 참고한다.
아키텍처는 [MLFLOW_5_STEP_ARCHITECTURE.md](./MLFLOW_5_STEP_ARCHITECTURE.md)를 참고한다.

## Skill Boundaries

- 사용자가 지정한 모델 프로젝트 폴더 안의 파일과 설정을 우선 확인한다.
- secret 값은 출력하지 않고 존재 여부만 말한다.
- 외부 다운로드나 원격 등록은 사용자가 명확히 요청한 경우에만 다룬다.
- 실행이 필요한 단계는 로컬/폐쇄망 환경을 우선 전제로 한다.
- 실패 시 단순 실패가 아니라 원인을 `missing_file`, `missing_dependency`, `config_error`, `runtime_error`, `mlflow_error`처럼 분류한다.
