import base64
import random
import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from kok_common import DEMO_USER, env, esc, hero, kpis, login_demo, notify, setup, table_html, topbar

setup("온라인 진료 (데모)", """
.demo{display:inline-block;font-size:.7rem;font-weight:800;color:#B96200;background:#FFF1DC;border-radius:5px;padding:2px 8px;margin-left:8px;vertical-align:middle}
.msgbox{background:#fff;border:1px solid var(--ln);border-radius:14px;padding:16px 18px;white-space:pre-wrap;line-height:1.7;font-size:.9rem}
.stp{display:flex;gap:10px;align-items:center;padding:8px 2px;font-size:.9rem}
.stp b{width:26px;height:26px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;background:#E3F6EC;color:#0B8F4A;font-size:.8rem}
.stp.wait b{background:#EEF2F7;color:var(--sb)}
.av{width:64px;height:64px;border-radius:50%;object-fit:cover;display:block;border:3px solid #fff;box-shadow:0 0 0 2px #BFD4EE,0 6px 14px rgba(11,37,69,.15)}
.av.sm{width:44px;height:44px;border-width:2px}
.av.ph{display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#1D5FD1,#0E8F81);color:#fff;font-weight:800;font-size:1.3rem}
.av.sm.ph{font-size:1rem}
.dline{display:flex;align-items:center;gap:12px;margin:4px 0 8px}
.dline b{font-size:1rem}
.drug{background:#fff;border:1px solid var(--ln);border-radius:18px;padding:20px 22px;box-shadow:var(--sh);animation:rise .5s var(--ease) both}
.drug-h{display:flex;gap:16px;align-items:center;padding-bottom:14px;border-bottom:1px solid var(--ln);margin-bottom:6px}
.drug-h img{width:92px;height:62px;object-fit:contain;border-radius:10px;background:#F4F7FB;border:1px solid var(--ln)}
.drug-h .pill{width:62px;height:62px;border-radius:16px;background:linear-gradient(135deg,#F76B9C,#F59E0B);color:#fff;display:flex;align-items:center;justify-content:center;font-size:1.6rem;font-weight:800}
.drug-h h3{margin:0;font-size:1.15rem;font-weight:800}
.drug-h span{font-size:.8rem;color:var(--sb)}
.dsec{display:grid;grid-template-columns:110px 1fr;gap:14px;padding:12px 0;border-top:1px solid #EEF2F7;font-size:.88rem;line-height:1.7}
.dsec:first-of-type{border-top:0}
.dsec>b{color:var(--bl2);font-weight:800}
.dsec.warn>b{color:#B96200}
.dsec.warn>div{background:#FFF8EB;border-radius:10px;padding:8px 12px}
@media(max-width:640px){.dsec{grid-template-columns:1fr;gap:4px}}
""")

SS = st.session_state
ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "data"

