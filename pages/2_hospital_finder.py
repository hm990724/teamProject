import json
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit_js_eval import get_geolocation
except Exception:  # noqa: BLE001
    get_geolocation = None

from kok_common import (bars, cnt, env, esc, hero, hira_get, kpis, link_cards, open_badge, setup, skel, stack_bars,
                    table_html, topbar, week_hours)

setup("병원 찾기", """
.hc{position:relative;overflow:hidden;background:#fff;border:1px solid #E3ECF6;border-radius:16px;padding:16px 18px 14px 22px;margin-bottom:12px;
 box-shadow:0 1px 2px rgba(16,42,67,.04),0 8px 20px rgba(16,42,67,.05);
 transition:transform .3s var(--ease),box-shadow .3s,border-color .3s;animation:rise .55s var(--ease) both;animation-delay:calc(var(--i,0)*60ms)}
.hc::before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;background:var(--acc,#1E6FD9);transition:width .3s var(--ease)}
.hc::after{content:"✚";position:absolute;right:-8px;top:-18px;font-size:72px;line-height:1;color:var(--acc,#1E6FD9);opacity:.05;transition:transform .5s var(--ease),opacity .3s}
.hc:hover{transform:translateY(-4px);box-shadow:0 14px 32px rgba(30,111,217,.14);border-color:#BFD4EE}
.hc:hover::before{width:8px}.hc:hover::after{transform:rotate(90deg) scale(1.15);opacity:.09}
.hc-top{display:flex;gap:12px;align-items:flex-start;position:relative;z-index:1}
.badge{flex:0 0 34px;height:34px;border-radius:50%;background:#EEF4FB;color:var(--sb);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.9rem}
.badge.top{background:linear-gradient(135deg,#1E6FD9,#17A2A8);color:#fff;box-shadow:0 4px 10px rgba(30,111,217,.35)}
.hc-name{font-weight:700;line-height:1.35;font-size:1.02rem}
.hc-meta{font-size:.82rem;color:var(--sb);margin-top:4px;line-height:1.5}
.tag{display:inline-block;font-size:.72rem;font-weight:700;padding:2px 9px;border-radius:99px;margin-right:6px;color:#fff}
.hc-dist{margin-left:auto;text-align:right;font-weight:800;white-space:nowrap;background:#F1F7FE;color:#1B5FC1;border-radius:10px;padding:6px 10px}
.hc-dist small{display:block;font-weight:500;color:var(--sb);font-size:.7rem}
.mini{display:flex;height:6px;border-radius:99px;overflow:hidden;margin-top:10px;background:#EDF2F8;position:relative;z-index:1}
.mini i{display:block;height:100%;transform-origin:left;animation:grow .8s var(--ease) both}
.links{margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;position:relative;z-index:1}
.links a{font-size:.8rem;font-weight:600;color:#1B5FC1;text-decoration:none;background:#fff;border:1px solid #DCE8F7;padding:6px 13px;border-radius:99px;
 transition:background .2s,color .2s,border-color .2s,transform .15s}
.links a:hover{background:#1E6FD9;color:#fff;border-color:#1E6FD9}.links a:active{transform:scale(.95)}
.empty{background:#fff;border:1px dashed #C9D8EA;border-radius:16px;padding:28px;text-align:center;color:var(--sb);line-height:1.7}
button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,#1E6FD9,#17A2A8)!important;border:0!important;transition:transform .15s,box-shadow .25s!important}
button[data-testid="stBaseButton-primary"]:hover{transform:translateY(-1px);box-shadow:0 8px 20px rgba(30,111,217,.28)}
.hero{background:linear-gradient(120deg,#0B2545,#123A73 40%,#1D5FD1 75%,#17A2A8)!important;background-size:220% 220%!important;animation:rise .6s var(--ease) both,gm 14s ease-in-out infinite!important}
@keyframes gm{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
.st-key-filters{background:rgba(255,255,255,.86);backdrop-filter:blur(10px);border:1px solid #DCE8F7;border-radius:18px;padding:16px 18px 6px;margin:4px 0 14px;
 box-shadow:0 10px 30px rgba(16,42,67,.08);animation:rise .6s .1s var(--ease) both}
[data-testid="stPills"] button{border-radius:99px!important;transition:background .2s,color .2s,transform .2s var(--ease),box-shadow .25s!important}
[data-testid="stPills"] button:hover{transform:translateY(-2px)}
button[data-testid="stBaseButton-pillsActive"],[data-testid="stPills"] button[aria-checked="true"],[data-testid="stPills"] button[aria-pressed="true"]{
 background:linear-gradient(135deg,#1E6FD9,#17A2A8)!important;border-color:transparent!important;box-shadow:0 6px 16px rgba(30,111,217,.30)!important}
button[data-testid="stBaseButton-pillsActive"] *,[data-testid="stPills"] button[aria-checked="true"] *,[data-testid="stPills"] button[aria-pressed="true"] *{color:#fff!important}
[data-baseweb="tag"]{background:linear-gradient(135deg,#1E6FD9,#17A2A8)!important;border-radius:99px!important;animation:pop .35s var(--ease) both}
[data-baseweb="tag"] span,[data-baseweb="tag"] svg{color:#fff!important;fill:#fff!important}
[data-baseweb="tab-list"]{gap:6px}
[data-baseweb="tab"]{border-radius:10px 10px 0 0;padding:10px 16px;transition:background .2s,color .2s}
[data-baseweb="tab"]:hover{background:#F1F7FE}[data-baseweb="tab"][aria-selected="true"]{color:#1B5FC1}
.prox{display:flex;align-items:center;gap:8px;margin-top:10px;position:relative;z-index:1;font-size:.72rem;font-weight:600;color:var(--sb)}
.prox span{flex:1;height:5px;border-radius:99px;background:#EDF2F8;overflow:hidden}
.prox i{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,var(--acc),#17A2A8);transform-origin:left;animation:grow 1s var(--ease) both}
*::-webkit-scrollbar{width:8px;height:8px}*::-webkit-scrollbar-thumb{background:#C9D8EA;border-radius:99px}
iframe[height="640"]{border-radius:16px;border:1px solid #E3ECF6;box-shadow:0 10px 30px rgba(16,42,67,.10)}
@supports (animation-timeline:view()){.chart,.tw,.kpis,.lks{animation:rise linear both!important;animation-timeline:view();animation-range:entry 5% cover 28%}}
""")

