/**
 * 파일 설계 계약
 * 목적/책임: 개발용 React UI 진입점.
 * 입력/출력: API 동작을 사용자 검색 화면으로 보여준다.
 * 신뢰 경계/권한: 실제 공고·공식 판정으로 혼동할 수 없는 합성 데이터 안내를 유지한다.
 * 상태 변경/부작용: 브라우저 DOM 렌더링.
 * 실패/타임아웃/재시도: 검색 요청 상태는 App에서 사용자에게 표시한다.
 * 핵심 불변조건: 외부 콘텐츠를 HTML로 직접 해석하지 않는다.
 * 관련 요구사항/테스트/설계 문서: Sprint 1, frontend/src/App.tsx.
 */
import React from 'react'
import ReactDOM from 'react-dom/client'
import { App } from './App'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><App /></React.StrictMode>,
)
