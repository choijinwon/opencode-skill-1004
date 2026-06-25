# Start Guide

## Mode Priority

이 파일은 Launch 모드 진입 안내용 전역 참고 문서입니다.
현재 활성 모드가 Build 모드이거나 Build 탭 프롬프트가 적용된 상태에서는 Launch 읽기 전용 규칙을 적용하지 않습니다.
Build 모드에서 사용자가 `1`, `2`, `3`, `sklearn`, `pytorch`, `tensorflow` 중 하나를 입력하면 안내만 하지 말고 즉시 선택된 샘플 복사 명령을 실행합니다.
특히 `2`는 PyTorch 샘플 선택이므로 다음 명령을 직접 실행합니다.

```text
python .opencode/scripts/bootstrap_sample_project.py --project <workspace-root> --sample pytorch --execute
```

새 채팅 세션의 첫 assistant 응답에서는 사용자의 첫 입력 내용과 관계없이 Launch Guide를 먼저 출력합니다.
그 다음에는 곧바로 현재 워크스페이스를 분석해 모델 있음/없음을 확인합니다.
Launch 모드는 읽기 전용입니다. 파일 생성, 수정, 삭제, 복사, 설치, 실행, 커밋, 푸시는 Build 단계에서만 진행합니다.

적용 예:

- `하이`
- `안녕`
- `아무거나`
- `분석해줘`
- `sklearn 샘플 생성해줘` 같은 Build 단계 요청
- 그 밖의 구체적인 작업 요청

Launch Guide를 먼저 출력한 뒤에는 다음 기준으로 이어서 응답합니다.

- 첫 메시지가 어떤 단어이든 현재 워크스페이스 루트를 먼저 분석합니다.
- `model_found` 값을 먼저 결정하고 출력합니다.
- 모델이 있으면 발견된 모델 프로젝트 경로 기준으로 계속 진행합니다.
- 모델이 없으면 sklearn / pytorch / tensorflow 중 하나를 선택하도록 안내합니다.
- 첫 메시지가 구체적인 읽기 전용 요청이면 워크스페이스 분석 후 그 요청을 계속 처리합니다.
- 첫 메시지가 수정/복사/실행/설치/커밋/푸시 요청이면 Launch 모드에서는 수행하지 않고 Build 단계로 안내합니다.
- 같은 채팅 세션에서는 사용자가 명시적으로 다시 요청하지 않는 한 Launch Guide를 반복 출력하지 않습니다.

다음 표현은 Launch Guide 재출력 요청으로 처리합니다.

- `/launch`
- `런치 가이드`
- `처음 안내 다시`
- `시작 가이드`
- `launch guide`

보안 규칙:

- API keys, passwords, tokens, secret values를 출력하지 않습니다.
- secret-like field는 `set`, `empty`, `missing` 상태만 말합니다.
- Launch 모드에서는 파일이나 실행 상태를 변경하지 않습니다.
