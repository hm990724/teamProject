import html
import json
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

from common import bars, donut, env, hira_get, kpis, setup, skel, table_html, topbar, vbars

setup("콕콕")

HIRA_DISEASE = env("HIRA_DISEASE_SERVICE_KEY")
GEMINI = env("GEMINI_API_KEY")
ROOT = Path(__file__).resolve().parent
HOSPITAL_PAGE = "pages/2_hospital_finder.py"
HOSPITAL_FILE = ROOT / "pages" / "2_hospital_finder.py"
DISS = "diseaseInfoService1"
COLS = ["질환명", "상병코드"]
LEVELS = ("높음", "중간", "낮음")
SEVS = ["가벼워요", "보통이에요", "꽤 아파요", "참기 힘들어요"]
SEXES = ["남성", "여성"]

candidates_dir = [ROOT / "body_map", ROOT.parent / "body_map", Path.cwd() / "body_map"]
map_dir = next((p for p in candidates_dir if (p / "index.html").exists()), None)
if map_dir is None:
    st.error("`body_map/index.html` 파일을 찾지 못했어요.")
    st.code(str(candidates_dir[0] / "index.html"))
    st.stop()
body_map = components.declare_component("body_map", path=str(map_dir))

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

ICD_DEPT = {"A": ["내과"], "B": ["내과"], "C": ["내과"], "D": ["내과"], "E": ["내분비내과"], "F": ["정신건강의학과"],
            "G": ["신경과"], "H": ["안과", "이비인후과"], "I": ["순환기내과"], "J": ["호흡기내과"], "K": ["소화기내과"],
            "L": ["피부과"], "M": ["정형외과"], "N": ["비뇨의학과"], "O": ["산부인과"], "P": ["소아청소년과"],
            "Q": ["소아청소년과"], "R": ["가정의학과"], "S": ["정형외과"], "T": ["정형외과"]}

RARE = [("모야모야병", "I675"), ("근위축성 측삭경화증(루게릭병)", "G122"), ("중증 근무력증", "G700"),
        ("다발성 경화증", "G35"), ("헌팅턴병", "G10"), ("낭성 섬유증", "E84"), ("마르팡 증후군", "Q874"),
        ("길랑-바레 증후군", "G610"), ("폰 빌레브란트병", "D680"), ("파브리병", "E752"), ("고셔병", "E752"),
        ("프라더-윌리 증후군", "Q871"), ("레트 증후군", "F842"), ("두센 근이영양증", "G710"),
        ("척수성 근위축증", "G120"), ("베체트병", "M352"), ("타카야수 동맥염", "M314"), ("전신 경화증", "M34"),
        ("유전성 혈관부종", "D841"), ("폐동맥 고혈압", "I270")]

RED = ("의식", "경련", "발작", "호흡곤란", "숨을 못", "숨이 안", "마비", "식은땀", "피를 토", "혈변", "검은 변",
       "시력을 잃", "말이 어눌", "실신", "쓰러")
EMERGENCY = "응급 가능성이 있어요. 지체하지 말고 119에 연락하거나 가까운 응급실로 가세요."


def txt(x):
    return x if isinstance(x, str) else ""


# ───────────────────────── 질환 목록 (심평원) ─────────────────────────
def is_disease(code, name):
    if not code or not name or code[0].upper() in "VWXY":
        return False
    return len(name) <= 60 and "진료를 받은" not in name and "해당상병" not in name


def diss_pages(**extra):
    out, page = [], 1
    while page <= 40:
        items, total, _ = hira_get(f"{DISS}/getDissNameCodeList1",
                                   {"numOfRows": 500, "pageNo": page, "medTp": 1, **extra}, HIRA_DISEASE)
        out += items
        if not items or len(out) >= total:
            break
        page += 1
    return out


def collect(items, accept=lambda code: True):
    out = {}
    for it in items:
        code, name = it.get("sickCd", ""), it.get("sickNm", "").strip()
        if is_disease(code, name) and accept(code):
            out.setdefault(name, code)
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def icd_list(prefixes: tuple):
    if not HIRA_DISEASE:
        raise RuntimeError("HIRA_DISEASE_SERVICE_KEY가 없어요.")
    out = {}
    for pf in prefixes:
        out.update(collect(diss_pages(sickType=2, diseaseType="SICK_CD", searchText=pf), lambda c: c.startswith(pf)))
    for name, code in RARE:
        if any(code.startswith(pf) for pf in prefixes):
            out.setdefault(name, code)
    if not out:
        raise RuntimeError("조회된 질환이 없어요.")
    return sorted(out.items(), key=lambda x: x[1])


@st.cache_data(ttl=3600, show_spinner=False)
def name_search(q: str):
    q = q.strip()
    if not HIRA_DISEASE or len(q) < 2:
        return []
    out, last = {}, None
    for sick_type in (2, 1):
        try:
            for name, code in collect(diss_pages(sickType=sick_type, diseaseType="SICK_NM", searchText=q)).items():
                out.setdefault(name, code)
        except Exception as e:  # noqa: BLE001
            last = e
    for name, code in RARE:
        if q in name:
            out.setdefault(name, code)
    if not out and last:
        raise RuntimeError(str(last))
    return sorted(out.items(), key=lambda x: x[1])


