import html
import json
import math
import time
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit_js_eval import get_geolocation
except Exception:  # noqa: BLE001
    get_geolocation = None

from common import bars, cnt, env, hira_get, hira_get_any, kpis, pricemap, setup, skel, table_html, topbar

setup("병원 찾기", """
.hc{background:#fff;border-radius:20px;padding:16px 18px;margin-bottom:10px;box-shadow:0 2px 12px rgba(25,31,40,.04);
 transition:transform .25s var(--ease),box-shadow .25s;animation:rise .5s var(--ease) both;animation-delay:calc(var(--i,0)*50ms)}
.hc:hover{transform:translateY(-3px);box-shadow:0 10px 26px rgba(25,31,40,.09)}
.hc-top{display:flex;gap:12px;align-items:flex-start}
.badge{flex:0 0 32px;height:32px;border-radius:10px;background:#F2F4F6;color:var(--sb);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.9rem}
.badge.top{background:var(--bl);color:#fff}
.hc-name{font-weight:700;line-height:1.35}.hc-meta{font-size:.82rem;color:var(--sb);margin-top:4px;line-height:1.5}
.tag{display:inline-block;font-size:.72rem;font-weight:700;padding:2px 9px;border-radius:999px;margin-right:6px;color:#fff}
.hc-dist{margin-left:auto;text-align:right;font-weight:800;white-space:nowrap}.hc-dist small{display:block;font-weight:500;color:var(--sb);font-size:.72rem}
.links{margin-top:10px;display:flex;gap:8px;flex-wrap:wrap}
.links a{font-size:.8rem;font-weight:600;color:var(--bl);text-decoration:none;background:var(--soft);padding:6px 13px;border-radius:999px;transition:background .2s,transform .15s}
.links a:hover{background:#D6E8FF}.links a:active{transform:scale(.95)}
.empty{background:#fff;border-radius:20px;padding:28px;text-align:center;color:var(--sb);line-height:1.7}
.seg{display:flex;height:14px;border-radius:999px;overflow:hidden;background:#F2F4F6;margin:8px 0 6px}
.seg i{display:block;height:100%;transform-origin:left;animation:grow .9s var(--ease) both}
""")

KAKAO, HIRA = env("KAKAO_REST_API_KEY"), env("HIRA_SERVICE_KEY")
HIRA_DETAIL = env("HIRA_DETAIL_SERVICE_KEY") or HIRA
HIRA_NPAY = env("HIRA_NPAY_SERVICE_KEY") or HIRA
DEFAULT_LOC = {"lat": 37.5665, "lng": 126.9780, "label": "서울시청 (기본 위치)"}

DEPT = {"내과": "01", "신경과": "02", "정신건강의학과": "03", "외과": "04", "정형외과": "05", "신경외과": "06", "흉부외과": "07",
        "성형외과": "08", "마취통증의학과": "09", "산부인과": "10", "소아청소년과": "11", "안과": "12", "이비인후과": "13",
        "피부과": "14", "비뇨의학과": "15", "영상의학과": "16", "재활의학과": "21", "가정의학과": "23", "응급의학과": "24"}
CL = {"01": ("상급종합", "#3182F6"), "11": ("종합병원", "#00B493"), "21": ("병원", "#FF9F43"), "31": ("의원", "#8B6CF6")}
PHARM = ("약국", "#F76B9C")
UNKNOWN = ("종별 미상", "#B0B8C1")
COLS = ["name", "cl", "addr", "tel", "url", "lat", "lng", "ykiho", "dr", "sp", "gp", "tr"]
MAX_PAGES = 5


def dept_code(name):
    if name in DEPT:
        return DEPT[name]
    return "01" if name.endswith("내과") else "04" if name.endswith("외과") else None


def haversine(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    x = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))


def dept_ok(name, depts):
    allowed = set(depts)
    for suffix in ("내과", "외과"):
        if any(x.endswith(suffix) for x in depts):
            allowed.add(suffix)
    found = [s for s in DEPT if s in name]
    found = [s for s in found if not any(s != o and s in o for o in found)]
    return not found or any(s in allowed for s in found)


def kakao(path, **params):
    r = requests.get(f"https://dapi.kakao.com/v2/local/search/{path}.json", timeout=10,
                     headers={"Authorization": f"KakaoAK {KAKAO}"}, params=params)
    return r.json().get("documents", [])


