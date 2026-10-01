"""어디가 불편하신가요? — 몸 그림 → 증상 입력 → AI 소견 + pandas 일치도 → 주변 병원·지도
실행: streamlit run main.py
.env: HIRA_DISEASE_SERVICE_KEY, GEMINI_API_KEY(무료 AI 분석용), (병원 화면용) KAKAO_REST_API_KEY, HIRA_SERVICE_KEY
"""
import html
import json
import math
import os
import re
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="어디가 불편하신가요?", page_icon="🩺", layout="wide", initial_sidebar_state="collapsed")


def env(n):
    v = (os.getenv(n) or "").strip().strip('"').strip("'").strip()
    return unquote(v) if "%" in v else (v or None)


HIRA_DISEASE = env("HIRA_DISEASE_SERVICE_KEY")
GEMINI = env("GEMINI_API_KEY")  # Google AI Studio 무료 키
HOSPITAL_PAGE = "pages/2_hospital_finder.py"
HOSPITAL_FILE = Path(__file__).resolve().parent / "pages" / "2_hospital_finder.py"

_here = Path(__file__).resolve().parent
_cands = [_here / "body_map", _here.parent / "body_map", Path.cwd() / "body_map"]
_dir = next((p for p in _cands if (p / "index.html").exists()), None)
if _dir is None:
    st.error("`body_map/index.html` 파일을 찾지 못했어요.")
    st.code(str(_cands[0] / "index.html"))
    st.stop()
body_map = components.declare_component("body_map", path=str(_dir))

st.markdown("""<style>
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css");
html,body,.stApp,[class*="css"]{font-family:"Pretendard","Malgun Gothic",sans-serif!important;color:#0F2A43}
.stApp{background:#F4F8FC}.block-container{max-width:1240px;padding-top:1rem}
#MainMenu,footer{visibility:hidden}header[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebarNav"],[data-testid="collapsedControl"],[data-testid="stSidebar"]{display:none}
.topbar{display:flex;align-items:center;gap:12px;background:#fff;border:1px solid #DCE6F1;border-radius:16px;padding:14px 20px;margin-bottom:10px;box-shadow:0 2px 10px rgba(27,111,224,.06)}
.logo{width:38px;height:38px;border-radius:11px;background:#1B6FE0;color:#fff;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:800}
.topbar b{font-size:1.15rem}.topbar span{color:#5E7186;font-size:.86rem;margin-left:8px}
.steps{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}
.steps span{font-size:.8rem;font-weight:600;color:#1B6FE0;background:#E8F1FD;border-radius:999px;padding:4px 12px}
.panel{background:#fff;border:1px solid #DCE6F1;border-radius:16px;padding:16px 20px;margin-bottom:10px}
.rg{font-size:.75rem;color:#5E7186;font-weight:600}.rgn{font-size:1.35rem;font-weight:800;letter-spacing:-.02em}
.chip{display:inline-block;padding:4px 12px;border-radius:999px;font-size:.85rem;font-weight:600;background:#E8F1FD;color:#1B6FE0;margin:0 6px 6px 0}
.rk{display:flex;gap:10px;align-items:center}.rk b{font-size:.95rem}
.rn{flex:0 0 28px;height:28px;border-radius:9px;background:#0F2A43;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.85rem}
.rn.top{background:#1B6FE0}
.sub{font-size:.78rem;color:#5E7186}
.g{height:10px;border-radius:99px;background:#EAF0F7;overflow:hidden}
.g>span{display:block;height:100%;background:linear-gradient(90deg,#4F9BFF,#1B6FE0);border-radius:99px}
.gl{font-size:.8rem;font-weight:800;color:#1B6FE0;margin-top:2px}
.note{font-size:.78rem;color:#5E7186;margin-top:10px}
.stButton>button{border-radius:12px}
</style>""", unsafe_allow_html=True)

