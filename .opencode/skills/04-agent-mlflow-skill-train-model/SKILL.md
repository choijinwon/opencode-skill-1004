---
name: agent-mlflow-skill-train-model
description: Use when the user asks "학습 실행", "모델 생성", "runtest.py", "run_model.py", "saved_model 확인", "artifact 생성", or train model; checks local training entrypoint, model artifact creation, config, and input example.
license: MIT
compatibility: opencode
metadata:
  flow: ml-workspace-development
  stage: 03-train-model
  step: 3
---

# Local Training And Model Creation

## Result First

```text
판단 결과: pass | warn | needs_user_input | blocked
현재 단계: 6. 로컬 학습 모델 실행
현재 대상: selected_project_path 또는 copied sample folder
핵심 판단: entrypoint 확정, 실행 성공, ai_studio 산출물 생성
다음 단계: 추론 테스트
```

## Workflow

```text
1. 실행 파일 확정
2. 환경 검증
3. 샘플 규격 확인/보충
4. 환경 변수 입력/export
5. 패키지 설치
6. 로컬 학습 모델 실행
7. 산출물 확인
```

## What To Do Now

```text
1. 기존 모델이면 실제 entrypoint를 먼저 확정한다.
2. 샘플 모델이면 복사된 샘플 폴더를 실행 대상으로 사용한다.
3. run_model.py로 고정하지 않는다.
4. 실행 전 MLflow/AI Studio 설정 블록을 확인한다.
5. 실행 후 ai_studio/metrics, ai_studio/code를 확인한다.
```

## Output Contract

```text
반드시 보여줄 값:
- 판단 결과
- 선택된 entrypoint
- 실행 command
- 실행 여부와 return code
- 생성된 metrics/code 산출물
- 누락된 산출물
- 다음 단계
```

성공 출력 UI:

```text
판단 결과: pass
entrypoint: run_model.py
command: python run_model.py
local outputs:
- ai_studio/metrics/
- ai_studio/code/
MLflow artifact:
- artifact_path="ai_studio" 아래 code/
```

## Commands

```text
실행 파일 자동 판단:
python .opencode/scripts/run_training.py --project <project>

로컬 학습 실행:
python .opencode/scripts/run_training.py --project <project> --execute

명시적 entrypoint 실행:
python .opencode/scripts/run_training.py --project <project> --entrypoint <file> --execute
```

## Artifact Map

```text
local metrics   -> ai_studio/metrics/
local code      -> ai_studio/code/
MLflow artifact -> artifact_path="ai_studio" 아래 code/
tracking store  -> ai_studio/tracking/
reference model -> saved_model/, model/, framework native model file
```

<details>
<summary>자세한 판단 기준 보기</summary>

```text
pass:
- entrypoint가 확정됨
- 실행이 완료됨
- ai_studio/metrics 또는 ai_studio/code 산출물이 생성됨

warn:
- Python 버전 경고가 있지만 실행은 가능함
- MLflow logging은 실패했지만 로컬 ai_studio 산출물은 생성됨

needs_user_input:
- entrypoint 후보가 여러 개임
- 기존 artifact 덮어쓰기 가능성이 있음
- MLflow 설정 값을 사용자가 직접 입력해야 함

blocked:
- 학습/모델 생성 entrypoint 없음
- 실행 후 산출물이 없음
- 필수 입력 데이터/config 없음
```

</details>

<details>
<summary>문제 해결 보기</summary>

```text
증상: run_model.py가 없다는 이유로 중단됨
원인: 실제 entrypoint 확인 없이 run_model.py로 고정함
조치: train.py, runtest.py, scripts/train.py 등 후보를 찾고 사용자에게 실제 파일명을 확인한다.

증상: 모델 실행 후 산출물이 안 보임
원인: model_info.json만 확인하거나 ai_studio/code 기준이 빠짐
조치: ai_studio/metrics, ai_studio/code, MLflow artifact_path="ai_studio" 아래 code/를 확인한다.

증상: Windows native 실행 실패
원인: standalone/native executable 경로 사용
조치: python entrypoint, mlflow.pyfunc, aiu_custom wrapper 기반 실행으로 우회한다.
```

</details>

<details>
<summary>전문가 상세 보기</summary>

기존 모델 흐름:

```text
1. selected_project_path를 실행 기준으로 사용
2. 실제 entrypoint 확정
3. config/input/dataset/model path 확인
4. dry run 또는 smoke test 확인
5. MLflow 설정 확인
6. 학습 또는 export 실행
7. ai_studio/metrics, ai_studio/code 확인
```

샘플 모델 흐름:

```text
1. selected_sample 확인
2. target_project_path 확인
3. aiu_custom/, local_serving/, saved_model/ 확인
4. requirements.txt, input_example.json 확인
5. run_model.py 또는 runtest.py 실행
6. ai_studio 산출물 확인
```

</details>

<details>
<summary>Safety 규칙 보기</summary>

- 오래 걸리는 학습은 예상 비용과 시간을 먼저 설명한다.
- 기존 artifact를 덮어쓸 수 있으면 실행 전 사용자 확인을 받는다.
- 샘플 원본을 직접 수정하지 않는다.
- 원격 학습이나 외부 데이터 다운로드는 기본 동작으로 가정하지 않는다.
- secret 값은 출력하지 않는다.
- Windows native/standalone executable 실행은 기본 경로로 안내하지 않는다.

</details>