@st.cache_data(ttl=3600, show_spinner=False)
def place_search(q):
    out = []
    if KAKAO:
        for path in ("address", "keyword"):
            try:
                for d in kakao(path, query=q, size=5):
                    name, addr = d.get("place_name"), d.get("address_name", "")
                    out.append({"label": f"{name} · {addr}" if name else addr, "lat": float(d["y"]), "lng": float(d["x"])})
            except Exception:  # noqa: BLE001
                continue
    if not out and len(q) >= 3:
        try:
            r = requests.get("https://nominatim.openstreetmap.org/search", headers={"User-Agent": "hospital-finder/1.0"}, timeout=8,
                             params={"q": q, "format": "json", "limit": 5, "accept-language": "ko"})
            out = [{"label": d["display_name"][:70], "lat": float(d["lat"]), "lng": float(d["lon"])} for d in r.json()]
        except Exception:  # noqa: BLE001
            pass
    return out


def hira_one(lat, lng, radius_km, cl, dept):
    """한 종별·진료과 조합을 페이지 끝까지(최대 MAX_PAGES) 가져온다. (items, totalCount) 반환"""
    base = {"xPos": lng, "yPos": lat, "radius": int(radius_km * 1000), "clCd": cl, "numOfRows": 100}
    if dept:
        base["dgsbjtCd"] = dept
    out, total, page = [], 0, 1
    while page <= MAX_PAGES:
        last = "알 수 없음"
        for _ in range(2):
            try:
                items, total, _raw = hira_get("hospInfoServicev2/getHospBasisList", {**base, "pageNo": page}, HIRA, (8, 30))
                break
            except requests.exceptions.RequestException as e:
                last, items = f"서버 응답 지연/실패({type(e).__name__})", None
        if items is None:
            raise RuntimeError("심평원 " + last)
        out += items
        if not items or len(out) >= total:
            break
        page += 1
    return out, total


def num(it, k):
    try:
        return float(it.get(k) or 0)
    except (TypeError, ValueError):
        return 0.0


def fetch_hira(lat, lng, radius_km, dept_codes):
    cache = st.session_state.setdefault("hira_cache2", {})
    now = time.time()
    jobs = [(c, d) for c in CL for d in (dept_codes or (None,))]
    key = lambda j: (lat, lng, radius_km) + j  # noqa: E731
    todo = [j for j in jobs if key(j) not in cache or now - cache[key(j)][0] > 1800]
    errs = []

    def run(job):
        try:
            items, total = hira_one(lat, lng, radius_km, *job)
            return job, items, total, None
        except Exception as e:  # noqa: BLE001
            return job, [], 0, str(e)[:140]

    if todo:
        with ThreadPoolExecutor(4) as ex:
            for job, items, total, err in ex.map(run, todo):
                if err:
                    errs.append(err)
                else:
                    cache[key(job)] = (now, items, total)
    rows, trunc = {}, 0
    for job in jobs:
        _, items, total = cache.get(key(job), (0, [], 0))
        trunc += int(total > len(items))
        for it in items:
            try:
                rows[it["ykiho"]] = {"name": it.get("yadmNm", ""), "cl": job[0], "addr": it.get("addr", ""), "tel": it.get("telno", ""),
                                     "url": it.get("hospUrl", ""), "lat": float(it["YPos"]), "lng": float(it["XPos"]),
                                     "ykiho": it["ykiho"], "dr": num(it, "drTotCnt"), "sp": num(it, "mdeptSdrCnt"),
                                     "gp": num(it, "mdeptGdrCnt"), "tr": num(it, "mdeptIntnCnt") + num(it, "mdeptResdntCnt")}
            except (KeyError, ValueError):
                continue
    return list(rows.values()), errs, len(jobs), trunc


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_kakao(lat, lng, radius_km, code, query):
    docs = kakao("keyword", query=query, x=lng, y=lat, radius=min(int(radius_km * 1000), 20000), sort="distance", size=15,
                 category_group_code=code)
    return [{"name": d["place_name"], "cl": "PH" if code == "PM9" else "?", "addr": d.get("road_address_name") or d.get("address_name", ""),
             "tel": d.get("phone", ""), "url": d.get("place_url", ""), "lat": float(d["y"]), "lng": float(d["x"]),
             "ykiho": "", "dr": 0.0, "sp": 0.0, "gp": 0.0, "tr": 0.0} for d in docs]


@st.cache_data(ttl=86400, show_spinner=False)
def dept_doctors(ykiho):
    """진료과목별 전문의 수 (의료기관별상세정보서비스). 필드명은 공식 명세 기준."""
    items, _, _ = hira_get("MadmDtlInfoService2.7/getDgsbjtInfo2.7", {"ykiho": ykiho, "numOfRows": 100, "pageNo": 1}, HIRA_DETAIL)
    out = []
    for it in items:
        n, name = num(it, "dgsbjtPrSdrCnt"), it.get("dgsbjtCdNm", "")
        if name and n > 0:
            out.append((name, n))
    return sorted(out, key=lambda x: -x[1])


