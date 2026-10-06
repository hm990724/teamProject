import time
from datetime import datetime

import streamlit as st

from kok_common import esc, hero, kpis, setup, topbar

setup("온라인 진료 (데모)", """
.demo{display:inline-block;font-size:.7rem;font-weight:800;color:#B96200;background:#FFF1DC;border-radius:5px;padding:2px 8px;margin-left:8px;vertical-align:middle}
.msgbox{background:#fff;border:1px solid var(--ln);border-radius:14px;padding:16px 18px;white-space:pre-wrap;line-height:1.7;font-size:.9rem}
.stp{display:flex;gap:10px;align-items:center;padding:8px 2px;font-size:.9rem}
.stp b{width:26px;height:26px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;background:#E3F6EC;color:#0B8F4A;font-size:.8rem}
.stp.wait b{background:#EEF2F7;color:var(--sb)}
""")

SS = st.session_state

# 전부 가상 데이터입니다. 실제 의료진·의료기관과 무관해요.
DOCTORS = [
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
REGIONS = ["서울", "경기", "부산"]
PHARMACIES = ["가상 햇살약국 (서울)", "가상 늘봄약국 (경기)", "가상 바다약국 (부산)"]
STATE_KEYS = ("tele_doc", "tele_msg", "tele_sent", "tele_reply", "tele_deliv", "tele_deliv_done")


def compose(ctx, doc):
    """main에서 입력한 증상 + Gemini 소견을 의사에게 보낼 메시지로 자동 구성."""
    who = " ".join(x for x in (f"{ctx['age']}세" if ctx.get("age") is not None else "", ctx.get("sex") or "") if x) or "미입력"
    lines = [f"안녕하세요, {doc['name']} 선생님. 온라인 진료를 요청드립니다.", "",
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
     "입력한 내용이 자동으로 정리돼요. 보내기 전에 직접 고칠 수 있어요.", ("자동 작성", "수정 가능", "약 배달 연결 예정"))
st.warning("이 화면은 상용화 시나리오를 보여주는 **데모**예요. 의사·약국은 모두 가상 데이터이고, 실제로 전송되거나 진료·배달되지 않아요.")

ctx = SS.get("consult_ctx")
if not ctx:
    st.info("먼저 증상을 입력하고 분석해 주세요. 입력한 내용을 이 화면에서 이어서 써요.")
    st.page_link("main.py", label="증상 입력하러 가기")
    st.stop()

emergency = ctx["emergency"]["on"]
if emergency:
    st.error("응급 가능성이 있어요. 온라인 진료를 기다리지 말고 119에 연락하거나 가까운 응급실로 가세요.")
st.page_link("pages/2_hospital_finder.py", label="병원 찾기로 돌아가기")

doc, sent = SS.get("tele_doc"), SS.get("tele_sent")

# 1단계: 의사 선택
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
            a, b = st.columns([3, 1], vertical_alignment="center")
            a.markdown(f"**{esc(d['name'])} 선생님** · {esc(d['dept'])}  \n{esc(d['clinic'])} · {esc(d['region'])}  \n"
                       f"<span class='sub'>예상 응답 {d['wait']} · 상담료 {d['fee']} (가상)</span>", unsafe_allow_html=True)
            if b.button("상담하기", key=f"pick_{d['id']}", type="primary", use_container_width=True, disabled=emergency):
                SS["tele_doc"] = d
                SS["tele_msg"] = compose(ctx, d)
                st.rerun()
    st.stop()

# 2단계: 메시지 확인·수정 / 전송
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
        st.rerun()
    st.stop()

# 3단계: 전송 완료 / 답변 / 처방
st.markdown('<div class="sec">3. 전송 완료</div>', unsafe_allow_html=True)
st.success(f"{sent['at']}에 {doc['name']} 선생님께 전달됐어요. (데모)")
with st.expander("보낸 내용 보기"):
    st.markdown(f'<div class="msgbox">{esc(sent["msg"])}</div>', unsafe_allow_html=True)

if not SS.get("tele_reply"):
    st.markdown('<div class="stp wait"><b>…</b>의사 확인 대기 중</div>', unsafe_allow_html=True)
    if st.button("데모: 의사 답변 도착시키기", use_container_width=True):
        SS["tele_reply"] = True
        st.rerun()
    st.stop()

st.markdown('<div class="stp"><b>✓</b>의사 확인 완료</div>', unsafe_allow_html=True)
st.markdown('<div class="sec">의사 답변 <span class="demo">가상 예시</span></div>'
            '<div class="msgbox">전달해 주신 내용 확인했습니다. (가상 답변) 실제 서비스에서는 이 자리에 의사의 소견과 안내가 표시돼요.\n\n'
            '처방전(가상): 약품명 OOO · 1일 O회 · O일분</div>', unsafe_allow_html=True)

# 4단계: 약 배달
st.markdown('<div class="sec">4. 약 배달 <span class="demo">가상 예시</span></div>', unsafe_allow_html=True)
if not SS.get("tele_deliv"):
    pharm = st.selectbox("약국 선택", PHARMACIES)
    addr = st.text_input("배달 주소", placeholder="예) 서울시 OO구 OO로 12")
    if st.button("약 배달 요청 (데모)", type="primary", use_container_width=True, disabled=not addr.strip()):
        SS["tele_deliv"] = {"ph": pharm, "addr": addr.strip()}
        st.rerun()
else:
    dv = SS["tele_deliv"]
    if not SS.get("tele_deliv_done"):
        box, stages = st.empty(), ["약국에서 처방전 접수", "조제 중", "배달 출발"]
        for i in range(len(stages)):
            box.markdown("".join(f'<div class="stp{"" if j <= i else " wait"}"><b>{"✓" if j <= i else j + 1}</b>{t}</div>'
                                 for j, t in enumerate(stages)), unsafe_allow_html=True)
            time.sleep(0.8)
        SS["tele_deliv_done"] = True
    st.success(f"{dv['ph']}에서 {dv['addr']}(으)로 배달 중이에요. (데모)")

if st.button("처음부터 다시 해보기", use_container_width=True):
    reset()
    st.rerun()