# 부위 → (이름, ICD-10 분류, 참고 진료과, 빠른 선택 증상[(증상, 응급여부)]). 화면 구성용 설정이며 의사 검수가 필요합니다.
REGIONS = {
    "head": ("머리 · 얼굴", ["G", "I6", "H", "J3"], ["신경과", "신경외과", "안과", "이비인후과"],
             [("두통", False), ("어지럼증", False), ("경련 · 발작", True), ("의식이 흐려짐", True),
              ("한쪽 팔다리에 힘이 빠지거나 말이 어눌함", True), ("시력 저하 · 이중으로 보임", False), ("눈 통증 · 충혈", False),
              ("이명 · 난청", False), ("코막힘 · 콧물", False), ("얼굴 한쪽이 처짐", True)]),
    "neck": ("목 · 갑상선", ["E0"], ["이비인후과", "내분비내과"],
             [("목에 덩어리가 만져짐", False), ("목소리 변화", False), ("삼킴 곤란", False), ("목 통증", False), ("체중 변화 · 더위를 탐", False)]),
    "shoulder": ("어깨", ["M"], ["정형외과", "재활의학과"],
                 [("어깨 통증", False), ("팔을 들기 힘듦", False), ("어깨가 빠지는 느낌", False), ("팔 저림", False)]),
    "chest": ("가슴 · 심장 · 폐", ["I", "J"], ["순환기내과", "호흡기내과"],
              [("가슴 통증 · 압박감", True), ("숨쉬기 힘듦", True), ("기침이 오래감", False), ("가래 · 쌕쌕거림", False), ("두근거림", False)]),
    "arm": ("팔 · 팔꿈치", ["M", "G5"], ["정형외과", "재활의학과", "신경과"],
            [("관절 통증", False), ("저림", False), ("근력 저하", False), ("붓기", False)]),
    "hand": ("아래팔 · 손목 · 손", ["M", "G5"], ["정형외과", "재활의학과", "신경과"],
             [("손목 통증", False), ("손 저림", False), ("손 떨림", False), ("손가락 뻣뻣함 · 변형", False)]),
    "abdomen": ("배 · 소화기", ["K"], ["소화기내과", "외과"],
                [("배가 아픔", False), ("구토 · 메스꺼움", False), ("설사", False), ("변비", False),
                 ("피가 섞인 변 · 검은 변", True), ("이유 없는 체중 감소", False), ("눈이나 피부가 노래짐", False)]),
    "flank": ("옆구리", ["N2", "K8", "N1"], ["비뇨의학과", "소화기내과"],
              [("옆구리 통증", False), ("소변에 피가 섞임", False), ("열 · 오한", False), ("구토 · 메스꺼움", False)]),
    "pelvis": ("골반 · 사타구니 · 생식", ["N"], ["비뇨의학과", "산부인과"],
               [("소변 볼 때 통증", False), ("소변 횟수 변화", False), ("소변에 피가 섞임", False), ("골반 통증", False), ("생리 이상", False)]),
    "hip": ("엉덩이 · 고관절", ["M", "K6"], ["정형외과", "대장항문외과"],
            [("엉덩이 통증", False), ("걸을 때 고관절 통증", False), ("항문 통증 · 출혈", False), ("앉기 힘듦", False)]),
    "upper_back": ("등", ["M", "J"], ["정형외과", "재활의학과", "호흡기내과"],
                   [("등 통증", False), ("숨 쉴 때 등이 아픔", False), ("어깨뼈 사이가 뻐근함", False), ("등이 굽음", False)]),
    "lower_back": ("허리", ["M", "N2"], ["정형외과", "신경외과", "재활의학과"],
                   [("허리 통증", False), ("다리로 뻗치는 통증", False), ("허리를 굽히기 힘듦", False), ("다리 힘 빠짐 + 대소변 이상", True)]),
    "thigh": ("허벅지 · 무릎", ["M", "I8"], ["정형외과", "재활의학과", "혈관외과"],
              [("무릎 통증", False), ("걷기 어려움", False), ("허벅지 통증", False), ("무릎이 붓거나 물이 참", False)]),
    "calf": ("종아리 · 발", ["M", "I8", "E1"], ["정형외과", "혈관외과", "내분비내과"],
             [("종아리 통증 · 쥐", False), ("발 · 발뒤꿈치 통증", False), ("다리 붓기", False),
              ("한쪽 다리만 붓고 아픔", True), ("발 저림 · 감각 저하", False)]),
    "whole": ("전신 · 피부 · 정신", ["D", "E", "L", "F"], ["가정의학과", "피부과", "정신건강의학과"],
              [("심한 피로", False), ("열이 오래감", False), ("피부 발진 · 가려움", False), ("멍이 잘 듦 · 출혈이 안 멎음", True),
               ("우울 · 불안", False), ("잠을 못 잠", False)]),
}
# 증상 표현 → 질환명 키워드 (AI 후보 좁히기 + AI 키가 없을 때 대체 판단)
KW = {"두통": "두통 편두통 뇌", "어지": "어지 현훈 전정 빈혈", "경련": "경련 간질 뇌전증", "의식": "뇌졸중 뇌경색 뇌출혈 혼수",
      "힘이 빠": "뇌경색 뇌출혈 마비 디스크", "시력": "근시 백내장 녹내장 망막 각막", "눈": "결막 각막 안구 녹내장", "이명": "이명 난청 중이염",
      "코": "비염 부비동 비출혈", "삼킴": "인두 식도 후두 편도", "덩어리": "갑상선 결절 종양 림프", "목소리": "후두 성대 갑상선",
      "체중": "갑상선 당뇨 종양", "가슴": "협심증 심근경색 심장 늑", "숨": "천식 폐렴 폐 심부전 기관지", "기침": "기관지 폐렴 천식 결핵",
      "가래": "기관지 천식 폐렴", "두근": "부정맥 빈맥 심방", "배": "위염 위 장염 담낭 췌장 충수", "구토": "위염 장염 담", "설사": "장염 대장",
      "변비": "변비 대장", "피가": "치핵 대장 위궤양 출혈", "노래": "간염 간 담도 황달", "소변": "방광 요로 신우 전립선 신장",
      "옆구리": "요로 결석 신우 신장 담", "골반": "골반 자궁 난소 전립선", "생리": "월경 자궁 난소", "관절": "관절 관절염 류마티스 통풍",
      "저림": "신경 디스크 추간판 수근관 협착", "손목": "수근관 건초염 관절", "어깨": "회전근개 어깨 관절낭 충돌", "허리": "추간판 요통 협착 척추",
      "무릎": "무릎 슬관절 연골 반월상", "발": "족저 무좀 통풍 당뇨 발", "종아리": "정맥 혈전 근", "붓기": "부종 림프 신장 심부전",
      "떨림": "파킨슨 진전 갑상선", "피로": "빈혈 갑상선 간 당뇨", "열": "감염 바이러스 결핵 폐렴", "발진": "피부염 두드러기 습진 건선",
      "멍": "혈소판 혈우 출혈 자반", "우울": "우울 불안 조울", "불안": "불안 공황 우울", "잠": "불면 수면", "항문": "치핵 치루 항문 직장",
      "등": "척추 측만 흉추 늑막"}


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