KAKAO, HIRA = env("KAKAO_REST_API_KEY"), env("HIRA_SERVICE_KEY")
HIRA_DETAIL = env("HIRA_DETAIL_SERVICE_KEY") or HIRA


def detail_off(e=None):
    if e is not None and "NOT_REGISTERED" in str(e):
        st.session_state["detail_off"] = True
    return st.session_state.get("detail_off", False)


DETAIL_ON = bool(HIRA_DETAIL) and not detail_off()
UNREG = "진료시간·전문의 상세는 공공데이터포털에서 '의료기관별상세정보서비스' 활용신청을 하면 쓸 수 있어요. 신청 전에는 이 항목이 숨겨져요."
DEFAULT_LOC = {"lat": 37.5665, "lng": 126.9780, "label": "서울시청 (기본 위치)"}
DEPT = {"내과": "01", "신경과": "02", "정신건강의학과": "03", "외과": "04", "정형외과": "05", "신경외과": "06", "흉부외과": "07",
        "성형외과": "08", "마취통증의학과": "09", "산부인과": "10", "소아청소년과": "11", "안과": "12", "이비인후과": "13",
        "피부과": "14", "비뇨의학과": "15", "영상의학과": "16", "재활의학과": "21", "가정의학과": "23", "응급의학과": "24"}
CL = {"01": ("상급종합", "#1E6FD9"), "11": ("종합병원", "#0E9F8E"), "21": ("병원", "#F59E0B"), "31": ("의원", "#7C5CE0")}
PHARM = ("약국", "#F76B9C")
TYPE_COLORS = {**dict(CL.values()), PHARM[0]: PHARM[1]}
UNKNOWN = ("종별 미상", "#B0B8C1")
COLS = ["name", "cl", "addr", "tel", "url", "lat", "lng", "ykiho", "dr", "sp", "gp", "tr"]
MAX_PAGES = 5
MAP_ZOOM = 17
HOSP_CL = ("01", "11", "21")
DETAIL_VERSIONS = ("2.8", "2.7")
DD_OPS = [("getSpcSbjtSdrInfo", ("dtlSdrCnt", "sdrCnt", "dgsbjtPrSdrCnt")), ("getDgsbjtInfo", ("dgsbjtPrSdrCnt", "dtlSdrCnt", "sdrCnt"))]
DAYS = [("월", "Mon"), ("화", "Tue"), ("수", "Wed"), ("목", "Thu"), ("금", "Fri"), ("토", "Sat"), ("일", "Sun")]
KST = timezone(timedelta(hours=9))
_DD, _DD_BEST = {}, []


def base_dept(name):
    return name if name in DEPT else "내과" if name.endswith("내과") else "외과" if name.endswith("외과") else None


def dept_code(name):
    return DEPT.get(base_dept(name))


def haversine(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    x = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))


def dept_ok(name, depts):
    allowed = set(depts) | {s for s in ("내과", "외과") if any(x.endswith(s) for x in depts)}
    found = [s for s in DEPT if s in name]
    found = [s for s in found if not any(s != o and s in o for o in found)]
    return not found or any(s in allowed for s in found)


def num(it, k):
    try:
        return float(it.get(k) or 0)
    except (TypeError, ValueError):
        return 0.0