DOCTORS = [  # 임시데이터
    {"id": "d1", "name": "김서연", "clinic": "가상 가온내과의원", "dept": "순환기내과", "region": "서울", "wait": "약 10분", "fee": "5,000원"},
    {"id": "d2", "name": "이도윤", "clinic": "가상 한빛정형외과", "dept": "정형외과", "region": "서울", "wait": "약 15분", "fee": "5,000원"},
    {"id": "d3", "name": "박지민", "clinic": "가상 소화기내과의원", "dept": "소화기내과", "region": "서울", "wait": "약 20분", "fee": "5,000원"},
    {"id": "d4", "name": "최하은", "clinic": "가상 마음채정신건강의학과", "dept": "정신건강의학과", "region": "서울", "wait": "약 30분", "fee": "6,000원"},
    {"id": "d5", "name": "오세린", "clinic": "가상 온누리내분비내과", "dept": "내분비내과", "region": "서울", "wait": "약 20분", "fee": "5,000원"},
    {"id": "d6", "name": "정우진", "clinic": "가상 숨결호흡기내과", "dept": "호흡기내과", "region": "경기", "wait": "약 10분", "fee": "5,000원"},
    {"id": "d7", "name": "한소율", "clinic": "가상 맑은피부과", "dept": "피부과", "region": "경기", "wait": "약 25분", "fee": "5,000원"},
    {"id": "d8", "name": "신태오", "clinic": "가상 맑은소리이비인후과", "dept": "이비인후과", "region": "경기", "wait": "약 15분", "fee": "5,000원"},
    {"id": "d9", "name": "윤재현", "clinic": "가상 바른신경과", "dept": "신경과", "region": "부산", "wait": "약 20분", "fee": "5,000원"},
    {"id": "d10", "name": "강민서", "clinic": "가상 우리가정의학과", "dept": "가정의학과", "region": "부산", "wait": "약 10분", "fee": "4,500원"},
]
REGIONS = ["서울", "경기", "부산"]  # 임시데이터
PHARMACIES = ["가상 햇살약국 (서울)", "가상 늘봄약국 (경기)", "가상 바다약국 (부산)"]  # 임시데이터
STATE_KEYS = ("tele_doc", "tele_msg", "tele_sent", "tele_reply", "tele_deliv", "tele_deliv_done", "tele_drug")

# ---------------------------------------------------------------- 의사 사진
# data/1.jpg ~ 7.jpg, data/8.png ~ 10.png (확장자는 jpg/png/jpeg 모두 탐색)


@st.cache_data(show_spinner=False)
def avatar_uri(n):
    for ext, mime in (("jpg", "jpeg"), ("jpeg", "jpeg"), ("png", "png")):
        p = IMG_DIR / f"{n}.{ext}"
        if p.exists():
            return f"data:image/{mime};base64," + base64.b64encode(p.read_bytes()).decode()
    return ""


def avatar(d, small=False):
    n = int(d["id"][1:])
    cls = "av sm" if small else "av"
    uri = avatar_uri(n)
    if uri:
        return f'<img class="{cls}" src="{uri}" alt="{esc(d["name"])}">'
    return f'<div class="{cls} ph">{esc(d["name"][:1])}</div>'


# ---------------------------------------------------------------- 약 제품 (e약은요)
DRUG_URL = "https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
DRUG_QUERIES = ["타이레놀정500", "탁센", "베아제"]  # 이 3개를 가져와 랜덤으로 1개 처방
DRUG_COLS = {"itemName": "제품명", "entpName": "제조사", "itemSeq": "품목코드", "efcyQesitm": "효능·효과",
             "useMethodQesitm": "용법·용량", "atpnWarnQesitm": "경고", "atpnQesitm": "주의사항",
             "intrcQesitm": "상호작용", "seQesitm": "이상반응", "depositMethodQesitm": "보관법", "itemImage": "이미지"}
SAMPLE_DRUGS = [  # 임시데이터 (API 실패 시 대체)
    {"제품명": "가상 해열진통정 500mg", "제조사": "가상제약", "품목코드": "SAMPLE-1", "효능·효과": "감기로 인한 발열 및 통증, 두통, 근육통의 완화",
     "용법·용량": "성인 1회 1~2정, 1일 3~4회 필요 시 복용 (4시간 이상 간격)", "경고": "", "주의사항": "매일 세 잔 이상 술을 마시는 사람은 복용 전 의사 또는 약사와 상담하세요.",
     "상호작용": "다른 해열진통제와 함께 복용하지 마세요.", "이상반응": "드물게 발진, 구역이 나타날 수 있어요.", "보관법": "실온(1~30℃) 보관, 어린이 손이 닿지 않는 곳", "이미지": ""},
    {"제품명": "가상 소염진통 연질캡슐", "제조사": "가상제약", "품목코드": "SAMPLE-2", "효능·효과": "관절통, 요통, 근육통 및 염증 완화",
     "용법·용량": "성인 1회 1캡슐, 1일 3회 식후 30분 복용", "경고": "", "주의사항": "위장 장애 병력이 있으면 복용 전 상담하세요.",
     "상호작용": "항응고제와 병용 시 주의하세요.", "이상반응": "속쓰림, 소화불량이 나타날 수 있어요.", "보관법": "실온 보관, 습기 피하기", "이미지": ""},
    {"제품명": "가상 소화효소정", "제조사": "가상제약", "품목코드": "SAMPLE-3", "효능·효과": "소화불량, 식욕부진, 과식, 체함, 위부팽만감",
     "용법·용량": "성인 1회 1정, 1일 3회 식후 복용", "경고": "", "주의사항": "증상이 계속되면 복용을 중지하고 의사와 상담하세요.",
     "상호작용": "특별히 알려진 상호작용이 없어요.", "이상반응": "드물게 설사가 나타날 수 있어요.", "보관법": "실온 보관", "이미지": ""},
]


