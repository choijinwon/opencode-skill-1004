---
name: agent-mlflow-skill-inference-test
description: Use only when the user explicitly asks "추론 테스트", selects step 6, "input_example.json", "predict.py", "aiu_custom 테스트", "local_serving", or inference test after selected-model preparation is complete; loads the prepared model wrapper and verifies predict contract and response schema. Do not use for model number selection.
license: MIT
compatibility: opencode
metadata:
  flow: ml-workspace-development
  stage: 04-inference-test
  step: 4
---

# Inference Test

## Result First

```text
판단 결과: pass | warn | needs_user_input | blocked
현재 단계: 추론 테스트
진행 조건: 사용자가 6번을 선택했을 때만 실행
현재 대상: trained model project
핵심 판단: config/config.json 선택 모델, input_example, load mode, predict contract, output schema
다음 단계: 7. 오류 재실행
```

## Workflow

```text
1. 모델 목록 확인
2. 모델 선택
3. 환경변수/requirements 갱신
4. 템플릿 변환
5. 원격 MLflow 등록 실행
6. 추론 테스트
7. 오류 재실행
```

## What To Do Now

```text
1. input_example.json을 확인한다.
2. local_serving/localservingtest.py를 확인한다.
3. config/config.json의 선택 모델 경로와 MODEL_KIND를 확인한다.
4. localservingtest.py의 load_selected_model()과 predict contract를 확인한다.
5. Windows native load는 보조 확인으로만 둔다.
6. 결과가 JSON serializable인지 확인한다.
```

## Output Contract

```text
반드시 보여줄 값:
- 판단 결과
- 사용한 input example
- 추론 entrypoint: local_serving/localservingtest.py
- 모델 로드 방식
- predict 결과 요약
- response schema
- result_path: not written, unless --output is set
- 다음 단계
```

성공 출력 UI:

```text
판단 결과: pass
input_example: input_example.json
load mode: aiu_custom wrapper
schema: JSON serializable
result_path: not written
next: MLflow verify
```

## Commands

```text
실제 추론 실행:
cd '<selected-project-path>\local_serving'
python localservingtest.py

보조 스크립트:
python .opencode\scripts\05-inference-test\test_inference.py --project <project> --execute
```

<details>
<summary>자세한 판단 기준 보기</summary>

```text
pass:
- input example 있음
- 모델 로드 성공
- predict 성공
- output schema 확인됨

warn:
- native load는 실패했지만 pyfunc/custom wrapper로 우회 가능
- 결과가 길어 요약 출력함

needs_user_input:
- input example이 없음
- 어떤 추론 entrypoint를 사용할지 모호함

blocked:
- 모델 로드 실패
- predict 실행 실패
- 응답을 직렬화할 수 없음
```

</details>

<details>
<summary>문제 해결 보기</summary>

```text
증상: native load 실패
원인: Windows x86_64 native/standalone 실행 불안정
조치: mlflow.pyfunc.load_model, aiu_custom wrapper, run_model.py/runtest.py 기반 검증으로 우회

증상: input_example 없음
원인: 테스트 입력 누락
조치: input_example.json 또는 README 예제를 먼저 확정

증상: predict 결과를 JSON으로 못 바꿈
원인: numpy/pandas/object 반환값 직렬화 처리 누락
조치: schema를 요약하고 JSON serializable 형태로 변환 기준을 안내
```

</details>

<details>
<summary>전문가 상세 보기</summary>

추론 entrypoint 후보:

```text
predict.py
aiu_custom/model_wrapper.py
aiu_custom/predict.py
local_serving/
run_model.py
runtest.py
serving/test script
```

모델 로드 우선순위:

```text
1. mlflow.pyfunc.load_model
2. aiu_custom custom wrapper load
3. framework native load, Windows에서는 보조 확인만
```

</details>

<details>
<summary>Safety 규칙 보기</summary>

- secret 또는 개인정보가 포함된 입력 예제를 그대로 출력하지 않는다.
- 추론 결과가 길면 schema 중심으로 요약한다.
- 외부 LLM endpoint 호출이 필요한 경우 endpoint와 인증 설정 존재 여부를 먼저 확인한다.
- 사용자가 별도로 요청하지 않는 한 native executable 실행 명령을 안내하지 않는다.

</details>
