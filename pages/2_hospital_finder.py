"""병원 찾기 — 진단된 질환·추천 진료과 기준으로 내 주변 병원을 지도와 거리순으로 보여줘요."""
import html
import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, unquote

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

try:
    from streamlit_js_eval import get_geolocation
except Exception:  # noqa: BLE001
    get_geolocation = None

load_dotenv()
st.set_page_config(page_title="병원 찾기", page_icon="🏥", layout="wide", initial_sidebar_state="collapsed")


def env(n):
    v = (os.getenv(n) or "").strip().strip('"').strip("'").strip()
    return unquote(v) if "%" in v else (v or None)


KAKAO, HIRA = env("KAKAO_REST_API_KEY"), env("HIRA_SERVICE_KEY")
UA = {"User-Agent": "hospital-finder/1.0"}
DEFAULT_LOC = {"lat": 37.5665, "lng": 126.9780, "label": "서울시청 (기본 위치)"}

st.markdown("""<style>
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css");
html,body,.stApp,[class*="css"]{font-family:"Pretendard","Malgun Gothic",sans-serif!important;color:#0F2A43}
.stApp{background:#F4F8FC}.block-container{max-width:1280px;padding-top:1rem}
#MainMenu,footer{visibility:hidden}header[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebarNav"],[data-testid="collapsedControl"],[data-testid="stSidebar"]{display:none}
.topbar{display:flex;align-items:center;gap:12px;background:#fff;border:1px solid #DCE6F1;border-radius:16px;padding:14px 20px;margin-bottom:14px;box-shadow:0 2px 10px rgba(27,111,224,.06)}
.logo{width:38px;height:38px;border-radius:11px;background:#1B6FE0;color:#fff;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:800}
.topbar b{font-size:1.1rem}.topbar span{color:#5E7186;font-size:.86rem;margin-left:8px}
.chip{display:inline-block;padding:4px 12px;border-radius:999px;font-size:.82rem;font-weight:600;background:#E8F1FD;color:#1B6FE0;margin:0 6px 6px 0}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:6px 0 12px}
.kpi{background:#fff;border:1px solid #DCE6F1;border-radius:14px;padding:12px 14px}
.kpi .k{font-size:.74rem;color:#5E7186;font-weight:600}.kpi .n{font-size:1.2rem;font-weight:800;margin-top:2px}
.hc{background:#fff;border:1px solid #DCE6F1;border-radius:14px;padding:14px 16px;margin-bottom:10px;box-shadow:0 1px 6px rgba(15,42,67,.04)}
.hc-top{display:flex;gap:12px;align-items:flex-start}
.badge{flex:0 0 32px;height:32px;border-radius:10px;background:#0F2A43;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.9rem}
.badge.top{background:#1B6FE0}
.hc-name{font-weight:700;line-height:1.35}.hc-meta{font-size:.82rem;color:#5E7186;margin-top:3px}
.tag{display:inline-block;font-size:.72rem;font-weight:700;padding:2px 9px;border-radius:999px;margin-right:6px;color:#fff}
.hc-dist{margin-left:auto;text-align:right;font-weight:800;white-space:nowrap}.hc-dist small{display:block;font-weight:500;color:#5E7186;font-size:.72rem}
.links{margin-top:9px;display:flex;gap:8px;flex-wrap:wrap}
.links a{font-size:.8rem;font-weight:600;color:#1B6FE0;text-decoration:none;border:1px solid #DCE6F1;padding:4px 11px;border-radius:999px}
.empty{background:#fff;border:1px dashed #BFD0E3;border-radius:14px;padding:26px;text-align:center;color:#5E7186;line-height:1.7}
.stButton>button{border-radius:12px}
@media(max-width:760px){.kpis{grid-template-columns:1fr}}
</style>""", unsafe_allow_html=True)

# 진료과 → 심평원 진료과목 코드(dgsbjtCd)
DEPT = {"내과": "01", "신경과": "02", "정신건강의학과": "03", "외과": "04", "정형외과": "05", "신경외과": "06", "흉부외과": "07",
        "성형외과": "08", "마취통증의학과": "09", "산부인과": "10", "소아청소년과": "11", "안과": "12", "이비인후과": "13",
        "피부과": "14", "비뇨의학과": "15", "영상의학과": "16", "재활의학과": "21", "가정의학과": "23", "응급의학과": "24"}
