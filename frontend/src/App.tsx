/**
 * 파일 설계 계약
 * 목적/책임: 합성 공고 검색, 분류, 상세 조회를 하나의 사용자 흐름으로 연결한다.
 * 입력/출력: 검색어/카테고리/선택 -> 서버가 검증한 공고 목록 및 상세 화면.
 * 신뢰 경계/권한: 사용자 입력과 API 출처는 모두 검증하며, React text node만 이용한다.
 * 상태 변경/부작용: 검색/상세 GET만 수행. 인증/개인 프로필/모델 호출 없음.
 * 실패/타임아웃/재시도: 네트워크/HTTP 오류를 명시, 0건과 분리한다.
 * 핵심 불변조건: 페이지 전체에서 이 데이터가 합성 fixture라는 사실을 유지한다.
 * 관련 요구사항/테스트/설계 문서: REQ-BID-001, docs/07-agile-development-workflow.md.
 */
import { useEffect, useState, type FormEvent } from 'react'
import { getNotice, searchNotices, type Category, type Notice } from './api'

type LoadState = 'loading' | 'success' | 'error'

export function App() {
  const [input, setInput] = useState('')
  const [category, setCategory] = useState<Category | ''>('')
  const [term, setTerm] = useState('')
  const [searchCategory, setSearchCategory] = useState<Category | ''>('')
  const [notices, setNotices] = useState<Notice[]>([])
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<Notice | null>(null)
  const [detailState, setDetailState] = useState<LoadState>('success')
  const [generation, setGeneration] = useState(0)

  useEffect(() => {
    let active = true
    searchNotices(term, searchCategory)
      .then(result => { if (active) { setNotices(result.items); setState('success') } })
      .catch(() => { if (active) { setNotices([]); setError('검색 정보를 가져오지 못했습니다. 백엔드 연결을 확인하세요.'); setState('error') } })
    return () => { active = false }
  }, [term, searchCategory, generation])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (input.length > 120) return
    setSelected(null)
    setState('loading')
    setError('')
    setTerm(input)
    setSearchCategory(category)
    setGeneration(g => g + 1)
  }

  async function selectNotice(id: string) {
    setSelected(null)
    setDetailState('loading')
    try { setSelected(await getNotice(id)); setDetailState('success') }
    catch { setDetailState('error') }
  }

  return (
    <main className="page">
      <header className="hero">
        <p><a href="/ai-account-preview.html" style={{color: '#fff', fontWeight: 800}}>내 ChatGPT / Codex 계정 설정 (화면 시안) →</a></p>
        <p><a href="/bid-management-preview.html" style={{color: '#fff', fontWeight: 800}}>새 입찰 진행관리 화면 열기 →</a></p>
        <div className="eyebrow">PUBLIC BID AGENT / DEVELOPMENT PREVIEW</div>
        <h1>공공 AI·SW 사업 탐색</h1>
        <p>공고 탐색과 근거 기반 적합성 분석을 개발하는 포트폴리오입니다.</p>
        <div role="status" className="notice"><strong>합성 데이터 데모</strong> · 아래 내용은 가상의 공고이며 실제 나라장터 공고나 접수 가능 여부를 의미하지 않습니다. AI 분석과 로그인 기능은 제공하지 않습니다.</div>
      </header>
      <section className="panel" aria-label="공고 검색">
        <h2>공고 검색</h2>
        <form onSubmit={submit} className="search-form">
          <label>검색어<input maxLength={120} value={input} onChange={e => setInput(e.target.value)} placeholder="예: FastAPI, Spring, 데이터" /></label>
          <label>분야<select value={category} onChange={e => setCategory(e.target.value as Category | '')}>
            <option value="">전체</option><option value="AI">AI</option><option value="SW">소프트웨어</option><option value="DATA">데이터</option>
          </select></label>
          <button type="submit">검색</button>
        </form>
      </section>
      <section className="panel" aria-label="검색 결과">
        <div className="section-title"><h2>검색 결과</h2>{state === 'success' && <span>{notices.length}건 (합성)</span>}</div>
        {state === 'loading' && <p role="status">검색 중입니다.</p>}
        {state === 'error' && <div role="alert">{error} <button type="button" onClick={() => { setState('loading'); setGeneration(g => g + 1) }}>다시 시도</button></div>}
        {state === 'success' && notices.length === 0 && <p role="status">조건에 맞는 합성 공고가 없습니다.</p>}
        {state === 'success' && notices.length > 0 && <ul className="cards">
          {notices.map(n => <li key={n.id} className="card">
            <div className="category">{n.category} · 합성 공고</div>
            <h3>{n.title}</h3><p>{n.organization}</p><p>{n.summary}</p>
            <div className="chips">{n.technologies.map(t => <span key={t}>{t}</span>)}</div>
            <button type="button" className="secondary" onClick={() => void selectNotice(n.id)}>상세 보기</button>
          </li>)}
        </ul>}
      </section>
      {(detailState === 'loading' || detailState === 'error' || selected) &&
        <section className="panel" aria-label="공고 상세">
          <h2>공고 상세</h2>
          {detailState === 'loading' && <p role="status">상세 조회 중입니다.</p>}
          {detailState === 'error' && <p role="alert">상세 정보를 조회하지 못했습니다.</p>}
          {selected && detailState === 'success' && <>
            <h3>{selected.title}</h3><p>{selected.summary}</p>
            <dl><dt>분야</dt><dd>{selected.category}</dd><dt>기관</dt><dd>{selected.organization}</dd>
              <dt>실제 공고 확인</dt><dd>불가 (합성 예시)</dd><dt>접수 가능 상태</dt><dd>확인되지 않음</dd>
              <dt>원문 최신성</dt><dd>확인되지 않음</dd></dl>
            <button type="button" className="secondary" onClick={() => setSelected(null)}>닫기</button>
          </>}
        </section>}
      <footer>실제 공식 API 연결, AI 추론, Google 인증, 참가자격 확정 기능은 후속 스프린트에서 검증합니다.</footer>
    </main>
  )
}