def kakao(path, **params):
    r = requests.get(f"https://dapi.kakao.com/v2/local/search/{path}.json", timeout=10, headers={"Authorization": f"KakaoAK {KAKAO}"}, params=params)
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
    base = {"xPos": lng, "yPos": lat, "radius": int(radius_km * 1000), "clCd": cl, "numOfRows": 100, **({"dgsbjtCd": dept} if dept else {})}
    out, total, page = [], 0, 1
    while page <= MAX_PAGES:
        items, last = None, ""
        for _ in range(2):
            try:
                items, total, _raw = hira_get("hospInfoServicev2/getHospBasisList", {**base, "pageNo": page}, HIRA, (8, 30))
                break
            except requests.exceptions.RequestException as e:
                last = f"서버 응답 지연/실패({type(e).__name__})"
        if items is None:
            raise RuntimeError("심평원 " + last)
        out += items
        if not items or len(out) >= total:
            break
        page += 1
    return out, total


def fetch_hira(lat, lng, radius_km, dept_codes):
    cache, now = st.session_state.setdefault("hira_cache2", {}), time.time()
    jobs = [(c, d) for c in CL for d in (dept_codes or (None,))]

    def key(j):
        return (lat, lng, radius_km) + j

    def run(job):
        try:
            return job, *hira_one(lat, lng, radius_km, *job), None
        except Exception as e:  # noqa: BLE001
            return job, [], 0, str(e)[:140]

    errs = []
    todo = [j for j in jobs if key(j) not in cache or now - cache[key(j)][0] > 1800]
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
                                     "url": it.get("hospUrl", ""), "lat": float(it["YPos"]), "lng": float(it["XPos"]), "ykiho": it["ykiho"],
                                     "dr": num(it, "drTotCnt"), "sp": num(it, "mdeptSdrCnt"), "gp": num(it, "mdeptGdrCnt"),
                                     "tr": num(it, "mdeptIntnCnt") + num(it, "mdeptResdntCnt")}
            except (KeyError, ValueError):
                continue
    return list(rows.values()), errs, len(jobs), trunc


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_kakao(lat, lng, radius_km, code, query):
    docs = kakao("keyword", query=query, x=lng, y=lat, radius=min(int(radius_km * 1000), 20000), sort="distance", size=15, category_group_code=code)
    return [{"name": d["place_name"], "cl": "PH" if code == "PM9" else "?", "addr": d.get("road_address_name") or d.get("address_name", ""),
             "tel": d.get("phone", ""), "url": d.get("place_url", ""), "lat": float(d["y"]), "lng": float(d["x"]),
             "ykiho": "", "dr": 0.0, "sp": 0.0, "gp": 0.0, "tr": 0.0} for d in docs]


def dept_doctors(ykiho):
    now, hit = time.time(), _DD.get(ykiho)
    if hit and now - hit[0] < (86400 if hit[1] is not None else 600):
        if hit[1] is None:
            raise RuntimeError(hit[2])
        return hit[1]
    combos = sorted(((v, op, f) for v in DETAIL_VERSIONS for op, f in DD_OPS), key=lambda c: (c[0], c[1]) not in _DD_BEST)
    errs, empty_ok = [], False
    for ver, op, fields in combos:
        for extra in ({}, {"numOfRows": 100, "pageNo": 1}):
            try:
                items = hira_get(f"MadmDtlInfoService{ver}/{op}{ver}", {"ykiho": ykiho, **extra}, HIRA_DETAIL, 15)[0]
            except Exception as e:  # noqa: BLE001
                errs.append(f"{op}{ver}: {e}")
                if "NO_OPENAPI_SERVICE_ERROR" in str(e):
                    break
                continue
            out = []
            for it in items:
                name = it.get("dgsbjtCdNm") or it.get("dgsbjtNm") or ""
                n = next((num(it, f) for f in fields if it.get(f) not in (None, "")), 0.0)
                if name and n > 0:
                    out.append((name, n))
            if out:
                _DD_BEST[:] = [(ver, op)]
                _DD[ykiho] = (now, sorted(out, key=lambda x: -x[1]), "")
                return _DD[ykiho][1]
            empty_ok = True
    if empty_ok:
        _DD[ykiho] = (now, [], "")
        return []
    msg = " | ".join(errs[:4]) if errs else "응답이 비어 있어요"
    _DD[ykiho] = (now, None, msg)
    raise RuntimeError(msg)


@st.cache_data(ttl=86400, show_spinner=False)
def hospital_detail(ykiho):
    last = None
    for extra in ({}, {"numOfRows": 10, "pageNo": 1}):
        try:
            items = hira_get("MadmDtlInfoService2.8/getDtlInfo2.8", {"ykiho": ykiho, **extra}, HIRA_DETAIL, 15)[0]
            return items[0] if items else {}
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(str(last))


def hhmm(v):
    s = str(v if v is not None else "").strip().split(".")[0]
    if not s.isdigit() or len(s) > 4:
        return None
    h, m = int(s.zfill(4)[:2]), int(s.zfill(4)[2:])
    return h * 60 + m if (h < 24 and m < 60) or (h == 24 and m == 0) else None