@st.cache_data(ttl=3600, show_spinner=False)
def gemini_models():
    """이 키로 지금 쓸 수 있는 Gemini flash 계열 모델 목록 (안정판 · 최신 버전 우선). 모델 이름이 바뀌어도 자동으로 따라가요."""
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", timeout=15,
                     headers={"x-goog-api-key": GEMINI}, params={"pageSize": 200})
    if r.status_code != 200:
        raise RuntimeError(f"모델 목록 조회 실패 HTTP {r.status_code} {r.text[:200]}")
    names = [m["name"].split("/")[-1] for m in r.json().get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    ok = [n for n in names if "flash" in n and not re.search(r"image|tts|live|audio|thinking|exp|robotics|computer|embedding", n)]
    if not ok:
        raise RuntimeError("쓸 수 있는 flash 모델이 없어요: " + ", ".join(names[:8]))
    return sorted(ok, key=lambda n: ("latest" not in n, [-int(x) for x in (re.findall(r"\d+", n) + ["0", "0"])[:2]], "preview" in n, "lite" in n))


def call_ai(prompt):
    """무료 Gemini API(AI Studio 키)로 JSON 응답을 받음. 모델이 막혀 있으면 다음 모델로 넘어가고, 다 실패하면 이유를 담아 예외."""
    if not GEMINI:
        raise RuntimeError(".env에 GEMINI_API_KEY가 없어요")
    last = ""
    queue = [m for m in dict.fromkeys([os.getenv("GEMINI_MODEL", "")] + gemini_models()) if m]
    tried = []
    while queue and len(tried) < 8:
        model = queue.pop(0)
        if model in tried:
            continue
        tried.append(model)
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", timeout=60,
                          headers={"x-goog-api-key": GEMINI},
                          json={"contents": [{"parts": [{"text": prompt}]}],
                                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}})
        if r.status_code == 200:
            return "".join(x.get("text", "") for x in r.json()["candidates"][0]["content"]["parts"])
        last = f"{model} → HTTP {r.status_code} {r.text[:200]}"
        if r.status_code in (400, 401, 403):  # 키 문제면 다른 모델도 소용없음
            break
        hint = re.search(r"use models/([\w.\-]+)", r.text)  # 구글이 대체 모델을 알려주면 그걸 먼저 시도
        if hint and hint.group(1) not in tried:
            queue.insert(0, hint.group(1))
    raise RuntimeError(last + f" (시도한 모델: {', '.join(tried)})")


