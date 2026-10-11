"""재개 가능한 공식 RFP 단일 작업자 배치.
목적: 부서 후보를 제한된 양씩 직렬 추출하고 증거/실패를 기록한다.
입력: 공식 공고/첨부 URL, 기존 추출기; 출력: 문서별 검증 전 추출 근거.
신뢰경계: 고정 공식 HTTPS만 허용; 문서는 지시가 아닌 데이터.
부작용: 기존 dashboard.json 특정 공고와 별도 rfp_batch.json 원자 갱신.
실패: 제한된 다운로드·추출, 사용자 중단, 실패만 명시적 재시도.
불변조건: 이미 성공한 공고/사람 결정 불변; 서버 재시작 후 재개 가능.
검증: test_rfp_batch.py / docs/design/RFP_RESUMABLE_BATCH_2026-10-11.md.
"""
import copy
import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import PurePath
from dashboard_backend import read as read_dashboard, ProviderError
from department_profile import load as load_department_profile
from procurement_documents import SUPPORTED, DocumentFetchError, fetch_attachment, official_url
from procurement_filter import apply as reclassify


def stamp():
    return datetime.now(timezone.utc).isoformat()



# 서버의 사용자/담당자 판단 필드는 해시 비교에서 제외하고, RFP만 낙관적 동시성 관리.
DOCUMENT_FIELDS=("attachments","document_status","rfp_text","document_source_name",
                 "document_evidence","document_error")


def document_signature(notice):
    if notice is None:return None
    content={key:notice.get(key) for key in DOCUMENT_FIELDS}
    return hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def ranked(notice):
    ranked_files, seen = [], set()
    for f in notice.get("attachments", [])[:40]:
        if not isinstance(f, dict):
            continue
        name, url = f.get("name", ""), f.get("url")
        if not isinstance(name, str) or not official_url(url) or (name,url) in seen:
            continue
        if PurePath(name).suffix.lower() not in SUPPORTED:
            continue
        seen.add((name,url))
        score = next((v for word,v in (("제안요청",7),("과업지시",6),("과업내용",6),
            ("과업설명",5),("사업설명",4),("규격서",3),("공고문",2)) if word in name),1)
        ranked_files.append((score,f))
    ranked_files.sort(key=lambda pair:-pair[0])
    return [f for _,f in ranked_files]


def analyze(notice, extractor, fetcher=fetch_attachment, related=None, key=None):
    """공식 링크의 RFP/과업 문서 최대 2개를 처리하고 문서별 출처를 기록."""
    notice = copy.deepcopy(notice)
    files = ranked(notice)
    attachments = []
    if related and key and not any(any(w in f["name"] for w in
             ("제안요청","과업지시","과업내용")) for f in files):
        try:
            details = related(key,notice["bid_no"],notice["bid_order"])
            if not isinstance(details,dict) or not isinstance(details.get("attachments"),list):
                raise ValueError("공식 상세 첨부 목록 형식 오류")
            attachments = [f for f in details["attachments"][:40] if isinstance(f,dict)
                           and isinstance(f.get("name"),str) and official_url(f.get("url"))]
            notice["attachments"] = notice.get("attachments",[]) + attachments
            files = ranked(notice)
        except (ValueError,OSError,RuntimeError,ProviderError):
            pass
    if not files:
        return {"document_status":"FAILED","document_error":"사용 가능한 공식 첨부 링크 없음",
                "document_evidence":[],"related_attachments":attachments}
    evidence=[]
    previous={x.get("identity"):x for x in notice.get("document_evidence",[])
              if isinstance(x,dict) and x.get("status")=="EXTRACTED"}
    for f in files[:2]:
        identity=hashlib.sha256((f["url"]+"\n"+f["name"]).encode()).hexdigest()
        if identity in previous:
            evidence.append(previous[identity])
            continue
        item={"identity":identity,"name":f["name"][:200],
              "source":str(f.get("source","공식 첨부"))[:80]}
        try:
            raw=fetcher(f["url"])
            doc=extractor(f["name"],raw)
            content=doc.get("text","") if isinstance(doc,dict) else ""
            if not isinstance(content,str) or not content.strip():
                raise DocumentFetchError("본문 없음")
            item.update({"status":"EXTRACTED","sha256":hashlib.sha256(raw).hexdigest(),
                         "chars":len(content),"excerpt":content[:6000],
                         "warnings":[str(w)[:90] for w in doc.get("warnings",[])[:5]]})
        except (DocumentFetchError,ValueError,OSError,TimeoutError):
            item.update({"status":"FAILED","error":"공식 첨부 다운로드 또는 추출 실패"})
        evidence.append(item)
    successes=[e for e in evidence if e["status"]=="EXTRACTED"]
    result={"document_evidence":evidence,"related_attachments":attachments}
    if successes:
        result.update({"document_status":"EXTRACTED",
            "rfp_text":"\n\n".join(e["excerpt"] for e in successes)[:12000],
            "document_source_name":" / ".join(e["name"] for e in successes)[:400],
            "document_error":""})
    else:
        result.update({"document_status":"FAILED",
                       "document_error":"공식 첨부 2개에서 추출 가능한 본문을 찾지 못했습니다"})
    return result