# ───────────────────────── 생성형 모델 호출 ─────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def gemini_models():
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", timeout=15,
                     headers={"x-goog-api-key": GEMINI}, params={"pageSize": 200})
    if r.status_code != 200:
        raise RuntimeError(f"모델 목록 조회 실패 HTTP {r.status_code} {r.text[:200]}")
    names = [m["name"].split("/")[-1] for m in r.json().get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    ok = [n for n in names if "flash" in n and not re.search(r"image|tts|live|audio|thinking|exp|robotics|computer|embedding", n)]
    if not ok:
        raise RuntimeError("쓸 수 있는 flash 모델이 없어요: " + ", ".join(names[:8]))
    return sorted(ok, key=lambda n: ("latest" not in n, [-int(x) for x in (re.findall(r"\d+", n) + ["0", "0"])[:2]],
                                     "preview" in n, "lite" in n))


def call_ai(prompt):
    if not GEMINI:
        raise RuntimeError(".env에 GEMINI_API_KEY가 없어요")
    queue = [m for m in dict.fromkeys([os.getenv("GEMINI_MODEL", "")] + gemini_models()) if m]
    tried, last = [], ""
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
        if r.status_code in (400, 401, 403):
            break
        hint = re.search(r"use models/([\w.\-]+)", r.text)
        if hint and hint.group(1) not in tried:
            queue.insert(0, hint.group(1))
    raise RuntimeError(last + f" (시도한 모델: {', '.join(tried)})")


def parse_json(s):
    """응답에서 첫 번째 JSON 객체만 읽는다 (코드펜스·뒤에 붙은 설명이 있어도 동작)."""
    s = s.strip()
    obj, _ = json.JSONDecoder().raw_decode(s[s.index("{"):])
    return obj


# ───────────────────────── 통계 응답 처리 ─────────────────────────
ENDPOINTS = {"성별·연령별": "getDissByGenderAgeStats1", "입원·외래별": "getDissByHsptlzFrgnStats1",
             "요양기관 종별": "getDissByClassesStats1", "요양기관 지역별": "getDissByAreaStats1"}
TOTAL = {"계", "합계", "전체", "소계", "total", "Total"}
CNT_RE = r"ptnt|patnt|patient"
LABELS = [(r"sex|gender", "성별"), (r"age", "연령"), (r"area|sido|region", "지역"), (r"cl(?!m)|class", "종별"),
          (r"hsptlz|inout|frgn", "구분"), (CNT_RE, "환자 수"), (r"cost|amt|fee|pay", "진료비"), (r"dd|day", "일수"), (r"clm", "청구건수")]


def label_of(col):
    return next((ko for pat, ko in LABELS if re.search(pat, col, re.I)), col)


def fetch_rows(endpoint, code):
    note, raw = "자료 없음", ""
    for year in (date.today().year - 1, date.today().year - 2):
        for sick_cd in dict.fromkeys([code, code.replace(".", "").upper()]):
            try:
                rows, _, raw = hira_get(f"{DISS}/{endpoint}", {"numOfRows": 500, "pageNo": 1, "sickType": 2, "medTp": 1,
                                                               "sickCd": sick_cd, "year": year}, HIRA_DISEASE, 12)
            except Exception as e:  # noqa: BLE001
                note, raw = f"조회 오류: {str(e)[:80]}", str(e)
                continue
            if rows:
                return rows, year, "", raw
            note = f"{year}년 자료가 없어요."
    return [], None, note, raw


@st.cache_data(ttl=86400, show_spinner=False)
def disease_stats(code):
    if not HIRA_DISEASE:
        return {k: {"rows": [], "year": None, "note": "HIRA_DISEASE_SERVICE_KEY가 없어요.", "raw": ""} for k in ENDPOINTS}
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda ep: fetch_rows(ep, code), ENDPOINTS.values()))
    return {k: dict(zip(("rows", "year", "note", "raw"), r)) for k, r in zip(ENDPOINTS, res)}


def to_num(s):
    return pd.to_numeric(s.astype(str).str.replace(",", ""), errors="coerce")


def tidy(rows):
    df = pd.DataFrame(rows)
    meas = [c for c in df.columns if re.search(CNT_RE + r"|cnt|amt|cost|dd|day|clm|fee|pay", c, re.I) and to_num(df[c]).notna().all()]
    cats = [c for c in df.columns if c not in meas and df[c].astype(str).nunique() > 1 and not re.search(r"year|yy|ym", c, re.I)]
    cats = [c for c in cats if not (c.endswith("Cd") and c[:-2] + "Nm" in cats)]
    for c in meas:
        df[c] = to_num(df[c])
    return df, meas, cats


