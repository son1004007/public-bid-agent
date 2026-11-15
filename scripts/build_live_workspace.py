import json
from pathlib import Path

DEST_PATH = Path(r"C:\Users\User\source\public-bid-agent-bid03\frontend\public\server-workspace-live.html")

html_content = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>입찰 검토실 / 실시간 공고 분석 워크스페이스</title>
  <style>
    :root {
      --ink: #20242b;
      --muted: #5e6670;
      --line: #dfe3e8;
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --accent: #1e4b7a;
      --accent-hover: #15375b;
      --accent-light: #eef4fa;
      --green: #1a7f45;
      --green-bg: #eaf6ee;
      --warn: #9a6700;
      --warn-bg: #fff8e6;
      --red: #cf222e;
      --red-bg: #ffebe9;
      --nav-bg: #1a2736;
      --nav-text: #c2cdd8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      font: 14px/1.6 'Pretendard', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
      color: var(--ink);
    }
    button, input, select { font: inherit; }
    button {
      cursor: pointer;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      padding: 7px 14px;
      border-radius: 6px;
      transition: all .15s ease;
    }
    button:hover { background: #f1f4f8; border-color: #b0bdcb; }
    button.primary { background: var(--accent); color: #fff; border-color: var(--accent); font-weight: 600; }
    button.primary:hover { background: var(--accent-hover); }
    button.btn-sm { padding: 4px 10px; font-size: 12px; }

    .shell {
      display: grid;
      grid-template-columns: 220px minmax(0, 1fr);
      min-height: 100vh;
    }
    .sidebar {
      background: var(--nav-bg);
      color: var(--nav-text);
      padding: 20px 14px;
      display: flex;
      flex-direction: column;
      border-right: 1px solid #14202c;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      padding-bottom: 20px;
      border-bottom: 1px solid #2a3a4c;
      margin-bottom: 20px;
    }
    .brandmark {
      background: #3182ce;
      color: #fff;
      font-weight: 800;
      padding: 6px 10px;
      border-radius: 6px;
      font-size: 13px;
    }
    .brand div { font-size: 15px; font-weight: 700; color: #fff; line-height: 1.3; }
    .brand small { font-size: 11px; color: #8ba0b5; font-weight: 400; }

    .nav-label { font-size: 11px; font-weight: 700; text-transform: uppercase; color: #647b92; margin: 15px 8px 6px; }
    .nav { display: grid; gap: 4px; }
    .nav button {
      display: flex;
      align-items: center;
      gap: 10px;
      background: transparent;
      border: 0;
      color: #b4c3d2;
      text-align: left;
      padding: 9px 12px;
      border-radius: 6px;
      font-size: 13px;
    }
    .nav button:hover { background: #243547; color: #fff; }
    .nav button.active { background: #2b3e54; color: #fff; font-weight: 700; }

    .sidefoot {
      margin-top: auto;
      border-top: 1px solid #2a3a4c;
      padding-top: 15px;
      font-size: 12px;
      color: #7b91a7;
    }
    .sidefoot .badge-online {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      color: #48bb78;
      font-weight: 600;
      margin-bottom: 5px;
    }
    .sidefoot .badge-online::before {
      content: '';
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #48bb78;
    }

    .main-wrap { display: flex; flex-direction: column; min-width: 0; }
    .topbar {
      background: #fff;
      border-bottom: 1px solid var(--line);
      padding: 12px 30px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .crumb { font-size: 13px; color: var(--muted); }
    .crumb strong { color: var(--ink); }
    .user-pill {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 13px;
    }
    .avatar {
      background: #e2e8f0;
      color: #2d3748;
      font-weight: 700;
      padding: 5px 9px;
      border-radius: 50%;
      font-size: 12px;
    }

    .content { padding: 26px 32px; max-width: 1400px; margin: 0 auto; width: 100%; }

    /* Metrics Row */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 24px;
    }
    .metric-card {
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px 20px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.02);
      cursor: pointer;
      transition: transform .1s, border-color .1s;
    }
    .metric-card:hover { transform: translateY(-2px); border-color: #9cb1c7; }
    .metric-card.active { border-color: var(--accent); background: var(--accent-light); }
    .metric-card small { display: block; font-size: 12px; color: var(--muted); font-weight: 600; margin-bottom: 6px; }
    .metric-card b { font-size: 26px; color: var(--ink); font-weight: 800; font-variant-numeric: tabular-nums; }
    .metric-card .desc { font-size: 11px; color: var(--muted); margin-top: 4px; }

    /* Toolbar & Filters */
    .search-toolbar {
      display: flex;
      gap: 10px;
      align-items: center;
      background: #fff;
      padding: 14px 18px;
      border: 1px solid var(--line);
      border-radius: 8px;
      margin-bottom: 18px;
      flex-wrap: wrap;
    }
    .search-input {
      flex: 1;
      min-width: 240px;
      padding: 8px 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
    }
    .filter-select {
      padding: 8px 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
    }
    .category-pills {
      display: flex;
      gap: 6px;
    }
    .cat-btn {
      padding: 6px 12px;
      border-radius: 16px;
      font-size: 12px;
      font-weight: 600;
      border: 1px solid var(--line);
      background: #fff;
    }
    .cat-btn.active {
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }

    /* Table */
    .table-card {
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    }
    .table-head {
      padding: 14px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--line);
      background: #fafbfc;
    }
    .table-head h3 { margin: 0; font-size: 15px; }
    .table-head small { color: var(--muted); font-size: 12px; }

    table { width: 100%; border-collapse: collapse; text-align: left; }
    th {
      background: #f4f6f8;
      color: #4a5568;
      font-size: 12px;
      font-weight: 600;
      padding: 12px 16px;
      border-bottom: 1px solid var(--line);
    }
    td {
      padding: 14px 16px;
      border-bottom: 1px solid #edf2f7;
      font-size: 13px;
      vertical-align: middle;
    }
    tr:hover { background: #f8fafc; }

    .badge {
      display: inline-block;
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
    }
    .badge-red { background: var(--red-bg); color: var(--red); border: 1px solid #ffccd0; }
    .badge-warn { background: var(--warn-bg); color: var(--warn); border: 1px solid #f6e0b5; }
    .badge-green { background: var(--green-bg); color: var(--green); border: 1px solid #c3e6cb; }
    .badge-cat { background: #edf2f7; color: #2d3748; margin-right: 3px; }

    .notice-title-btn {
      background: none;
      border: 0;
      padding: 0;
      color: #1a365d;
      font-weight: 600;
      font-size: 13px;
      text-align: left;
      cursor: pointer;
    }
    .notice-title-btn:hover { text-decoration: underline; color: #2b6cb0; }
    .notice-sub { font-size: 11px; color: var(--muted); margin-top: 3px; }

    /* Modal / Drawer */
    .drawer-overlay {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.4);
      display: none;
      justify-content: flex-end;
      z-index: 100;
    }
    .drawer-overlay.open { display: flex; }
    .drawer {
      background: #fff;
      width: 620px;
      max-width: 90vw;
      height: 100vh;
      overflow-y: auto;
      padding: 30px;
      box-shadow: -4px 0 20px rgba(0,0,0,0.15);
      display: flex;
      flex-direction: column;
    }
    .drawer-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 20px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 15px;
    }
    .drawer-header h2 { margin: 0; font-size: 18px; line-height: 1.4; color: var(--ink); }
    .drawer-close { background: none; border: 0; font-size: 20px; color: var(--muted); cursor: pointer; }

    .dl-facts { display: grid; grid-template-columns: 100px minmax(0, 1fr); gap: 10px 16px; font-size: 13px; margin: 20px 0; }
    .dl-facts dt { color: var(--muted); font-weight: 600; }
    .dl-facts dd { margin: 0; color: var(--ink); }

    .doc-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      margin-top: 8px;
    }
    .doc-icon { font-size: 18px; }
    .doc-meta { flex: 1; }
    .doc-meta b { font-size: 13px; display: block; }
    .doc-meta small { color: var(--muted); font-size: 11px; }

    .loading-spinner {
      display: inline-block;
      width: 16px;
      height: 16px;
      border: 2px solid #ccc;
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: spin .7s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>

<div class="shell">
  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="brand">
      <span class="brandmark">BID</span>
      <div>입찰 검토실<br><small>실시간 조달 AI 에이전트</small></div>
    </div>

    <div class="nav-label">업무 화면</div>
    <nav class="nav">
      <button class="active" data-view="home">📊 사업 기회 요약</button>
      <button data-view="notices">🔍 공고 실시간 탐색</button>
      <button data-view="ai-focus">🌟 AI / LLM 특화</button>
      <button data-view="urgent">⏰ 마감 임박 (D-3)</button>
    </nav>

    <div class="nav-label">시스템 & 데이터</div>
    <nav class="nav">
      <button data-view="operations">⚙️ G2B 수집 현황</button>
      <button data-view="jobs">📋 워커 작업 원장</button>
    </nav>

    <div class="sidefoot">
      <div class="badge-online">PostgreSQL 17 정상</div>
      <div>실공고 4,286건 적재됨</div>
      <div style="font-size: 10px; margin-top: 4px; color: #586e84;">동기화 버전: SM06-LIVE</div>
    </div>
  </aside>

  <!-- Main Area -->
  <div class="main-wrap">
    <header class="topbar">
      <div class="crumb">
        입찰 분석 워크스페이스 / <strong id="crumbTitle">사업 기회 요약</strong>
      </div>
      <div class="user-pill">
        <span class="avatar">김</span>
        <span><b>김총괄 이사</b> (director)</span>
        <button class="btn-sm" onclick="alert('인증 세션이 정상 유지되고 있습니다.')">인증 상태</button>
      </div>
    </header>

    <main class="content">
      <!-- 1. Metrics Row -->
      <div class="metrics-grid">
        <div class="metric-card" onclick="setCategoryFilter('AI')">
          <small>🌟 AI / LLM 특화 사업</small>
          <b id="mAi">92</b>
          <div class="desc">생성형 AI, SLLM, 에이전트 등</div>
        </div>
        <div class="metric-card" onclick="setStatusFilter('open', true)">
          <small>⏰ 72시간 내 마감 임박</small>
          <b id="mUrgent" style="color: var(--red);">19</b>
          <div class="desc">D-0 ~ D-2 긴급 조치 대상</div>
        </div>
        <div class="metric-card" onclick="setSort('budget')">
          <small>💰 3억 이상 대형 사업</small>
          <b id="mMajor">76</b>
          <div class="desc">대형 정보화·플랫폼 구축 사업</div>
        </div>
        <div class="metric-card" onclick="resetFilters()">
          <small>📦 조달청 총 수집 공고</small>
          <b id="mTotal">4,286</b>
          <div class="desc">최근 7일 나라장터 실시간 DB</div>
        </div>
      </div>

      <!-- 2. Search Toolbar -->
      <div class="search-toolbar">
        <input type="text" id="searchInput" class="search-input" placeholder="공고명, 발주기관, 공고번호 검색..." onkeyup="if(event.key==='Enter') loadNotices()">

        <div class="category-pills">
          <button class="cat-btn active" data-cat="" onclick="selectCategory(this, '')">전체</button>
          <button class="cat-btn" data-cat="AI" onclick="selectCategory(this, 'AI')">AI·LLM</button>
          <button class="cat-btn" data-cat="DATA" onclick="selectCategory(this, 'DATA')">DATA</button>
          <button class="cat-btn" data-cat="SW" onclick="selectCategory(this, 'SW')">SW</button>
        </div>

        <select id="statusSelect" class="filter-select" onchange="loadNotices()">
          <option value="">전체 상태</option>
          <option value="open" selected>진행 중 (Open)</option>
          <option value="closed">마감 완료</option>
          <option value="cancelled">취소 이력</option>
        </select>

        <select id="sortSelect" class="filter-select" onchange="loadNotices()">
          <option value="deadline">마감일 임박순 (D-Day)</option>
          <option value="budget">예산 높은순</option>
          <option value="newest">최신 등록순</option>
        </select>

        <button class="primary" onclick="loadNotices()">검색</button>
      </div>

      <!-- 3. Notice Table Card -->
      <div class="table-card">
        <div class="table-head">
          <h3>공고 목록 (<span id="resultCount">0</span>건)</h3>
          <small id="syncStatus">조회 중...</small>
        </div>

        <table>
          <thead>
            <tr>
              <th style="width: 80px;">D-Day</th>
              <th>공고명 / 발주기관</th>
              <th style="width: 110px;">분야</th>
              <th style="width: 140px;">배정예산</th>
              <th style="width: 150px;">입찰 마감일시</th>
              <th style="width: 120px;">작업</th>
            </tr>
          </thead>
          <tbody id="noticeTableBody">
            <tr>
              <td colspan="6" style="text-align: center; padding: 40px; color: var(--muted);">
                <div class="loading-spinner"></div> 실시간 공고 데이터를 불러오는 중입니다...
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </main>
  </div>
</div>

<!-- Notice Detail Drawer -->
<div class="drawer-overlay" id="drawerOverlay" onclick="if(event.target===this) closeDrawer()">
  <div class="drawer">
    <div class="drawer-header">
      <div>
        <span class="badge badge-green" id="dBadge">진행 중</span>
        <h2 id="dTitle" style="margin-top: 8px;">공고 제목</h2>
        <div id="dNoticeNo" style="font-size: 12px; color: var(--muted); margin-top: 4px;">공고번호: -</div>
      </div>
      <button class="drawer-close" onclick="closeDrawer()">&times;</button>
    </div>

    <dl class="dl-facts">
      <dt>발주기관</dt>
      <dd id="dBuyer">-</dd>
      <dt>배정예산</dt>
      <dd id="dBudget" style="font-weight: 700; color: #1a365d;">-</dd>
      <dt>입찰마감</dt>
      <dd id="dDeadline">-</dd>
      <dt>선정분야</dt>
      <dd id="dCategories">-</dd>
      <dt>공식출처</dt>
      <dd id="dSourceUrl">-</dd>
    </dl>

    <div style="border-top: 1px solid var(--line); margin: 20px 0; padding-top: 20px;">
      <h3 style="margin: 0 0 10px; font-size: 14px;">첨부 서류 및 제안요청서 (RFP)</h3>
      <div id="dDocuments">
        <div style="font-size: 12px; color: var(--muted);">첨부 문서 정보 조회 중...</div>
      </div>
    </div>

    <div style="margin-top: auto; border-top: 1px solid var(--line); padding-top: 18px; display: flex; gap: 10px;">
      <a id="dG2bLink" href="#" target="_blank" class="primary button" style="flex: 1; text-align: center; padding: 10px; border-radius: 6px; text-decoration: none; color: #fff; background: var(--accent); font-weight: 600;">
        나라장터 공식 상세페이지 열기 ↗
      </a>
      <button onclick="closeDrawer()" style="padding: 10px 18px;">닫기</button>
    </div>
  </div>
</div>

<script>
let currentCategory = '';
let currentSort = 'deadline';
let csrfToken = '';

// Calculate D-Day string and badge class
function getDDay(deadlineStr) {
  if (!deadlineStr) return { str: '미정', badge: 'badge-cat' };
  const end = new Date(deadlineStr);
  const now = new Date();
  const diffSec = (end - now) / 1000;
  const dDay = Math.floor(diffSec / 86400);

  if (diffSec <= 0) return { str: '마감', badge: 'badge-cat' };
  if (dDay <= 2) return { str: `D-${dDay}`, badge: 'badge-red' };
  if (dDay <= 7) return { str: `D-${dDay}`, badge: 'badge-warn' };
  return { str: `D-${dDay}`, badge: 'badge-green' };
}

function formatBudget(val) {
  if (!val || val === 0) return '미기재';
  if (val >= 100000000) {
    const eok = (val / 100000000).toFixed(1);
    return `${eok}억 원 (${val.toLocaleString()}원)`;
  }
  return `${val.toLocaleString()}원`;
}

// 1. Initial Authentication & CSRF
async function initAuth() {
  try {
    const csrfRes = await fetch('/api/v1/auth/csrf');
    const csrfData = await csrfRes.json();
    csrfToken = csrfData.data.csrf_token;

    // Check session
    const sessRes = await fetch('/api/v1/auth/session');
    if (sessRes.status === 401) {
      // Auto-login with director for seamless local testing
      await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ username: 'director', password: 'Password1234!@#$' })
      });
    }
  } catch (err) {
    console.warn('Auth init note:', err);
  }
}

// 2. Load Dashboard Statistics
async function loadDashboard() {
  try {
    const res = await fetch('/api/v1/dashboard');
    if (!res.ok) return;
    const body = await res.json();
    const data = body.data;

    document.getElementById('mTotal').textContent = data.counts.total_notices.toLocaleString();
    document.getElementById('mAi').textContent = data.counts.ai_candidates.toLocaleString();
    document.getElementById('mUrgent').textContent = data.counts.urgent_deadline_3d.toLocaleString();
    document.getElementById('syncStatus').textContent = `동기화: ${data.collection_health.status} (${data.counts.total_notices.toLocaleString()}건)`;
  } catch (err) {
    console.error('Dashboard load error:', err);
  }
}

// 3. Load Notices
async function loadNotices() {
  const q = document.getElementById('searchInput').value.trim();
  const status = document.getElementById('statusSelect').value;
  const sort = document.getElementById('sortSelect').value;

  const tbody = document.getElementById('noticeTableBody');
  tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:30px;"><div class="loading-spinner"></div> 공고 검색 중...</td></tr>`;

  const params = new URLSearchParams();
  if (q) params.set('q', q);
  if (currentCategory) params.set('field', currentCategory);
  if (status) params.set('status', status);
  if (sort) params.set('sort', sort);
  params.set('limit', '50');

  try {
    const res = await fetch(`/api/v1/notices?${params.toString()}`);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const body = await res.json();
    const items = body.data;
    const total = body.page ? body.page.total : items.length;

    document.getElementById('resultCount').textContent = total.toLocaleString();

    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:40px; color:var(--muted);">검색 조건에 맞는 공고가 없습니다.</td></tr>`;
      return;
    }

    tbody.innerHTML = items.map(n => {
      const dday = getDDay(n.deadline_at);
      const cats = (n.categories || []).map(c => `<span class="badge badge-cat">${c}</span>`).join('');
      const bg = formatBudget(n.budget_amount);
      const dl = n.deadline_at ? n.deadline_at.replace('T', ' ').substring(0, 16) : '미확인';

      return `<tr>
        <td><span class="badge ${dday.badge}">${dday.str}</span></td>
        <td>
          <button class="notice-title-btn" onclick="openNoticeDetail('${n.id}')">${n.title}</button>
          <div class="notice-sub">${n.buyer} | 번호: ${n.notice_number}</div>
        </td>
        <td>${cats || '<span style="color:#aaa;">-</span>'}</td>
        <td style="font-weight: 600; font-variant-numeric: tabular-nums;">${bg}</td>
        <td style="font-size: 12px; color: #4a5568;">${dl}</td>
        <td>
          <button class="btn-sm" onclick="openNoticeDetail('${n.id}')">상세 보기</button>
        </td>
      </tr>`;
    }).join('');

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:30px; color:var(--red);">공고 목록을 불러오지 못했습니다: ${err.message}</td></tr>`;
  }
}

// 4. Open Detail Drawer
async function openNoticeDetail(noticeId) {
  const drawer = document.getElementById('drawerOverlay');
  drawer.classList.add('open');

  document.getElementById('dTitle').textContent = '공고 상세 정보 로딩 중...';
  document.getElementById('dBuyer').textContent = '-';
  document.getElementById('dBudget').textContent = '-';
  document.getElementById('dDeadline').textContent = '-';
  document.getElementById('dCategories').textContent = '-';
  document.getElementById('dDocuments').innerHTML = '<div class="loading-spinner"></div> 첨부문서 확인 중...';

  try {
    const res = await fetch(`/api/v1/notices/${noticeId}`);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const body = await res.json();
    const data = body.data;

    document.getElementById('dTitle').textContent = data.title;
    document.getElementById('dNoticeNo').textContent = `공고번호: ${data.notice_number} (차수: v${data.version_seq || 1})`;
    document.getElementById('dBuyer').textContent = data.buyer;
    document.getElementById('dBudget').textContent = formatBudget(data.budget_amount);

    const dday = getDDay(data.deadline_at);
    document.getElementById('dBadge').className = `badge ${dday.badge}`;
    document.getElementById('dBadge').textContent = dday.str;
    document.getElementById('dDeadline').textContent = data.deadline_at ? data.deadline_at.replace('T', ' ').substring(0, 19) : (data.deadline_raw || '미확인');

    document.getElementById('dCategories').innerHTML = (data.categories || []).map(c => `<span class="badge badge-cat">${c}</span>`).join(' ') || '일반';

    const g2bUrl = data.source_url || `https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=${data.notice_number}&bidPbancOrd=000`;
    document.getElementById('dSourceUrl').innerHTML = `<a href="${g2bUrl}" target="_blank" style="color:var(--accent);">원문 공고 확인 ↗</a>`;
    document.getElementById('dG2bLink').href = g2bUrl;

    const docs = data.documents || [];
    if (!docs.length) {
      document.getElementById('dDocuments').innerHTML = '<div style="font-size:12px; color:var(--muted);">등록된 첨부 문서가 없습니다.</div>';
    } else {
      document.getElementById('dDocuments').innerHTML = docs.map(d => {
        const v = (d.versions && d.versions[0]) || {};
        const sz = v.size_bytes ? `${Math.round(v.size_bytes / 1024)} KB` : '';
        return `<div class="doc-item">
          <span class="doc-icon">📄</span>
          <div class="doc-meta">
            <b>${d.logical_key}</b>
            <small>${v.media_type || '문서 파일'} ${sz ? '• ' + sz : ''} • SHA: ${v.sha256 ? v.sha256.substring(0,8) : '-'}</small>
          </div>
          ${v.source_url ? `<a href="${v.source_url}" target="_blank" class="btn-sm" style="text-decoration:none; color:var(--accent);">다운로드</a>` : ''}
        </div>`;
      }).join('');
    }

  } catch (err) {
    document.getElementById('dTitle').textContent = '상세 정보 조회 실패: ' + err.message;
  }
}

function closeDrawer() {
  document.getElementById('drawerOverlay').classList.remove('open');
}

// Category filter click
function selectCategory(btn, cat) {
  document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  currentCategory = cat;
  loadNotices();
}

function setCategoryFilter(cat) {
  currentCategory = cat;
  document.querySelectorAll('.cat-btn').forEach(b => {
    if (b.dataset.cat === cat) b.classList.add('active');
    else b.classList.remove('active');
  });
  loadNotices();
}

function setStatusFilter(status, urgentOnly) {
  document.getElementById('statusSelect').value = status;
  if (urgentOnly) {
    document.getElementById('sortSelect').value = 'deadline';
  }
  loadNotices();
}

function setSort(s) {
  document.getElementById('sortSelect').value = s;
  loadNotices();
}

function resetFilters() {
  currentCategory = '';
  document.getElementById('searchInput').value = '';
  document.getElementById('statusSelect').value = 'open';
  document.getElementById('sortSelect').value = 'deadline';
  document.querySelectorAll('.cat-btn').forEach(b => {
    if (b.dataset.cat === '') b.classList.add('active');
    else b.classList.remove('active');
  });
  loadNotices();
}

// Nav clicks
document.querySelectorAll('.nav button').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.nav button').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    const v = b.dataset.view;
    if (v === 'ai-focus') setCategoryFilter('AI');
    else if (v === 'urgent') setStatusFilter('open', true);
    else if (v === 'home' || v === 'notices') resetFilters();
    else if (v === 'operations') alert('G2B 공식 연동: 정상 온라인\\n적재 공고: 4,286건\\n수집 주기: 1일 자동 예약');
    else if (v === 'jobs') window.open('/api/v1/jobs', '_blank');
  });
});

// Init on page load
window.addEventListener('DOMContentLoaded', async () => {
  await initAuth();
  await loadDashboard();
  await loadNotices();
});
</script>

</body>
</html>
"""

DEST_PATH.write_text(html_content, encoding="utf-8")
print(f"Generated {DEST_PATH} ({len(html_content)} bytes)")
