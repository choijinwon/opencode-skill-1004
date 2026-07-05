---
name: agent-mlflow-skill-environment-check
description: Use when the user asks "환경 검증", "dependency 확인", "MLflow 설치", ".env", "API key 위치", or environment check; verifies Python, dependencies, MLflow, env vars, and required AI Studio settings.
license: MIT
compatibility: opencode
metadata:
  flow: ml-workspace-development
  stage: 03-environment-check
  step: 3
---

# Execution Environment Check

## Result First

```text
판단 결과: pass | warn | needs_user_input | blocked
현재 단계: 3. 환경 검증
현재 대상: selected_project_path
핵심 판단: 현재 Python, 원격 MLflow version, dependency, 설정 상태
다음 단계: 사용자가 4. 템플릿 변환 선택 후, 사용자가 5. 원격 MLflow 등록 실행 선택
```

## Workflow

```text
1. 모델 목록 확인
2. 모델 선택
3. 환경 검증
4. 템플릿 변환 (사용자 선택)
5. 원격 MLflow 등록 실행 (사용자 선택)
6. 추론 테스트 (사용자 선택)
7. 오류 재실행 (사용자 선택)
```

## What To Do Now

```text
1. 선택 모델 정보가 config/config.json 기준으로 유지되는지 확인한다.
2. Python 실행 파일과 버전을 확인하되, 고정 버전 강제 대신 MLflow/requirements 호환성 기준으로 판단한다.
3. dependency 파일과 핵심 패키지를 확인하되, 로컬 설치를 요구하지 않는다.
4. 원격 MLflow 서버 version과 requirements.txt 변환 기준을 우선한다.
5. mlflow_tracking_uri이 있으면 원격 MLflow 서버 version을 확인하고, 확인된 서버 version에 맞춰 requirements.txt의 mlflow 버전을 변환한다.
6. 선택 모델 MODEL_KIND 기준으로 필요한 프레임워크 패키지만 requirements.txt에 반영한다. 선택 모델과 무관한 프레임워크 패키지는 제거한다.
7. 변환된 코드 import 기준 추가 Python 패키지가 필요하면 requirements.txt를 변환한다. 이때 필수 패키지 5개는 항상 유지한다.
8. `kserve==0.15.0`은 requirements.txt 필수 항목으로 유지한다. 로컬 PC 환경 검증에서는 kserve 미설치를 차단/처리 항목으로 표시하지 않고, 별도 설치를 요구하지 않는다.
9. requirements.txt에는 `torch==2.x.x+cpu`, `torchvision==...+cpu` 같은 wheel local tag를 넣지 않는다. CPU wheel 선택은 내부 Nexus/pip index 설정으로 처리하고, 파일은 `torch==2.x.x` 형식으로 유지한다.
10. `.env`의 비어 있는 값은 사용자가 직접 `.env`에 입력하도록 안내한다.
11. `mlflow_tracking_uri`, `mlflow_tracking_username`, `mlflow_tracking_password` 3개 값이 비어 있으면 4번 템플릿 변환과 5번 원격 MLflow 등록 실행으로 넘어가지 않는다.
```

## Output Contract

```text
기본 출력은 짧게 보여준다:
- 판단 결과
- 선택 모델 / MODEL_KIND
- Python 현재 version과 MLflow·requirements 호환성 기준
- requirements.txt 확인/변환 상태
- 원격 MLflow URI 상태
- 처리해야 할 항목
- 다시 검증 명령
- requirements 기본 항목: `mlflow`, `kserve==0.15.0`
- 선택 모델 패키지 후보: 모델 형식 기준 후보를 사용자가 직접 선택해 `requirements.txt`에 입력
- 이미지 모델 패키지 후보: 이미지/CNN/vision 모델일 때 `pillow`, `matplotlib` 등 보조 후보를 별도 표시

상세 출력은 사용자가 요청하거나 --verbose 실행 시에만 보여준다:
- OS, virtualenv, dependency 파일 전체
- requirements.txt 전체 패키지 목록
- 원격 MLflow 서버 version 상세
- 환경 변수 전체 상태
- TODO Guide
- 차단 항목 요약, Failures 전체
```

상태 출력 UI:

```text
판단 결과: warn
Python: compatibility_check, current=<현재버전>, 기준=MLflow/requirements
MLflow: set
Remote MLflow: version_match | version_mismatch | unreachable | skipped
Secrets: mlflow_tracking_password=set, value hidden
입력이 필요한 값: mlflow_tracking_uri, mlflow_tracking_username, mlflow_tracking_password
```

환경 검증 결과를 설명할 때는 `다음단계 진행하시겠습니까?`처럼 질문하지 않는다.
사용자가 해야 할 일은 아래처럼 짧게 안내한다.

```text
환경 검증 결과
- 판단 결과: needs_user_input
- Python: <현재버전> (MLflow/requirements 호환성 기준)
- requirements.txt: 확인/변환 완료
- 원격 MLflow URI: missing

처리해야 할 항목
1. Python <현재버전>: MLflow/requirements 호환성 확인
2. mlflow: 버전 불일치
3. .env 입력 필요: mlflow_tracking_uri, mlflow_tracking_username, mlflow_tracking_password

다시 검증
- python .opencode/scripts/03-environment-check/check_environment.py --project . --entrypoint runtest_2.py
```

## Commands