# 종별 코드 → (이름, 정렬용 값(미사용), 색)
CL = {"01": ("상급종합", 40, "#1B6FE0"), "11": ("종합병원", 30, "#0E9F8E"), "21": ("병원", 20, "#F59E0B"), "31": ("의원", 10, "#8B5CF6")}
PHARM = ("약국", 0, "#EC4899")
UNKNOWN = ("종별 미상", 0, "#94A3B8")  # 카카오 데이터처럼 종별 정보가 없는 경우


def dept_code(name):
    if name in DEPT:
        return DEPT[name]
    return "01" if name.endswith("내과") else "04" if name.endswith("외과") else None


def hav(a, b, c, d):
    p1, p2 = math.radians(a), math.radians(c)
    x = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))


def dept_ok(name, depts):
    """병원 이름에 '선택하지 않은 다른 진료과'가 들어 있으면 제외 (예: 이비인후과 선택 → ○○정형외과 제외)"""
    allowed = set(depts)
    if any(x.endswith("내과") for x in depts):
        allowed.add("내과")
    if any(x.endswith("외과") for x in depts):
        allowed.add("외과")
    found = [s for s in DEPT if s in name]
    found = [s for s in found if not any(s != o and s in o for o in found)]  # '정형외과' 안의 '외과' 같은 중복 제거
    return not found or any(s in allowed for s in found)


@st.cache_data(ttl=3600, show_spinner=False)
def place_search(q):
    out = []
    if KAKAO:
        h = {"Authorization": f"KakaoAK {KAKAO}"}
        for ep in ("address", "keyword"):
            try:
                r = requests.get(f"https://dapi.kakao.com/v2/local/search/{ep}.json", headers=h, params={"query": q, "size": 5}, timeout=8)
                for d in r.json().get("documents", []):
                    lb = d.get("place_name") or d.get("address_name")
                    sub = d.get("address_name", "")
                    out.append({"label": f"{lb} · {sub}" if d.get("place_name") else lb, "lat": float(d["y"]), "lng": float(d["x"])})
            except Exception:  # noqa: BLE001
                continue
    if not out and len(q) >= 3:
        try:
            r = requests.get("https://nominatim.openstreetmap.org/search", headers=UA, timeout=8,
                             params={"q": q, "format": "json", "limit": 5, "accept-language": "ko"})
            out = [{"label": d["display_name"][:70], "lat": float(d["lat"]), "lng": float(d["lon"])} for d in r.json()]
        except Exception:  # noqa: BLE001
            pass
    return out


HIRA_URL = "https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"


def hira_one(lat, lng, radius_km, cl, dc):
    """심평원 병원정보서비스 1건(종별 × 진료과목) 조회. 서버가 느리면 한 번 더 시도하고, 그래도 안 되면 예외."""
    p = {"serviceKey": HIRA, "xPos": lng, "yPos": lat, "radius": int(radius_km * 1000), "clCd": cl,
         "numOfRows": 100, "pageNo": 1, "_type": "json"}
    if dc:
        p["dgsbjtCd"] = dc
    last = "알 수 없음"
    for _ in range(2):
        try:
            r = requests.get(HIRA_URL, params=p, timeout=(8, 30))
        except requests.exceptions.RequestException as e:
            last = f"서버 응답 지연/실패({type(e).__name__})"
            continue
        try:
            items = r.json()["response"]["body"]["items"]
            items = items.get("item", []) if items else []
        except Exception:
            raise RuntimeError(f"심평원 응답 오류 HTTP {r.status_code}: {r.text[:100]}")
        return [items] if isinstance(items, dict) else items
    raise RuntimeError("심평원 " + last)