def clean(v):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(v or ""))).strip()


def _drug_items(data):
    body = (data.get("response") or data)["body"]
    items = body.get("items") or []
    if isinstance(items, dict):
        items = items.get("item", [])
    return [items] if isinstance(items, dict) else items


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_drugs(key):
    rows = []
    for q in DRUG_QUERIES:
        r = requests.get(DRUG_URL, timeout=8, params={"serviceKey": key, "itemName": q, "type": "json", "numOfRows": 3, "pageNo": 1})
        try:
            items = _drug_items(r.json())
        except Exception:
            raise RuntimeError(f"약 정보 API 응답 오류 (HTTP {r.status_code}): {r.text[:120]}")
        if items:
            rows.append({ko: clean(items[0].get(en)) for en, ko in DRUG_COLS.items()})
    if not rows:
        raise RuntimeError("조회된 약 제품이 없어요")
    return rows


def drug_frame():
    """(DataFrame, 안내문, 가상여부)"""
    key = env("HIRA_SERVICE_KEY")
    if not key:
        return pd.DataFrame(SAMPLE_DRUGS), "HIRA_SERVICE_KEY가 없어서 가상 예시 약 정보를 써요.", True
    try:
        return pd.DataFrame(fetch_drugs(key)), "", False
    except Exception as e:
        return (pd.DataFrame(SAMPLE_DRUGS),
                f"약 정보 API를 불러오지 못해 가상 예시로 보여드려요. 공공데이터포털에서 '의약품개요정보(e약은요)' 활용신청이 필요할 수 있어요. ({str(e)[:100]})", True)


def short(s, n=36):
    s = str(s or "")
    return s if len(s) <= n else s[:n] + "…"


def show_drug(row, sample):
    img = f'<img src="{esc(row["이미지"])}" alt="">' if row.get("이미지") else '<div class="pill">약</div>'
    tag = '<span class="demo">가상 예시</span>' if sample else ""
    secs = [("효능·효과", "효능·효과", ""), ("용법·용량", "용법·용량", ""), ("경고", "경고", " warn"), ("주의사항", "주의사항", " warn"),
            ("상호작용", "함께 먹을 때", ""), ("이상반응", "이상반응", ""), ("보관법", "보관법", "")]
    body = "".join(f'<div class="dsec{cls}"><b>{esc(lab)}</b><div>{esc(row[col])}</div></div>' for col, lab, cls in secs if row.get(col))
    st.markdown(f'<div class="drug"><div class="drug-h">{img}<div><h3>{esc(row["제품명"])}{tag}</h3>'
                f'<span>{esc(row["제조사"])} · 품목코드 {esc(row["품목코드"])}</span></div></div>{body}</div>', unsafe_allow_html=True)
    st.caption("의약품 정보는 식품의약품안전처 e약은요 기준이에요. 실제 복용은 의사·약사의 안내를 따르세요.")