def rank(df, kws):
    """질환명에서 증상 키워드를 찾아 점수를 매기는 pandas 계산.
    - 여러 질환에 흔히 들어가는 단어(예: '심장')는 가중치를 낮추고, 드문 단어(예: '협심증')는 높여요.
    - 일치도(%) = 상위 후보 6개 안에서 각 질환의 점수 비중 (합계 100%)."""
    names, n = df["질환명"], len(df)
    s = pd.Series(0.0, index=df.index)
    for k, w in kws.items():
        hit = names.str.contains(k, regex=False)
        d = int(hit.sum())
        if d:
            s = s + hit.astype(float) * w * (math.log((n + 1) / (d + 1)) + 1)
    out = df.assign(점수=s)
    out = out[out["점수"] > 0]
    out = out.assign(길이=out["질환명"].str.len()).sort_values(["점수", "길이"], ascending=[False, True]).head(6)
    out = out.drop(columns="길이").reset_index(drop=True)
    out["일치도"] = (out["점수"] / out["점수"].sum() * 100).round().astype(int)
    return out


@st.cache_data(ttl=1800, show_spinner="증상을 분석하는 중...")
def analyze(region, picked, text, sev, prefixes, depts):
    """AI(Gemini)는 '소견'과 키워드만 담당. 질환 후보와 일치도는 심평원 상병 데이터에서 pandas로 계산."""
    df = pd.DataFrame(icd_list(prefixes), columns=["질환명", "상병코드"])
    ai, err = {}, ""
    try:
        prompt = (f"불편한 부위: {REGIONS[region][0]}\n선택한 증상: {', '.join(picked) or '없음'}\n불편한 정도: {sev}\n"
                  f"환자가 직접 쓴 설명: {text or '없음'}\n\n"
                  "아래 JSON 객체로만 답하세요. "
                  '{"opinion":"환자 표현을 근거로 한 종합 소견 3~4문장","emergency":true,"depts":["진료과"],'
                  '"keywords":["질환명에 들어갈 법한 한글 단어(예: 협심증, 추간판)"],"advice":"생활 안내 한 문장"}. '
                  "depts는 최대 3개, keywords는 최대 8개. 응급 가능성이 있으면 emergency를 true로. "
                  "진단이 아니라 병원을 찾기 위한 참고용이라는 점을 소견에 반영하세요.")
        txt = call_ai(prompt)
        ai = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
    except Exception as e:  # noqa: BLE001
        err = str(e)[:250]
    kws = {}

    def add(k, w):
        k = k.strip()
        if len(k) >= 2:
            kws[k] = max(kws.get(k, 0), w)

    for sym in list(picked) + ([text] if text else []):
        for k, v in KW.items():
            if k in sym:
                for x in v.split():
                    add(x, 1.0)
    for k in ai.get("keywords", []):
        if isinstance(k, str):
            add(k, 2.0)
    for x in re.findall(r"[가-힣]{2,}", text):
        add(x, 0.5)
        if len(x) >= 3:
            add(x[:2], 0.5)  # '통증이' → '통증'
    return {"ai": ai, "err": err, "table": rank(df, kws), "depts": (ai.get("depts") or list(depts))[:3]}