def fetch_hira(lat, lng, radius_km, dcodes):
    """종별(상급·종합·병원·의원) × 진료과목 코드로 주변 병원 조회. 일부가 실패해도 성공한 결과는 쓰고, 성공분만 30분 캐시해요.
    돌려주는 값: (병원 목록, 실패 메시지 목록, 전체 조회 수)"""
    cache = st.session_state.setdefault("hira_cache", {})
    now = time.time()
    jobs = [(c, d) for c in CL for d in (dcodes or (None,))]
    key = lambda j: (lat, lng, radius_km) + j  # noqa: E731
    todo = [j for j in jobs if key(j) not in cache or now - cache[key(j)][0] > 1800]
    errs = []

    def run(j):
        try:
            return j, hira_one(lat, lng, radius_km, *j), None
        except Exception as e:  # noqa: BLE001
            return j, [], str(e)[:140]

    if todo:
        with ThreadPoolExecutor(4) as ex:
            for j, items, e in ex.map(run, todo):
                if e:
                    errs.append(e)
                else:
                    cache[key(j)] = (now, items)
    rows = {}
    for j in jobs:
        if key(j) not in cache:
            continue
        for it in cache[key(j)][1]:
            try:
                rows[it["ykiho"]] = {"name": it.get("yadmNm", ""), "cl": j[0], "addr": it.get("addr", ""), "tel": it.get("telno", ""),
                                     "url": it.get("hospUrl", ""), "lat": float(it["YPos"]), "lng": float(it["XPos"]),
                                     "doctors": float(it["drTotCnt"]) if it.get("drTotCnt") else 0.0}
            except (KeyError, ValueError):
                continue
    return list(rows.values()), errs, len(jobs)


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_kakao(lat, lng, radius_km, code, query):
    """카카오 로컬: 병원(HP8) 또는 약국(PM9). 종별 정보가 없어서 병원은 '?'(종별 미상)로 둬요."""
    r = requests.get("https://dapi.kakao.com/v2/local/search/keyword.json", timeout=10, headers={"Authorization": f"KakaoAK {KAKAO}"},
                     params={"query": query, "x": lng, "y": lat, "radius": min(int(radius_km * 1000), 20000), "sort": "distance",
                             "size": 15, "category_group_code": code})
    return [{"name": d["place_name"], "cl": "PH" if code == "PM9" else "?", "addr": d.get("road_address_name") or d.get("address_name", ""),
             "tel": d.get("phone", ""), "url": d.get("place_url", ""), "lat": float(d["y"]), "lng": float(d["x"]), "doctors": 0.0}
            for d in r.json().get("documents", [])]


def build(rows, lat, lng, radius, depts=()):
    df = pd.DataFrame(rows, columns=["name", "cl", "addr", "tel", "url", "lat", "lng", "doctors"])
    if df.empty:
        return df
    df = df.drop_duplicates(["name", "lat", "lng"])
    df["dist"] = [hav(lat, lng, a, b) for a, b in zip(df["lat"], df["lng"])]
    df = df[df["dist"] <= radius].copy()
    keep = [(c == "PH") or dept_ok(n, depts) for c, n in zip(df["cl"], df["name"])]  # 약국은 그대로, 병원만 진료과 필터
    df = df[keep].copy()
    info = lambda c: PHARM if c == "PH" else CL.get(c, UNKNOWN)  # noqa: E731
    df["type"] = [info(c)[0] for c in df["cl"]]
    df["color"] = [info(c)[2] for c in df["cl"]]
    return df.sort_values("dist").reset_index(drop=True)  # 점수 없이 거리순


def card(r, rank=None):
    badge = (f'<div class="badge{" top" if rank and rank <= 3 else ""}">{rank}</div>' if rank else
             f'<div class="badge" style="background:{r["color"]}">+</div>')
    bar = (f'<div class="hc-meta">의사 {int(r["doctors"])}명</div>' if rank and r["doctors"] else "")
    links = (f'<a href="tel:{html.escape(r["tel"])}">📞 전화</a>' if r["tel"] else "")
    links += f'<a target="_blank" href="https://map.kakao.com/link/to/{quote(r["name"])},{r["lat"]},{r["lng"]}">🧭 길찾기</a>'
    if r["url"]:
        links += f'<a target="_blank" href="{html.escape(r["url"])}">상세</a>'
    return (f'<div class="hc"><div class="hc-top">{badge}<div style="min-width:0"><div class="hc-name">{html.escape(r["name"])}</div>'
            f'<div class="hc-meta"><span class="tag" style="background:{r["color"]}">{r["type"]}</span>{html.escape(r["addr"])}</div></div>'
            f'<div class="hc-dist">{r["dist"]:.1f} km<small>직선거리</small></div></div>{bar}<div class="links">{links}</div></div>')