def parse_hours(d):
    rows = []
    for ko, en in DAYS:
        s, e = hhmm(d.get(f"trmt{en}Start")), hhmm(d.get(f"trmt{en}End"))
        rows.append((ko, s, e) if s is not None and e is not None and e > s else (ko, None, None))
    return rows


def open_state(rows, now):
    if not any(r[1] is not None for r in rows):
        return None
    _, s, e = rows[now.weekday()]
    m = now.hour * 60 + now.minute
    if s is None:
        return "closed", "오늘은 휴진이거나 미신고예요"
    if s <= m < e:
        return "open", f"지금 진료 중 · {e // 60:02d}:{e % 60:02d}까지"
    return ("closed", f"진료 전 · {s // 60:02d}:{s % 60:02d} 시작") if m < s else ("closed", "오늘 진료가 끝났어요")


def build(rows, lat, lng, radius, depts=()):
    df = pd.DataFrame(rows, columns=COLS)
    if df.empty:
        return df
    df = df.drop_duplicates(["name", "lat", "lng"])
    df["dist"] = [haversine(lat, lng, a, b) for a, b in zip(df["lat"], df["lng"])]
    df = df[df["dist"] <= radius]
    df = df[[c == "PH" or dept_ok(n, depts) for c, n in zip(df["cl"], df["name"])]].copy()
    info = [PHARM if c == "PH" else CL.get(c, UNKNOWN) for c in df["cl"]]
    df["type"], df["color"] = [i[0] for i in info], [i[1] for i in info]
    return df.sort_values("dist").reset_index(drop=True)


def web_links(name, url=""):
    items = [("병원 공식 홈페이지", "의료진 소개 · 진료시간 · 예약", url)] if url else []
    items += [("의료진 검색", "네이버에서 소속 의료진 찾기", f"https://search.naver.com/search.naver?query={quote(name + ' 의료진')}"),
              ("위치 · 방문자 후기", "카카오맵에서 보기", f"https://map.kakao.com/?q={quote(name)}"),
              ("진료시간 · 전문의 검색", "구글에서 보기", f"https://www.google.com/search?q={quote(name + ' 전문의 진료시간')}")]
    return link_cards(items)


def card(r, rank=None, i=0):
    badge = f'<div class="badge{" top" if rank and rank <= 3 else ""}">{rank}</div>' if rank else f'<div class="badge" style="background:{r["color"]};color:#fff">약</div>'
    doc = ""
    if rank and r["dr"]:
        tot = r["dr"]
        segs = [(r["sp"], "#1D5FD1"), (r["gp"], "#6FA0EA"), (r["tr"], "#A9C6F2"), (max(tot - r["sp"] - r["gp"] - r["tr"], 0), "#D9E2EE")]
        doc = (f'<div class="hc-meta">의사 {int(tot)}명' + (f' · 전문의 {int(r["sp"])}명' if r["sp"] else "") + "</div>"
               '<div class="mini">' + "".join(f'<i style="width:{v / tot * 100:.1f}%;background:{c}"></i>' for v, c in segs if v > 0) + "</div>")
    if rank:
        doc += f'<div class="prox"><b>근접도</b><span><i style="width:{max(6, (1 - r["dist"] / radius) * 100):.0f}%"></i></span></div>'
    links = f'<a href="tel:{esc(r["tel"])}">전화</a>' if r["tel"] else ""
    links += f'<a target="_blank" href="https://map.kakao.com/link/to/{quote(r["name"])},{r["lat"]},{r["lng"]}">길찾기</a>'
    if r["url"]:
        links += f'<a target="_blank" href="{esc(r["url"])}">홈페이지</a>'
    if rank:
        links += f'<a target="_blank" href="https://search.naver.com/search.naver?query={quote(r["name"] + " 의료진")}">의료진</a>'
    return (f'<div class="hc" style="--i:{i};--acc:{r["color"]}"><div class="hc-top">{badge}<div style="min-width:0"><div class="hc-name">{esc(r["name"])}</div>'
            f'<div class="hc-meta"><span class="tag" style="background:{r["color"]}">{r["type"]}</span>{esc(r["addr"])}</div></div>'
            f'<div class="hc-dist">{r["dist"]:.1f} km<small>직선거리</small></div></div>{doc}<div class="links">{links}</div></div>')