@st.cache_data(ttl=86400, show_spinner="질환 정보를 정리하는 중...")
def disease_brief(name, code):
    """선택한 질환의 일반적 경과·완치 가능성 (AI 일반 정보)."""
    txt = call_ai(f"질환: {name} (KCD {code})\n아래 JSON 객체로만 답하세요. "
                  '{"course":"일반적인 경과와 치료 기간 2문장","cure":"완치 또는 회복 가능성과 관리 방법 2문장"}. '
                  "확실하지 않은 내용이나 수치는 쓰지 말고 '자료 없음'이라고 쓰세요. 숫자를 지어내지 마세요.")
    return json.loads(txt[txt.index("{"):txt.rindex("}") + 1])


@st.cache_data(ttl=86400, show_spinner=False)
def wiki_summary(name):
    try:
        n = re.sub(r"\s*[\[\(].*?[\]\)]", "", name).strip() or name
        r = requests.get("https://ko.wikipedia.org/w/api.php", timeout=8, headers={"User-Agent": "body-finder/1.0"}, params={
            "action": "query", "format": "json", "generator": "search", "gsrsearch": n, "gsrlimit": 1, "prop": "extracts|info",
            "exintro": 1, "explaintext": 1, "exsentences": 4, "inprop": "url", "redirects": 1})
        p = next(iter(r.json()["query"]["pages"].values()))
        return p.get("extract", ""), p.get("fullurl", "")
    except Exception:  # noqa: BLE001
        return "", ""


@st.cache_data(show_spinner=False)
def load_stats():
    """data/disease_stats.(csv|xlsx) — 보건의료빅데이터개방시스템 '질병 세분류(4단 상병) 통계' 다운로드 파일을 pandas로 읽음."""
    for f in sorted((_here / "data").glob("*.csv")) + sorted((_here / "data").glob("*.xlsx")):  # data 폴더의 아무 이름의 파일
        d = None
        try:
            if f.suffix == ".xlsx":
                d = pd.read_excel(f)
            else:
                for enc in ("utf-8-sig", "cp949"):
                    try:
                        d = pd.read_csv(f, encoding=enc)
                        break
                    except Exception:  # noqa: BLE001
                        continue
        except Exception:  # noqa: BLE001
            d = None
        if d is None:
            continue
        code = next((c for c in d.columns if "상병" in str(c) and "코드" in str(c)), None) or next((c for c in d.columns if "코드" in str(c)), None)
        pat = next((c for c in d.columns if "환자" in str(c)), None)
        if code is None or pat is None:
            continue
        yr = next((c for c in d.columns if "년도" in str(c) or "연도" in str(c)), None)
        if yr is not None:
            d = d[d[yr] == d[yr].max()]  # 여러 해가 섞여 있으면 가장 최근 해만
        d = d[[code, pat]].copy()
        d.columns = ["코드", "환자수"]
        d["코드"] = d["코드"].astype(str).str.replace(".", "", regex=False).str.upper().str.strip()
        d["환자수"] = pd.to_numeric(d["환자수"].astype(str).str.replace(",", ""), errors="coerce")
        return d.dropna().groupby("코드")["환자수"].sum().to_dict()
    return {}


def patients(S, code):
    c = code.replace(".", "").upper()
    return S.get(c, S.get(c[:3])) if S else None


RED = ("의식", "경련", "발작", "호흡곤란", "숨을 못", "숨이 안", "마비", "식은땀", "피를 토", "혈변", "검은 변", "시력을 잃", "말이 어눌", "실신", "쓰러")