def build(rows, lat, lng, radius, depts=()):
    df = pd.DataFrame(rows, columns=COLS)
    if df.empty:
        return df
    df = df.drop_duplicates(["name", "lat", "lng"])
    df["dist"] = [haversine(lat, lng, a, b) for a, b in zip(df["lat"], df["lng"])]
    df = df[df["dist"] <= radius]
    df = df[[(c == "PH") or dept_ok(n, depts) for c, n in zip(df["cl"], df["name"])]].copy()
    info = [PHARM if c == "PH" else CL.get(c, UNKNOWN) for c in df["cl"]]
    df["type"] = [i[0] for i in info]
    df["color"] = [i[1] for i in info]
    return df.sort_values("dist").reset_index(drop=True)


def web_links(name):
    return (f'<a target="_blank" href="https://search.naver.com/search.naver?query={quote(name + " 의료진")}">의료진 검색</a>'
            f'<a target="_blank" href="https://map.kakao.com/?q={quote(name)}">지도 후기</a>'
            f'<a target="_blank" href="https://www.google.com/search?q={quote(name + " 의사 후기")}">후기 검색</a>')


def card(r, rank=None, i=0):
    top = " top" if rank and rank <= 3 else ""
    badge = f'<div class="badge{top}">{rank}</div>' if rank else f'<div class="badge" style="background:{r["color"]};color:#fff">약</div>'
    doc = ""
    if rank and r["dr"]:
        doc = f'<div class="hc-meta">의사 {int(r["dr"])}명' + (f' · 전문의 {int(r["sp"])}명' if r["sp"] else "") + "</div>"
    links = f'<a href="tel:{html.escape(r["tel"])}">전화</a>' if r["tel"] else ""
    links += f'<a target="_blank" href="https://map.kakao.com/link/to/{quote(r["name"])},{r["lat"]},{r["lng"]}">길찾기</a>'
    if r["url"]:
        links += f'<a target="_blank" href="{html.escape(r["url"])}">상세</a>'
    return (f'<div class="hc" style="--i:{i}"><div class="hc-top">{badge}<div style="min-width:0"><div class="hc-name">{html.escape(r["name"])}</div>'
            f'<div class="hc-meta"><span class="tag" style="background:{r["color"]}">{r["type"]}</span>{html.escape(r["addr"])}</div></div>'
            f'<div class="hc-dist">{r["dist"]:.1f} km<small>직선거리</small></div></div>{doc}<div class="links">{links}</div></div>')


MAP_JS = r"""
const D=__DATA__;
const msg=t=>{const e=document.getElementById('msg');e.style.display='block';e.textContent=t;};
function loadJs(urls,cb,i){i=i||0;if(i>=urls.length){msg('지도 라이브러리를 불러오지 못했어요. cdnjs/jsdelivr/unpkg 접근을 확인해 주세요.');return;}
const s=document.createElement('script');s.src=urls[i];s.onload=cb;s.onerror=()=>loadJs(urls,cb,i+1);document.head.appendChild(s);}
const css=document.createElement('link');css.rel='stylesheet';css.href='https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css';document.head.appendChild(css);
loadJs(['https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js','https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js','https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'],()=>{try{start();}catch(e){msg('지도 오류: '+e.message);}});
function start(){
 const map=L.map('m');map.fitBounds(L.latLng(D.c[0],D.c[1]).toBounds(D.r*2000));
 const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'}).addTo(map);
 let errors=0;tiles.on('tileerror',()=>{if(++errors===3)msg('지도 타일 서버에 접속하지 못했어요.');});
 L.circle(D.c,{radius:D.r*1000,color:'#3182F6',weight:1,fillOpacity:.04}).addTo(map);
 L.circleMarker(D.c,{radius:8,color:'#fff',weight:3,fillColor:'#191F28',fillOpacity:1}).addTo(map).bindTooltip('내 위치');
 D.p.forEach(p=>{const top=p.rank&&p.rank<=5,s=top?26:14;
  const icon=L.divIcon({className:'',iconSize:[s,s],iconAnchor:[s/2,s/2],html:'<div style="width:'+s+'px;height:'+s+'px;border-radius:50%;background:'+p.color+';border:2px solid #fff;color:#fff;font:700 13px/'+(s-4)+'px sans-serif;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.35)">'+(top?p.rank:'')+'</div>'});
  L.marker([p.lat,p.lng],{icon}).addTo(map).bindPopup(p.html);});
 setTimeout(()=>map.invalidateSize(),300);}
"""


