# WSL Offline Package Install

폐쇄망에서는 Python 패키지 다운로드가 느리거나 실패할 수 있으므로 `.opencode/wsl/wheelhouse/`에 wheel 파일을 미리 받아두고 오프라인 설치를 우선 사용한다.
SSL은 사용하지 않는다. `torch`도 `https://download.pytorch.org` 같은 SSL 인덱스로 설치하지 않는다.

## 1. 온라인 WSL에서 wheelhouse 만들기

```bash
bash .opencode/wsl/download_wheels.sh
```

내부 PyPI 미러를 써야 하면 WSL 환경에서 `PIP_INDEX_URL` 또는 `PIP_EXTRA_INDEX_URL`을 먼저 설정한 뒤 실행한다.
URL은 반드시 `http://`여야 한다. `https://`를 넣으면 스크립트가 중단된다.

```bash
export PIP_INDEX_URL="http://<internal-pypi>/simple"
bash .opencode/wsl/download_wheels.sh
```

내부 미러 없이 SSL 문제로 `torch` 다운로드가 막히면, 인터넷이 되는 별도 PC에서 wheel 파일을 받아 `.opencode/wsl/wheelhouse/`에 직접 복사한다. 폐쇄망 PC에서는 다운로드하지 않고 `install_offline.sh`만 실행한다.

## Nexus URL 지정 위치

내부 Nexus 경로는 스크립트를 수정하지 않고 실행 시 `PIP_INDEX_URL`에 직접 지정한다.

```bash
PIP_INDEX_URL="http://<nexus-host>/repository/pypi/simple" bash .opencode/wsl/download_wheels.sh
```

필요하면 환경 변수로 먼저 지정해도 된다.

```bash
export PIP_INDEX_URL="http://<nexus-host>/repository/pypi/simple"
bash .opencode/wsl/download_wheels.sh
```

Nexus가 별도 trusted host 값을 요구하면 `PIP_TRUSTED_HOST`를 함께 지정한다.

```bash
export PIP_INDEX_URL="http://<nexus-host>/repository/pypi/simple"
export PIP_TRUSTED_HOST="<nexus-host>"
bash .opencode/wsl/download_wheels.sh
```

## 2. 폐쇄망으로 복사

온라인 환경에서 생성된 아래 폴더를 폐쇄망 워크스페이스의 같은 위치로 복사한다.

```text
.opencode/wsl/wheelhouse/
```

## 3. 폐쇄망 WSL에서 바로 설치

```bash
bash .opencode/wsl/install_offline.sh
```

기본 venv는 현재 작업 디렉터리의 `.venv`다. 다른 경로를 쓰려면 `VENV_DIR`을 지정한다.

```bash
VENV_DIR=.venv-ai bash .opencode/wsl/install_offline.sh
```

## Package Set

`requirements-ai-studio.txt`는 Python 3.11.9 기준 AI Studio/MLflow 샘플 실행용 고정 버전 목록이다.

```text
kserve==0.15.0
mlflow==3.10.0
numpy==1.26.4
pandas==2.2.3
requests==2.32.4
requests-oauthlib==2.0.0
joblib==1.5.1
matplotlib==3.10.3
cloudpickle==3.1.1
databricks-sdk==0.57.0
smart-open==7.1.0
scikit-learn==1.7.0
torch==2.7.1
torchmetrics==1.7.3
torchvision==0.22.1
```

주의: pip 패키지명은 정규 이름을 사용한다. `torchmetric`은 `torchmetrics`, `databricks` SDK는 `databricks-sdk`로 설치한다.
주의: `pip install torch -f https://...`, `--index-url https://...`, `--extra-index-url https://...` 방식은 사용하지 않는다.