MAP_JS = r"""
const D=__DATA__;
const msg=t=>{const e=document.getElementById('msg');e.style.display='block';e.textContent=t;};
function loadJs(urls,cb,i){i=i||0;if(i>=urls.length){msg('지도 라이브러리를 불러오지 못했어요. cdnjs/jsdelivr/unpkg 접근을 확인해 주세요.');return;}
const s=document.createElement('script');s.src=urls[i];s.onload=cb;s.onerror=()=>loadJs(urls,cb,i+1);document.head.appendChild(s);}
const css=document.createElement('link');css.rel='stylesheet';css.href='https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css';document.head.appendChild(css);
loadJs(['https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js','https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js','https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'],()=>{try{start();}catch(e){msg('지도 오류: '+e.message);}});
function start(){
 const map=L.map('m',{zoomSnap:.5});
 const near=D.p.filter(p=>p.rank===1).map(p=>[p.lat,p.lng]).concat([D.c]);
 if(near.length>1)map.fitBounds(near,{padding:[70,70],maxZoom:D.z});else map.setView(D.c,D.z);
 const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'}).addTo(map);
 let errors=0;tiles.on('tileerror',()=>{if(++errors===3)msg('지도 타일 서버에 접속하지 못했어요.');});
 L.circle(D.c,{radius:D.r*1000,color:'#3182F6',weight:1,fillOpacity:.04}).addTo(map);
 L.circleMarker(D.c,{radius:10,color:'#fff',weight:3,fillColor:'#1E6FD9',fillOpacity:1}).addTo(map).bindTooltip('내 위치',{permanent:true,direction:'top',offset:[0,-8]});
 D.p.forEach(p=>{const top=p.rank&&p.rank<=5,s=top?30:16;
  const icon=L.divIcon({className:'',iconSize:[s,s],iconAnchor:[s/2,s/2],html:'<div class="pin'+(top?' top':'')+'" style="width:'+s+'px;height:'+s+'px;border-radius:50%;background:'+p.color+';border:2px solid #fff;color:#fff;font:700 14px/'+(s-4)+'px sans-serif;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.35)">'+(top?p.rank:'')+'</div>'});
  L.marker([p.lat,p.lng],{icon}).addTo(map).bindPopup(p.html);});
 document.getElementById('me').onclick=()=>map.setView(D.c,D.z);
 setTimeout(()=>map.invalidateSize(),300);}
"""
MAP_CSS = ("html,body,#m{height:100%;margin:0;border-radius:20px}#msg{position:absolute;left:10px;bottom:10px;z-index:9999;background:#fff;color:#b42318;"
           "padding:8px 12px;border-radius:8px;font:13px sans-serif;box-shadow:0 1px 6px rgba(0,0,0,.25);display:none;max-width:80%}"
           "#me{position:absolute;right:10px;top:10px;z-index:9999;background:#1E6FD9;color:#fff;border:0;border-radius:99px;padding:8px 14px;font:700 13px sans-serif;"
           "box-shadow:0 4px 12px rgba(30,111,217,.35);cursor:pointer}"
           ".pin.top{animation:pl 2s infinite}@keyframes pl{0%{box-shadow:0 0 0 0 rgba(30,111,217,.5)}100%{box-shadow:0 0 0 14px rgba(30,111,217,0)}}")


