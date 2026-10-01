"""어디가 불편하신가요? — 몸 그림에서 부위를 눌러 증상·관련 질환·병원 찾기"""
import json
import os
from pathlib import Path
from urllib.parse import unquote

import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="어디가 불편하신가요?", page_icon="🧍", layout="wide", initial_sidebar_state="collapsed")


def env(n):
    v = (os.getenv(n) or "").strip().strip('"').strip("'").strip()
    return unquote(v) if "%" in v else (v or None)


HIRA_DISEASE = env("HIRA_DISEASE_SERVICE_KEY")
_here = Path(__file__).resolve().parent
_cands = [_here.parent / "body_map", _here / "body_map", Path.cwd() / "body_map"]
_dir = next((p for p in _cands if (p / "index.html").exists()), None)
if _dir is None:
    st.error("`body_map/index.html` 파일을 찾지 못했어요. 아래 위치에 폴더를 만들고 index.html을 넣어 주세요.")
    st.code(str(_cands[0] / "index.html"))
    st.stop()
body_map = components.declare_component("body_map", path=str(_dir))

st.markdown("""<style>
.stApp{background:#F2F6F8}.block-container{max-width:1200px;padding-top:1.2rem}
#MainMenu,footer{visibility:hidden}
.panel{background:#fff;border:1px solid #E3EAEF;border-radius:16px;padding:20px 22px}
.chip{display:inline-block;padding:4px 12px;border-radius:999px;font-size:.85rem;font-weight:600;background:#E6F2F1;color:#0F766E;margin:0 6px 6px 0}
.note{font-size:.78rem;color:#5B6B7B;margin-top:8px}
</style>""", unsafe_allow_html=True)

# ---------------------------------------------------------------
# 부위 → 증상 · 진료과 · ICD-10 분류. 화면 구성용 설정값이며 의사 검수가 필요합니다.
# (질환 목록은 여기 없고, 아래 icd_list()가 심평원 상병 데이터에서 불러옵니다.)
# 증상 튜플의 두 번째 값이 True면 응급 안내를 띄웁니다.
# ---------------------------------------------------------------
REGIONS = {
    "head": ("머리 · 뇌", ["G", "I6"], ["신경과", "신경외과"],
             [("두통", False), ("어지럼증", False), ("경련 · 발작", True), ("의식이 흐려짐", True),
              ("한쪽 팔다리에 힘이 빠지거나 말이 어눌함", True), ("기억력 저하", False), ("시야가 흐리거나 이중으로 보임", False)]),
    "face": ("눈 · 코 · 입 · 귀", ["H", "J3"], ["안과", "이비인후과"],
             [("시력 저하", False), ("눈 통증 · 충혈", False), ("갑작스러운 시력 상실", True), ("이명 · 난청", False),
              ("코막힘 · 콧물", False), ("삼킴 곤란", False), ("얼굴 한쪽이 처짐", True)]),
    "neck": ("목 · 갑상선", ["E0"], ["이비인후과", "내분비내과"],
             [("목에 덩어리가 만져짐", False), ("목소리 변화", False), ("삼킴 곤란", False), ("목 통증", False), ("체중 변화 · 더위를 탐", False)]),
    "chest": ("가슴 · 심장 · 폐", ["I", "J"], ["순환기내과", "호흡기내과"],
              [("가슴 통증 · 압박감", True), ("숨쉬기 힘듦", True), ("기침이 오래감", False), ("가래 · 쌕쌕거림", False),
               ("두근거림", False), ("쉽게 숨이 참", False)]),
    "abdomen": ("배 · 소화기", ["K"], ["소화기내과", "외과"],
                [("배가 아픔", False), ("구토 · 메스꺼움", False), ("설사", False), ("변비", False),
                 ("피가 섞인 변 · 검은 변", True), ("이유 없는 체중 감소", False), ("눈이나 피부가 노래짐", False)]),
    "pelvis": ("골반 · 비뇨 · 생식", ["N"], ["비뇨의학과", "산부인과"],
               [("소변 볼 때 통증", False), ("소변 횟수 변화", False), ("소변에 피가 섞임", False), ("골반 통증", False), ("생리 이상", False)]),
    "arm": ("팔 · 어깨 · 손", ["M"], ["정형외과", "재활의학과", "신경과"],
            [("관절 통증", False), ("저림", False), ("근력 저하", False), ("붓기", False), ("손 떨림", False)]),
    "leg": ("다리 · 무릎 · 발", ["M", "I8"], ["정형외과", "재활의학과", "혈관외과"],
            [("관절 통증", False), ("걷기 어려움", False), ("다리 붓기", False), ("저림", False),
             ("한쪽 다리만 붓고 아픔", True), ("자주 넘어짐", False)]),
    "whole": ("전신 · 피부 · 정신", ["D", "E", "L", "F"], ["가정의학과", "피부과", "정신건강의학과"],
              [("심한 피로", False), ("열이 오래감", False), ("피부 발진 · 가려움", False), ("멍이 잘 듦 · 출혈이 안 멎음", True),
               ("우울 · 불안", False), ("잠을 못 잠", False), ("성장이 또래보다 느림", False)]),
}
AGES = {"baby": "👶 영유아 (0–5세)", "kid": "🧒 어린이 (6–12세)", "adult": "🧑 성인", "senior": "👴 노인 (65세+)"}


