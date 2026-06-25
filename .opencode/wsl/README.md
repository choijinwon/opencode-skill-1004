# WSL Offline Package Install

폐쇄망에서는 Python 패키지 다운로드가 느리거나 실패할 수 있으므로 `.opencode/wsl/wheelhouse/`에 wheel 파일을 미리 받아두고 오프라인 설치를 우선 사용한다.

## 1. 온라인 WSL에서 wheelhouse 만들기

```bash
bash .opencode/wsl/download_wheels.sh
```

내부 PyPI 미러를 써야 하면 WSL 환경에서 `PIP_INDEX_URL` 또는 `PIP_EXTRA_INDEX_URL`을 먼저 설정한 뒤 실행한다.

```bash
export PIP_INDEX_URL="https://<internal-pypi>/simple"
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