def patient_field(meas):
    return next((c for c in meas if re.search(CNT_RE, c, re.I)), None)


def verify(rows):
    """'계' 행과 세부 항목 합계를 비교해 환자 수를 검산한다."""
    if not rows:
        return None
    df, meas, cats = tidy(rows)
    f = patient_field(meas)
    if f is None:
        return {"error": "응답에서 환자 수 항목을 못 찾았어요. 항목: " + ", ".join(df.columns)}
    if not cats:
        return {"total": float(df[f].sum()), "status": "part", "parts": None, "diff": None}
    is_tot = df[cats].astype(str).isin(TOTAL)
    t = df.loc[is_tot.all(axis=1), f]
    p = df.loc[~is_tot.any(axis=1), f]
    s = float(p.sum()) if len(p) else None
    if len(t) and s is not None:
        tv = float(t.iloc[0])
        diff = abs(tv - s) / tv * 100 if tv else None
        return {"total": tv, "parts": s, "diff": diff, "status": "ok" if diff is not None and diff <= 0.5 else "diff"}
    if len(t):
        return {"total": float(t.iloc[0]), "parts": None, "diff": None, "status": "total"}
    return {"total": s, "parts": s, "diff": None, "status": "part"}


def parse_band(s):
    nums = [int(x) for x in re.findall(r"\d+", str(s))]
    if not nums:
        return None
    hi = 200 if re.search(r"이상|over|\+", str(s), re.I) else (nums[1] if len(nums) > 1 else nums[0])
    return nums[0], hi


def short_age(s):
    p = parse_band(s)
    if not p:
        return str(s)
    lo, hi = p
    if hi >= 200:
        return f"{lo}+"
    if lo == 0 and hi == 9:
        return "0~9세"
    return f"{lo}대" if (hi - lo == 9 and lo % 10 == 0) else (f"{lo}세" if lo == hi else f"{lo}~{hi}")


def profile(rows):
    """성별·연령별 응답 → 연령 구간별/성별 환자 수"""
    if not rows:
        return None
    df, meas, cats = tidy(rows)
    f = patient_field(meas)
    if f is None or not cats:
        return None
    base = df[~df[cats].astype(str).isin(TOTAL).any(axis=1)]
    if base.empty:
        return None
    age_c = next((c for c in cats if base[c].astype(str).map(lambda s: parse_band(s) is not None).mean() > 0.8), None)
    sex_c = next((c for c in cats if c != age_c and base[c].astype(str).str.contains("남|여").mean() > 0.8), None)
    out = {"f": f, "age_c": age_c, "sex_c": sex_c, "cats": cats, "base": base}
    if age_c:
        ages = base.groupby(age_c, sort=False)[f].sum()
        out["ages"] = ages.reindex(sorted(ages.index, key=lambda s: parse_band(str(s))[0]))
    if sex_c:
        out["sex"] = base.groupby(sex_c, sort=False)[f].sum()
    return out


def fit(prof, age, sex):
    """내 연령대·성별이 이 질환 환자 중 얼마나 차지하는지 (환자 수 기준, 인구 보정 아님)"""
    if not prof or "ages" not in prof or prof["ages"].sum() <= 0:
        return None
    ages = prof["ages"]
    tot = float(ages.sum())
    res = {"peak": ages.idxmax(), "peak_share": float(ages.max()) / tot * 100, "n": len(ages)}
    if age is not None:
        mine = next((b for b in ages.index if (p := parse_band(str(b))) and p[0] <= age <= p[1]), None)
        if mine is not None:
            res.update(mine=mine, share=float(ages[mine]) / tot * 100, rank=int((ages > ages[mine]).sum()) + 1)
    if sex and "sex" in prof and prof["sex"].sum() > 0:
        key = next((k for k in prof["sex"].index if sex[0] in str(k)), None)
        if key is not None:
            res["sex_share"] = float(prof["sex"][key]) / float(prof["sex"].sum()) * 100
    return res


def fit_text(fi, sex=None):
    if not fi:
        return ""
    parts = []
    if "mine" in fi:
        parts.append(f"내 연령대({short_age(fi['mine'])}) 비중 {fi['share']:.1f}% · {fi['n']}개 중 {fi['rank']}위")
    else:
        parts.append(f"가장 많은 연령대 {short_age(fi['peak'])}({fi['peak_share']:.0f}%)")
    if "sex_share" in fi and sex:
        parts.append(f"{sex} {fi['sex_share']:.0f}%")
    return " · ".join(parts)


_GS = {}


def gs_fit(code, age, sex):
    """후보 질환의 성별·연령 분포를 가져와 내 조건과 비교 (모듈 단위 캐시)"""
    if code not in _GS:
        try:
            rows, *_ = fetch_rows(ENDPOINTS["성별·연령별"], code)
            _GS[code] = profile(rows)
        except Exception:  # noqa: BLE001
            _GS[code] = None
    return fit(_GS[code], age, sex)