MAP_JS = r"""
const D=__DATA__;const msg=t=>{const e=document.getElementById('msg');e.style.display='block';e.textContent=t;};
function loadJs(u,cb,i){i=i||0;if(i>=u.length){msg('지도 라이브러리를 불러오지 못했어요. cdnjs/jsdelivr/unpkg 접근을 확인해 주세요.');return;}
const s=document.createElement('script');s.src=u[i];s.onload=cb;s.onerror=()=>loadJs(u,cb,i+1);document.head.appendChild(s);}
const l=document.createElement('link');l.rel='stylesheet';l.href='https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css';document.head.appendChild(l);
loadJs(['https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js','https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js','https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'],start);
function start(){try{start2();}catch(e){msg('지도 오류: '+e.message);}}
function start2(){const map=L.map('m');map.fitBounds(L.latLng(D.c[0],D.c[1]).toBounds(D.r*2000));
 const T=[['https://tile.openstreetmap.org/{z}/{x}/{y}.png','© OpenStreetMap contributors']];
 let ti=0,er=0,ly=null;function use(){if(ly)map.removeLayer(ly);if(ti>=T.length){msg('지도 타일 서버에 접속하지 못했어요.');return;}
  ly=L.tileLayer(T[ti][0],{maxZoom:19,attribution:T[ti][1]}).addTo(map);er=0;ly.on('tileerror',()=>{if(++er===3){ti++;use();}});}use();
 L.circle(D.c,{radius:D.r*1000,color:'#1B6FE0',weight:1,fillOpacity:.04}).addTo(map);
 L.circleMarker(D.c,{radius:8,color:'#fff',weight:3,fillColor:'#0F2A43',fillOpacity:1}).addTo(map).bindTooltip('내 위치');
 D.p.forEach(p=>{const top=p.rank&&p.rank<=5,s=top?26:14;
  const ic=L.divIcon({className:'',iconSize:[s,s],iconAnchor:[s/2,s/2],html:'<div style="width:'+s+'px;height:'+s+'px;border-radius:50%;background:'+p.color+';border:2px solid #fff;color:#fff;font:700 13px/'+(s-4)+'px sans-serif;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.35)">'+(top?p.rank:'')+'</div>'});
  L.marker([p.lat,p.lng],{icon:ic}).addTo(map).bindPopup(p.html);});
 setTimeout(()=>map.invalidateSize(),300);}
"""


def map_html(center, radius, df):
    pts = []
    for i, r in df.iterrows():
        rank = i + 1 if r["type"] != "약국" else None
        pts.append({"lat": r["lat"], "lng": r["lng"], "color": r["color"], "rank": rank,
                    "html": f'<b>{html.escape(r["name"])}</b><br>{r["type"]} · {r["dist"]:.1f}km<br>{html.escape(r["addr"])}'})
    data = json.dumps({"c": center, "r": radius, "p": pts[:120]}, ensure_ascii=False).replace("</", "<\\/")
    css = ("html,body,#m{height:100%;margin:0}#msg{position:absolute;left:10px;bottom:10px;z-index:9999;background:#fff;color:#b42318;"
           "padding:8px 12px;border-radius:8px;font:13px sans-serif;box-shadow:0 1px 6px rgba(0,0,0,.25);display:none;max-width:80%}")
    return (f'<html><head><meta charset="utf-8"><style>{css}</style></head><body><div id="m"></div><div id="msg"></div>'
            f'<script>{MAP_JS.replace("__DATA__", data)}</script></body></html>')


# ---------------------------------------------------------------
d = st.session_state.get("pick_disease") or {}
st.markdown('<div class="topbar"><div class="logo">✚</div><div><b>병원 찾기</b>'
            '<span>추천 진료과 기준으로 내 주변 병원을 지도와 거리순으로 보여드려요</span></div></div>', unsafe_allow_html=True)
st.page_link("main.py", label="← 증상 다시 선택", icon="🧍")

if not (HIRA or KAKAO):
    st.error("`.env`에 HIRA_SERVICE_KEY 또는 KAKAO_REST_API_KEY가 필요해요. (키 이름과 따옴표를 확인해 주세요)")
    st.stop()

if d:
    st.markdown(f"### {html.escape(d.get('n', ''))} <span style='color:#5E7186;font-size:.9rem'>상병코드 {html.escape(str(d.get('c', '')))}</span>",
                unsafe_allow_html=True)