def map_html(center, radius, df):
    pts = [{"lat": r["lat"], "lng": r["lng"], "color": r["color"], "rank": None if r["type"] == "약국" else i + 1,
            "html": f'<b>{html.escape(r["name"])}</b><br>{r["type"]} · {r["dist"]:.1f}km<br>{html.escape(r["addr"])}'}
           for i, r in df.iterrows()]
    data = json.dumps({"c": center, "r": radius, "p": pts[:120]}, ensure_ascii=False).replace("</", "<\\/")
    css = ("html,body,#m{height:100%;margin:0;border-radius:20px}#msg{position:absolute;left:10px;bottom:10px;z-index:9999;background:#fff;color:#b42318;"
           "padding:8px 12px;border-radius:8px;font:13px sans-serif;box-shadow:0 1px 6px rgba(0,0,0,.25);display:none;max-width:80%}")
    return (f'<html><head><meta charset="utf-8"><style>{css}</style></head><body><div id="m"></div><div id="msg"></div>'
            f'<script>{MAP_JS.replace("__DATA__", data)}</script></body></html>')


def current_location():
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
            st.info("현재 위치를 확인하는 중이에요. 브라우저에서 위치 권한을 '허용'해 주세요. (안 되면 아래에서 주소를 검색하세요)")
        loc = {**DEFAULT_LOC, "label": "위치 확인 중 (임시: 서울시청)"}
    return loc


def load_hospitals(lat, lng, radius, depts):
    rows, err, warn = [], "", ""
    la, ln = round(lat, 4), round(lng, 4)
    if HIRA:
        rows, errs, jobs, trunc = fetch_hira(la, ln, radius, tuple(sorted({dept_code(x) for x in depts if dept_code(x)})))
        if errs and len(errs) == jobs:
            err, rows = errs[0], []
        elif errs:
            warn = f"심평원 조회 {jobs}건 중 {len(errs)}건이 실패해서 일부 병원이 빠졌을 수 있어요."
        if trunc and not err:
            warn = (warn + " " if warn else "") + f"결과가 많은 {trunc}개 조건은 앞쪽 {MAX_PAGES * 100}곳까지만 반영했어요. 반경을 줄이면 더 정확해요."
    if (not HIRA or err) and KAKAO:
        try:
            rows = [r for dn in (depts or [""]) for r in fetch_kakao(la, ln, radius, "HP8", f"{dn} 병원".strip())]
            if err:
                warn, err = "심평원 서버가 응답하지 않아 카카오 데이터로 대신 보여드려요. 종별·의사 수 정보는 없어요.", ""
        except Exception as e:  # noqa: BLE001
            err = (err + " / " if err else "") + f"카카오 조회 실패: {str(e)[:100]}"
    if KAKAO:
        try:
            rows = rows + fetch_kakao(la, ln, radius, "PM9", "약국")
        except Exception:  # noqa: BLE001
            warn = (warn + " " if warn else "") + "약국 정보를 불러오지 못했어요."
    return rows, err, warn