def go(name, code, depts=()):
    if not HOSPITAL_FILE.exists():
        st.error("`pages/2_hospital_finder.py` 파일이 없어요. 병원 화면 파일을 teamProject/pages/ 폴더에 넣어 주세요.")
        return
    st.session_state["pick_disease"] = {"n": name, "c": code, "depts": list(depts)}
    st.switch_page(HOSPITAL_PAGE)


def show_detail(nm, cd, pct, S, depts):
    with st.container(border=True):
        st.markdown(f"#### {nm} · `{cd}`")
        if pct is not None:
            st.progress(pct / 100, text=f"후보 중 일치도 {pct}%")
        n = patients(S, cd)
        if n is not None:
            st.metric("연간 진료 환자 수 (건강보험 청구 기준)", f"{int(n):,}명",
                      help="청구 명세서의 주상병 기준이고, 자료 구분(입원·외래, 연령 등)을 합산해 중복이 있을 수 있어요.")
        else:
            st.caption("환자 수 통계 파일이 없어요. (선택) `data` 폴더에 심평원 4단상병 통계 CSV를 넣으면 표시돼요.")
        if GEMINI:
            try:
                b = disease_brief(nm, cd)
                st.markdown("**경과 · 완치 가능성** (AI 일반 정보)")
                st.write(f"{b.get('course', '')} {b.get('cure', '')}")
            except Exception as e:  # noqa: BLE001
                st.caption(f"AI 정보를 불러오지 못했어요. ({str(e)[:120]})")
        ext, url = wiki_summary(nm)
        if ext:
            st.markdown("**개요**")
            st.write(ext)
            st.caption(f"출처: [위키백과]({url}) · 일반 정보이며 진단·치료를 대신하지 않아요.")
        if st.button("📍 가까운 병원 · 지도 보기", type="primary", use_container_width=True, key=f"go_{cd}"):
            go(nm, cd, depts)


def row_html(i, nm, cd, n):
    extra = f" · 연 {int(n):,}명" if n is not None else ""
    return (f'<div class="rk"><span class="rn{" top" if i == 0 else ""}">{i + 1}</span>'
            f'<div><b>{html.escape(nm)}</b><div class="sub">{html.escape(cd)}{extra}</div></div></div>')


# ---------------------------------------------------------------
st.markdown('<div class="topbar"><div class="logo">✚</div><div><b>어디가 불편하신가요?</b>'
            '<span>증상 분석 · 질환 정보 · 가까운 병원 찾기</span></div></div>'
            '<div class="steps"><span>① 부위 선택</span><span>② 증상 입력</span><span>③ 질환 확인</span><span>④ 병원 찾기</span></div>',
            unsafe_allow_html=True)

left, right = st.columns([1, 1.3], gap="large")
with left:
    val = body_map(sel=st.session_state.get("region"), key="body", default=None)
    if val and val.get("region"):
        st.session_state["region"] = val["region"]
region = st.session_state.get("region")