# --- 위치: 접속하면 현재 위치를 먼저 시도하고, 거부·실패하면 기본 위치 + 검색 ---
if "loc" not in st.session_state and get_geolocation:
    g = get_geolocation(component_key=f"geo{st.session_state.get('geo_n', 0)}")
    if isinstance(g, dict) and "coords" in g:
        st.session_state["loc"] = {"lat": g["coords"]["latitude"], "lng": g["coords"]["longitude"], "label": "내 위치"}
        st.rerun()
    elif isinstance(g, dict) and "error" in g:
        st.session_state["loc"] = dict(DEFAULT_LOC)
        st.warning("위치 권한이 거부돼서 기본 위치로 보여드려요. 브라우저 주소창의 위치 권한을 허용하거나 아래에서 주소를 검색해 주세요.")
loc = st.session_state.get("loc")
if loc is None:
    if get_geolocation:
        st.info("📍 현재 위치를 확인하는 중이에요. 브라우저에서 위치 권한을 '허용'해 주세요. (안 되면 아래에서 주소를 검색하세요)")
    loc = {**DEFAULT_LOC, "label": "위치 확인 중 (임시: 서울시청)"}

c1, c2, c3, c4 = st.columns([1.4, 1.4, 1.6, 0.4], vertical_alignment="bottom")
with c1:
    q = st.text_input("지역 · 주소 검색", placeholder=f"현재: {loc['label']}")
with c2:
    found = place_search(q.strip()) if len(q.strip()) >= 2 else []
    sel = st.selectbox("검색 결과", [f["label"] for f in found], index=None, placeholder="결과에서 선택") if found else None
    if sel:
        pick = next(f for f in found if f["label"] == sel)
        if pick["label"] != loc["label"]:
            st.session_state["loc"] = pick
            st.rerun()
with c3:
    default = [x for x in d.get("depts", []) if x in DEPT or x.endswith(("내과", "외과"))] or ["내과"]
    depts = st.multiselect("진료과", sorted(set(list(DEPT) + default + [x for x in d.get("depts", []) if dept_code(x)])), default=default)
with c4:
    if st.button("📍", help="내 위치로 이동", use_container_width=True):
        st.session_state.pop("loc", None)
        st.session_state["geo_n"] = st.session_state.get("geo_n", 0) + 1
        st.rerun()
radius = st.pills("검색 반경", [3, 5, 10, 20, 30], format_func=lambda x: f"{x}km", default=10, selection_mode="single") or 10

lat, lng = loc["lat"], loc["lng"]
st.caption(f"📍 {loc['label']} 기준")
if d.get("depts"):
    st.markdown("**추천 진료과** &nbsp;" + "".join(f'<span class="chip">{html.escape(x)}</span>' for x in d["depts"]), unsafe_allow_html=True)

err, warn, rows = "", "", []
with st.spinner("주변 병원을 찾는 중... (심평원 서버가 느리면 1분 정도 걸릴 수 있어요)"):
    codes = tuple(sorted({dept_code(x) for x in depts if dept_code(x)}))
    la, ln = round(lat, 4), round(lng, 4)
    if HIRA:
        rows, errs, njobs = fetch_hira(la, ln, radius, codes)
        if errs and len(errs) == njobs:  # 전부 실패
            err, rows = errs[0], []
        elif errs:
            warn = f"심평원 조회 {njobs}건 중 {len(errs)}건이 실패해서 일부 병원이 빠졌을 수 있어요."
    if (not HIRA or err) and KAKAO:  # 심평원을 못 쓰면 카카오로 대신 (선택한 진료과를 전부 검색)
        try:
            rows = []
            for dn in (depts or [""]):
                rows += fetch_kakao(la, ln, radius, "HP8", f"{dn} 병원".strip())
            if err:
                warn = "심평원 서버가 응답하지 않아 카카오 데이터로 대신 보여드려요. 종별·의사 수 정보는 없어요."
                err = ""
        except Exception as e:  # noqa: BLE001
            err = (err + " / " if err else "") + f"카카오 조회 실패: {str(e)[:100]}"
    if KAKAO:
        try:
            rows += fetch_kakao(la, ln, radius, "PM9", "약국")
        except Exception:  # noqa: BLE001
            warn = (warn + " " if warn else "") + "약국 정보를 불러오지 못했어요."