@st.cache_data(ttl=3600, show_spinner=False)
def icd_list(prefixes: tuple):
    """심평원 상병 목록(4단 상병)에서 해당 분류 코드로 시작하는 질환 조회. 실패하면 예외 → 캐시되지 않음."""
    if not HIRA_DISEASE:
        raise RuntimeError("HIRA_DISEASE_SERVICE_KEY가 없어요.")
    out = {}
    for pf in prefixes:
        r = requests.get("https://apis.data.go.kr/B551182/diseaseInfoService1/getDissNameCodeList1", timeout=12,
                         params={"serviceKey": HIRA_DISEASE, "numOfRows": 300, "pageNo": 1, "_type": "json",
                                 "sickType": 2, "medTp": 1, "diseaseType": "SICK_CD", "searchText": pf})
        try:
            items = r.json()["response"]["body"]["items"]
            items = items.get("item", []) if items else []
        except Exception:
            raise RuntimeError(f"응답을 읽지 못했어요: {r.text[:150]}")
        for it in ([items] if isinstance(items, dict) else items):
            cd, nm = it.get("sickCd", ""), it.get("sickNm", "").strip()
            if nm and cd.startswith(pf):
                out[nm] = cd
    if not out:
        raise RuntimeError("조회된 질환이 없어요.")
    return sorted(out.items(), key=lambda x: x[1])


def go(name, code):
    st.session_state["pick_disease"] = {"n": name, "c": code, "l": "ko"}
    st.switch_page("app_v2.py")


# ---------------------------------------------------------------
st.markdown("### 🧍 어디가 불편하신가요?")
st.caption("몸에서 불편한 부위를 눌러 보세요. 증상을 체크하면 관련 질환과 주변 병원을 찾아드려요.")

c1, c2 = st.columns([1.6, 1])
with c1:
    age = st.pills("연령대", list(AGES), format_func=AGES.get, default="adult", selection_mode="single") or "adult"
with c2:
    sex = st.pills("성별", ["m", "f"], format_func=lambda x: "남자" if x == "m" else "여자", default="m",
                   selection_mode="single") or "m"

left, right = st.columns([1, 1.25], gap="large")
with left:
    val = body_map(age=age, sex=sex, sel=st.session_state.get("region"), key="body", default=None)
    if val and val.get("region"):
        st.session_state["region"] = val["region"]
region = st.session_state.get("region")

with right:
    if region not in REGIONS:
        st.markdown('<div class="panel">왼쪽 몸 그림에서 <b>불편한 부위</b>를 눌러 주세요.<br>'
                    '<span class="note">연령대와 성별을 바꾸면 그림도 바뀌어요.</span></div>', unsafe_allow_html=True)
    else:
        label, prefixes, depts, symptoms = REGIONS[region]
        depts = (["소아청소년과"] + depts) if age in ("baby", "kid") else depts
        st.markdown(f"#### {label}")

        st.markdown("**어떻게 아프신가요?**")
        picked = st.multiselect("증상 선택", [s for s, _ in symptoms], label_visibility="collapsed",
                                placeholder="해당하는 증상을 모두 골라 주세요")
        if any(u for s, u in symptoms if s in picked):
            st.error("⚠️ 응급 가능성이 있는 증상이에요. 지체하지 말고 119에 연락하거나 가까운 응급실로 가세요.")
        if picked:
            st.select_slider("불편한 정도", ["약함", "보통", "심함", "견디기 어려움"], value="보통")
            chips = "".join(f'<span class="chip">{d}</span>' for d in depts)
            st.markdown(f"**추천 진료과** &nbsp; {chips}", unsafe_allow_html=True)
            cols = st.columns(len(depts))
            for col, d in zip(cols, depts):
                if col.button(f"{d} 병원", key=f"dept_{d}", use_container_width=True):
                    go(d, "진료과")

        st.markdown("**이 부위와 관련된 질환** (심평원 상병 목록)")
        try:
            items = icd_list(tuple(prefixes))
            names = [f"{n}   ·   {c}" for n, c in items]
            sel = st.selectbox("질환", names, index=None, placeholder="질환명을 입력해 검색하세요",
                               label_visibility="collapsed")
            if sel:
                nm, cd = [x.strip() for x in sel.rsplit("·", 1)]
                if st.button(f"'{nm}' 치료 병원 찾기", type="primary", use_container_width=True):
                    go(nm, cd)
        except Exception as e:  # noqa: BLE001
            st.warning(f"관련 질환 목록을 불러오지 못했어요. ({e})  메인 화면의 'API 연결 점검'을 확인해 주세요.")

st.markdown('<div class="note">이 화면은 진단이 아니라 진료과와 병원을 찾기 위한 안내예요. '
            '증상이 계속되거나 심해지면 의료진과 상담하세요.</div>', unsafe_allow_html=True)