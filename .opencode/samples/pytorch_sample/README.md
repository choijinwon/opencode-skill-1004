# pytorch_sample

폐쇄망에서 사용자가 PyTorch 계열 모델 샘플을 넣는 기본 폴더입니다.

이 폴더는 기본 자리만 제공합니다. 실제 모델 코드, 데이터, artifact는 사용 환경에 맞게 추가합니다.

권장 구조:

```text
aiu_custom/
local_serving/
save_model/
run_model.py
input_example.json
requirements.txt
```

## MLflow Tracking 설정

`runtest.py` 또는 `run_model.py`에서 tracking 값을 자동으로 만들거나 출력하지 않습니다.
사용자가 `run_model.py` 또는 `runtest.py`의 MLflow/AI Studio 설정 블록에 값을 직접 입력합니다.

필수 값:

```text
mlflow_tracking_url = ""          # tracking 서버 URL
mlflow_tracking_username = ""     # 사용자명
mlflow_tracking_password = ""     # 비밀번호, 출력 금지
mlflow_experiment_name = "pytorch_sample"
mlflow_register_model_name = "pytorch_sample_model"
```

주의: `mflow_tracking_url`이 아니라 `mlflow_tracking_url`을 사용합니다.

주의:

- 실제 API key, password, token 값은 넣지 않습니다.
- Git에는 `.env`, `ai_studio.env`, 대용량 모델 artifact를 올리지 않습니다.
- 사용자 워크스페이스에 모델이 없으면 `sklearn`, `pytorch`, `tensorflow` 중 하나로 이 폴더를 루트에 복사할 수 있습니다.