df = build(rows, lat, lng, radius, tuple(depts))
hosp = df[df["type"] != "약국"].reset_index(drop=True) if not df.empty else df
if err:
    st.error(f"병원 데이터를 불러오지 못했어요: {err}")
if warn:
    st.warning(warn)

left, right = st.columns([1.5, 1], gap="large")
with left:
    components.html(map_html([lat, lng], radius, pd.concat([hosp.head(60), df[df["type"] == "약국"].head(20)]) if not df.empty else df),
                    height=640)
    st.caption("지도의 숫자는 가까운 순위 상위 5곳이에요. 점을 누르면 상세가 보여요.")
with right:
    if hosp.empty:
        st.markdown('<div class="empty"><b>반경 안에서 병원을 찾지 못했어요</b><br>반경을 넓히거나 진료과를 바꿔 보세요.</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="kpis"><div class="kpi"><div class="k">병원</div><div class="n">{len(hosp)}곳</div></div>'
                    f'<div class="kpi"><div class="k">가장 가까운 곳</div><div class="n">{hosp["dist"].min():.1f}km</div></div>'
                    f'<div class="kpi"><div class="k">가장 가까운 병원</div><div class="n" style="font-size:.95rem">{html.escape(hosp.loc[0, "name"])}</div></div></div>',
                    unsafe_allow_html=True)
        t1, t3 = st.tabs(["가까운순", "약국"])
        with t1, st.container(height=520, border=False):
            for i, r in hosp.head(12).iterrows():
                st.markdown(card(r, i + 1), unsafe_allow_html=True)
        with t3, st.container(height=520, border=False):
            ph = df[df["type"] == "약국"].sort_values("dist").head(12)
            if ph.empty:
                st.markdown('<div class="empty">약국 정보는 KAKAO_REST_API_KEY가 있어야 나와요.</div>', unsafe_allow_html=True)
            for _, r in ph.iterrows():
                st.markdown(card(r), unsafe_allow_html=True)
        st.caption("진료과 필터는 심평원 진료과목 코드와 병원 이름으로 적용돼요. 순서는 직선거리 기준이고 공식 평가가 아니에요.")


# =========================================================
# 주변 병원 데이터 분석 (pandas)
# =========================================================
if not hosp.empty:
    st.markdown("### 📊 주변 병원 데이터 분석")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("병원 수", f"{len(hosp)}곳")
    m2.metric("평균 거리", f"{hosp['dist'].mean():.1f}km")
    m3.metric("상급·종합병원", f"{int(hosp['type'].isin(['상급종합', '종합병원']).sum())}곳")
    m4.metric("의사 수 합계", f"{int(hosp['doctors'].sum()):,}명" if hosp["doctors"].sum() else "자료 없음")

    ca, cb = st.columns(2)
    with ca:
        st.markdown("**종별 병원 수**")
        order = ["상급종합", "종합병원", "병원", "의원", "종별 미상"]
        by_type = hosp["type"].value_counts().reindex(order).fillna(0).astype(int)
        by_type = by_type[by_type > 0]
        st.bar_chart(by_type.rename("병원 수"), color="#1B6FE0")
    with cb:
        st.markdown("**거리별 병원 수**")
        band = pd.cut(hosp["dist"], bins=[0, 1, 3, 5, 10, 20, 30], labels=["1km 이내", "1~3km", "3~5km", "5~10km", "10~20km", "20~30km"],
                      include_lowest=True)
        by_dist = band.value_counts().sort_index()
        by_dist.index = by_dist.index.astype(str)
        st.bar_chart(by_dist.rename("병원 수"), color="#0E9F8E")

    st.markdown("**가까운 병원 순위표**")
    tbl = hosp.head(15)[["name", "type", "dist", "doctors", "addr"]].rename(
        columns={"name": "병원", "type": "종별", "dist": "거리", "doctors": "의사 수", "addr": "주소"})
    tbl.insert(0, "순위", range(1, len(tbl) + 1))
    st.dataframe(tbl, hide_index=True, use_container_width=True, column_config={
        "거리": st.column_config.NumberColumn("거리(km)", format="%.1f"),
        "의사 수": st.column_config.NumberColumn("의사 수", format="%d명"),
    })