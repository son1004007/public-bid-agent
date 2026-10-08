# ADR-004 AI 추론 연결·요금·장애 시 기능 범위

- 상태: **외부 서비스 지원 범위 검증 전 조건부 설계**
- 관련 지적: DSR-008, Gemini F-01
- 상위 요구사항: 별도 종량제 OpenAI API 과금을 MVP 필수 전제로 삼지 않는다. 상용 LLM 및 실제 사용자 대상 서비스 가능성 확보를 지향한다.

## 공식 근거와 구분

- OpenAI [Sign in with ChatGPT 오픈소스 개요](https://developers.openai.com/siwc/token-sharing-open-source): 이용 자격이 있는 사용자가 자신의 ChatGPT 플랜을 이용하여 적격 AI 요청을 실행할 수 있는 연동이 있다.
- OpenAI [오픈소스 앱 연동 안내](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt): **로컬 실행 오픈소스/개인 프로젝트**에 대한 경로와, **유료·원격 호스팅 앱에 대한 별도 참여 신청**을 구분한다.
- OpenAI [Self-hosted VM](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms): 특정 사용자 소유 원격 VM 사용 설명이 존재하나, 불특정 다수가 사용하는 공개 호스팅 서비스의 승인으로 해석하지 않는다.
- 개발자 API 사용량 과금과 ChatGPT 플랜 권한은 별개다. 사용권/인증 관련 정보는 구현 전에 현재 공식 문서와 해당 앱 참여 승인 조건으로 확인한다.

## 결정

1. **Google OIDC 앱 로그인**과 **ChatGPT/Codex 모델 사용 권한**은 서로 다른 인증·동의·세션 경계다. Google 로그인만으로 모델을 호출하지 않는다.
2. 사용자 API Key, ChatGPT 비밀번호, 브라우저 쿠키 또는 개인 Codex 로그인 세션을 임의 수집·공유하지 않는다. NAS 개인 세션을 공개 서비스의 공용 추론 자격증명으로 재사용하지 않는다.
3. 원격 호스팅 공개 웹사이트에서는 별도 적격성/참여 승인 및 사용 조건 확인 전 `SIWC remote inference`를 **비활성화**한다.
4. 실제 AI 추론이 가능한 인증 경로가 검증되지 않은 상태에서 'AI 분석 제공'을 운영 기능으로 표시하지 않는다.
5. LLM 경계는 `Provider.analyze(requirements, evidence, profile, limits)`처럼 인증/호출 코드를 도메인에서 분리하고 `fake`(검증용), `approved_remote`(검증 후), `disabled` 상태를 구분한다. 모델 출력은 비신뢰 데이터다.
6. 승인된 제공자에 대해서만 사용자 동의·데이터 전송 범위, 호출 횟수/토큰/비용 budget, rate limit 및 철회·실패 시 동작을 정한다.
7. 별도 종량제 API 비용을 필수로 하지 않는 조건이 충족되지 않는 한, 공개 데모는 공식 공고 검색·원문/요건·근거 기반 규칙 검토를 제공하고 AI 분석 기능은 `이용 불가/검증 중`으로 명확히 표시한다. 오프라인 fixture + fake provider 시연은 **AI 모델 실제 추론으로 주장하지 않는다**.
8. 사용자에게 유료 API 키 입력을 요구하는 방식과 로컬 LLM은 사용자가 선호하지 않는 대안이므로 **자동 채택하지 않는다**. 선택 변경은 별도 사용자 결정 대상이다.
9. embedding은 ADR-003에서 별도 결정한다. 추론 계정이 embedding 권한을 제공한다고 가정하지 않는다.

## 결정 게이트와 검증

- 원격 호스팅 형태·오픈소스 공개 여부·신청/승인 필요성 및 현재 적격성에 대한 공식 근거 확보.
- 승인된 경우 최소 1인/2인 테스트 계정으로 명시적 동의, 호출 범위, 제한 초과/철회, 사용자 격리, 사용량 표시, 세션 갱신을 E2E 검증.
- 승인 불가/미확정 시 기능 비활성·fallback 확인. 운영 비용을 정액과 종량으로 나누어 측정·고지하고 과금을 추측하지 않는다.