# ---------------------------------------------------------------- 메시지
def compose(ctx, doc, user):
    age = ctx.get("age")
    sex = ctx.get("sex")
    who = " ".join(x for x in (f"{age}세" if age is not None else "", sex or "") if x) or "미입력"
    lines = [f"안녕하세요, {doc['name']} 선생님. 온라인 진료를 요청드립니다.", "",
             f"[신청자] {user['name']}",
             f"[환자 정보] {who}",
             f"[불편 부위] {ctx['region']}",
             f"[불편 정도] {ctx['sev']}",
             f"[직접 작성한 증상] {ctx['text']}"]
    if ctx.get("opinion"):
        lines += ["", f"[AI 참고 소견] {ctx['opinion']}"]
    if ctx.get("cands"):
        lines.append("[관련 질환 후보(추정)] " + ", ".join(ctx["cands"]))
    lines += ["", "※ AI 소견은 진단이 아닌 참고용 정보이며, 최종 판단은 선생님께 맡깁니다."]
    return "\n".join(lines)


def reset():
    for k in STATE_KEYS:
        SS.pop(k, None)


topbar("콕콕", "온라인 진료")
hero("ONLINE CONSULT", "내 증상과 AI 소견을\n의사에게 한 번에 전달해요",
     "입력한 내용이 자동으로 정리돼요. 보내기 전에 직접 고칠 수 있어요.", ("자동 작성", "수정 가능", "답변 알림", "약 배달 연결 예정"))
st.warning("이 화면은 상용화 시나리오를 보여주는 **데모**예요. 의사·약국은 모두 가상 데이터이고, 실제로 전송되거나 진료·배달되지 않아요.")

ctx = SS.get("consult_ctx")
if not ctx:
    st.info("먼저 증상을 입력하고 분석해 주세요. 입력한 내용을 이 화면에서 이어서 써요.")
    st.page_link("main.py", label="증상 입력하러 가기")
    st.stop()