class Manager:
    def __init__(self, root, lock, persist, extractor, related=None,
                 key_getter=None, fetcher=fetch_attachment, delay=3):
        self.root,self.lock,self.persist=root,lock,persist
        self.extractor,self.related,self.key_getter=extractor,related,key_getter
        self.fetcher,self.delay=fetcher,delay
        self.stop_event=threading.Event()
        self.worker=None

    def _load(self):
        path=self.root/"rfp_batch.json"
        if not path.exists():
            return {"schema_version":1,"revision":0,"status":"IDLE",
                    "target_ids":[],"items":{},"updated_at":None}
        with path.open(encoding="utf-8") as f: state=json.load(f)
        if (not isinstance(state,dict) or state.get("schema_version")!=1 or
            not isinstance(state.get("target_ids"),list) or
            not isinstance(state.get("items"),dict)):
            raise ValueError("RFP 배치 상태 파일이 손상되었습니다")
        return state

    def _save(self,state):
        state["revision"]+=1
        state["updated_at"]=stamp()
        self.persist(state,self.root/"rfp_batch.json")

    def _summary(self,state):
        stats={"total":len(state["target_ids"]),"done":0,"failed":0,"pending":0}
        for ident in state["target_ids"]:
            v=state["items"].get(ident,{}).get("status","PENDING")
            stats[{"DONE":"done","FAILED":"failed"}.get(v,"pending")]+=1
        live=bool(self.worker and self.worker.is_alive())
        status="RUNNING" if live and not self.stop_event.is_set() else (
            "PAUSED" if state["status"]=="RUNNING" else state["status"])
        return {"status":status,"statistics":stats,"revision":state["revision"],
                "updated_at":state["updated_at"],"rate_limit_seconds":self.delay}

    def status(self):
        with self.lock: return self._summary(self._load())

    def start(self,limit=3,retry_failed=False):
        if type(limit) is not int or limit not in (1,3,10,25):
            raise ValueError("한 회차는 1, 3, 10 또는 25건만 가능합니다")
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise ValueError("RFP 배치가 이미 실행 중입니다")
            state=self._load()
            board=read_dashboard(self.root/"dashboard.json")
            profile=load_department_profile(self.root/"department_profile.json")
            if not state["target_ids"]:
                candidates=[n for n in board["notices"] if n.get("department_status")=="CANDIDATE"
                    and any(x in profile["categories"] for x in n.get("department_categories",[]))]
                candidates.sort(key=lambda n:(n.get("window_status")!="OPEN",
                    not bool(ranked(n)),n["id"]))
                state["target_ids"]=[n["id"] for n in candidates]
                state["items"]={n["id"]:{"status":"DONE" if n.get("document_status")=="EXTRACTED"
                    else "PENDING","attempts":0} for n in candidates}
            # 파일 쓰기 직후 비정상 종료되어 ledger만 PENDING인 경우 재다운로드하지 않는다.
            for n in board["notices"]:
                if (n["id"] in state["items"] and n.get("document_status")=="EXTRACTED"):
                    state["items"][n["id"]]["status"]="DONE"
            failed_ids={i for i,item in state["items"].items() if item.get("status")=="FAILED"}
            if retry_failed:
                for ident in failed_ids: state["items"][ident]["status"]="PENDING"
            pending=[i for i in state["target_ids"] if state["items"].get(i,{}).get("status")=="PENDING"
                     and (not retry_failed or i in failed_ids)]
            remaining=any(state["items"].get(i,{}).get("status")=="PENDING" for i in state["target_ids"])
            state["status"]="RUNNING" if pending else ("PAUSED" if remaining else "COMPLETE")
            self._save(state)
            if pending:
                self.stop_event.clear()
                self.worker=threading.Thread(target=self._run,args=(pending[:limit],),
                    daemon=True,name="rfp-sequential-batch")
                self.worker.start()
            return self._summary(state)

    def pause(self):
        with self.lock:
            self.stop_event.set()
            state=self._load()
            if state["status"]=="RUNNING":
                state["status"]="PAUSED"
                self._save(state)
            return self._summary(state)

    def _run(self,targets):
        try:
            for index,ident in enumerate(targets):
                if self.stop_event.is_set(): break
                with self.lock:
                    board=read_dashboard(self.root/"dashboard.json")
                    notice=next((n for n in board["notices"] if n["id"]==ident),None)
                    source_signature=document_signature(notice)
                result=None
                if notice is not None:
                    try:
                        files=ranked(notice)
                        need_related=not any(any(w in f["name"] for w in
                            ("제안요청","과업지시","과업내용")) for f in files)
                        key=self.key_getter() if need_related and self.key_getter else None
                        result=analyze(notice,self.extractor,self.fetcher,self.related,key)
                    except Exception:
                        # 한 공고의 비신뢰 문서/스키마 오류가 나머지 대기열을 중단시키지 않는다.
                        result={"document_status":"FAILED","document_error":"처리 오류",
                                "document_evidence":[],"related_attachments":[]}
                with self.lock:
                    state=self._load()
                    board=read_dashboard(self.root/"dashboard.json")
                    current=next((n for n in board["notices"] if n["id"]==ident),None)
                    outcome="FAILED"
                    if current is not None and result is not None:
                        # 느린 네트워크 중 다른 탭이 새 문서/첨부를 저장한 경우 절대 덮어쓰지 않는다.
                        if document_signature(current)!=source_signature:
                            outcome="DONE" if current.get("document_status")=="EXTRACTED" else "PENDING"
                        elif current.get("document_status")=="EXTRACTED":
                            outcome="DONE"
                        elif current.get("rfp_text") and result["document_status"]!="EXTRACTED":
                            # 실패한 재시도로 사용자가 이전에 확인한 텍스트가 사라지지 않게 한다.
                            outcome="FAILED"
                        else:
                            extras=result.pop("related_attachments",[])
                            known={f.get("url") for f in current.get("attachments",[]) if isinstance(f,dict)}
                            for f in extras:
                                if f.get("url") not in known:
                                    current.setdefault("attachments",[]).append(f)
                                    known.add(f.get("url"))
                            if (current.get("rfp_text") and
                                current["rfp_text"]!=result.get("rfp_text")):
                                history=current.setdefault("document_prior_versions",[])
                                if len(history)>=10:
                                    outcome="FAILED"
                                    result=None
                                else:
                                    history.append({"at":stamp(),"text":current["rfp_text"],
                                        "source_name":current.get("document_source_name",""),
                                        "status":current.get("document_status"),
                                        "evidence":copy.deepcopy(current.get("document_evidence",[]))})
                            if result is not None:
                                current.update(result)
                                reclassify(current)
                                board["revision"]+=1
                                self.persist(board,self.root/"dashboard.json")
                                outcome="DONE" if result["document_status"]=="EXTRACTED" else "FAILED"
                    item=state["items"].setdefault(ident,{"status":"PENDING","attempts":0})
                    item.update({"status":outcome,"attempts":item.get("attempts",0)+1,"updated_at":stamp()})
                    self._save(state)
                if index<len(targets)-1 and self.stop_event.wait(self.delay): break
        finally:
            with self.lock:
                state=self._load()
                pending=any(state["items"].get(i,{}).get("status")=="PENDING" for i in state["target_ids"])
                state["status"]="PAUSED" if pending else "COMPLETE"
                self._save(state)
