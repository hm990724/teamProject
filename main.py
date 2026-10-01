"""어디가 불편하신가요? — 몸 그림 → 증상 입력 → AI 소견 + 관련 질환 추정 → 질환 통계(pandas) → 주변 병원·지도
실행: streamlit run main.py
.env: HIRA_DISEASE_SERVICE_KEY, GEMINI_API_KEY(무료 AI 분석용), (병원 화면용) KAKAO_REST_API_KEY, HIRA_SERVICE_KEY
통계는 파일 없이 심평원 질병정보서비스 API(HIRA_DISEASE_SERVICE_KEY)로 조회해요.
"""
import html
import json
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date
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
.rk{display:flex;gap:10px;align-items:flex-start}.rk b{font-size:.95rem}
.rn{flex:0 0 28px;height:28px;border-radius:9px;background:#0F2A43;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.85rem}
.rn.top{background:#1B6FE0}
.lv{font-size:.72rem;font-weight:700;padding:2px 9px;border-radius:999px;color:#fff;margin-left:6px;vertical-align:middle}
.lv.h{background:#1B6FE0}.lv.m{background:#0E9F8E}.lv.l{background:#94A3B8}
.sub{font-size:.78rem;color:#5E7186}
.note{font-size:.78rem;color:#5E7186;margin-top:10px}
.stButton>button{border-radius:12px}
</style>""", unsafe_allow_html=True)

# 부위 → (이름, ICD-10 분류 접두어, 참고 진료과). 화면 구성용 설정이며 의사 검수가 필요합니다.
REGIONS = {
    "head": ("머리 · 얼굴", ["G", "I6", "H", "J3"], ["신경과", "신경외과", "안과", "이비인후과"]),
    "neck": ("목 · 갑상선", ["E0"], ["이비인후과", "내분비내과"]),
    "shoulder": ("어깨", ["M"], ["정형외과", "재활의학과"]),
    "chest": ("가슴 · 심장 · 폐", ["I", "J"], ["순환기내과", "호흡기내과"]),
    "arm": ("팔 · 팔꿈치", ["M", "G5"], ["정형외과", "재활의학과", "신경과"]),
    "hand": ("아래팔 · 손목 · 손", ["M", "G5"], ["정형외과", "재활의학과", "신경과"]),
    "abdomen": ("배 · 소화기", ["K"], ["소화기내과", "외과"]),
    "flank": ("옆구리", ["N2", "K8", "N1"], ["비뇨의학과", "소화기내과"]),
    "pelvis": ("골반 · 사타구니 · 생식", ["N"], ["비뇨의학과", "산부인과"]),
    "hip": ("엉덩이 · 고관절", ["M", "K6"], ["정형외과", "대장항문외과"]),
    "upper_back": ("등", ["M", "J"], ["정형외과", "재활의학과", "호흡기내과"]),
    "lower_back": ("허리", ["M", "N2"], ["정형외과", "신경외과", "재활의학과"]),
    "thigh": ("허벅지 · 무릎", ["M", "I8"], ["정형외과", "재활의학과", "혈관외과"]),
    "calf": ("종아리 · 발", ["M", "I8", "E1"], ["정형외과", "혈관외과", "내분비내과"]),
    "whole": ("전신 · 피부 · 정신", ["D", "E", "L", "F"], ["가정의학과", "피부과", "정신건강의학과"]),
}

# 질환 이름으로 직접 검색했을 때(부위 없음) 병원 화면에 넘길 진료과: 상병코드 첫 글자 기준
ICD_DEPT = {"A": ["내과"], "B": ["내과"], "C": ["내과"], "D": ["내과"], "E": ["내분비내과"], "F": ["정신건강의학과"],
            "G": ["신경과"], "H": ["안과", "이비인후과"], "I": ["순환기내과"], "J": ["호흡기내과"], "K": ["소화기내과"],
            "L": ["피부과"], "M": ["정형외과"], "N": ["비뇨의학과"], "O": ["산부인과"], "P": ["소아청소년과"],
            "Q": ["소아청소년과"], "R": ["가정의학과"], "S": ["정형외과"], "T": ["정형외과"]}

DISS_URL = "https://apis.data.go.kr/B551182/diseaseInfoService1/getDissNameCodeList1"

# 상병 목록 API가 놓칠 때를 대비한 희귀질환 보강 목록 (이름 검색·부위 목록에 함께 섞여요)
RARE = [("모야모야병", "I675"), ("근위축성 측삭경화증(루게릭병)", "G122"), ("중증 근무력증", "G700"),
        ("다발성 경화증", "G35"), ("헌팅턴병", "G10"), ("낭성 섬유증", "E84"), ("마르팡 증후군", "Q874"),
        ("길랑-바레 증후군", "G610"), ("폰 빌레브란트병", "D680"), ("파브리병", "E752"), ("고셔병", "E752"),
        ("프라더-윌리 증후군", "Q871"), ("레트 증후군", "F842"), ("두센 근이영양증", "G710"),
        ("척수성 근위축증", "G120"), ("베체트병", "M352"), ("타카야수 동맥염", "M314"), ("전신 경화증", "M34"),
        ("유전성 혈관부종", "D841"), ("폐동맥 고혈압", "I270")]


def _is_disease(cd, nm):
    """진짜 질환만 남겨요. 산정특례 안내 코드(V…)나 외인(V~Y) 코드, '진료를 받은 당일…' 같은 긴 설명 항목은 제외."""
    if not cd or not nm or cd[0].upper() in "VWXY":
        return False
    return len(nm) <= 60 and "진료를 받은" not in nm and "해당상병" not in nm


def _hira_pages(extra):
    """심평원 상병 API를 마지막 페이지까지 모두 읽어요. (1페이지만 읽으면 뒤쪽 질환이 잘려요.)"""
    out, page = [], 1
    while page <= 40:
        r = requests.get(DISS_URL, timeout=15, params={"serviceKey": HIRA_DISEASE, "numOfRows": 500, "pageNo": page,
                                                       "_type": "json", "medTp": 1, **extra})
        try:
            body = r.json()["response"]["body"]
            items = body["items"]
            items = items.get("item", []) if items else []
            total = int(body.get("totalCount", 0) or 0)
        except Exception:
            raise RuntimeError(f"응답을 읽지 못했어요: {r.text[:150]}")
        items = [items] if isinstance(items, dict) else items
        out += items
        if not items or len(out) >= total:
            break
        page += 1
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def icd_list(prefixes: tuple):
    """부위 분류 코드로 시작하는 질환 전체(4단 상병, 페이지 끝까지) + 희귀질환 보강 목록. 실패하면 예외 → 캐시되지 않음."""
    if not HIRA_DISEASE:
        raise RuntimeError("HIRA_DISEASE_SERVICE_KEY가 없어요.")
    out = {}
    for pf in prefixes:
        for it in _hira_pages({"sickType": 2, "diseaseType": "SICK_CD", "searchText": pf}):
            cd, nm = it.get("sickCd", ""), it.get("sickNm", "").strip()
            if _is_disease(cd, nm) and cd.startswith(pf):
                out[nm] = cd
    for nm, cd in RARE:
        if any(cd.startswith(pf) for pf in prefixes):
            out.setdefault(nm, cd)
    if not out:
        raise RuntimeError("조회된 질환이 없어요.")
    return sorted(out.items(), key=lambda x: x[1])


@st.cache_data(ttl=3600, show_spinner=False)
def name_search(q: str):
    """부위와 상관없이 질환명으로 전체 검색 (희귀질환 포함). 3단·4단 상병을 모두 찾아요. 예) 모야모야"""
    q = q.strip()
    if not HIRA_DISEASE or len(q) < 2:
        return []
    out, last = {}, None
    for st_type in (2, 1):
        try:
            for it in _hira_pages({"sickType": st_type, "diseaseType": "SICK_NM", "searchText": q}):
                cd, nm = it.get("sickCd", ""), it.get("sickNm", "").strip()
                if _is_disease(cd, nm):
                    out.setdefault(nm, cd)
        except Exception as e:  # noqa: BLE001
            last = e
    for nm, cd in RARE:
        if q in nm:
            out.setdefault(nm, cd)
    if not out and last:
        raise RuntimeError(str(last))
    return sorted(out.items(), key=lambda x: x[1])


# ---------------- Gemini ----------------
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


def parse_json(txt):
    return json.loads(txt[txt.index("{"):txt.rindex("}") + 1])


# ---------------- 관련 질환: 키워드로 후보 → Gemini가 추정 ----------------
def candidates(df, kws, limit=40):
    """질환명에 키워드가 들어간 질환을 pandas로 골라 후보를 만들어요.
    여러 질환에 흔한 단어는 가중치를 낮추고 드문 단어는 높여요. (후보 좁히기용 점수이고 확률이 아니에요.)"""
    names, n = df["질환명"], len(df)
    s = pd.Series(0.0, index=df.index)
    for k, w in kws.items():
        hit = names.str.contains(k, regex=False)
        d = int(hit.sum())
        if d:
            s = s + hit.astype(float) * w * (math.log((n + 1) / (d + 1)) + 1)
    out = df.assign(점수=s)
    out = out[out["점수"] > 0].assign(길이=out["질환명"].str.len())
    return out.sort_values(["점수", "길이"], ascending=[False, True]).head(limit).drop(columns="길이").reset_index(drop=True)


@st.cache_data(ttl=1800, show_spinner="증상을 분석하는 중...")
def analyze(region, text, sev, prefixes, depts):
    """1) Gemini: 소견 + 질환명 키워드  2) pandas: 심평원 상병 목록(+키워드 이름 검색, 희귀질환 포함)에서 후보 추리기
    3) Gemini: 후보 목록 '안에서만' 가능성 높은 질환을 골라 근거와 함께 순위 매김 (목록에 없는 코드는 버려요)."""
    df = pd.DataFrame(icd_list(prefixes), columns=["질환명", "상병코드"])
    ai, err, pick_err = {}, "", ""
    try:
        prompt = (f"불편한 부위: {REGIONS[region][0]}\n불편한 정도: {sev}\n환자가 직접 쓴 설명: {text}\n\n"
                  "아래 JSON 객체로만 답하세요. "
                  '{"opinion":"환자 표현을 근거로 한 종합 소견 3~4문장","emergency":true,"depts":["진료과"],'
                  '"keywords":["질환명에 들어갈 법한 한글 단어(예: 협심증, 추간판, 모야모야)"],"advice":"생활 안내 한 문장"}. '
                  "depts는 최대 3개, keywords는 최대 10개. 흔한 질환뿐 아니라 증상과 맞는 희귀질환 이름도 일부 포함하세요. "
                  "응급 가능성이 있으면 emergency를 true로. 진단이 아니라 병원을 찾기 위한 참고용이라는 점을 소견에 반영하세요.")
        ai = parse_json(call_ai(prompt))
    except Exception as e:  # noqa: BLE001
        err = str(e)[:250]

    kws = {}

    def add(k, w):
        k = k.strip()
        if len(k) >= 2:
            kws[k] = max(kws.get(k, 0), w)

    for k in ai.get("keywords", []):
        if isinstance(k, str):
            add(k, 2.0)
    for x in re.findall(r"[가-힣]{2,}", text):  # 환자가 쓴 단어 그대로
        add(x, 0.5)
        if len(x) >= 3:
            add(x[:2], 0.5)  # '통증이' → '통증'

    # 부위 분류 밖의 희귀질환도 후보에 들어오도록, AI 키워드로 질환명 전체 검색
    extra = []
    for k in [k for k in ai.get("keywords", []) if isinstance(k, str)][:6]:
        try:
            extra += name_search(k)
        except Exception:  # noqa: BLE001
            pass
    if extra:
        df = pd.concat([df, pd.DataFrame(extra, columns=["질환명", "상병코드"])]).drop_duplicates("상병코드").reset_index(drop=True)
    cand = candidates(df, kws)

    table = cand.head(6).assign(가능성="", 근거="")  # Gemini가 실패했을 때의 대체 결과
    if not cand.empty and GEMINI:
        try:
            lst = "\n".join(f"{c}|{n}" for n, c in zip(cand["질환명"], cand["상병코드"]))
            prompt = (f"불편한 부위: {REGIONS[region][0]}\n불편한 정도: {sev}\n환자가 직접 쓴 설명: {text}\n"
                      f"앞선 종합 소견: {ai.get('opinion', '없음')}\n\n후보 질환 목록(상병코드|질환명):\n{lst}\n\n"
                      "위 목록 안에서만 환자 설명과 가장 잘 맞는 질환을 가능성이 높은 순서로 최대 6개 고르세요. "
                      "목록에 없는 질환이나 코드는 절대 쓰지 마세요. 설명과 맞지 않으면 적게 골라도 됩니다. "
                      '아래 JSON 객체로만 답하세요. {"picks":[{"code":"목록의 상병코드 그대로","level":"높음|중간|낮음",'
                      '"reason":"환자 표현을 근거로 한 한 문장"}]}. 진단이 아니라 참고용입니다.')
            picks = parse_json(call_ai(prompt)).get("picks", [])
            by_code = dict(zip(cand["상병코드"], cand["질환명"]))
            rows, seen = [], set()
            for p in picks:
                cd = str(p.get("code", "")).strip()
                if cd in by_code and cd not in seen:  # 후보에 있는 코드만 인정
                    seen.add(cd)
                    lv = p.get("level") if p.get("level") in ("높음", "중간", "낮음") else ""
                    rows.append({"질환명": by_code[cd], "상병코드": cd, "가능성": lv, "근거": str(p.get("reason", ""))[:200]})
            if rows:
                table = pd.DataFrame(rows[:6])
            else:
                pick_err = "AI가 후보 안에서 고른 질환이 없어서 키워드 순서로 보여드려요."
        except Exception as e:  # noqa: BLE001
            pick_err = str(e)[:250]
    elif not GEMINI:
        pick_err = "GEMINI_API_KEY가 없어서 키워드 순서로만 보여드려요."
    return {"ai": ai, "err": err, "pick_err": pick_err, "table": table.reset_index(drop=True),
            "depts": (ai.get("depts") or list(depts))[:3]}


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


# ---------------- 질환 통계: 심평원 질병정보서비스 API → pandas ----------------
STATS_BASE = "https://apis.data.go.kr/B551182/diseaseInfoService1"
ENDPOINTS = {"성별·연령별": "getDissByGenderAgeStats1", "입원·외래별": "getDissByHsptlzFrgnStats1",
             "요양기관 종별": "getDissByClassesStats1", "요양기관 지역별": "getDissByAreaStats1"}
TOTAL = {"계", "합계", "전체", "소계", "total", "Total"}
CNT_RE = r"ptnt|patnt|patient"


def fetch_rows(ep, code):
    """최근 연도부터 조회해 자료가 있는 첫 결과를 돌려줘요. 없으면 빈 목록과 이유."""
    note, raw = "자료 없음", ""
    for year in (date.today().year - 1, date.today().year - 2):
        for sc in dict.fromkeys([code, code.replace(".", "").upper()]):
            try:
                r = requests.get(f"{STATS_BASE}/{ep}", timeout=12, params={
                    "serviceKey": HIRA_DISEASE, "numOfRows": 500, "pageNo": 1, "_type": "json",
                    "sickType": 2, "medTp": 1, "sickCd": sc, "year": year})
                raw = r.text[:1500]
                items = r.json()["response"]["body"]["items"]
                rows = items.get("item", []) if items else []
                rows = [rows] if isinstance(rows, dict) else rows
            except Exception as e:  # noqa: BLE001
                note = f"조회 오류: {str(e)[:80]}"
                continue
            if rows:
                return rows, year, "", raw
            note = f"{year}년 자료가 없어요."
    return [], None, note, raw


@st.cache_data(ttl=86400, show_spinner="통계를 불러오는 중...")
def disease_stats(code):
    if not HIRA_DISEASE:
        return {k: {"rows": [], "year": None, "note": "HIRA_DISEASE_SERVICE_KEY가 없어요.", "raw": ""} for k in ENDPOINTS}
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda ep: fetch_rows(ep, code), ENDPOINTS.values()))
    return {k: {"rows": r[0], "year": r[1], "note": r[2], "raw": r[3]} for k, r in zip(ENDPOINTS, res)}


def _num(s):
    return pd.to_numeric(s.astype(str).str.replace(",", ""), errors="coerce")


def tidy(rows):
    """API 응답을 DataFrame으로. 환자수·건수·금액처럼 숫자로 읽히는 항목(meas)과, 값이 여러 가지인 구분 항목(cats)을 나눠요."""
    df = pd.DataFrame(rows)
    meas = [c for c in df.columns if re.search(CNT_RE + r"|cnt|amt|cost|dd|day|clm|fee|pay", c, re.I) and _num(df[c]).notna().all()]
    cats = [c for c in df.columns if c not in meas and df[c].astype(str).nunique() > 1 and not re.search(r"year|yy|ym", c, re.I)]
    for c in meas:
        df[c] = _num(df[c])
    return df, meas, cats


def total_patients(rows):
    """성별·연령 통계에서 연간 환자 수. 전체('계') 행이 있으면 그 값, 없으면 구간 합산(일부 중복 가능). 못 찾으면 None."""
    if not rows:
        return None, ""
    df, meas, cats = tidy(rows)
    f = next((c for c in meas if re.search(CNT_RE, c, re.I)), None)
    if f is None:
        return None, "응답에서 환자 수 항목을 못 찾았어요. 항목: " + ", ".join(df.columns)
    tot = df[df[cats].astype(str).isin(TOTAL).all(axis=1)] if cats else df.iloc[0:0]
    if not tot.empty:
        return float(tot[f].iloc[0]), "성별·연령 전체('계') 행의 값이에요."
    return float(df[f].sum()), "성별·연령 구간을 합산한 값이라, 연령 이동으로 일부 중복될 수 있어요."


def show_stat(label, info):
    rows = info["rows"]
    if not rows:
        st.caption(f"{label} 자료를 가져오지 못했어요. ({info['note']})")
        if info["raw"]:
            with st.expander("API 응답 확인"):
                st.code(info["raw"])
        return
    df, meas, cats = tidy(rows)
    f = next((c for c in meas if re.search(CNT_RE, c, re.I)), None)
    if f and cats:
        base = df[~df[cats].astype(str).isin(TOTAL).any(axis=1)]  # '계' 행은 막대에서 제외
        if not base.empty:
            if len(cats) == 2:  # 예) 성별 × 연령 → 연령별 막대를 성별로 쌓아요
                col = min(cats, key=lambda c: base[c].astype(str).nunique())
                idx = next(c for c in cats if c != col)
                chart = base.groupby([idx, col], sort=False)[f].sum().unstack(col)
            else:
                chart = base.groupby(base[cats].astype(str).agg(" · ".join, axis=1), sort=False)[f].sum().rename("환자 수")
            st.bar_chart(chart)
    st.dataframe(df[cats + meas], hide_index=True, use_container_width=True)
    st.caption(f"{info['year']}년 · 건강보험 · 주상병 기준 · 출처: 건강보험심사평가원 질병정보서비스")


RED = ("의식", "경련", "발작", "호흡곤란", "숨을 못", "숨이 안", "마비", "식은땀", "피를 토", "혈변", "검은 변", "시력을 잃", "말이 어눌", "실신", "쓰러")


def go(name, code, depts=()):
    if not HOSPITAL_FILE.exists():
        st.error("`pages/2_hospital_finder.py` 파일이 없어요. 병원 화면 파일을 pages/ 폴더에 넣어 주세요.")
        return
    depts = list(depts) or ICD_DEPT.get(code[:1].upper(), ["내과"])
    st.session_state["pick_disease"] = {"n": name, "c": code, "depts": depts}
    st.switch_page(HOSPITAL_PAGE)


def show_detail(nm, cd, depts, level=None, reason=None, tag="a"):
    with st.container(border=True):
        st.markdown(f"#### {nm} · `{cd}`")
        if level or reason:
            st.caption(f"AI 추정 가능성: {level or '-'} · {reason or ''}")
        stats = disease_stats(cd)
        n, how = total_patients(stats["성별·연령별"]["rows"])
        if n is not None:
            st.metric(f"{stats['성별·연령별']['year']}년 진료 환자 수 (건강보험)", f"{int(n):,}명", help=how)
        else:
            st.caption(f"환자 수를 가져오지 못했어요. ({how or stats['성별·연령별']['note']})")
        st.markdown("**📊 통계**")
        tabs = st.tabs(list(ENDPOINTS))
        for t, k in zip(tabs, ENDPOINTS):
            with t:
                show_stat(k, stats[k])
        st.caption("※ 건강보험 청구 자료라 진단·진료 현황만 있고, 완치·회복 여부 같은 치료 결과는 이 자료에 없어요.")
        ext, url = wiki_summary(nm)
        if ext:
            st.markdown("**개요**")
            st.write(ext)
            st.caption(f"출처: [위키백과]({url}) · 일반 정보이며 진단·치료를 대신하지 않아요.")
        if st.button("📍 가까운 병원 · 지도 보기", type="primary", use_container_width=True, key=f"go_{tag}_{cd}"):
            go(nm, cd, depts)


def _s(x):
    """pandas 3에서는 빈 값이 NaN(float)으로 바뀌어 html.escape가 죽어요. 문자열이 아니면 빈 문자열로."""
    return x if isinstance(x, str) else ""


def row_html(i, nm, cd, level, reason):
    nm, cd, level, reason = _s(nm), _s(cd), _s(level), _s(reason)
    lv = {"높음": "h", "중간": "m", "낮음": "l"}.get(level)
    badge = f'<span class="lv {lv}">가능성 {level}</span>' if lv else ""
    why = f'<div class="sub">{html.escape(reason)}</div>' if reason else ""
    return (f'<div class="rk"><span class="rn{" top" if i == 0 else ""}">{i + 1}</span>'
            f'<div><b>{html.escape(nm)}</b>{badge}<div class="sub">{html.escape(cd)}</div>{why}</div></div>')


def disease_search(prefixes=None, depts=()):
    """질환명 전체 검색(희귀질환 포함). 검색어가 없으면 선택한 부위의 질환 목록을 보여줘요."""
    q = st.text_input("질환명 검색", placeholder="예) 협심증, 모야모야병, 루게릭", key="gs_q", label_visibility="collapsed")
    try:
        if q.strip():
            if len(q.strip()) < 2:
                st.caption("두 글자 이상 입력해 주세요.")
                return
            allv = pd.DataFrame(name_search(q.strip()), columns=["질환명", "상병코드"])
            st.caption(f"'{q.strip()}' 검색 결과 {len(allv)}건 (부위와 상관없이 전체에서 찾았어요)")
        elif prefixes:
            allv = pd.DataFrame(icd_list(tuple(prefixes)), columns=["질환명", "상병코드"])
            st.caption(f"선택한 부위의 질환 {len(allv)}건 · 다른 질환은 위에서 이름으로 검색하세요")
        else:
            st.caption("질환 이름의 일부만 입력해도 돼요. 희귀질환도 함께 검색돼요.")
            return
        if allv.empty:
            st.info("검색 결과가 없어요. 다른 표기(띄어쓰기·한자어)로 다시 검색해 보세요.")
            return
        allv = allv.head(500).reset_index(drop=True)
        ev = st.dataframe(allv, hide_index=True, use_container_width=True, height=300,
                          on_select="rerun", selection_mode="single-row", key="allt")
        if ev.selection.rows:
            r = allv.iloc[ev.selection.rows[0]]
            show_detail(r["질환명"], r["상병코드"], depts, tag="s")
    except Exception as e:  # noqa: BLE001
        st.warning(f"질환 목록을 불러오지 못했어요. ({e})")


# ---------------------------------------------------------------
st.markdown('<div class="topbar"><div class="logo">✚</div><div><b>어디가 불편하신가요?</b>'
            '<span>증상 분석 · 질환 통계 · 가까운 병원 찾기</span></div></div>'
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
        with st.expander("🔎 질환 이름으로 바로 찾기 (희귀질환 포함)", expanded=False):
            disease_search()
    else:
        label, prefixes, depts = REGIONS[region]
        st.markdown(f'<div class="panel"><span class="rg">선택한 부위</span><div class="rgn">{label}</div></div>', unsafe_allow_html=True)
        text = st.text_area("어떻게 아픈지 자세히 적어 주세요", height=120,
                            placeholder="예) 어제 저녁부터 왼쪽 가슴이 조이듯 아프고, 계단을 오르면 숨이 차요. 식은땀도 났어요.")
        sev = st.select_slider("불편한 정도", ["약함", "보통", "심함", "견디기 어려움"], value="보통")
        if any(w in text for w in RED):
            st.error("⚠️ 응급 가능성이 있는 표현이 있어요. 지체하지 말고 119에 연락하거나 가까운 응급실로 가세요.")
        if st.button("🔍 분석하기", type="primary", use_container_width=True, disabled=not text.strip()):
            st.session_state.pop("detail", None)
            try:
                st.session_state["res"] = (region, analyze(region, text.strip(), sev, tuple(prefixes), tuple(depts)))
            except Exception as e:  # noqa: BLE001
                st.session_state.pop("res", None)
                st.warning(f"분석하지 못했어요. ({e})")

        res = st.session_state.get("res")
        if res and res[0] == region:
            res = res[1]
            ai, rdepts = res["ai"], res["depts"]
            if res["err"]:
                st.warning("AI 소견을 가져오지 못했어요. " + res["err"])
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
                st.markdown("**관련 질환** &nbsp;<span class='sub'>AI가 심평원 상병 후보 중에서 고른 추정이에요 · 진단이 아니에요</span>",
                            unsafe_allow_html=True)
                if res["pick_err"]:
                    st.caption("⚠️ " + res["pick_err"])
                with st.container(border=True):
                    for i, r in table.iterrows():
                        c1, c3 = st.columns([5, 0.9], vertical_alignment="center")
                        c1.markdown(row_html(i, r["질환명"], r["상병코드"], r["가능성"], r["근거"]), unsafe_allow_html=True)
                        if c3.button("상세", key=f"d_{r['상병코드']}_{i}", use_container_width=True):
                            st.session_state["detail"] = (r["질환명"], r["상병코드"], _s(r["가능성"]), _s(r["근거"]))
                dt = st.session_state.get("detail")
                if dt and dt[1] in set(table["상병코드"]):
                    show_detail(dt[0], dt[1], rdepts, dt[2], dt[3], tag="r")

        with st.expander("📋 질환 전체 목록 · 이름으로 검색 (희귀질환 포함)"):
            disease_search(prefixes, depts)

st.markdown('<div class="note">이 화면은 진단이 아니라 진료과와 병원을 찾기 위한 안내예요. AI 소견과 관련 질환은 입력한 설명을 바탕으로 한 추정이에요. '
            '증상이 계속되거나 심해지면 의료진과 상담하세요.</div>', unsafe_allow_html=True)