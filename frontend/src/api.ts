/**
 * 파일 설계 계약
 * 목적/책임: 합성 공고 API의 검증 가능한 응답 계약과 fetch 실패를 표현한다.
 * 입력/출력: 검색 필터/공고 ID -> 명시적 fixture 출처의 응답.
 * 신뢰 경계/권한: 외부 API 응답은 비신뢰; 출처와 상태 및 핵심 필드 확인.
 * 상태 변경/부작용: GET 요청만 실행한다.
 * 실패/타임아웃/재시도: 비정상 HTTP/스키마/네트워크 실패를 throw하고 0건으로 위장하지 않는다.
 * 핵심 불변조건: source URL이나 HTML을 임의 렌더링하지 않는다.
 * 관련 요구사항/테스트/설계 문서: REQ-BID-001, docs/07-agile-development-workflow.md.
 */
export type Category = 'AI' | 'SW' | 'DATA'
export type Notice = {
  id: string
  title: string
  organization: string
  category: Category
  summary: string
  technologies: string[]
  source_type: 'SYNTHETIC_FIXTURE'
  source_url: null
  submission_status: 'UNKNOWN'
  source_freshness: 'UNKNOWN'
}
export type SearchResponse = {
  items: Notice[]
  total: number
  data_source: 'SYNTHETIC_FIXTURE'
  disclaimer: string
}

function isNotice(value: unknown): value is Notice {
  if (!value || typeof value !== 'object') return false
  const n = value as Record<string, unknown>
  return typeof n.id === 'string' && /^demo-[a-z0-9-]+$/.test(n.id)
    && typeof n.title === 'string' && typeof n.organization === 'string'
    && typeof n.summary === 'string' && ['AI', 'SW', 'DATA'].includes(String(n.category))
    && Array.isArray(n.technologies) && n.technologies.every((t: unknown) => typeof t === 'string')
    && n.source_type === 'SYNTHETIC_FIXTURE' && n.source_url === null
    && n.submission_status === 'UNKNOWN' && n.source_freshness === 'UNKNOWN'
}

async function request(path: string): Promise<unknown> {
  const response = await fetch(path, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
  if (!response.ok) throw new Error('HTTP ' + response.status)
  return response.json() as Promise<unknown>
}

export async function searchNotices(q: string, category: Category | ''): Promise<SearchResponse> {
  const query = new URLSearchParams()
  if (q.trim()) query.set('q', q.trim())
  if (category) query.set('category', category)
  const raw = await request('/api/notices?' + query.toString())
  if (!raw || typeof raw !== 'object') throw new Error('API 계약 오류')
  const result = raw as Record<string, unknown>
  if (result.data_source !== 'SYNTHETIC_FIXTURE' || !Array.isArray(result.items)
    || !result.items.every(isNotice) || typeof result.total !== 'number'
    || result.total !== result.items.length || typeof result.disclaimer !== 'string') {
    throw new Error('API 계약 오류')
  }
  return result as SearchResponse
}

export async function getNotice(id: string): Promise<Notice> {
  if (!/^demo-[a-z0-9-]+$/.test(id)) throw new Error('공고 식별자 오류')
  const raw = await request('/api/notices/' + encodeURIComponent(id))
  if (!isNotice(raw)) throw new Error('API 계약 오류')
  return raw
}
