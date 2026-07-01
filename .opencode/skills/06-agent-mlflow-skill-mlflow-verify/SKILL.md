---
name: agent-mlflow-skill-mlflow-verify
description: Use when the user asks "MLflow 확인", "run 생성 확인", "artifact 확인", "registered model", "Model Registry", or MLflow verify; checks runs, params, metrics, artifacts, pyfunc logging, and registered model status.
license: MIT
compatibility: opencode
metadata:
  flow: ml-workspace-development
  stage: 05-mlflow-verify
  step: 5
---

# MLflow Run And Model Verification

## Result First

```text
판단 결과: pass | warn | needs_user_input | blocked
현재 단계: MLflow 검증
현재 대상: tracking URI, experiment, latest run
핵심 판단: run, metrics, artifact, registry 상태
다음 단계: 완료 또는 차단 항목 해결
```

## Workflow

```text
1. tracking target 확인
2. experiment 확인
3. 최근 run 확인
4. params/metrics/tags 확인
5. artifact_path="ai_studio" 아래 code/ 확인
6. registry 상태 확인
7. 완료 또는 후속 조치 안내
8. 오류가 있으면 수정 후 실패한 단계부터 재검증
```

## What To Do Now

```text
1. tracking URI를 확인한다.
2. experiment name 또는 id를 확인한다.
3. 최신 run을 찾는다.
4. metrics와 artifacts를 확인한다.
5. registry 등록 여부를 확인한다.
```

## Output Contract

```text
반드시 보여줄 값:
- 판단 결과
- tracking target
- experiment
- latest run id
- metrics status
- artifact status
- registry status
- MLflow UI 또는 local path
- 남은 차단 항목
```

성공 출력 UI:

```text
판단 결과: pass
run: created
metrics: pass
artifacts: pass, artifacts/ai_studio/code/...
registry: pass | warn
```

## Commands

```text
MLflow 확인:
cd '<selected-project-path>'
python '<opencode-package-path>\.opencode\scripts\verify_mlflow.py' --project '<selected-project-path>'

tracking URI 명시:
cd '<selected-project-path>'
python '<opencode-package-path>\.opencode\scripts\verify_mlflow.py' --project '<selected-project-path>' --tracking-uri http://<tracking-server>

experiment 명시:
cd '<selected-project-path>'
python '<opencode-package-path>\.opencode\scripts\verify_mlflow.py' --project '<selected-project-path>' --experiment-name <name>
```

`--tracking-uri`에는 원격 MLflow/리포트 URL인 `http://` 또는 `https://`만 사용한다. `file://` 로컬 tracking은 사용하지 않는다.

## Artifact Map

```text
local metrics   -> ai_studio/metrics/
local code      -> ai_studio/code/
MLflow artifact -> artifacts/ai_studio/code/
tracking target -> 사용자가 입력한 원격 MLflow tracking 서버
```

<details>
<summary>자세한 판단 기준 보기</summary>

```text
pass:
- experiment 확인됨
- latest run 생성됨
- metrics 기록됨
- artifact_path="ai_studio" 아래 code/ 확인됨

warn:
- registry만 없음
- remote registry 확인 권한 부족이나 후속 확인 가능

needs_user_input:
- tracking URI 또는 experiment name이 모호함
- registry 등록 여부를 사용자가 결정해야 함

blocked:
- tracking server 접근 실패
- experiment 없음
- run 없음
- artifact 없음
```

</details>

<details>
<summary>문제 해결 보기</summary>

```text
증상: run은 있는데 artifact가 없음
원인: log_artifacts 또는 artifact_path 설정 누락
조치: artifact_path="ai_studio" 아래 code/ 구조를 확인

증상: registry만 없음
원인: 모델 등록을 수행하지 않았거나 권한 부족
조치: warn으로 표시하고 등록 여부를 사용자에게 확인

증상: remote tracking 접근 실패
원인: URL, username, password, network, 권한 문제
조치: secret 값은 숨기고 set/empty/missing 상태만 표시
```

</details>

<details>
<summary>전문가 상세 보기</summary>

검증 대상:

```text
tracking target: remote MLflow/report URL only
experiment: name 또는 id
run: latest run
records: params, metrics, tags, artifacts
pyfunc model: MLmodel, python_model.pkl, code/, signature, input example
registry: registered model, version, source URI, alias/stage/tag
```

GenAI agent 추가 확인:

```text
traces
chat sessions
prompts
judges
datasets
```

</details>

<details>
<summary>Safety 규칙 보기</summary>

- 인증 정보는 출력하지 않는다.
- remote registry 등록/삭제/alias 변경은 사용자가 명확히 요청한 경우에만 수행한다.
- artifact root가 sample 내부인지 별도 `ai_studio` 경로인지 구분해서 설명한다.
- secret-like field는 `set`, `empty`, `missing` 상태만 말한다.

</details>