def show_doctors(hosp):
    st.markdown('<div class="sec">의료진 정보</div><div class="sub" style="margin:-8px 0 12px">가까운 10곳의 의사 수예요. 의사 개인의 이름·경력·평점은 심평원 공개 데이터에 없어서, 각 병원의 검색 링크를 함께 드려요.</div>',
                unsafe_allow_html=True)
    h = hosp[hosp["dr"] > 0].head(10)
    if h.empty:
        st.info("의사 수는 심평원 데이터에서만 제공돼요. 지금은 카카오 데이터로 보고 있어서 표시할 수 없어요.")
        return
    t = pd.DataFrame({"병원": h["name"], "종별": h["type"], "거리": h["dist"], "의사": h["dr"], "전문의": h["sp"],
                      "전문의 비율": (h["sp"] / h["dr"]).clip(upper=1) * 100})
    st.markdown(table_html(t, fmts={"거리": lambda v: f"{v:.1f}km", "의사": lambda v: f"{v:,.0f}명", "전문의": lambda v: f"{v:,.0f}명",
                                    "전문의 비율": lambda v: f"{v:.0f}%"}, heat={"전문의 비율": 100}), unsafe_allow_html=True)
    st.caption("전문의 비율 = 의과 전문의 ÷ 의사 총수 (건강보험심사평가원 병원정보서비스 기준)")

    names = [f"{r['name']} · {r['type']} · {r['dist']:.1f}km" for _, r in h.iterrows()]
    sel = st.selectbox("병원 선택", names, key="doc_pick")
    r = h.iloc[names.index(sel)]
    others = max(r["dr"] - r["sp"] - r["gp"] - r["tr"], 0)
    parts = [("전문의", r["sp"], "#3182F6"), ("일반의", r["gp"], "#7FB3FA"), ("수련의", r["tr"], "#B9D7FF"), ("기타", others, "#E5E8EB")]
    seg = "".join(f'<i style="width:{v / r["dr"] * 100:.1f}%;background:{c};animation-delay:{k * 80}ms"></i>' for k, (_, v, c) in enumerate(parts) if v > 0)
    legend = " ".join(f'<span class="chip g">{n} {v:,.0f}명</span>' for n, v, _ in parts if v > 0)
    st.markdown(kpis([("의사 총수", f"{r['dr']:,.0f}명"), ("전문의", f"{r['sp']:,.0f}명", f"비율 {min(r['sp'] / r['dr'], 1) * 100:.0f}%"),
                      ("일반의", f"{r['gp']:,.0f}명"), ("수련의(인턴·레지던트)", f"{r['tr']:,.0f}명")])
                + f'<div class="chart"><div class="ct">의사 구성</div><div class="seg">{seg}</div>{legend}</div>', unsafe_allow_html=True)
    if r["ykiho"] and st.button("진료과목별 전문의 수 보기", key=f"dd_{r['ykiho']}"):
        ph = st.empty()
        ph.markdown(skel(2), unsafe_allow_html=True)
        try:
            data = dept_doctors(r["ykiho"])
            ph.empty()
            if data:
                st.markdown('<div class="chart"><div class="ct">진료과목별 전문의</div>' + bars(data, top=True, share=False) + "</div>", unsafe_allow_html=True)
            else:
                st.caption("진료과목별 전문의 정보가 없어요.")
        except Exception as e:  # noqa: BLE001
            ph.empty()
            st.warning(f"진료과목별 정보를 불러오지 못했어요. 공공데이터포털에서 '의료기관별상세정보서비스' 활용 신청이 필요할 수 있어요. ({str(e)[:100]})")
    st.markdown(f'<div class="links" style="margin-top:12px">{web_links(r["name"])}</div>', unsafe_allow_html=True)


# ───────────────────────── 비급여 진료비 비교 ─────────────────────────
NPAY_PATH = "nonPaymentDamtInfoService/getNonPaymentItemHospDtlList"
NPAY_CL = ("01", "11", "21")  # 병원급 이상만 공개 대상 (의원 제외)
NPAY_BASE = ["MRI", "CT", "초음파", "도수치료", "1인실"]
NPAY_BY_DEPT = {"정형외과": ["MRI", "도수치료", "초음파"], "신경외과": ["MRI", "CT"], "신경과": ["MRI", "CT"],
                "재활의학과": ["도수치료", "MRI"], "소화기내과": ["내시경", "초음파", "CT"], "순환기내과": ["CT", "초음파", "MRI"],
                "호흡기내과": ["CT", "초음파"], "산부인과": ["초음파", "MRI"], "비뇨의학과": ["초음파", "CT"],
                "이비인후과": ["CT", "MRI"], "안과": ["MRI", "CT"], "내분비내과": ["초음파"], "외과": ["초음파", "CT"]}


@st.cache_data(ttl=86400, show_spinner=False)
def npay_items(ykiho):
    """한 병원의 비급여 항목 전체(최대 6페이지). 하루 캐시."""
    out, page = [], 1
    while page <= 6:
        items, total = hira_get_any(NPAY_PATH, {"ykiho": ykiho, "pageNo": page, "numOfRows": 500}, HIRA_NPAY, 20)
        out += items
        if not items or len(out) >= total:
            break
        page += 1
    return out


def npay_filter(items, kw):
    """키워드에 맞고 현재 적용 중이며 금액이 유효한 항목만 남긴다."""
    k, today, rows = kw.lower(), date.today().strftime("%Y%m%d"), []
    for it in items:
        name, alias = it.get("npayKorNm") or "", it.get("yadmNpayCdNm") or ""
        if k not in name.lower() and k not in alias.lower():
            continue
        if str(it.get("adtEndDd") or "99991231") < today:
            continue
        try:
            price = float(str(it.get("curAmt")).replace(",", ""))
        except ValueError:
            continue
        if price <= 0:
            continue
        frm = str(it.get("adtFrDd") or "")
        rows.append({"item": name or alias, "alias": alias, "price": price,
                     "from": f"{frm[:4]}-{frm[4:6]}-{frm[6:]}" if len(frm) == 8 else frm})
    return rows


