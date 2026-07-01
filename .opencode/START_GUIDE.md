# Start Guide

## Quick View

```text
AIU Studio -> model_found 확인 후 복사/수정/설치/실행 가능
모델 있음  -> 루트/data 모델 목록 -> 모델 선택 -> 자동 준비 실행 -> 환경변수 체크
모델 없음  -> 1 sklearn / 2 pytorch / 3 tensorflow
진행 방법  -> 화면에 표시된 모델 번호나 단계 번호를 숫자 키로 입력

주의 -> 모델 파일은 aiu_studio/로 복사하지 않음, secret 값은 출력하지 않음
```

## Mode Priority

이 파일은 AIU Studio 모드 진입 안내용 전역 참고 문서입니다.
AIU Studio 모드는 생성/수정/설치/실행 권한을 포함합니다.
AIU Studio 모드에서 사용자가 숫자만 입력하면 최신 화면 상태를 먼저 판단합니다.
모델 목록이 표시된 상태라면 숫자는 TOD 단계가 아니라 모델 번호 선택입니다.
모델 번호 선택 직후에는 다음 명령을 직접 실행해 자동 준비를 먼저 끝냅니다.

```text
python .opencode/scripts/prepare_selected_model.py --project . --model <번호|경로> --execute
```

이 단계에서 `.opencode/samples/aiu_studio/` 내부 템플릿이 워크스페이스 루트로 복사되고, `runtest_2.py`, `local_serving/`, `saved_model/`, `aiu_custom/`, `input_example.json`, `requirements.txt`가 생성/갱신됩니다.
추론 테스트는 이 자동 준비 이후 단계에서만 실행합니다.

모델 목록이 없고 TOD Guide가 표시된 상태라면 숫자는 TOD 단계 선택입니다.
모델이 없어서 샘플 선택지가 표시된 상태라면 `1`, `2`, `3`은 각각 `sklearn`, `pytorch`, `tensorflow` 샘플 선택입니다.
특히 모델 없음 상태에서 `2`는 PyTorch 샘플 선택이므로 다음 명령을 직접 실행합니다.
이 패키지는 Python 스크립트만 사용합니다. opencode Bun 런타임 환경에서 파일 트리 오류 처리 중 세그멘테이션 폴트가 발생할 수 있으므로 `bun`, `bunx`, `bun install`, `bun run`을 사용하지 않습니다.
JavaScript 패키지 설치가 필요한 프로젝트이고 `package.json`이 있으면 `npm i`만 사용합니다.
폐쇄망 WSL에서는 `.opencode/wsl/wheelhouse/`가 있으면 `bash .opencode/wsl/install_offline.sh`로 바로 설치하고, 없으면 내부 `http://` PyPI 미러나 별도 PC에서 wheel 파일을 준비합니다. torch도 SSL/HTTPS 인덱스로 설치하지 않습니다.
PyTorch CPU wheel의 Nexus proxy upstream 참고 URL은 `https://download.pytorch.org/whl/cpu`입니다. 폐쇄망 WSL에서는 이 URL을 직접 쓰지 말고 내부 `http://` Nexus URL 또는 wheelhouse를 사용합니다.
폐쇄망에서 OpenCode 응답이나 인덱싱이 느리면 먼저 `python .opencode/scripts/response_speed_check.py --project .`로 원인을 확인한 뒤 `python .opencode/scripts/apply_index_ignore.py --project .`로 `.venv`, wheelhouse, MLflow 산출물, 대용량 모델 파일을 인덱싱 제외합니다.
Windows에서는 `standaloneExecutable` 실행 경로를 사용하지 않고, 워크스페이스에서 `python ...` 명령으로 스크립트를 직접 실행합니다.
Windows x86_64에서는 native/standalone 모델 실행이 불안정할 수 있으므로 Python 스크립트, `mlflow.pyfunc`, `aiu_custom` wrapper 흐름을 우선합니다.
전체 상태를 한 번에 보려면 `python .opencode/scripts/doctor.py --workspace . --project .`를 먼저 실행합니다.

Windows에서 AIU Studio 모드로 고정 실행하려면 프로젝트 루트에서 다음 파일을 실행합니다.

```powershell
.\start-aistudio.ps1
```

기존 `.\start-aiustudio.ps1`도 호환용으로 동작하지만, 에이전트 이름은 `aistudio`입니다.

`opencode`만 입력해도 AIU Studio 모드로 열고 싶으면 프로젝트 루트의 wrapper를 실행합니다.

```powershell
.\opencode.ps1
```

CMD 또는 현재 폴더 `.cmd` 실행을 허용하는 콘솔에서는 아래처럼 실행할 수 있습니다.

```bat
opencode
```

`.opencode` 폴더만 복사한 프로젝트에서는 다음 파일을 실행합니다.

```powershell
.\.opencode\start-aistudio.ps1
```

또는:

```powershell
.\.opencode\opencode.ps1
```

CMD에서는:

```bat
.\.opencode\opencode.cmd
```

```text
python .opencode/scripts/bootstrap_sample_project.py --project . --sample pytorch --execute
```

새 채팅 세션의 첫 assistant 응답에서는 사용자의 첫 입력 내용과 관계없이 AIU Studio Guide를 먼저 출력합니다.
그 다음에는 곧바로 현재 워크스페이스를 분석해 모델 있음/없음을 확인합니다.
AIU Studio 모드는 워크스페이스 분석 후 파일 생성, 수정, 삭제, 복사, 설치, 실행을 직접 진행할 수 있습니다. 커밋/푸시는 사용자가 명시적으로 요청한 경우에만 진행합니다.

적용 예:

- `하이`
- `안녕`
- `아무거나`
- `분석해줘`
- `sklearn 샘플 생성해줘` 같은 AIU Studio 실행 요청
- 그 밖의 구체적인 작업 요청

AIU Studio Guide를 먼저 출력한 뒤에는 다음 기준으로 이어서 응답합니다.

- 첫 메시지가 어떤 단어이든 현재 워크스페이스 루트를 먼저 분석합니다.
- `model_found` 값을 먼저 결정하고 출력합니다.
- 모델이 있으면 발견된 모델 프로젝트 경로 기준으로 계속 진행합니다.
- 모델이 없으면 sklearn / pytorch / tensorflow 중 하나를 선택하도록 안내합니다.
- 첫 메시지가 구체적인 읽기/수정/복사/실행/설치 요청이면 워크스페이스 분석 후 그 요청을 계속 처리합니다.
- 커밋/푸시는 사용자가 명시적으로 요청한 경우에만 진행합니다.
- 같은 채팅 세션에서는 사용자가 명시적으로 다시 요청하지 않는 한 AIU Studio Guide를 반복 출력하지 않습니다.

다음 표현은 AIU Studio Guide 재출력 요청으로 처리합니다.

- `/launch`
- `런치 가이드`
- `처음 안내 다시`
- `시작 가이드`
- `launch guide`

보안 규칙:

- API keys, passwords, tokens, secret values를 출력하지 않습니다.
- secret-like field는 `set`, `empty`, `missing` 상태만 말합니다.
- AIU Studio 모드는 필요한 파일 변경과 로컬 실행을 수행할 수 있습니다.