# ───────────────────────── 분석 파이프라인 ─────────────────────────
def candidates(df, kws, limit=40):
    names, n = df["질환명"], len(df)
    score = pd.Series(0.0, index=df.index)
    for k, w in kws.items():
        hit = names.str.contains(k, regex=False)
        if hit.any():
            score = score + hit.astype(float) * w * (math.log((n + 1) / (int(hit.sum()) + 1)) + 1)
    out = df.assign(점수=score)
    out = out[out["점수"] > 0].assign(길이=lambda x: x["질환명"].str.len())
    return out.sort_values(["점수", "길이"], ascending=[False, True]).head(limit).drop(columns="길이").reset_index(drop=True)


def overview(ctx):
    prompt = (ctx + "\n아래 JSON 객체로만 답하세요. "
              '{"opinion":"환자 표현과 나이·성별을 근거로 한 종합 소견 3~4문장","emergency":true,"depts":["진료과"],'
              '"keywords":["질환명에 들어갈 법한 한글 단어(예: 협심증, 추간판, 모야모야)"],"advice":"생활 안내 한 문장"}. '
              "depts는 최대 3개, keywords는 최대 10개. 흔한 질환뿐 아니라 증상과 맞는 희귀질환 이름도 일부 포함하세요. "
              "응급 가능성이 있으면 emergency를 true로. 진단이 아니라 병원을 찾기 위한 참고용이라는 점을 소견에 반영하세요.")
    return parse_json(call_ai(prompt))


def rank(ctx, opinion, cand, hints):
    lst = "\n".join(f"{c}|{n}" + (f"|{hints[c]}" if hints.get(c) else "") for n, c in zip(cand["질환명"], cand["상병코드"]))
    prompt = (f"{ctx}앞선 종합 소견: {opinion or '없음'}\n\n후보 질환 목록(상병코드|질환명|건강보험 환자 분포 참고):\n{lst}\n\n"
              "위 목록 안에서만 환자 설명과 가장 잘 맞는 질환을 가능성이 높은 순서로 최대 6개 고르세요. "
              "증상 설명이 1순위 근거이고, 환자 분포는 나이·성별이 비슷한 환자가 얼마나 많은지 보는 보조 근거예요(인구 보정 전 수치). "
              "목록에 없는 질환이나 코드는 절대 쓰지 마세요. 설명과 맞지 않으면 적게 골라도 됩니다. "
              '아래 JSON 객체로만 답하세요. {"picks":[{"code":"목록의 상병코드 그대로","level":"높음|중간|낮음",'
              '"reason":"환자 표현(필요하면 나이·성별 분포)을 근거로 한 한 문장"}]}. 진단이 아니라 참고용입니다.')
    by_code = dict(zip(cand["상병코드"], cand["질환명"]))
    rows, seen = [], set()
    for p in parse_json(call_ai(prompt)).get("picks", []):
        code = str(p.get("code", "")).strip()
        if code in by_code and code not in seen:
            seen.add(code)
            level = p.get("level")
            rows.append({"질환명": by_code[code], "상병코드": code, "가능성": level if level in LEVELS else "",
                         "근거": str(p.get("reason", ""))[:200]})
    return pd.DataFrame(rows[:6])