def npay_collect(kw, targets):
    """targets: [(ykiho, 병원명, 종별, 거리)] → (매칭 DataFrame, 오류 목록)"""
    errs, rows = [], []

    def run(t):
        try:
            return t, npay_filter(npay_items(t[0]), kw), None
        except Exception as e:  # noqa: BLE001
            return t, [], f"{t[1]}: {str(e)[:90]}"

    with ThreadPoolExecutor(4) as ex:
        for (yk, name, typ, dist), found, err in ex.map(run, targets):
            if err:
                errs.append(err)
            rows += [{"ykiho": yk, "hosp": name, "type": typ, "dist": dist, **f} for f in found]
    return pd.DataFrame(rows, columns=["ykiho", "hosp", "type", "dist", "item", "alias", "price", "from"]), errs


def show_prices(hosp, depts):
    st.markdown('<div class="sec" style="margin-top:6px">비급여 진료비 비교</div><div class="sub" style="margin:-8px 0 12px">'
                '가까운 병원급 이상 의료기관(최대 8곳)이 심평원에 신고한 현재 가격을 비교해요. 의원은 공개 대상이 아니라 빠져요.</div>',
                unsafe_allow_html=True)
    if not HIRA_NPAY:
        st.info(".env에 HIRA_NPAY_SERVICE_KEY(또는 HIRA_SERVICE_KEY)가 있어야 비급여 가격을 비교할 수 있어요.")
        return
    elig = hosp[hosp["cl"].isin(NPAY_CL) & (hosp["ykiho"] != "")].head(8)
    if elig.empty:
        st.info("반경 안에 병원급 이상 의료기관이 없어요. 반경을 넓혀 보세요.")
        return
    targets = tuple((r["ykiho"], r["name"], r["type"], float(r["dist"])) for _, r in elig.iterrows())
    presets = list(dict.fromkeys([x for d in depts for x in NPAY_BY_DEPT.get(d, [])] + NPAY_BASE))[:8]
    pre = st.pills("자주 비교하는 항목", presets, selection_mode="single", key="np_pre")
    txt_in = st.text_input("항목 직접 검색", placeholder="예) MRI, 도수치료, 초음파, 1인실", key="np_txt").strip()
    kw = txt_in or pre or ""
    busy = st.session_state.get("np_job") is not None
    clicked = st.button("가격 불러오는 중이에요" if busy else "가격 비교하기", type="primary", use_container_width=True,
                        key="np_busy" if busy else "np_idle", disabled=busy or not kw)
    if clicked:
        st.session_state["np_job"] = (kw, targets)
        st.rerun()
    if busy:
        st.markdown(skel(3), unsafe_allow_html=True)
        job_kw, job_t = st.session_state["np_job"]
        try:
            df_, errs = npay_collect(job_kw, list(job_t))
            st.session_state["np_res"] = {"kw": job_kw, "keys": {t[0] for t in job_t}, "df": df_, "errs": errs, "n": len(job_t)}
        finally:
            st.session_state["np_job"] = None
        st.rerun()
    res = st.session_state.get("np_res")
    if not res or res["keys"] != {t[0] for t in targets}:
        if res:
            st.caption("위치나 반경이 바뀌어서 이전 비교 결과를 숨겼어요. 다시 비교해 주세요.")
        return
    df_, errs = res["df"], res["errs"]
    if len(errs) == res["n"]:
        st.warning("비급여 가격을 불러오지 못했어요. 공공데이터포털에서 '비급여진료비정보조회서비스' 활용신청이 됐는지, "
                   "키가 다르면 .env에 HIRA_NPAY_SERVICE_KEY=발급키 형태로 넣었는지 확인해 주세요. (" + errs[0] + ")")
        return
    if errs:
        st.caption(f"{len(errs)}곳은 가격을 불러오지 못해서 빠졌어요.")
    if df_.empty:
        st.info(f"'{res['kw']}'와 맞는 현재 적용 중인 비급여 항목이 없어요. 다른 표기로 검색해 보세요.")
        return

    counts = df_.groupby("item")["hosp"].nunique().sort_values(ascending=False)
    opts = [f"{i}  ({n}곳)" for i, n in counts.items()]
    sel = st.selectbox("세부 항목", opts, key="np_item")
    item = list(counts.index)[opts.index(sel)]
    sub = df_[df_["item"] == item]
    best = sub.sort_values("price").groupby("hosp", as_index=False).first()  # 병원별 최저가 1건
    best["n"] = best["hosp"].map(sub.groupby("hosp").size())
    best = best.sort_values("price").reset_index(drop=True)
    p = best["price"]
    lo, hi, med = p.min(), p.max(), p.median()
    cheap, dear = best.iloc[0], best.iloc[-1]
    near = best.sort_values("dist").iloc[0]

    st.markdown(kpis([("최저가", f"{lo:,.0f}원", html.escape(cheap["hosp"])), ("중앙값", f"{med:,.0f}원", f"{len(best)}곳 기준"),
                      ("최고가", f"{hi:,.0f}원", html.escape(dear["hosp"])),
                      ("최고가 ÷ 최저가", f"{hi / lo:.1f}배" if lo else "-", f"차이 {hi - lo:,.0f}원")]), unsafe_allow_html=True)
    if len(best) >= 2:
        gap = (near["price"] - med) / med * 100 if med else 0
        msg = (f"가장 저렴한 곳은 {cheap['hosp']}({lo:,.0f}원)이고, 가장 비싼 곳과 {hi - lo:,.0f}원 차이가 나요. "
               f"가장 가까운 {near['hosp']}({near['dist']:.1f}km)은 중앙값보다 {abs(gap):.0f}% {'비싸요' if gap > 0 else '저렴해요' if gap < 0 else '같아요'}.")
        st.markdown(f'<div class="insight">{html.escape(msg)}</div>', unsafe_allow_html=True)
    if len(best) < 3:
        st.caption("비교 대상이 3곳보다 적어서 중앙값·편차는 참고만 해 주세요.")

    labels = [f"{r['hosp']} · {r['dist']:.1f}km" for _, r in best.iterrows()]
    mark = f"{near['hosp']} · {near['dist']:.1f}km"
    c1, c2 = st.columns([1.7, 1], gap="medium")
    c1.markdown(f'<div class="chart"><div class="ct">병원별 가격</div><div class="cs">낮은 순 · 점선은 중앙값 · {html.escape(item)}</div>'
                + pricemap(list(zip(labels, best["price"])), med=med, mark=mark)
                + "</div>", unsafe_allow_html=True)
    by_type = best.groupby("type")["price"].mean().sort_values()
    if len(by_type) >= 2:
        c2.markdown('<div class="chart"><div class="ct">종별 평균 가격</div><div class="cs">같은 항목, 병원 종별 평균</div>'
                    + bars(list(by_type.items()), unit="원", share=False, color="#00B493") + "</div>", unsafe_allow_html=True)
    else:
        c2.markdown('<div class="chart"><div class="ct">가격 분포</div><div class="cs">최저·중앙·최고</div>'
                    + bars([("최저", lo), ("중앙값", med), ("최고", hi)], unit="원", share=False) + "</div>", unsafe_allow_html=True)

    flag = lambda v: ("편차 큼" if len(best) >= 3 and med and (v > med * 3 or v < med / 3) else "")  # noqa: E731
    t = pd.DataFrame({"병원": best["hosp"], "종별": best["type"], "거리": best["dist"], "병원 표기명": best["alias"].replace("", "-"),
                      "가격": best["price"], "적용 시작": best["from"], "동일 항목 건수": best["n"], "비고": best["price"].map(flag)})
    st.markdown('<div style="height:10px"></div>' + table_html(t, fmts={"거리": lambda v: f"{v:.1f}km", "가격": lambda v: f"{v:,.0f}원",
                                                                       "동일 항목 건수": lambda v: f"{v:,.0f}건"}, heat={"가격": None}),
                unsafe_allow_html=True)
    st.caption("병원이 심평원에 자율 신고한 현재 적용 금액이에요. 같은 항목명이어도 장비·검사 범위가 다를 수 있고, 한 병원에 같은 항목이 여러 건이면 "
               "가장 낮은 금액을 썼어요. '편차 큼'은 중앙값의 3배 초과 또는 1/3 미만이에요. 출처: 건강보험심사평가원 비급여진료비정보조회서비스(공공누리 제1유형)")


