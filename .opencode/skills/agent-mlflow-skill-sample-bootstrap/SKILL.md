---
name: agent-mlflow-skill-sample-bootstrap
description: Use when the user says "sklearn", "pytorch", "tensorflow", "샘플 생성", "폴더째 복사", "모델이 없음", or sample bootstrap; selects one bundled sample and copies the sample folder into the workspace.
license: MIT
compatibility: opencode
metadata:
  flow: ml-workspace-development
  stage: 00-sample-bootstrap
  step: 0
---

# Sample Bootstrap

## When To Use

- 사용자가 "현재 프로젝트에 아무것도 없다", "샘플을 폴더째 가져오고 싶다", "샘플 3개 중 선택해서 시작하고 싶다"고 요청할 때
- 모델 프로젝트 폴더에 `.opencode`만 있고 실제 모델 코드가 없을 때
- 폐쇄망 기본 모델 샘플을 빠르게 워크스페이스 아래 별도 폴더로 구성해야 할 때
- Project Analyze 결과에서 `model_found: false`가 나온 뒤 사용자가 `sklearn`, `pytorch`, `tensorflow`, `1번`, `2번`, `3번`처럼 선택했을 때

이 스킬은 `agent-mlflow-skill-project-analyze` 결과가 `model_found: false`일 때만 사용한다. 모델 파일이나 실행 entrypoint가 있으면 이 스킬을 실행하지 않는다.

## Natural Language Selection

사용자 선택은 고정 문구가 아니어도 된다. 아래 입력은 모두 선택으로 해석한다.

```text
1, 1번, 첫 번째, sklearn, 사이킷런
2, 2번, 두 번째, pytorch, torch, 파이토치
3, 3번, 세 번째, tensorflow, tf, keras, 텐서플로우, 케라스
```

선택 매핑:

```text
1 | 1번 | 첫 번째 | sklearn | 사이킷런 -> sklearn
2 | 2번 | 두 번째 | pytorch | torch | 파이토치 -> pytorch
3 | 3번 | 세 번째 | tensorflow | tf | keras | 텐서플로우 | 케라스 -> tensorflow
```

선택이 모호하면 복사하지 말고 다시 선택을 요청한다.

## Selectable Samples

사용자에게 아래 3개 중 하나를 선택하게 한다.

```text
1. sklearn
   샘플 폴더: .opencode/samples/sklearn_sample
   목적: 폐쇄망 sklearn 모델 프로젝트 기본 구조

2. pytorch
   샘플 폴더: .opencode/samples/pytorch_sample
   목적: 폐쇄망 PyTorch 모델 프로젝트 기본 구조

3. tensorflow
   샘플 폴더: .opencode/samples/tensorflow_sample
   목적: 폐쇄망 TensorFlow/Keras 모델 프로젝트 기본 구조
```

## Workspace Rule

기본 복사 방식은 `copy_mode: folder`다. 이 방식은 워크스페이스 루트에 파일을 풀어놓지 않고 선택한 샘플 폴더 자체를 복사한다.

```text
<workspace-root>/sklearn_sample/
<workspace-root>/pytorch_sample/
<workspace-root>/tensorflow_sample/
```

워크스페이스에 기존 파일이 있어도 대상 샘플 폴더가 없으면 복사할 수 있다. 단, 같은 이름의 샘플 폴더가 이미 있으면 기본적으로 중단한다.

`copy_mode: root`를 명시적으로 사용할 때만 프로젝트 루트가 아래 항목만 가지고 있는지 확인한다.

```text
.opencode/
.git/
.gitignore
.DS_Store
```

## Required Sample Folder Rule

선택형 샘플은 아래 기본 폴더를 원본 샘플 안에 가지고 있어야 한다.

```text
aiu_custom/
local_serving/
save_model/
```

기본 폴더가 없는 샘플은 선택형 폴더 복사 대상으로 사용하지 않는다.