def map_html(center, radius, df):
    pts = [{"lat": r["lat"], "lng": r["lng"], "color": r["color"], "rank": None if r["type"] == "약국" else i + 1,
            "html": f'<b>{esc(r["name"])}</b><br>{r["type"]} · {r["dist"]:.1f}km<br>{esc(r["addr"])}'} for i, r in df.iterrows()]
    data = json.dumps({"c": center, "r": radius, "z": MAP_ZOOM, "p": pts[:120]}, ensure_ascii=False).replace("</", "<\\/")
    return (f'<html><head><meta charset="utf-8"><style>{MAP_CSS}</style></head><body><div id="m"></div><button id="me">내 위치로</button><div id="msg"></div>'
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
            rows += fetch_kakao(la, ln, radius, "PM9", "약국")
        except Exception:  # noqa: BLE001
            warn = (warn + " " if warn else "") + "약국 정보를 불러오지 못했어요."
    return rows, err, warn


def tidy_time(v):
    return re.sub(r"(?<!\d)(\d{2})(\d{2})(?!\d)", r"\1:\2", v)


def show_hospital_info(r):
    st.markdown('<div class="sec" style="margin-top:22px">진료시간 · 운영 정보</div><div class="sub" style="margin:-8px 0 10px">'
                f'{esc(r["name"])}이(가) 심평원에 신고한 정보예요. 신고하지 않은 병원은 비어 있어요.</div>', unsafe_allow_html=True)
    if not (r["ykiho"] and DETAIL_ON):
        return
    ph = st.empty()
    ph.markdown(skel(2), unsafe_allow_html=True)
    try:
        d = hospital_detail(r["ykiho"])
    except Exception as e:  # noqa: BLE001
        ph.empty()
        st.caption(UNREG if detail_off(e) else f"진료시간을 불러오지 못했어요: {str(e)[:300]}")
        return
    ph.empty()
    rows, now = parse_hours(d), datetime.now(KST)
    state = open_state(rows, now)
    if state is None:
        st.info("이 병원은 요일별 진료시간을 신고하지 않았어요. 공식 홈페이지나 전화로 확인해 주세요.")
    else:
        st.markdown('<div class="chart"><div class="hh"><div><div class="ct">요일별 진료시간</div><div class="cs" style="margin:0">주황 선은 지금 시각이에요</div></div>'
                    + open_badge(*state) + "</div>" + week_hours(rows, now.weekday(), now.hour * 60 + now.minute) + "</div>", unsafe_allow_html=True)
    notes = [f"{lab} {tidy_time(v)}" for lab, key in (("점심시간", "lunchWeek"), ("접수 마감", "rcvWeek"), ("토요일 점심", "lunchSat"),
                                                     ("토요일 접수 마감", "rcvSat"), ("일요일", "noTrmtSun"), ("공휴일", "noTrmtHoli"))
             if (v := str(d.get(key) or "").strip())]
    notes += [n for n, key in (("응급실 주간 운영", "emyDayYn"), ("응급실 야간 운영", "emyNgtYn")) if str(d.get(key) or "").upper() == "Y"]
    if notes:
        st.markdown('<div style="margin-top:10px">' + "".join(f'<span class="chip">{esc(n)}</span>' for n in notes) + "</div>", unsafe_allow_html=True)
    st.caption("공휴일·임시 휴진은 반영되지 않아요. 방문 전에 전화로 확인해 주세요. 출처: 건강보험심사평가원 의료기관별상세정보서비스")


def show_doctors(hosp):
    st.markdown('<div class="sec">의료진 정보</div><div class="sub" style="margin:-8px 0 12px">가까운 병원 10곳의 의사 구성을 한 그래프로 비교해요. 막대 길이는 의사 수라서 병원 규모 차이가 그대로 보여요.</div>',
                unsafe_allow_html=True)
    h = hosp[hosp["dr"] > 0].head(10).reset_index(drop=True)
    if h.empty:
        st.info("의사 수는 심평원 데이터에서만 제공돼요. 지금은 카카오 데이터로 보고 있어서 표시할 수 없어요.")
        return
    names = [f"{r['name']} · {r['type']} · {r['dist']:.1f}km" for _, r in h.iterrows()]
    r = h.iloc[names.index(st.selectbox("병원 선택", names, key="doc_pick"))]
    keys = ["전문의", "일반의", "수련의", "기타(치과·한방 등)"]
    rows = [(f"{x['name']} · {x['dist']:.1f}km", dict(zip(keys, [x["sp"], x["gp"], x["tr"], max(x["dr"] - x["sp"] - x["gp"] - x["tr"], 0)]))) for _, x in h.iterrows()]
    ratio = (h["sp"] / h["dr"]).clip(upper=1) * 100
    my_ratio = min(r["sp"] / r["dr"], 1) * 100 if r["dr"] else 0
    st.markdown(kpis([("의사 총수", f"{cnt(r['dr'])}명", f"가까운 {len(h)}곳 중앙값 {h['dr'].median():,.0f}명"),
                      ("전문의", f"{cnt(r['sp'])}명", f"비율 {my_ratio:.0f}% · 중앙값 {ratio.median():.0f}%"),
                      ("일반의", f"{cnt(r['gp'])}명"), ("수련의(인턴·레지던트)", f"{cnt(r['tr'])}명")]), unsafe_allow_html=True)
    st.markdown('<div class="chart"><div class="ct">의사 구성 비교</div><div class="cs">선택한 병원이 굵게 표시돼요 · 막대에 마우스를 올리면 인원이 보여요</div>'
                + stack_bars(rows, list(zip(keys, ["#1D5FD1", "#6FA0EA", "#A9C6F2", "#D9E2EE"])), on=f"{r['name']} · {r['dist']:.1f}km") + "</div>",
                unsafe_allow_html=True)
    t = pd.DataFrame({"병원": h["name"], "종별": h["type"], "거리": h["dist"], "의사": h["dr"], "전문의": h["sp"], "전문의 비율": ratio})
    with st.expander("표로 보기"):
        st.markdown(table_html(t, fmts={"거리": lambda v: f"{v:.1f}km", "의사": lambda v: f"{v:,.0f}명", "전문의": lambda v: f"{v:,.0f}명",
                                        "전문의 비율": lambda v: f"{v:.0f}%"}, heat={"의사": None, "전문의": None, "전문의 비율": 100},
                               rank=True, chips={"종별": TYPE_COLORS}), unsafe_allow_html=True)
        st.caption("순번은 가까운 순이에요. 막대는 표 안에서 가장 큰 값 대비 길이이고, 전문의 비율 = 의과 전문의 ÷ 의사 총수예요. (건강보험심사평가원 병원정보서비스 기준)")
    if r["ykiho"] and DETAIL_ON:
        ph = st.empty()
        ph.markdown(skel(2), unsafe_allow_html=True)
        try:
            data = dept_doctors(r["ykiho"])
            ph.empty()
            if data:
                st.markdown('<div class="chart" style="margin-top:12px"><div class="ct">진료과목별 전문의</div><div class="cs">이 병원의 과별 전문의 수</div>'
                            + bars(data, top=True, share=False) + "</div>", unsafe_allow_html=True)
            else:
                st.caption("이 병원은 진료과목별 전문의 정보가 없어요.")
        except Exception as e:  # noqa: BLE001
            ph.empty()
            st.caption(UNREG if detail_off(e) else f"진료과목별 정보를 불러오지 못했어요: {str(e)[:400]}")
    show_hospital_info(r)
    st.markdown('<div class="sec" style="margin-top:22px">더 알아보기</div><div class="sub" style="margin:-8px 0 4px">'
                '의사 개인의 이름·경력은 심평원 공개 API에 없어서, 아래 외부 링크에서 확인할 수 있어요.</div>' + web_links(r["name"], r["url"]),
                unsafe_allow_html=True)


def show_compare(hosp, depts):
    st.markdown('<div class="sec" style="margin-top:6px">진료과별 전문의 비교</div><div class="sub" style="margin:-8px 0 12px">'
                '가까운 병원급 이상 의료기관(최대 8곳)에서 선택한 진료과 전문의가 몇 명인지 비교해요. 전문의가 많을수록 해당 과 진료 규모가 크다는 뜻이에요.</div>',
                unsafe_allow_html=True)
    bases = list(dict.fromkeys(b for b in map(base_dept, depts) if b))
    elig = hosp[hosp["cl"].isin(HOSP_CL) & (hosp["ykiho"] != "")].head(8)
    if elig.empty or not bases:
        st.info("비교할 병원급 이상 의료기관이나 진료과가 없어요. 반경을 넓히거나 진료과를 골라 주세요.")
        return
    targets = tuple((r["ykiho"], r["name"], r["type"], float(r["dist"])) for _, r in elig.iterrows())
    sig = (tuple(t[0] for t in targets), tuple(bases))
    st.caption("비교 진료과: " + ", ".join(bases))
    busy = st.session_state.get("dc_job") is not None
    if st.button("전문의 수 불러오는 중이에요" if busy else "전문의 수 비교하기", type="primary", use_container_width=True,
                 key="dc_busy" if busy else "dc_idle", disabled=busy):
        st.session_state["dc_job"] = (targets, tuple(bases))
        st.rerun()
    if busy:
        st.markdown(skel(3), unsafe_allow_html=True)
        job_t, job_b = st.session_state["dc_job"]

        def run(t):
            try:
                return t, dict(dept_doctors(t[0])), None
            except Exception as e:  # noqa: BLE001
                return t, {}, f"{t[1]}: {str(e)[:90]}"

        rows, errs = [], []
        try:
            with ThreadPoolExecutor(4) as ex:
                for (_, name, typ, dist), by, err in ex.map(run, job_t):
                    if err:
                        errs.append(err)
                    else:
                        rows.append({"hosp": name, "type": typ, "dist": dist, "sel": sum(by.get(b, 0) for b in job_b), "all": sum(by.values())})
            st.session_state["dc_res"] = {"sig": (tuple(t[0] for t in job_t), job_b), "rows": rows, "errs": errs, "n": len(job_t)}
        finally:
            st.session_state["dc_job"] = None
        st.rerun()
    res = st.session_state.get("dc_res")
    if not res or res["sig"] != sig:
        if res:
            st.caption("위치·반경·진료과가 바뀌어서 이전 결과를 숨겼어요. 다시 비교해 주세요.")
        return
    if len(res["errs"]) == res["n"]:
        st.warning(UNREG if detail_off(res["errs"][0]) else "전문의 정보를 불러오지 못했어요. (" + res["errs"][0] + ")")
        return
    if res["errs"]:
        st.caption(f"{len(res['errs'])}곳은 정보를 불러오지 못해서 빠졌어요.")
    d = pd.DataFrame(res["rows"]).sort_values(["sel", "dist"], ascending=[False, True]).reset_index(drop=True)
    if d["sel"].sum() == 0:
        st.info("선택한 진료과 전문의 정보가 있는 병원이 없어요. 진료과를 바꿔 보세요.")
        return
    top, near = d.iloc[0], d.sort_values("dist").iloc[0]
    st.markdown(kpis([("비교한 병원", f"{len(d)}곳"), ("전문의 최다", f"{top['sel']:,.0f}명", esc(top["hosp"])),
                      ("가장 가까운 병원", f"{near['sel']:,.0f}명", esc(near["hosp"]) + f" · {near['dist']:.1f}km")]), unsafe_allow_html=True)
    msg = (f"{'·'.join(bases)} 전문의가 가장 많은 곳은 {top['hosp']}({top['sel']:,.0f}명, {top['dist']:.1f}km)예요. "
           f"가장 가까운 {near['hosp']}에는 {near['sel']:,.0f}명이 있어요.")
    st.markdown(f'<div class="insight">{esc(msg)}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.7, 1], gap="medium")
    c1.markdown('<div class="chart"><div class="ct">병원별 전문의 수</div><div class="cs">선택 진료과 합계 · 가장 많은 곳이 진하게 표시돼요</div>'
                + bars([(f"{r['hosp']} · {r['dist']:.1f}km", r["sel"]) for _, r in d.iterrows()], share=False, top=True) + "</div>", unsafe_allow_html=True)
    by_type = d.groupby("type")["sel"].mean().sort_values(ascending=False)
    if len(by_type) >= 2:
        c2.markdown('<div class="chart"><div class="ct">종별 평균 전문의</div><div class="cs">같은 진료과, 병원 종별 평균</div>'
                    + bars([(k, round(v, 1)) for k, v in by_type.items()], share=False, color="#0E9F8E") + "</div>", unsafe_allow_html=True)
    t = pd.DataFrame({"병원": d["hosp"], "종별": d["type"], "거리": d["dist"], "선택 진료과 전문의": d["sel"], "전체 전문의": d["all"],
                      "해당 과 비중": (d["sel"] / d["all"].replace(0, float("nan"))) * 100})
    st.markdown('<div style="height:10px"></div>' + table_html(t, fmts={"거리": lambda v: f"{v:.1f}km", "선택 진료과 전문의": lambda v: f"{v:,.0f}명",
                                                                       "전체 전문의": lambda v: f"{v:,.0f}명", "해당 과 비중": lambda v: f"{v:.0f}%"},
                                                         heat={"선택 진료과 전문의": None, "전체 전문의": None, "해당 과 비중": 100},
                                                         rank=True, chips={"종별": TYPE_COLORS}), unsafe_allow_html=True)
    st.caption("진료과목별 전문의 수는 건강보험심사평가원 의료기관별상세정보서비스 기준이에요. 의사 개인의 이름·경력은 공개 API에 없어서 병원별 링크로 연결해요.")


picked = st.session_state.get("pick_disease") or {}
topbar("콕콕", "병원 찾기")
hero("FIND A HOSPITAL", "추천 진료과 기준으로\n내 주변 병원을 찾아보세요", "지도와 거리순 목록, 의사 구성, 진료시간, 진료과별 전문의 수를 한곳에서 비교해요.",
     ("전국 병원·약국", "의사·전문의 현황", "진료시간", "직선거리 기준"))
st.page_link("main.py", label="증상 다시 선택")

if not (HIRA or KAKAO):
    st.error("`.env`에 HIRA_SERVICE_KEY 또는 KAKAO_REST_API_KEY가 필요해요. (키 이름과 따옴표를 확인해 주세요)")
    st.stop()

if picked:
    st.markdown(f"### {esc(picked.get('n', ''))} "
                + (f"<span style='color:#6B7684;font-size:.9rem'>상병코드 {esc(picked.get('c', ''))}</span>" if picked.get("c") else ""), unsafe_allow_html=True)

loc = current_location()
with st.container(key="filters"):
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
        default = [x for x in recommended if base_dept(x)] or ["내과"]
        depts = st.multiselect("진료과", sorted(set(DEPT) | set(default)), default=default)
    with c4:
        if st.button("내 위치", help="현재 위치로 이동", use_container_width=True):
            st.session_state.pop("loc", None)
            st.session_state["geo_n"] = st.session_state.get("geo_n", 0) + 1
            st.rerun()
    radius = st.pills("검색 반경", [1, 2, 3, 5, 10, 20, 30], format_func=lambda x: f"{x}km", default=3, selection_mode="single") or 3

lat, lng = loc["lat"], loc["lng"]
st.caption(f"{loc['label']} 기준")
if recommended:
    st.markdown("**추천 진료과** &nbsp;" + "".join(f'<span class="chip">{esc(x)}</span>' for x in recommended), unsafe_allow_html=True)

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
    components.html(map_html([lat, lng], radius, pd.concat([hosp.head(60), pharmacies.head(20)]) if not df.empty else df), height=640)
    st.caption("지도는 내 위치와 가장 가까운 병원이 보이도록 최대한 확대돼요. 숫자는 가까운 순위 상위 5곳이고, 점을 누르면 상세가 보여요.")
with right:
    if hosp.empty:
        st.markdown('<div class="empty"><b>반경 안에서 병원을 찾지 못했어요</b><br>반경을 넓히거나 진료과를 바꿔 보세요.</div>', unsafe_allow_html=True)
    else:
        st.markdown(kpis([("병원", f"{cnt(len(hosp))}곳"), ("가장 가까운 곳", f"{hosp['dist'].min():.1f}km"),
                          ("가장 가까운 병원", f'<span style="font-size:.95rem">{esc(hosp.loc[0, "name"])}</span>')]), unsafe_allow_html=True)
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
    if DETAIL_ON:
        t_doc, t_cmp = st.tabs(["의료진 · 진료시간", "진료과별 전문의 비교"])
        with t_doc:
            show_doctors(hosp)
        with t_cmp:
            show_compare(hosp, depts)
    else:
        show_doctors(hosp)