picked = st.session_state.get("pick_disease") or {}
topbar("병원 찾기", "추천 진료과 기준으로 내 주변 병원을 지도와 거리순으로 보여드려요")
st.page_link("main.py", label="증상 다시 선택")

if not (HIRA or KAKAO):
    st.error("`.env`에 HIRA_SERVICE_KEY 또는 KAKAO_REST_API_KEY가 필요해요. (키 이름과 따옴표를 확인해 주세요)")
    st.stop()

if picked:
    st.markdown(f"### {html.escape(picked.get('n', ''))} "
                f"<span style='color:#6B7684;font-size:.9rem'>상병코드 {html.escape(str(picked.get('c', '')))}</span>", unsafe_allow_html=True)

loc = current_location()
c1, c2, c3, c4 = st.columns([1.4, 1.4, 1.6, 0.6], vertical_alignment="bottom")
with c1:
    q = st.text_input("지역 · 주소 검색", placeholder=f"현재: {loc['label']}").strip()
with c2:
    found = place_search(q) if len(q) >= 2 else []
    chosen = st.selectbox("검색 결과", [f["label"] for f in found], index=None, placeholder="결과에서 선택") if found else None
    if chosen:
        place = next(f for f in found if f["label"] == chosen)
        if place["label"] != loc["label"]:
            st.session_state["loc"] = place
            st.rerun()