@st.cache_data(ttl=1800, show_spinner=False)
def analyze(region, text, sev, age, sex, prefixes, depts):
    df = pd.DataFrame(icd_list(prefixes), columns=COLS)
    pool = len(df)
    who = (f"{age}세 " if age is not None else "") + (sex or "")
    ctx = (f"불편한 부위: {REGIONS[region][0]}\n불편한 정도: {sev}\n"
           + (f"환자: {who.strip()}\n" if who.strip() else "") + f"환자가 직접 쓴 설명: {text}\n")
    ai, err, pick_err = {}, "", ""
    try:
        ai = overview(ctx)
    except Exception as e:  # noqa: BLE001
        err = str(e)[:250]

    ai_kws = [k for k in ai.get("keywords", []) if isinstance(k, str)]
    kws = {}

    def add(k, w):
        k = k.strip()
        if len(k) >= 2:
            kws[k] = max(kws.get(k, 0), w)

    for k in ai_kws:
        add(k, 2.0)
    for word in re.findall(r"[가-힣]{2,}", text):
        add(word, 0.5)
        if len(word) >= 3:
            add(word[:2], 0.5)

    extra = []
    for k in ai_kws[:6]:
        try:
            extra += name_search(k)
        except Exception:  # noqa: BLE001
            pass
    if extra:
        df = pd.concat([df, pd.DataFrame(extra, columns=COLS)]).drop_duplicates("상병코드").reset_index(drop=True)
    cand = candidates(df, kws)
    names = df["질환명"]
    kw_hit = sorted(((k, int(names.str.contains(k, regex=False).sum())) for k in kws), key=lambda t: (-kws[t[0]], -t[1]))
    kw_hit = [t for t in kw_hit if t[1] > 0][:8]

    # 나이·성별을 반영한 환자 분포 (상위 후보 10개)
    fits = {}
    if (age is not None or sex) and not cand.empty:
        top_codes = list(cand["상병코드"].head(10))
        with ThreadPoolExecutor(5) as ex:
            for c, fi in zip(top_codes, ex.map(lambda c: gs_fit(c, age, sex), top_codes)):
                if fi:
                    fits[c] = fi
    hints = {c: fit_text(fi, sex) for c, fi in fits.items()}

    table = cand.head(6).assign(가능성="", 근거="")
    ranked = False
    if not GEMINI:
        pick_err = "GEMINI_API_KEY가 없어서 키워드 순서로만 보여드려요."
    elif not cand.empty:
        try:
            picked = rank(ctx, ai.get("opinion"), cand, hints)
            if picked.empty:
                pick_err = "후보 안에서 고른 질환이 없어서 키워드 순서로 보여드려요."
            else:
                table, ranked = picked, True
        except Exception as e:  # noqa: BLE001
            pick_err = str(e)[:250]
    table = table.reset_index(drop=True)
    table["일치어"] = table["질환명"].map(lambda n: sorted([k for k in kws if k in n], key=lambda k: -kws[k])[:4])
    table["연령"] = table["상병코드"].map(lambda c: hints.get(c, ""))
    meta = {"pool": pool, "pool_all": len(df), "kw_total": len(kws), "kw_ai": len(ai_kws), "kw_hit": kw_hit,
            "cand": len(cand), "ranked": ranked, "ai_ok": bool(ai), "fit_n": len(fits), "age": age, "sex": sex}
    return {"ai": ai, "err": err, "pick_err": pick_err, "table": table, "meta": meta,
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


# ───────────────────────── 화면 조각 ─────────────────────────
def go(name, code, depts=()):
    if not HOSPITAL_FILE.exists():
        st.error("`pages/2_hospital_finder.py` 파일이 없어요. 병원 화면 파일을 pages/ 폴더에 넣어 주세요.")
        return
    st.session_state["pick_disease"] = {"n": name, "c": code, "depts": list(depts) or ICD_DEPT.get(code[:1].upper(), ["내과"])}
    st.switch_page(HOSPITAL_PAGE)


def show_age_sex(info, age, sex):
    prof = profile(info["rows"])
    if not prof or "ages" not in prof:
        return False
    fi = fit(prof, age, sex)
    ages = prof["ages"]
    mine = fi.get("mine") if fi else None
    msg = f"환자가 가장 많은 연령대는 {short_age(fi['peak'])}(전체의 {fi['peak_share']:.1f}%)예요."
    if fi and "mine" in fi:
        msg += f" 입력하신 연령대({short_age(mine)})는 {fi['share']:.1f}%로 {fi['n']}개 구간 중 {fi['rank']}위예요."
    if fi and "sex_share" in fi:
        msg += f" 성별로는 {sex}이 {fi['sex_share']:.0f}%예요."
    st.markdown(f'<div class="insight">{html.escape(msg)}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.7, 1], gap="medium")
    c1.markdown('<div class="chart"><div class="ct">연령대별 환자 비중</div><div class="cs">전체 환자 중 각 연령대가 차지하는 비율</div>'
                + vbars([(short_age(b), v, b) for b, v in ages.items()], mine=mine) + "</div>", unsafe_allow_html=True)
    if "sex" in prof:
        c2.markdown('<div class="chart"><div class="ct">성별 비중</div><div class="cs">전체 환자 기준</div>'
                    + donut(list(prof["sex"].items())) + "</div>", unsafe_allow_html=True)
    return True


def show_stat(label, info, age=None, sex=None):
    rows = info["rows"]
    if not rows:
        st.caption(f"{label} 자료를 가져오지 못했어요. ({info['note']})")
        if info["raw"]:
            with st.expander("API 응답 확인"):
                st.code(info["raw"])
        return
    df, meas, cats = tidy(rows)
    f = patient_field(meas)
    drawn = False
    if label == "성별·연령별":
        drawn = show_age_sex(info, age, sex)
    elif f and cats:
        base = df[~df[cats].astype(str).isin(TOTAL).any(axis=1)]
        if not base.empty:
            s = base.groupby(base[cats].astype(str).agg(" · ".join, axis=1), sort=False)[f].sum()
            if label == "요양기관 지역별":
                s = s.sort_values(ascending=False).head(10)
            st.markdown(f'<div class="chart"><div class="ct">{html.escape(label)} 환자 수</div>'
                        f'<div class="cs">가장 많은 항목이 진하게 표시돼요</div>' + bars(list(s.items()), top=True) + "</div>",
                        unsafe_allow_html=True)
            drawn = True
    if not drawn:
        st.caption("차트로 그릴 수 있는 환자 수 항목이 없어서 표로 보여드려요.")
    with st.expander("원본 표 보기"):
        names, used = {}, set()
        for c in cats + meas:
            n = label_of(c)
            if n in used:  # 같은 한글명이 겹치면 원래 이름을 덧붙여 구분
                n = f"{n}({c})"
            used.add(n)
            names[c] = n
        show = df[cats + meas].rename(columns=names)
        show = show.loc[:, ~show.columns.duplicated()]
        st.markdown(table_html(show, scroll=True), unsafe_allow_html=True)
    st.caption(f"{info['year']}년 · 건강보험 · 주상병 기준 · 출처: 건강보험심사평가원 질병정보서비스 · 환자 수 기준이며 인구 대비 비율이 아니에요.")


def show_detail(name, code, depts, level=None, reason=None, tag="a"):
    age, sex = st.session_state.get("age_in"), st.session_state.get("sex_in")
    age = int(age) if age is not None else None
    with st.container(border=True):
        st.markdown(f"#### {name} · `{code}`")
        if level or reason:
            st.caption(f"{('가능성 ' + level) if level else ''} {('· ' + reason) if reason else ''}")
        # 통계 영역에서 오류가 나도 버튼이 사라지지 않도록 맨 위에 둔다
        if st.button("가까운 병원 보기", type="primary", use_container_width=True, key=f"go_{tag}_{code}"):
            go(name, code, depts)
        ph = st.empty()
        ph.markdown(skel(2), unsafe_allow_html=True)
        try:
            stats = disease_stats(code)
        except Exception as e:  # noqa: BLE001
            ph.empty()
            st.warning(f"통계를 불러오지 못했어요. ({str(e)[:120]})")
            return
        ph.empty()
        info = stats["성별·연령별"]
        try:
            v = verify(info["rows"])
        except Exception as e:  # noqa: BLE001
            v = {"error": f"환자 수를 계산하지 못했어요. ({str(e)[:80]})"}
        if v and v.get("total") is not None:
            tag_ = {"ok": ("검산 일치", "ok"), "diff": ("검산 불일치", "warn"), "total": ("계 행 기준", "ok"), "part": ("합산값", "warn")}[v["status"]]
            sub = ""
            if v.get("parts") is not None and v.get("diff") is not None:
                sub = f"세부 합계 {v['parts']:,.0f}명 · 계 {v['total']:,.0f}명 · 차이 {v['diff']:.2f}%"
            elif v["status"] == "part":
                sub = "'계' 행이 없어 세부 구간을 합산했어요. 연령 이동으로 일부 중복될 수 있어요."
            st.markdown(kpis([(f"{info['year']}년 진료 환자 수 (건강보험)",
                               f'{v["total"]:,.0f}명<span class="vf {tag_[1]}">{tag_[0]}</span>', sub)]), unsafe_allow_html=True)
        elif v and v.get("error"):
            st.caption(v["error"])
        else:
            st.caption(f"환자 수를 가져오지 못했어요. ({info['note']})")
        st.markdown('<div class="sec" style="margin-top:8px">통계</div>', unsafe_allow_html=True)
        for tab, key in zip(st.tabs(list(ENDPOINTS)), ENDPOINTS):
            with tab:
                try:
                    show_stat(key, stats[key], age, sex)
                except Exception as e:  # noqa: BLE001
                    st.warning(f"{key} 통계를 표시하지 못했어요. ({str(e)[:100]})")
        st.caption("건강보험 청구 자료라 진단·진료 현황만 있고, 완치·회복 여부 같은 치료 결과는 이 자료에 없어요.")
        extract, url = wiki_summary(name)
        if extract:
            st.markdown('<div class="sec" style="margin-top:8px">개요</div>', unsafe_allow_html=True)
            st.write(extract)
            st.caption(f"출처: [위키백과]({url}) · 일반 정보이며 진단·치료를 대신하지 않아요.")


def row_html(i, name, code, level, reason, kws, agetxt):
    name, code, level, reason, agetxt = txt(name), txt(code), txt(level), txt(reason), txt(agetxt)
    cls = {"높음": "h", "중간": "m", "낮음": "l"}.get(level)
    badge = f'<span class="lv {cls}">가능성 {level}</span>' if cls else ""
    why = f'<div class="sub">{html.escape(reason)}</div>' if reason else ""
    chips = "".join(f'<span class="chip g">{html.escape(k)}</span>' for k in (kws if isinstance(kws, list) else []))
    ag = f'<div class="sub" style="color:#1B64DA;font-weight:600;margin-top:2px">{html.escape(agetxt)}</div>' if agetxt else ""
    return (f'<div class="rk" style="--i:{i}"><span class="rn{" top" if i == 0 else ""}">{i + 1}</span>'
            f'<div style="min-width:0"><b>{html.escape(name)}</b>{badge}<div class="sub">{html.escape(code)}</div>{why}{ag}'
            f'<div style="margin-top:6px">{chips}</div></div></div>')


def explain(res, region):
    m, label, prefixes = res["meta"], REGIONS[region][0], REGIONS[region][1]
    who = ", ".join(x for x in [f"{m['age']}세" if m["age"] is not None else "", m["sex"] or ""] if x)
    steps = [
        ("부위로 범위 좁히기", f"'{label}'은 상병 분류 {', '.join(prefixes)} 계열로 보고, 질환 {m['pool']:,}건을 후보 풀로 잡았어요."),
        ("설명에서 단어 뽑기", f"AI가 제안한 질환명 단어 {m['kw_ai']}개와 직접 쓰신 단어를 합쳐 {m['kw_total']}개를 썼어요."),
        ("질환명과 맞춰 점수 매기기", f"흔하지 않은 단어가 맞을수록 높은 점수를 줘서 후보 {m['cand']}건을 추렸어요(풀 {m['pool_all']:,}건)."),
        ("나이·성별 반영", (f"입력하신 {who} 기준으로 상위 후보 {m['fit_n']}건의 환자 분포를 비교해 참고 자료로 넘겼어요."
                          if who and m["fit_n"] else "나이·성별을 입력하지 않았거나 통계를 가져오지 못해 이 단계는 건너뛰었어요.")),
        ("최종 선택", ("AI가 후보 안에서만 최대 6개를 골랐어요. 가능성은 설명과 얼마나 잘 맞는지에 대한 상대적 판단이며 확률이 아니에요."
                    if m["ranked"] else "AI 선택을 쓰지 못해서 점수 순서로 보여드렸어요.")),
    ]
    flow = "".join(f'<div class="rk" style="--i:{i}"><span class="rn">{i + 1}</span><div><b>{t}</b><div class="sub">{html.escape(d)}</div></div></div>'
                   for i, (t, d) in enumerate(steps))
    with st.expander("이 결과가 나온 과정", expanded=False):
        st.markdown(kpis([("후보 풀", f"{m['pool_all']:,}건"), ("추린 후보", f"{m['cand']}건"),
                          ("환자 분포 반영", f"{m['fit_n']}건"), ("최종 표시", f"{len(res['table'])}건")]), unsafe_allow_html=True)
        st.markdown(flow, unsafe_allow_html=True)
        if m["kw_hit"]:
            st.markdown('<div class="chart" style="margin-top:12px"><div class="ct">많이 맞은 단어</div>'
                        '<div class="cs">질환명에 해당 단어가 들어간 질환 수</div>' + bars(m["kw_hit"], unit="건", share=False) + "</div>",
                        unsafe_allow_html=True)
        st.caption("환자 분포는 건강보험 청구 환자 수 기준이라 인구 대비 비율이 아니에요. 나이·성별은 보조 단서로만 쓰여요.")


def disease_search(prefixes=None, depts=()):
    q = st.text_input("질환명 검색", placeholder="예) 협심증, 모야모야병, 루게릭", key="gs_q", label_visibility="collapsed").strip()
    try:
        if q:
            if len(q) < 2:
                st.caption("두 글자 이상 입력해 주세요.")
                return
            found = pd.DataFrame(name_search(q), columns=COLS)
            st.caption(f"'{q}' 검색 결과 {len(found)}건 (부위와 상관없이 전체에서 찾았어요)")
        elif prefixes:
            found = pd.DataFrame(icd_list(tuple(prefixes)), columns=COLS)
            st.caption(f"선택한 부위의 질환 {len(found)}건 · 다른 질환은 위에서 이름으로 검색하세요")
        else:
            st.caption("질환 이름의 일부만 입력해도 돼요. 희귀질환도 함께 검색돼요.")
            return
        if found.empty:
            st.info("검색 결과가 없어요. 다른 표기(띄어쓰기·한자어)로 다시 검색해 보세요.")
            return
        found = found.head(500).reset_index(drop=True)
        opts = [f"{n}  ({c})" for n, c in zip(found["질환명"], found["상병코드"])]
        sel = st.selectbox("질환 선택", opts, index=None, placeholder="목록에서 고르거나 입력해서 찾기", key="gs_pick")
        if sel:
            r = found.iloc[opts.index(sel)]
            show_detail(r["질환명"], r["상병코드"], depts, tag="s")
        with st.expander("목록 전체 보기"):
            st.markdown(table_html(found, scroll=True), unsafe_allow_html=True)
    except Exception as e:  # noqa: BLE001
        st.warning(f"질환 목록을 불러오지 못했어요. ({e})")


def show_result(res, region):
    ai, depts, table = res["ai"], res["depts"], res["table"]
    if res["err"]:
        st.warning("종합 소견을 가져오지 못했어요. " + res["err"])
    if ai.get("emergency"):
        st.error(EMERGENCY)
    if ai.get("opinion"):
        st.markdown('<div class="sec" style="margin-top:6px">증상 요약</div>', unsafe_allow_html=True)
        body = html.escape(ai["opinion"]) + (f'<br><br><span style="color:#6B7684">{html.escape(ai["advice"])}</span>' if ai.get("advice") else "")
        st.markdown(f'<div class="panel" style="line-height:1.7">{body}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec" style="margin-top:6px">추천 진료과</div>' + "".join(f'<span class="chip">{html.escape(d)}</span>' for d in depts),
                unsafe_allow_html=True)
    if table.empty:
        st.info("입력한 증상과 맞는 질환명을 찾지 못했어요. 증상을 더 자세히 적어 보세요.")
        return
    st.markdown('<div class="sec">관련 질환 후보</div><div class="sub" style="margin:-8px 0 10px">입력하신 설명과 심평원 상병 목록을 맞춰 본 추정이에요. 진단이 아니에요.</div>',
                unsafe_allow_html=True)
    if res["pick_err"]:
        st.caption(res["pick_err"])
    with st.container(border=True):
        for i, r in table.iterrows():
            c1, c2 = st.columns([5, 1], vertical_alignment="center")
            c1.markdown(row_html(i, r["질환명"], r["상병코드"], r["가능성"], r["근거"], r["일치어"], r["연령"]), unsafe_allow_html=True)
            if c2.button("상세", key=f"d_{r['상병코드']}_{i}", use_container_width=True):
                st.session_state["detail"] = (r["질환명"], r["상병코드"], txt(r["가능성"]), txt(r["근거"]))
    explain(res, region)
    detail = st.session_state.get("detail")
    if detail and detail[1] in set(table["상병코드"]):
        show_detail(detail[0], detail[1], depts, detail[2], detail[3], tag="r")


# ───────────────────────── 페이지 ─────────────────────────
topbar("콕콕", "증상 분석 · 질환 통계 · 가까운 병원 찾기")
st.markdown('<div class="steps"><span><b>1</b>부위 선택</span><span><b>2</b>증상 입력</span><span><b>3</b>질환 확인</span><span><b>4</b>병원 찾기</span></div>',
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
                    '<span class="sub">왼쪽 몸 그림에서 앞면·뒷면을 바꿔 가며 고를 수 있어요.</span></div>', unsafe_allow_html=True)
        if st.button("병원 바로 찾기", use_container_width=True):
            st.switch_page(HOSPITAL_PAGE)
        with st.expander("질환 이름으로 바로 찾기 (희귀질환 포함)"):
            disease_search()
    else:
        label, prefixes, depts = REGIONS[region]
        busy = st.session_state.get("job") is not None
        st.markdown(f'<div class="panel"><span class="rg">선택한 부위</span><div class="rgn">{label}</div></div>', unsafe_allow_html=True)
        text = st.text_area("어떻게 아픈지 자세히 적어 주세요", height=120, key="symptom", disabled=busy,
                            placeholder="예) 어제 저녁부터 왼쪽 가슴이 조이듯 아프고, 계단을 오르면 숨이 차요. 식은땀도 났어요.")
        a, s_ = st.columns(2)
        age_v = a.number_input("나이 (선택)", min_value=0, max_value=120, value=None, step=1, key="age_in", disabled=busy, placeholder="예) 34")
        sex_v = s_.segmented_control("성별 (선택)", SEXES, key="sex_in", disabled=busy)
        sev = st.segmented_control("불편한 정도", SEVS, default=SEVS[1], key="sev_in", disabled=busy) or SEVS[1]
        if any(w in text for w in RED):
            st.error(EMERGENCY)
        clicked = st.button("분석 중이에요" if busy else "분석하기", type="primary", use_container_width=True,
                            key="run_busy" if busy else "run_idle", disabled=busy or not text.strip())
        if clicked:
            st.session_state["job"] = (region, text.strip(), sev, int(age_v) if age_v is not None else None, sex_v)
            st.session_state.pop("detail", None)
            st.rerun()
        if busy:
            st.markdown(skel(3), unsafe_allow_html=True)
            j = st.session_state["job"]
            try:
                st.session_state["res"] = (j[0], analyze(j[0], j[1], j[2], j[3], j[4], tuple(REGIONS[j[0]][1]), tuple(REGIONS[j[0]][2])))
                st.session_state.pop("res_err", None)
            except Exception as e:  # noqa: BLE001
                st.session_state.pop("res", None)
                st.session_state["res_err"] = str(e)
            finally:
                st.session_state["job"] = None
            st.rerun()
        if st.session_state.get("res_err"):
            st.warning(f"분석하지 못했어요. ({st.session_state['res_err']})")
        res = st.session_state.get("res")
        if res and res[0] == region:
            show_result(res[1], region)
        with st.expander("질환 전체 목록 · 이름으로 검색 (희귀질환 포함)"):
            disease_search(prefixes, depts)

st.markdown('<div class="note">이 화면은 진단이 아니라 진료과와 병원을 찾기 위한 안내예요. 관련 질환은 입력한 설명과 나이·성별을 바탕으로 한 추정이에요. '
            '증상이 계속되거나 심해지면 의료진과 상담하세요.</div>', unsafe_allow_html=True)