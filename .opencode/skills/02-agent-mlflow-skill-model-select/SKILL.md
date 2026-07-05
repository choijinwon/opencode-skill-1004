---
name: agent-mlflow-skill-model-select
description: Use when the user selects a model by number/path/natural language after workspace analysis; locks the selected model and keeps it for later Ai Studio steps.
license: MIT
compatibility: opencode
metadata:
  flow: ml-workspace-development
  stage: 02-model-select
  step: 2
---

# Model Select

## Result First

```text
판단 결과: pass | needs_user_input | blocked
현재 단계: 2. 모델 선택
현재 대상: selected workspace root
핵심 판단: 사용자가 선택한 모델 번호/경로를 하나로 고정
다음 단계: 3. 환경 검증
```

## Workflow

```text
1. 모델 목록 확인
2. 모델 선택
3. 환경 검증
4. 템플릿 변환
5. 원격 MLflow 등록 실행
6. 추론 테스트
7. 오류 재실행
```

## What To Do Now

```text
1. 1단계에서 출력된 모델 목록을 그대로 사용한다.
2. 사용자가 입력한 숫자 또는 상대경로를 선택 모델로 고정한다.
3. 번호 선택은 화면에 표시된 프로젝트 상대경로 알파벳 정렬 목록을 그대로 따른다.
4. 프레임워크, 확장자, 파일명 기준으로 다시 정렬하지 않는다.
5. 선택 후 3~7번을 자동 실행하지 않는다.
6. 이후 단계는 저장된 선택 모델을 계속 사용한다.
```

## Output Contract

```text
반드시 보여줄 값:
- 선택 모델
- MODEL_KIND
- 실행 파일
- 작업 폴더
- 다음 가능 단계
```

다음 가능 단계는 Markdown Table로만 보여준다.

```text
| Status | Step | Action |
|---|---:|---|
| 대기 | 3 | 환경 검증 |
| 대기 | 4 | 템플릿 변환 |
| 대기 | 5 | 원격 MLflow 등록 실행 |
| 대기 | 6 | 추론 테스트 |
| 대기 | 7 | 오류 재실행 |
```

## Commands

```text
모델 선택:
& ".opencode/scripts/common/invoke-aistudio-python.ps1" ".opencode/scripts/02-model-select/select_model.py" --project . --model <번호 또는 상대경로> -AutoInstallIfMissing

예:
& ".opencode/scripts/common/invoke-aistudio-python.ps1" ".opencode/scripts/02-model-select/select_model.py" --project . --model 3 -AutoInstallIfMissing
& ".opencode/scripts/common/invoke-aistudio-python.ps1" ".opencode/scripts/02-model-select/select_model.py" --project . --model 'data\pytorch_cnn\cnn_model.pt' -AutoInstallIfMissing
```

<details>
<summary>자세한 판단 기준 보기</summary>

```text
pass:
- 모델 번호 또는 경로가 하나의 모델로 해석됨
- 선택 모델과 MODEL_KIND가 출력됨
- 선택 모델 정보가 이후 단계에서 재사용 가능함

needs_user_input:
- 모델 목록이 없거나 선택값이 모호함
- 숫자가 모델 목록 범위를 벗어남

blocked:
- 선택한 워크스페이스가 아님
- .opencode 샘플 원본 또는 드라이브 루트 분석을 시도함
- 선택 모델 파일이 존재하지 않음
```

</details>

<details>
<summary>Safety 규칙 보기</summary>

- 2번 모델 선택은 파일 복사/변환/실행을 하지 않는다.
- 숫자 입력은 모델 목록이 보이는 상태에서는 TODO 단계 번호가 아니라 모델 번호로 처리한다.
- 선택 모델은 사용자가 다시 선택하기 전까지 유지한다.
- 사용자-facing 출력에는 절대경로 대신 워크스페이스 기준 상대경로를 사용한다.

</details>