## Copy Rule

선택한 샘플 폴더를 워크스페이스 아래로 폴더째 복사한다.

```text
<workspace-root>/<sample-folder>/aiu_custom/
<workspace-root>/<sample-folder>/local_serving/
<workspace-root>/<sample-folder>/save_model/
<workspace-root>/<sample-folder>/run_model.py
<workspace-root>/<sample-folder>/requirements.txt
<workspace-root>/<sample-folder>/input_example.json
```

`runtest.py`가 대상 워크스페이스 또는 대상 샘플 폴더에 이미 있으면 `run_model.py`를 새로 만들거나 덮어쓰지 않는다. 이 경우 `runtest.py`를 모델 생성/테스트 entrypoint로 사용한다.

복사하지 않는 항목:

```text
.venv/
__pycache__/
mlruns/
aiu_studio/
mlflow.db
.DS_Store
model/
saved_model/
artifacts/aiu_studio/
```

복사 후 아래 필수 폴더는 항상 복사된 샘플 폴더 안에 존재해야 한다. 샘플 원본에 없으면 빈 폴더로 생성한다.

```text
aiu_custom/
local_serving/
save_model/
```

## Script

샘플 목록 확인:

```text
python .opencode/scripts/bootstrap_sample_project.py --list
```

복사 전 dry-run:

```text
python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample sklearn
python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample pytorch
python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample tensorflow
```

실제 폴더 복사:

```text
python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample sklearn --execute
```

기존 파일이 있는데 사용자가 명시적으로 덮어쓰기를 요청한 경우:

```text
python .opencode/scripts/bootstrap_sample_project.py --project <model-project-folder> --sample sklearn --execute --force
```

## Required Response

샘플 복사 전 사용자에게 반드시 아래 형식으로 선택지를 보여준다.

```text
현재 워크스페이스에서 실행 가능한 모델을 찾지 못했습니다. 아래 샘플 중 하나를 폴더째 복사할 수 있습니다.

1. sklearn - sklearn 모델
2. pytorch - PyTorch 모델
3. tensorflow - TensorFlow/Keras 모델

원하는 샘플 번호 또는 이름을 알려주세요.
```

선택 질문을 출력해야 하는 조건:

```text
model_found: false
```

선택 질문을 출력하지 않는 조건:

```text
model_found: true
```

사용자가 선택하면 아래 정보를 출력한다.

```text
selected_sample
sample_source_path
target_project_path
copy_mode: folder
ignored_generated_files
next_action:
  1. 환경 검증
  2. 샘플 폴더 이동
  3. 환경 변수 입력
  4. 환경 변수 export
```

샘플 폴더 복사 후 첫 번째 다음 단계는 반드시 환경 검증이다.

```text
1. 환경 검증: python .opencode/scripts/check_environment.py --project <target_project_path>
```

세 번째 다음 단계는 반드시 환경 변수 입력 안내다. `run_model.py` 또는 `runtest.py`의 MLflow/AI Studio 설정 블록에 필수 값 5개를 사용자가 직접 입력하도록 안내하고, secret 값은 출력하지 않는다.

```text
3. 환경 변수 입력: run_model.py 또는 runtest.py의 설정 블록에 MLflow/AI Studio 필수 값 5개를 직접 입력
4. 환경 변수 export: run_model.py 실행 시 설정 블록 값을 MLFLOW_* 환경변수로 export
```

## Safety

- 사용자 선택 없이 임의로 샘플을 복사하지 않는다.
- 모델이 발견된 워크스페이스에서는 샘플 선택을 요청하지 않는다.
- 대상 샘플 폴더가 이미 있으면 기본적으로 중단한다.
- secret 값은 복사 후에도 출력하지 않는다.
- `.env`, `ai_studio.env`의 실제 key/password/token 값은 출력하지 않는다.
- 샘플 원본 폴더는 수정하지 않는다.
