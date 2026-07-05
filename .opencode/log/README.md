# Ai Studio Prompt Log

사용자가 작성한 프롬프트와 작업 히스토리를 남기는 폴더입니다.

## 기록 기준

- 사용자가 직접 작성한 프롬프트만 기록합니다.
- 비밀번호, 토큰, 내부 서버 인증값 같은 secret 값은 기록하지 않습니다.
- 실행 결과는 짧게 요약합니다.
- 긴 로그나 에러 전문은 필요한 경우 별도 파일로 분리합니다.

## 날짜별 폴더 구조

| 형식 | 예시 | 용도 |
|---|---|
| `YYYYMMDD/prompts.md` | `20260705/prompts.md` | 해당 날짜의 프롬프트/히스토리 기록 |
| `YYYYMMDD/errors.md` | `20260705/errors.md` | 해당 날짜의 에러 기록 |

## 기록 양식

```markdown
| Time | Type | Step | Content | Result |
|---|---|---|---|---|
```

## 기록 명령

```powershell
python .opencode/scripts/common/prompt_history.py --project . --type prompt --step "3 환경 검증" --content "사용자 프롬프트" --result "처리 결과"
```

```powershell
python .opencode/scripts/common/prompt_history.py --project . --type error --step "5 원격 MLflow 등록 실행" --content "에러 요약" --result "조치 내용"
```
