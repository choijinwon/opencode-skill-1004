# 05 Inference Test

Skill folder:
`../../skills/05-agent-mlflow-skill-inference-test`

Scripts:

- `test_inference.py`

Generated runtime entrypoint:

- `local_serving/localservingtest.py`

Responsibility:

- 선택 모델 기준 추론 계약 점검
- `input_example.json` 기반 입력/출력 schema 확인
- local serving smoke test 확인
- `predict_2.py`는 생성하지 않고 `local_serving/localservingtest.py`만 사용