with c3:
    recommended = picked.get("depts", [])
    default = [x for x in recommended if x in DEPT or x.endswith(("내과", "외과"))] or ["내과"]
    options = sorted(set(list(DEPT) + default + [x for x in recommended if dept_code(x)]))
    depts = st.multiselect("진료과", options, default=default)
with c4:
    if st.button("내 위치", help="현재 위치로 이동", use_container_width=True):
        st.session_state.pop("loc", None)
        st.session_state["geo_n"] = st.session_state.get("geo_n", 0) + 1
        st.rerun()
radius = st.pills("검색 반경", [3, 5, 10, 20, 30], format_func=lambda x: f"{x}km", default=10, selection_mode="single") or 10

lat, lng = loc["lat"], loc["lng"]
st.caption(f"{loc['label']} 기준")
if recommended:
    st.markdown("**추천 진료과** &nbsp;" + "".join(f'<span class="chip">{html.escape(x)}</span>' for x in recommended), unsafe_allow_html=True)

ph = st.empty()
ph.markdown(skel(3), unsafe_allow_html=True)
rows, err, warn = load_hospitals(lat, lng, radius, depts)
ph.empty()
df = build(rows, lat, lng, radius, tuple(depts))
hosp = df[df["type"] != "약국"].reset_index(drop=True) if not df.empty else df
pharmacies = df[df["type"] == "약국"] if not df.empty else df
if err:
    st.error(f"병원 데이터를 불러오지 못했어요: {err}")
if warn:
    st.warning(warn)

left, right = st.columns([1.5, 1], gap="large")
with left:
    shown = pd.concat([hosp.head(60), pharmacies.head(20)]) if not df.empty else df
    components.html(map_html([lat, lng], radius, shown), height=640)
    st.caption("지도의 숫자는 가까운 순위 상위 5곳이에요. 점을 누르면 상세가 보여요.")
with right:
    if hosp.empty:
        st.markdown('<div class="empty"><b>반경 안에서 병원을 찾지 못했어요</b><br>반경을 넓히거나 진료과를 바꿔 보세요.</div>', unsafe_allow_html=True)
    else:
        st.markdown(kpis([("병원", f"{cnt(len(hosp))}곳"), ("가장 가까운 곳", f"{hosp['dist'].min():.1f}km"),
                          ("가장 가까운 병원", f'<span style="font-size:.95rem">{html.escape(hosp.loc[0, "name"])}</span>')]),
                    unsafe_allow_html=True)
        tab_near, tab_pharm = st.tabs(["가까운순", "약국"])
        with tab_near, st.container(height=520, border=False):
            for i, r in hosp.head(12).iterrows():
                st.markdown(card(r, i + 1, i), unsafe_allow_html=True)
        with tab_pharm, st.container(height=520, border=False):
            if pharmacies.empty:
                st.markdown('<div class="empty">약국 정보는 KAKAO_REST_API_KEY가 있어야 나와요.</div>', unsafe_allow_html=True)
            for i, (_, r) in enumerate(pharmacies.sort_values("dist").head(12).iterrows()):
                st.markdown(card(r, None, i), unsafe_allow_html=True)
        st.caption("진료과 필터는 심평원 진료과목 코드와 병원 이름으로 적용돼요. 순서는 직선거리 기준이고 공식 평가가 아니에요.")

if not hosp.empty:
    t_doc, t_price = st.tabs(["의료진 정보", "비급여 진료비 비교"])
    with t_doc:
        show_doctors(hosp)
    with t_price:
        show_prices(hosp, depts)