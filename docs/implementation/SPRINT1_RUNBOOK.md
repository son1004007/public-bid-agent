# Sprint 1 실행 및 검증

## 실제 구현 범위

- FastAPI 읽기 전용 /api/health, /api/notices, /api/notices/{id}.
- React/TypeScript 검색/분류/상세·0건/오류 화면.
- 소스 데이터는 backend/app/data/sample_notices.json 합성 fixture 4건뿐이다.
- 인증·공식 API·LLM·RAG·PDF 파서는 **이 스프린트에 구현하지 않았다**.

## 로컬 실행

Python 3.12+, Node 22.12+ 권장. 두 터미널을 사용한다.

Linux/macOS 첫 터미널:

    python -m venv .venv
    source .venv/bin/activate
    python -m pip install -r backend/requirements-dev.txt
    PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8000

Windows PowerShell 첫 터미널:

    py -3 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r backend/requirements-dev.txt
    $env:PYTHONPATH="backend"
    uvicorn app.main:app --host 127.0.0.1 --port 8000

다른 터미널:

    cd frontend
    npm install
    npm run dev

브라우저에서 http://127.0.0.1:5173 를 연다. Vite는 개발용으로 /api만 http://127.0.0.1:8000에 전달한다. 인터넷 공개 배포 용도가 아니다.

## 검증

Linux/macOS:

    PYTHONPATH=backend python -m pytest backend/tests -q
    cd frontend && npm run build

Windows PowerShell:

    $env:PYTHONPATH="backend"
    python -m pytest backend/tests -q
    cd frontend
    npm run build

## 다음 단계

나라장터 API의 공식 신청 조건과 실제 조회/상세/정정/취소/첨부 필드를 읽기 전용으로 확인한 뒤 내부 표준 모델을 확장한다. API key가 필요한 경우 서버 환경변수에서만 읽도록 구현하고 .env, key 값을 코드·로그·Git에 넣지 않는다. 외부 URL을 브라우저 사용자 입력만으로 fetch하지 않는다.

## 검수 상태

테스트와 CI의 실제 결과는 CURRENT_STATE.md 및 GitHub Actions에서 확인한다. 기능의 독립 최종 리뷰를 수행하지 않았다면 REVIEWED/RELEASED로 표시하지 않는다.
