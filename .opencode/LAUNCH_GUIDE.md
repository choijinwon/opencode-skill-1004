# Launch Guide

Build 모드에서는 이 Launch Guide의 읽기 전용 제한을 적용하지 않습니다.
Build 모드에서 `1`, `2`, `3`을 입력하면 sklearn / pytorch / tensorflow 샘플 선택으로 보고, 명령어를 안내만 하지 말고 직접 실행합니다.

이 프로젝트는 MLflow 모델 프로젝트 분석과 샘플 생성을 돕는 OpenCode 패키지입니다.
처음 진입하면 어떤 단어를 입력해도 워크스페이스를 먼저 분석해 모델 있음/없음을 확인합니다.

모델이 있으면 본인 모델 경로를 기준으로 실행 파일 확정부터 시작하는 MLflow 7단계 프로세스를 진행합니다.
모델이 없으면 sklearn / pytorch / tensorflow 중 하나를 선택해 샘플을 생성합니다.
생성 시 샘플 내용만 루트에 풀지 않고 `<workspace>/sklearn_sample/` 같은 샘플 폴더 자체를 복사합니다.

Launch 모드는 읽기 전용이라 파일을 수정하지 않습니다.
실제 복사/모델 생성/환경 검증 실행은 OpenCode Build 모드에서 직접 실행합니다.

추천 첫 요청:

- 이 워크스페이스를 MLflow 모델 있음/없음 기준으로 분석해줘.
- 모델이 없으면 Build 모드에서 sklearn 샘플 생성 단계로 안내해줘.

보안 규칙: API key, password, token 값은 출력하지 않고 서버 배포 시 Secret/환경변수를 사용합니다.
