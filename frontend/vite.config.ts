/**
 * 파일 설계 계약
 * 목적/책임: 개발 서버에서 상대 경로 API만 FastAPI localhost로 프록시한다.
 * 입력/출력: /api 경로 -> 127.0.0.1:8000.
 * 신뢰 경계/권한: 개발 전용이며 외부 서비스 및 credential 전달용 설정이 아니다.
 * 상태 변경/부작용: 개발 중 API 라우팅만 변경.
 * 실패/타임아웃/재시도: 백엔드 장애는 프런트엔드 API 오류로 노출.
 * 핵심 불변조건: wildcard CORS나 전체 외부 호스트 노출을 추가하지 않는다.
 * 관련 요구사항/테스트/설계 문서: Sprint 1, backend/tests/test_api.py.
 */
import { defineConfig } from 'vite'

export default defineConfig({
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } }
})
