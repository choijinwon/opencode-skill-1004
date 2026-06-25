---
name: agent-mlflow-skill-project-analyze
description: Use when the user asks "분석해줘", "MLflow 모델 프로세스", "모델 있음/없음", "워크스페이스 분석", or project structure analysis; analyzes framework, entrypoint, artifact, config, input example, aiu_custom/local_serving/saved_model.
license: MIT
compatibility: opencode
metadata:
  flow: ml-workspace-development
  stage: 01-project-analyze
  step: 1
---

# Project Structure Analysis

## Result First

```text
판단 결과: pass | needs_user_input | blocked
현재 단계: 1. 프로젝트 분석
현재 대상: workspace root 또는 user project path
핵심 판단: model_found: true | false
다음 단계: 모델 있음 -> 환경 검증 / 모델 없음 -> 샘플 선택
```

## Workflow

```text
1. 프로젝트 분석
2. 환경 검증
3. 샘플 규격 확인/보충
4. 환경 변수 입력/export
5. 패키지 설치
6. 로컬 학습 모델 실행
7. 산출물 확인
```

## What To Do Now

```text
1. 현재 워크스페이스 경로를 확인한다.
2. 모델 파일, 실행 entrypoint, 필수 폴더를 찾는다.
3. model_found 값을 먼저 결정한다.
4. 모델이 있으면 샘플 선택을 묻지 않는다.
5. 모델이 없으면 1 sklearn / 2 pytorch / 3 tensorflow 선택지를 보여준다.
```

## Output Contract

```text
반드시 보여줄 값:
- model_found: true | false
- selected_project_path
- framework
- train_entrypoint
- inference_entrypoint
- model_artifact_path
- input_example_path
- 발견 항목
- 누락 항목
- 다음 단계
```

모델이 있으면:

```text
판단 결과: pass
model_found: true
다음 단계: 2. 환경 검증
```

모델이 없으면:

```text
판단 결과: needs_user_input
model_found: false
선택 가능:
1. sklearn
2. pytorch
3. tensorflow
```

<details>
<summary>자세한 판단 기준 보기</summary>

```text
pass:
- 실행 가능한 모델 구성 또는 entrypoint를 찾음

needs_user_input:
- 모델을 찾지 못했고 샘플 선택이 필요함
- 모델은 있으나 실제 학습/모델 생성 entrypoint 후보가 여러 개라 사용자 확인이 필요함

blocked:
- 지정한 프로젝트 경로가 없음
- 읽을 수 없는 경로이거나 분석 자체가 불가능함
```

모델 프로젝트 판단 기준:

```text
학습 entrypoint: train.py, scripts/train.py
실행/등록 entrypoint: runtest.py, run_model.py
추론 entrypoint: predict.py, app.py, main.py
필수 폴더: aiu_custom/, local_serving/, saved_model/
모델 wrapper: aiu_custom/model_wrapper.py, aiu_custom/predict.py
모델 artifact: ai_studio/, saved_model/, model/, artifacts/, .pkl, .joblib, .pt, .pth, .h5, .keras
MLflow model: MLmodel, python_model.pkl
입력 예제: input_example.json
```

</details>

<details>
<summary>문제 해결 보기</summary>

```text
증상: 모델이 있는데 샘플 선택지가 나옴
원인: entrypoint 또는 artifact 근거를 찾지 못함
조치: 실제 사용하는 학습 파일명과 모델 경로를 먼저 확정한다.

증상: run_model.py로 고정해서 안내됨
원인: 기존 모델 프로젝트의 실제 entrypoint 확인이 빠짐
조치: "로컬 학습/모델 생성에 실제로 사용하는 파일명을 알려주세요."라고 묻는다.

증상: 샘플 규격 폴더가 부족함
원인: aiu_custom/, local_serving/, saved_model/ 등이 누락됨
조치: 샘플 선택 질문을 하지 말고 --scaffold-existing으로 부족한 골격만 보충한다.
```

</details>

<details>
<summary>전문가 상세 보기</summary>

Framework evidence:

```text
sklearn: sklearn, .pkl, .joblib, .fit()
pytorch: torch, .pt, .pth, state_dict
tensorflow: tensorflow, keras, .h5, .keras, saved_model.pb
huggingface: transformers, tokenizer files, model.safetensors
custom pyfunc: mlflow.pyfunc.PythonModel, aiu_custom, ModelWrapper
```

보충 명령:

```text
python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample <sklearn|pytorch|tensorflow> --scaffold-existing --execute
```

</details>

<details>
<summary>Safety 규칙 보기</summary>

- Launch 모드에서는 분석만 수행하고 파일을 수정하지 않는다.
- 모델이 발견되면 `.opencode/samples` 선택을 요청하지 않는다.
- 샘플 규격 보충은 기존 모델 파일을 덮어쓰지 않는다.
- secret 값은 출력하지 않는다.
- 발견한 artifact를 이동하거나 복사하지 않는다.

</details>
