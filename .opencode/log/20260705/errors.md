# Error Log - 2026-07-05

| Time | Type | Step | Content | Result |
|---|---|---|---|---|
| 20:50:08 | error | import | ModuleNotFoundError: No module named 'aiu_custom' | 실행 위치 또는 템플릿 변환 후 aiu_custom 폴더 생성 여부 확인 필요 |
| 20:53:10 | error | 5 원격 MLflow 등록 실행 | 5번 실패 시 워크스페이스 생성 폴더가 삭제됨 | saved_model 복사를 임시 경로 성공 후 교체 방식으로 변경 |