```text
환경 검증:
python .opencode/scripts/03-environment-check/check_environment.py --project .
python .opencode/scripts/03-environment-check/check_environment.py --project . --entrypoint <file>
python .opencode/scripts/03-environment-check/check_environment.py --project . --entrypoint <file>

폐쇄망 패키지 처리:
환경 검증 단계에서는 패키지를 설치하지 않는다.
mlflow/torch/numpy/pandas 미설치 또는 버전 불일치는 requirements.txt 변환 결과로만 보여준다.

PyTorch CPU wheel Nexus upstream 참고:
https://download.pytorch.org/whl/cpu

torch SSL 설치 금지:
https://download.pytorch.org, https://pypi.org 인덱스를 사용하지 않는다.
내부 http:// PyPI/Nexus 미러만 사용한다.

인덱싱 제외 적용:
python .opencode/scripts/03-environment-check/apply_index_ignore.py --project .
```

## Artifact Map

```text
local metrics   -> ai_studio/metrics/
local code      -> ai_studio/code/
MLflow artifact -> artifact_path="ai_studio" 아래 code/
tracking target -> 사용자가 입력한 원격 MLflow tracking 서버
artifact uri    -> Windows 상대경로 사용, 예: saved_model\model.pt, config\config.json
artifact path   -> Linux 패키지 내부 경로 사용, 예: artifacts/model.pt, artifacts/config.json
kserve path     -> Linux 컨테이너의 context.artifacts 경로 사용
forbidden       -> Windows 로컬 절대경로를 KServe 런타임 경로로 사용 금지
```

<details>
<summary>자세한 판단 기준 보기</summary>

```text
pass:
- 현재 Python에서 MLflow/requirements 필수 패키지 호환성 확인됨
- MLflow 3.13.0 설치됨
- 원격 MLflow 서버 version과 로컬 mlflow version 일치
- 핵심 dependency 확인됨
- 필수 MLflow 설정이 소스 또는 환경에 있음

warn:
- Python 버전은 고정 기대값이 아니라 MLflow/requirements 호환성 확인이 필요함
- 폐쇄망 설치 준비가 필요하지만 다음 단계 안내 가능
- 원격 MLflow 서버 version 확인 실패(unreachable)지만 URL/인증을 다시 확인할 수 있음

needs_user_input:
- mlflow_tracking_uri, username, password 입력 필요
- 실제 entrypoint 확인 필요

blocked:
- 프로젝트 경로 없음
- 실행 파일 없음
- requirements/config를 읽을 수 없음
- 원격 MLflow 서버 version과 로컬/requirements mlflow version 불일치
```

사용자가 직접 입력할 설정:

```text
mlflow_tracking_uri
mlflow_tracking_username
mlflow_tracking_password
```

`.env`의 MLflow 값이 비어 있으면 학습 테스트 실행을 진행하지 않는다. 사용자가 `.env`에 직접 입력한 뒤 같은 단계부터 다시 실행한다.

자동 생성되는 설정:

```text
mlflow_experiment_name
mlflow_register_model_name
```

`mlflow_tracking_uri`은 사용자가 직접 입력한다. 단, 5번 원격 MLflow 등록 실행에서는 원격 MLflow/리포트 URI만 사용한다. `http://` 또는 `https://`를 입력하고, `localhost`, `127.0.0.1`, `0.0.0.0`, `file://`, `sqlite:` 로컬 tracking은 사용하지 않는다.

</details>

<details>
<summary>문제 해결 보기</summary>

```text
증상: Python 버전 확인 필요
원인: 현재 Python에서 MLflow/requirements 필수 패키지 호환성을 확인해야 함
조치: 고정 버전 전환을 강제하지 않고 MLflow 서버 버전과 requirements.txt 기준으로 확인

증상: 환경변수를 입력했는데 체크가 안 됨
원인: `.env` 값 누락 또는 export 설정 누락
조치: `.env` 5개 값과 MLFLOW_* export 상태를 표시

증상: 폐쇄망 설치가 느림
원인: PyPI 다운로드/resolver 지연
조치: 내부 http:// PyPI/Nexus 미러와 requirements.txt 고정 버전 우선

증상: torch가 SSL 문제로 설치 불가
원인: pip가 https:// PyPI 또는 https://download.pytorch.org 인덱스를 사용함
조치: SSL 설치 금지. 내부 http:// PyPI/Nexus 미러 URI를 사용해 requirements.txt 기준으로 설치
```

</details>

<details>
<summary>전문가 상세 보기</summary>

허용 alias:

```text
tracking_uri -> mlflow_tracking_uri
username -> mlflow_tracking_username
password -> mlflow_tracking_password
```

원격 tracking/report URI:

```text
MLFLOW_TRACKING_URI=<사용자가 입력한 원격 http://... 또는 https://...>
MLflow artifact는 artifact_path="ai_studio" 아래 code/ 구조로 기록
```

</details>

<details>
<summary>Safety 규칙 보기</summary>

- secret 값을 로그나 응답에 포함하지 않는다.
- `MLFLOW_TRACKING_PASSWORD`와 `mlflow_tracking_password` 값은 절대 출력하지 않는다.
- 폐쇄망에서는 GitHub issue, crash report, telemetry URI를 열지 않는다.
- 환경 검증의 차단/경고 항목은 프로세스를 종료시키는 실패가 아니라 보고서 항목으로 출력한다.
- Bun 런타임은 사용하지 않는다.
- JavaScript 설치가 필요하고 `package.json`이 있으면 `npm i`만 사용한다.
- Windows에서는 `standaloneExecutable` 경로 대신 `python ...` 명령을 사용한다.
- Windows x86_64에서는 native/standalone executable 모델 실행을 기본 경로로 안내하지 않는다.

</details>