user = SS.get("user")
if not user:
    st.markdown('<div class="login-card"><span class="acct">로그인 필요</span><h3>온라인 진료는 로그인 후 이용할 수 있어요</h3>'
                '<p>증상과 AI 소견 같은 건강 정보가 의사에게 전달되기 때문에, 본인 확인을 위해 로그인이 필요해요. '
                '데모에서는 가상 계정으로 바로 들어갈 수 있어요.</p></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(f"**데모 계정**  \n{esc(DEMO_USER['name'])} · {esc(DEMO_USER['email'])}")
        if st.button("데모 계정으로 로그인", type="primary", use_container_width=True, key="gate_login"):
            login_demo()
            st.rerun()
    st.page_link("pages/2_hospital_finder.py", label="병원 찾기로 돌아가기")
    st.stop()

emergency = ctx["emergency"]["on"]
if emergency:
    st.error("응급 가능성이 있어요. 온라인 진료를 기다리지 말고 119에 연락하거나 가까운 응급실로 가세요.")
st.page_link("pages/2_hospital_finder.py", label="병원 찾기로 돌아가기")

doc, sent = SS.get("tele_doc"), SS.get("tele_sent")

if not doc:
    st.markdown('<div class="sec">1. 상담할 의사 선택<span class="demo">가상 데이터</span></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    reg = c1.selectbox("지역", REGIONS, index=0)
    all_depts = sorted({d["dept"] for d in DOCTORS})
    sel = c2.multiselect("진료과", all_depts, default=[d for d in ctx["depts"] if d in all_depts])
    shown = [d for d in DOCTORS if d["region"] == reg and (not sel or d["dept"] in sel)]
    if not shown:
        st.info("조건에 맞는 가상 의사가 없어요. 지역이나 진료과를 바꿔 보세요.")
    for d in shown:
        with st.container(border=True):
            p, a, b = st.columns([0.7, 3, 1], vertical_alignment="center")
            p.markdown(avatar(d), unsafe_allow_html=True)
            a.markdown(f"**{esc(d['name'])} 선생님** · {esc(d['dept'])}  \n{esc(d['clinic'])} · {esc(d['region'])}  \n"
                       f"<span class='sub'>예상 응답 {d['wait']} · 상담료 {d['fee']} (가상)</span>", unsafe_allow_html=True)
            if b.button("상담하기", key=f"pick_{d['id']}", type="primary", use_container_width=True, disabled=emergency):
                SS["tele_doc"] = d
                SS["tele_msg"] = compose(ctx, d, user)
                st.rerun()
    st.stop()

st.markdown(f'<div class="dline">{avatar(doc, small=True)}<b>{esc(doc["name"])} 선생님</b></div>', unsafe_allow_html=True)
st.markdown(kpis([("상담 의사", f"{esc(doc['name'])} 선생님", esc(f"{doc['clinic']} · {doc['dept']}")),
                  ("예상 응답", doc["wait"]), ("상담료", doc["fee"], "가상 금액")]), unsafe_allow_html=True)

if not sent:
    st.markdown('<div class="sec">2. 보낼 내용 확인</div><div class="sub" style="margin:-8px 0 10px">'
                '입력하신 증상과 AI 소견이 자동으로 들어갔어요. 자유롭게 고쳐도 돼요.</div>', unsafe_allow_html=True)
    msg = st.text_area("의사에게 보낼 메시지", key="tele_msg", height=320, label_visibility="collapsed")
    agree = st.checkbox("건강 정보(증상·AI 소견)가 의사에게 전달되는 것에 동의해요 (데모)")
    c1, c2 = st.columns(2)
    if c1.button("의사 다시 고르기", use_container_width=True):
        SS.pop("tele_doc", None)
        SS.pop("tele_msg", None)
        st.rerun()
    if c2.button("의사에게 전송 (데모)", type="primary", use_container_width=True, disabled=not (agree and msg.strip())):
        SS["tele_sent"] = {"at": datetime.now().strftime("%H:%M"), "msg": msg}
        notify("상담 요청을 보냈어요", f"{doc['name']} 선생님께 전달됐어요. 답변이 오면 알려드릴게요.")
        st.rerun()
    st.stop()

st.markdown('<div class="sec">3. 전송 완료</div>', unsafe_allow_html=True)
st.success(f"{sent['at']}에 {doc['name']} 선생님께 전달됐어요. (데모)")
with st.expander("보낸 내용 보기"):
    st.markdown(f'<div class="msgbox">{esc(sent["msg"])}</div>', unsafe_allow_html=True)

if not SS.get("tele_reply"):
    st.markdown('<div class="stp wait"><b>…</b>의사 확인 대기 중 · 답변이 오면 오른쪽 위 알림으로 알려드려요</div>', unsafe_allow_html=True)
    if st.button("데모: 의사 답변 도착시키기", use_container_width=True):
        # 약 제품 3종을 가져와 랜덤으로 1개를 처방으로 고정 (이후 rerun에도 유지)
        df, note, sample = drug_frame()
        SS["tele_drug"] = {"row": df.sample(1).iloc[0].to_dict(), "all": df.to_dict("records"), "note": note, "sample": sample}
        SS["tele_reply"] = True
        notify("의사 답변이 도착했어요", f"{doc['name']} 선생님이 답변을 보냈어요. 처방전도 확인해 보세요.")
        st.rerun()
    st.stop()

drug = SS.get("tele_drug")
if not drug:  # 안전장치
    df, note, sample = drug_frame()
    drug = SS["tele_drug"] = {"row": df.sample(1).iloc[0].to_dict(), "all": df.to_dict("records"), "note": note, "sample": sample}
rx = drug["row"]

st.markdown('<div class="stp"><b>✓</b>의사 확인 완료</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sec">의사 답변 <span class="demo">가상 예시</span></div>'
            f'<div class="dline">{avatar(doc, small=True)}<b>{esc(doc["name"])} 선생님</b></div>'
            f'<div class="msgbox">{esc(user["name"])}님, 전달해 주신 내용 확인했습니다. (가상 답변) 실제 서비스에서는 이 자리에 의사의 소견과 안내가 표시돼요.\n\n'  # 임시데이터
            f'처방전(가상): {esc(rx["제품명"])} · 1일 O회 · O일분</div>', unsafe_allow_html=True)  # 임시데이터

st.markdown('<div class="sec">처방 약 정보</div><div class="sub" style="margin:-8px 0 12px">처방된 약이 어떤 약인지 한눈에 볼 수 있어요.</div>',
            unsafe_allow_html=True)
if drug["note"]:
    st.caption(drug["note"])
st.markdown(kpis([("제품명", esc(short(rx["제품명"], 20))), ("제조사", esc(short(rx["제조사"], 16))),
                  ("용법·용량", f'<span style="font-size:.9rem">{esc(short(rx["용법·용량"], 40))}</span>')]), unsafe_allow_html=True)
show_drug(rx, drug["sample"])
with st.expander("후보 3종 비교 (pandas 표)"):
    cmp = pd.DataFrame(drug["all"])
    t = pd.DataFrame({"제품명": cmp["제품명"], "제조사": cmp["제조사"], "효능·효과": cmp["효능·효과"].map(short),
                      "용법·용량": cmp["용법·용량"].map(lambda s: short(s, 30))})
    st.markdown(table_html(t, rank=True), unsafe_allow_html=True)
    st.caption("후보 중 1개가 랜덤으로 처방돼요. '처음부터 다시 해보기'를 누르면 다시 뽑아요.")

st.markdown('<div class="sec">4. 약 받기 <span class="demo">가상 예시</span></div>', unsafe_allow_html=True)
if not SS.get("tele_deliv"):
    mode = st.radio("받는 방법", ["약 배달", "약국에서 직접 수령"], horizontal=True)
    pharm = st.selectbox("약국 선택", PHARMACIES)
    addr = ""
    if mode == "약 배달":
        addr = st.text_input("배달 주소", placeholder="예) 서울시 OO구 OO로 12")
        ready = bool(addr.strip())
    else:
        st.caption("조제가 끝나면 알림으로 알려드려요. 약국에 방문해서 처방전을 확인하고 받아가세요. (예상 준비 시간 약 20분)")  # 임시데이터
        ready = True
    if st.button("약 배달 요청 (데모)" if mode == "약 배달" else "약 수령 요청 (데모)", type="primary", use_container_width=True, disabled=not ready):
        SS["tele_deliv"] = {"mode": mode, "ph": pharm, "addr": addr.strip()}
        notify("약 배달을 요청했어요" if mode == "약 배달" else "약 수령을 요청했어요", f"{pharm}에서 처방전을 접수하고 있어요.")
        st.rerun()
else:
    dv = SS["tele_deliv"]
    delivery = dv["mode"] == "약 배달"
    if not SS.get("tele_deliv_done"):
        box, stages = st.empty(), ["약국에서 처방전 접수", "조제 중", "배달 출발" if delivery else "수령 준비 완료"]
        for i in range(len(stages)):
            box.markdown("".join(f'<div class="stp{"" if j <= i else " wait"}"><b>{"✓" if j <= i else j + 1}</b>{t}</div>'
                                 for j, t in enumerate(stages)), unsafe_allow_html=True)
            time.sleep(0.8)
        SS["tele_deliv_done"] = True
        if delivery:
            notify("약 배달이 출발했어요", f"{dv['ph']}에서 {dv['addr']}(으)로 이동 중이에요.", toast_now=True)
        else:
            notify("약이 준비됐어요", f"{dv['ph']}에서 받아가실 수 있어요.", toast_now=True)
    if delivery:
        st.success(f"{dv['ph']}에서 {dv['addr']}(으)로 {rx['제품명']} 배달 중이에요. (데모)")
    else:
        st.success(f"{dv['ph']}에서 {rx['제품명']}을(를) 받아가실 수 있어요. (데모)")

if st.button("처음부터 다시 해보기", use_container_width=True):
    reset()
    st.rerun()