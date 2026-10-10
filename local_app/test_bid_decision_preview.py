"""공고 중심 UI 퍼블리싱의 독립 실행·명시적 가상 기능 계약 검사."""
from pathlib import Path
import unittest
import sys
sys.path.insert(0,str(Path(__file__).parent))
import server

PAGE=Path(__file__).resolve().parents[1]/"frontend"/"public"/"bid-decision-dashboard-preview.html"
SCRIPT=PAGE.with_suffix(".js")

class BidDecisionPreviewTests(unittest.TestCase):
 def test_page_provides_core_views_profiles_and_reason_trace(self):
  content=PAGE.read_text(encoding="utf-8")+"\n"+SCRIPT.read_text(encoding="utf-8")
  for identifier in ('id="view-notices"','id="view-collection"','id="view-policy"',
                     'id="view-variables"','id="view-history"','id="noticeRows"',
                     'id="statusFilters"','id="factorWeights"','id="gateVariables"',
                     'id="detail"','id="assess-all"','id="policyMargin"'):
   self.assertIn(identifier,content)
  self.assertIn("참여 판단 시연",content)
  self.assertIn("불참 사유",content)
  self.assertIn("logDecision(",content)
  self.assertIn("function weightedFit(n)",content)
  self.assertIn("담당자 최종 불참 사유",content)

 def test_full_detail_navigation_and_four_tabs_without_automatic_assessment(self):
  html=PAGE.read_text(encoding="utf-8")
  js=SCRIPT.read_text(encoding="utf-8")
  self.assertIn('id="view-full-detail"',html)
  for key in ("overview","requirements","evaluation","decision"):
   self.assertIn(f'data-detail-tab="{key}"',html)
  self.assertIn('id="detailBack"',html)
  self.assertIn('id="detailAssess"',html)
  self.assertIn("note.id='fullDetailNoBidReason'",js)
  self.assertIn("function openFullDetail(id,tab='overview')",js)
  self.assertIn("function renderFullDetail()",js)
  self.assertIn("function renderFullRequirements(n,pane)",js)
  self.assertIn("function renderFullEvaluation(n,pane)",js)
  self.assertIn("function renderFullDecision(n,pane)",js)
  self.assertIn("const b=el('button','btn small','상세보기')",js)
  self.assertIn("b.addEventListener('click',()=>openFullDetail(n.id))",js)
  self.assertIn("function recordHumanNoBid(n,text)",js)
  self.assertNotIn("b.addEventListener('click',()=>{selected=n.id;if(!n.rec)assess(n)",js)
  self.assertIn("const entries=logs.filter(x=>x.id===n.id)",js)

 def test_not_live_collection_model_or_storage(self):
  t=PAGE.read_text(encoding="utf-8")+"\n"+SCRIPT.read_text(encoding="utf-8")
  self.assertIn("합성 공고",t)
  self.assertIn("새로고침하면 초기화",t)
  self.assertNotIn("localStorage",t)
  self.assertNotIn("sessionStorage",t)
  self.assertNotIn("fetch(",t)
  self.assertNotIn("XMLHttpRequest",t)
  self.assertNotIn("WebSocket",t)
  self.assertIn("const seed=[",t)
  self.assertIn('<script defer src="bid-decision-dashboard-preview.js"></script>',PAGE.read_text(encoding="utf-8"))
 def test_server_route_exists_and_existing_app_links_to_it(self):
  self.assertTrue(server.DECISION_PREVIEW.is_file())
  self.assertTrue(server.DECISION_PREVIEW_JS.is_file())
  self.assertIn('if self.path=="/bid-decision-dashboard-preview.js":',Path(server.__file__).read_text(encoding="utf-8"))
  self.assertIn('href="/decision-preview"',server.HTML.read_text(encoding="utf-8"))
  self.assertIn('if self.path=="/decision-preview":',Path(server.__file__).read_text(encoding="utf-8"))