with right:
    if region not in REGIONS:
        st.markdown('<div class="panel"><b>불편한 부위를 눌러 주세요</b><br>'
                    '<span class="note">왼쪽 몸 그림에서 앞면·뒷면을 바꿔 가며 고를 수 있어요.</span></div>', unsafe_allow_html=True)
        st.write("")
        if st.button("🏥 병원 바로 찾기", use_container_width=True):
            st.switch_page(HOSPITAL_PAGE)
    else:
        label, prefixes, depts, _sym = REGIONS[region]
        st.markdown(f'<div class="panel"><span class="rg">선택한 부위</span><div class="rgn">{label}</div></div>', unsafe_allow_html=True)
        text = st.text_area("어떻게 아픈지 자세히 적어 주세요", height=120,
                            placeholder="예) 어제 저녁부터 왼쪽 가슴이 조이듯 아프고, 계단을 오르면 숨이 차요. 식은땀도 났어요.")
        sev = st.select_slider("불편한 정도", ["약함", "보통", "심함", "견디기 어려움"], value="보통")
        if any(w in text for w in RED):
            st.error("⚠️ 응급 가능성이 있는 표현이 있어요. 지체하지 말고 119에 연락하거나 가까운 응급실로 가세요.")
        if st.button("🔍 분석하기", type="primary", use_container_width=True, disabled=not text.strip()):
            st.session_state.pop("detail", None)
            try:
                st.session_state["res"] = (region, analyze(region, (), text.strip(), sev, tuple(prefixes), tuple(depts)))
            except Exception as e:  # noqa: BLE001
                st.session_state.pop("res", None)
                st.warning(f"분석하지 못했어요. ({e})")

        S = load_stats()
        res = st.session_state.get("res")
        if res and res[0] == region:
            res = res[1]
            ai, rdepts = res["ai"], res["depts"]
            if res["err"]:
                st.warning("AI 소견을 가져오지 못해서 키워드 계산만 했어요. " + res["err"])
            if ai.get("emergency"):
                st.error("⚠️ 응급 가능성이 있어 보여요. 지체하지 말고 119에 연락하거나 가까운 응급실로 가세요.")
            if ai.get("opinion"):
                st.markdown("**🩺 AI 소견**")
                st.info(ai["opinion"] + (f"\n\n💡 {ai['advice']}" if ai.get("advice") else ""))
            st.markdown("**추천 진료과** &nbsp;" + "".join(f'<span class="chip">{d}</span>' for d in rdepts), unsafe_allow_html=True)

            table = res["table"]
            if table.empty:
                st.info("입력한 증상과 맞는 질환명을 찾지 못했어요. 증상을 더 자세히 적어 보세요.")
            else:
                st.markdown("**관련 질환** &nbsp;<span class='sub'>일치도순 · 후보 6개 안에서의 상대 비중(합계 100%) · 진단 확률이 아니에요</span>",
                            unsafe_allow_html=True)
                with st.container(border=True):
                    for i, r in table.iterrows():
                        c1, c2, c3 = st.columns([3.1, 2.2, 0.9], vertical_alignment="center")
                        c1.markdown(row_html(i, r["질환명"], r["상병코드"], patients(S, r["상병코드"])), unsafe_allow_html=True)
                        c2.markdown(f'<div class="g"><span style="width:{r["일치도"]}%"></span></div><div class="gl">{r["일치도"]}%</div>',
                                    unsafe_allow_html=True)
                        if c3.button("상세", key=f"d_{r['상병코드']}_{i}", use_container_width=True):
                            st.session_state["detail"] = (r["질환명"], r["상병코드"], int(r["일치도"]))
                dt = st.session_state.get("detail")
                if dt and dt[1] in set(table["상병코드"]):
                    show_detail(dt[0], dt[1], dt[2], S, rdepts)

        with st.expander("📋 이 부위의 전체 질환 목록 (심평원 상병 데이터)"):
            try:
                allv = pd.DataFrame(icd_list(tuple(prefixes)), columns=["질환명", "상병코드"])
                q = st.text_input("질환명 검색", placeholder="예) 협심증", label_visibility="collapsed")
                if q.strip():
                    allv = allv[allv["질환명"].str.contains(q.strip(), regex=False)]
                allv = allv.head(300).reset_index(drop=True)
                cfg = {}
                if S:
                    allv["연간 환자수"] = [patients(S, c) for c in allv["상병코드"]]
                    cfg["연간 환자수"] = st.column_config.NumberColumn("연간 환자수", format="%d")
                ev = st.dataframe(allv, hide_index=True, use_container_width=True, height=300, column_config=cfg,
                                  on_select="rerun", selection_mode="single-row", key="allt")
                if ev.selection.rows:
                    r = allv.iloc[ev.selection.rows[0]]
                    show_detail(r["질환명"], r["상병코드"], None, S, depts)
            except Exception as e:  # noqa: BLE001
                st.warning(f"질환 목록을 불러오지 못했어요. ({e})")

st.markdown('<div class="note">이 화면은 진단이 아니라 진료과와 병원을 찾기 위한 안내예요. '
            '증상이 계속되거나 심해지면 의료진과 상담하세요.</div>', unsafe_allow_html=True)