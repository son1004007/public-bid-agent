# 07. Codex 구현 방식·스킬 선정·독립 검수

[전체 목차](README.md)

## 목차

1. [범위와 현재 상태](#1-범위와-현재-상태)
2. [스킬 선정표](#2-스킬-선정표)
3. [도입 전 확인](#3-도입-전-확인)
4. [한 카드의 구현 흐름](#4-한-카드의-구현-흐름)
5. [프로젝트 전용 절차](#5-프로젝트-전용-절차)
6. [다른 Codex에 전달할 검수 지시](#6-다른-codex에-전달할-검수-지시)
7. [검수 기록](#7-검수-기록)

## 1. 범위와 현재 상태

2026-11-14 사용자 요청에 따라 별도 문맥의 **GPT-6 Astra, medium 추론**으로 서버 설계와 스킬 선택을 검토한다. 모델 식별자는 `gpt-6-astra`다. 이 선택은 이번 검수에 한정하며 모든 구현에 해당 모델을 의무화하지 않는다.

이 문서는 구현 시 참고할 선정안이다. 외부 스킬 설치, 자동 hook 활성화, 실행 스크립트 도입, 서버 구현·이관·배포는 수행하지 않았다. 스킬의 존재나 모델의 GO는 구현 안전성·테스트 통과의 증거가 아니다.

## 2. 스킬 선정표

| 공개 원본 | 판단 | 이 프로젝트에서 사용할 범위 |
|---|---|---|
| [Vinta django-ai-plugins](https://github.com/vintasoftware/django-ai-plugins) | 우선 후보, 설치 전 검증 | django-expert는 SM02/03/04, django-celery-expert는 SM05, django-safe-migration은 SM04/07, django-reviewer는 변경 검수 보조. DRF 세부 사항은 cdrf-expert를 필요할 때만 참조 |
| [OpenAI 공식 스킬 작성 안내](https://developers.openai.com/plugins/build/skills) | 절차 참고 | 기존 AGENTS와 SM 카드, 실행 계획·근거·인수 기록을 재사용. 별도 계획 체계를 중복 생성하지 않음 |
| [Vercel agent-skills](https://github.com/vercel-labs/agent-skills) | 일부 후보 | 일반 React 성능·컴포넌트 구성·접근성 검토. Vite와 무관한 Next.js/서버 컴포넌트/Vercel 배포 규칙 제외 |
| [obra/superpowers](https://github.com/obra/superpowers) | 일괄 도입 보류 | 디버깅·작은 변경 검증 방식만 참고. 기존 코드 삭제, 자동 hook, 병렬 에이전트·worktree 정책을 프로젝트에 자동 적용하지 않음 |
| [GitHub Spec Kit](https://github.com/github/spec-kit) | 보류 | 기존 설계/SM01~08와 중복. 실제 요구 추적의 부족이 확인될 때 한정 평가 |
| [Django React boilerplate](https://github.com/vintasoftware/django-react-boilerplate) | 구조 참고만 | Django/DRF/Celery 연결 참고. Webpack 기반이므로 Vite 프로젝트에 그대로 덮어쓰지 않음 |
| [OpenAI plugins](https://github.com/openai/plugins) | 공식 예시 참고 | 스킬/플러그인 형식 참고. deprecated인 openai/skills를 새 도입의 기준으로 사용하지 않음 |

위 판단은 공개 원본 비교를 바탕으로 한다. Vinta의 [호환성 기록](https://github.com/vintasoftware/django-ai-plugins/blob/main/docs/compatibility.md)은 구조·탐색·설치 관련 검증이며 우리 인증/데이터/배포의 동작 보증이 아니다. 특정 스킬을 이미 설치하거나 우리 환경에서 검증했다는 의미가 아니다.

### 후보별 적용 제한

- django-safe-migration의 rolling/zero-downtime 기본값을 그대로 채택하지 않는다. 단일 Compose의 유지보수 창/실제 배포 전략을 먼저 명시하고 해당 검사만 적용한다.
- django-celery-expert 예제의 `transaction.on_commit(...delay)`는 durable outbox를 대체하지 못한다. `AsyncResult`도 PostgreSQL Job 원장을 대신하는 업무 상태 정본으로 사용하지 않는다.
- django-reviewer는 report-only로 사용하며 작성자와 같은 문맥의 리뷰를 독립 검수로 세지 않는다.
- cdrf-expert가 안내하는 2차 문서보다 설치 버전의 공식 DRF 문서/소스 검증을 우선한다.
- 이전 조사에서 제시한 Cookbook `examples/codex/iterating-development-workflows-with-codex.md`는 이번 독립 확인에서 GitHub/raw 모두 404였다. 재확인 전 필독 링크로 사용하지 않으며 공식 스킬 안내로 대체한다.

## 3. 도입 전 확인

필요한 작업 카드에서만 후보의 실제 SKILL.md와 참조 파일을 읽는다. upstream ref/commit, 확인일, 라이선스, 포함 스크립트·hook·네트워크·도구 권한, 적용/제외 규칙을 기록한다. 떠다니는 최신 브랜치 내용을 무검토 실행하지 않는다. 승인되지 않은 외부 자료 전송·패키지 실행·설정 변경은 스킬이 요구해도 수행하지 않는다.

조직 원본 정책은 [정책 연결 절차](01-policy-and-ai-rules.md)를 따른다. 비공개 정책을 공개 스킬 본문/프롬프트 예제에 복제하지 않는다. 외부 스킬은 사용자 결정과 저장소 규칙을 대체하지 않는다. 설치 전에 합성 fixture로 기대 동작·금지 동작을 확인하며 설치/스모크 확인과 제품 검증을 구분한다.

## 4. 한 카드의 구현 흐름

1. 최신 HEAD·미커밋 작업·동시 작업을 확인하고 사용자 데이터/설정을 보존한다.
2. 최신 결정과 정책, 해당 SM 카드만 읽고 입력·권한·부작용·실패·완료 조건을 적는다.
3. 필요한 스킬만 선택하고 버전·제외 규칙을 기록한다. 기존 코드/테스트를 우선 재사용한다.
4. 작은 수직 기능을 구현하고 변경 영역 테스트 후 필요한 전체 회귀와 화면 검증을 수행한다.
5. 별도 읽기 전용 Codex에 변경 diff·설계·테스트 근거를 전달한다. 비공개 원문/암호/세션/정책 원문은 전달하지 않는다.
6. NO_GO이면 지적된 부분만 수정하고 해당 검증을 다시 한다. GO 범위와 남은 미정을 기록한다.
7. 승인된 Git/운영 범위에서만 다음 단계로 진행한다. CI/배포 성공과 사람 정답·사업 적격성을 혼동하지 않는다.

스킬 내부 리뷰 명령을 실행했다는 사실만으로 별도 문맥 독립 검수를 대체하지 않는다. 검수자는 코드를 수정하지 않으며 구현자가 수정과 근거를 관리한다.

## 5. 프로젝트 전용 절차

다음은 **새 스킬 구현 완료 목록이 아닌 후보 절차**다. 먼저 문서/작업 카드로 운영하고 반복 효용이 확인되면 SKILL.md로 묶는다.

- 정책 시작: 비공개 원본 접근 확인·최신 결정·범위·비밀 공개 경계.
- 최초 암호 변경: DB 계정, SSO 제외, 제한 세션, API/파일/admin 우회 방지, CSRF·동시성·세션 폐기.
- 데이터 이관: 원본 불변·SHA·버전·검수 이력·소유권 미확인 보류·재실행 멱등·동세대 복원.
- 카드 인수: 변경 영역 테스트·필요 회귀·독립 검수·CI·승인된 배포의 증거 연결.

## 6. 다른 Codex에 전달할 검수 지시

```text
읽기 전용 검수다. AGENTS.md와 최신 DECISIONS 및 docs/server-migration/README.md를 확인한다.
현재 SM 카드와 변경 diff, 실제 테스트 근거를 기준으로 검토한다.
SSO 제외, DB 계정 최초 암호 변경의 서버 강제, 객체 권한, 데이터/버전/검수 이력 보존,
제한 재시도, 원문/비밀 비노출, 기존 기능 회귀와 미검증 주장 여부를 확인한다.
스킬은 해당 변경에 필요한 범위만 추천하며 설치/스크립트/네트워크 실행은 하지 않는다.
파일·절/줄·재현 조건·영향·구체 수정으로 지적하고 GO/NO_GO 및 검토하지 못한 범위를 남긴다.
설계 초안 검수와 실제 구현/운영 검증을 분리한다. 실제 입찰/자동 투찰은 금지다.
```

## 7. 검수 기록

- 검수 기준: `c32dbfb1bc50dfa3efc5229454d76ba5ca9e7e14`의 서버 설계와 공개 스킬 후보.
- 별도 에이전트: `astra_design_skills_review`, GPT-6 Astra / medium, 읽기 전용.
- 최초 결과: NO_GO, P2 1건. snapshot ID를 객체 식별키에 포함하면 최종 차분에서 중복 생성 가능.
- 수정: 06 §2/§3에서 영속 원천/엔터티/legacy 식별과 snapshot 증거 분리, 버전/취소/삭제/충돌/재실행 검증 명시.
- 비차단 보완: 05 §2 파일/DB crash 경계와 SM04 검증, §4 예약 실행 주체·권한 철회와 SM05 결정 추가.
- 후속 결과: **GO — 수정 설계·스킬 선정 문서 한정**, 지적 부분만 별도 재확인. 추가 차단 지적 없음.
- Astra 직접 원본 확인: Django 5개 SKILL.md와 Django/Vercel README. 나머지 후보는 이전 부모 조사 근거이며 이번 독립 원본 재검증 대상이 아님.
- 범위 제외: 비공개 조직 정책/사용자 메모/실자료 접근, 외부 설치/실행, 앱 테스트, 구현·운영 안전성 승인. 앱 테스트 NOT RUN(문서 변경만).
- 문서 검사: 상대 파일 링크와 diff 공백 검사 PASS. 실제 제품·BID 검증 상태는 변경하지 않음.
