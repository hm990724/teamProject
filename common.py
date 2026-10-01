import html
import os
import xml.etree.ElementTree as ET
from urllib.parse import unquote

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

HIRA_BASE = "https://apis.data.go.kr/B551182"

BASE_CSS = """
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css");
@property --n{syntax:'<integer>';inherits:false;initial-value:0}
:root{--bl:#3182F6;--bl2:#1B64DA;--bg:#F2F4F6;--tx:#191F28;--sb:#6B7684;--ln:#E5E8EB;--soft:#E8F3FF;--ease:cubic-bezier(.2,.8,.2,1)}
html,body,.stApp,[class*="css"]{font-family:"Pretendard","Malgun Gothic",sans-serif!important;color:var(--tx);letter-spacing:-.01em}
.stApp{background:var(--bg)}.block-container{max-width:1240px;padding-top:1.2rem}
#MainMenu,footer{visibility:hidden}[data-testid="stStatusWidget"]{display:none}
header[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebarNav"],[data-testid="collapsedControl"],[data-testid="stSidebar"]{display:none}

@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes shine{to{background-position:-200% 0}}
@keyframes cnt{from{--n:0}to{--n:var(--to)}}
@keyframes pop{0%{transform:scale(.8);opacity:0}60%{transform:scale(1.06)}100%{transform:scale(1);opacity:1}}
.rise{animation:rise .55s var(--ease) both;animation-delay:calc(var(--i,0)*70ms)}
.cnt{animation:cnt 1.1s var(--ease) both;counter-reset:n var(--n)}.cnt::after{content:counter(n)}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}

.topbar{display:flex;align-items:center;gap:14px;padding:6px 4px 18px}
.logo{width:42px;height:42px;border-radius:14px;background:var(--bl);color:#fff;display:flex;align-items:center;justify-content:center;font-size:1.05rem;font-weight:800;animation:pop .6s var(--ease) both}
.topbar b{font-size:1.3rem;font-weight:800;letter-spacing:-.03em;display:block}.topbar span{color:var(--sb);font-size:.88rem}
.sec{font-size:1.1rem;font-weight:800;letter-spacing:-.02em;margin:26px 0 12px}
.sub{font-size:.8rem;color:var(--sb);line-height:1.5}
.note{font-size:.78rem;color:var(--sb);margin-top:14px;line-height:1.6}
.panel{background:#fff;border-radius:20px;padding:20px 22px;margin-bottom:12px;box-shadow:0 2px 12px rgba(25,31,40,.04);animation:rise .5s var(--ease) both}
.chip{display:inline-block;padding:5px 12px;border-radius:999px;font-size:.82rem;font-weight:600;background:var(--soft);color:var(--bl);margin:0 6px 6px 0}
.chip.g{background:#F2F4F6;color:var(--sb);font-weight:500;font-size:.74rem;padding:3px 9px}
.steps{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px}
.steps span{font-size:.82rem;font-weight:600;color:var(--sb);background:#fff;border-radius:999px;padding:6px 14px 6px 8px;display:inline-flex;align-items:center}
.steps b{display:inline-flex;width:20px;height:20px;border-radius:50%;background:var(--bl);color:#fff;font-size:.72rem;align-items:center;justify-content:center;margin-right:8px}
.rg{font-size:.78rem;color:var(--sb);font-weight:600}.rgn{font-size:1.45rem;font-weight:800;letter-spacing:-.03em;margin-top:2px}

.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:6px 0 14px}
.kpi{background:#fff;border-radius:18px;padding:16px 18px;box-shadow:0 2px 12px rgba(25,31,40,.04);animation:rise .5s var(--ease) both;animation-delay:calc(var(--i,0)*70ms)}
.kpi .k{font-size:.76rem;color:var(--sb);font-weight:600}.kpi .n{font-size:1.45rem;font-weight:800;margin-top:4px;letter-spacing:-.03em}
.kpi .s{font-size:.74rem;color:var(--sb);margin-top:4px}
.vf{display:inline-block;font-size:.7rem;font-weight:700;padding:2px 8px;border-radius:999px;margin-left:6px;vertical-align:middle}
.vf.ok{background:#E6F8EE;color:#0B8F4A}.vf.warn{background:#FFF3E0;color:#C26A00}

.rk{display:flex;gap:14px;align-items:flex-start;padding:6px 2px;animation:rise .5s var(--ease) both;animation-delay:calc(var(--i,0)*70ms)}
.rn{flex:0 0 30px;height:30px;border-radius:10px;background:#F2F4F6;color:var(--sb);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.86rem}
.rn.top{background:var(--bl);color:#fff}
.lv{font-size:.72rem;font-weight:700;padding:3px 9px;border-radius:999px;margin-left:8px;vertical-align:middle}
.lv.h{background:var(--soft);color:var(--bl)}.lv.m{background:#E6F8EE;color:#0B8F4A}.lv.l{background:#F2F4F6;color:var(--sb)}

.bars{display:flex;flex-direction:column;gap:10px;margin:6px 0 4px}
.br{display:grid;grid-template-columns:minmax(80px,180px) 1fr minmax(90px,130px);gap:12px;align-items:center;font-size:.86rem}
.bl{color:var(--sb);font-weight:600;line-height:1.3;word-break:keep-all}
.bt{height:12px;border-radius:999px;background:#F2F4F6;overflow:hidden}
.bf{height:100%;border-radius:999px;transform-origin:left;animation:grow .9s var(--ease) both;animation-delay:calc(var(--i,0)*60ms)}
.bv{font-weight:700;text-align:right}.bv small{color:var(--sb);font-weight:500;margin-left:6px}

.tw{background:#fff;border-radius:18px;overflow-x:auto;box-shadow:0 2px 12px rgba(25,31,40,.04);animation:rise .5s var(--ease) both}
.tw.sc{max-height:380px;overflow-y:auto}
.tbl{width:100%;border-collapse:separate;border-spacing:0;font-size:.86rem}
.tbl th{position:sticky;top:0;background:#F9FAFB;color:var(--sb);font-weight:600;text-align:left;padding:12px 16px;white-space:nowrap;z-index:1}
.tbl td{padding:12px 16px;border-top:1px solid #F2F4F6;white-space:nowrap}
.tbl td.num,.tbl th.num{text-align:right;font-variant-numeric:tabular-nums}
.tbl tbody tr{transition:background .15s}.tbl tbody tr:hover{background:#F9FAFB}

.sk{display:flex;flex-direction:column;gap:12px;padding:6px 0}
.sk i{display:block;height:64px;border-radius:16px;background:linear-gradient(90deg,#E9ECEF 25%,#F6F7F8 45%,#E9ECEF 65%);background-size:200% 100%;animation:shine 1.3s linear infinite}
.sk i:nth-child(2){opacity:.75}.sk i:nth-child(3){opacity:.5}

.stButton>button,.stLinkButton>a{border-radius:14px;font-weight:700;min-height:48px;border:0;transition:transform .15s var(--ease),background .2s,box-shadow .2s}
.stButton>button:active{transform:scale(.96)}
.stButton button[kind="primary"],.stButton button[data-testid="stBaseButton-primary"]{background:var(--bl);color:#fff}
.stButton button[kind="primary"]:hover,.stButton button[data-testid="stBaseButton-primary"]:hover{background:var(--bl2);box-shadow:0 8px 20px rgba(49,130,246,.28);transform:translateY(-1px)}
.stButton button[kind="secondary"],.stButton button[data-testid="stBaseButton-secondary"]{background:#fff;color:var(--tx);box-shadow:inset 0 0 0 1px var(--ln)}
.stButton button[kind="secondary"]:hover,.stButton button[data-testid="stBaseButton-secondary"]:hover{background:#F9FAFB;box-shadow:inset 0 0 0 1px #CBD1D8}
[class*="_busy"] button:disabled{opacity:1!important;background:var(--bl)!important;color:#fff!important;cursor:progress}
[class*="_busy"] button:disabled::before{content:"";width:16px;height:16px;margin-right:10px;border:2.5px solid rgba(255,255,255,.35);border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite}

[data-baseweb="input"],[data-baseweb="textarea"],[data-baseweb="select"]>div{border-radius:14px!important;background:#fff!important;border:1px solid var(--ln)!important;transition:border-color .2s,box-shadow .2s}
[data-baseweb="input"]:focus-within,[data-baseweb="textarea"]:focus-within{border-color:var(--bl)!important;box-shadow:0 0 0 4px rgba(49,130,246,.15)}
[data-baseweb="input"] input,[data-baseweb="textarea"] textarea{background:#fff!important}
[data-baseweb="tab-highlight"]{background:var(--bl)!important}
[data-baseweb="tab"]{font-weight:700}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:20px!important;border-color:transparent!important;background:#fff;box-shadow:0 2px 12px rgba(25,31,40,.04)}
[data-testid="stExpander"]{border:0!important;background:#fff;border-radius:18px;box-shadow:0 2px 12px rgba(25,31,40,.04)}
[data-testid="stExpander"] summary{font-weight:700}
[data-testid="stButtonGroup"] button{border-radius:12px;font-weight:600}
.stAlert{border-radius:16px}
@keyframes growy{from{transform:scaleY(0)}to{transform:scaleY(1)}}
.chart{background:#fff;border-radius:20px;padding:18px 20px 14px;box-shadow:0 2px 12px rgba(25,31,40,.04);animation:rise .5s var(--ease) both;height:100%}
.ct{font-size:.9rem;font-weight:800;margin-bottom:2px}.cs{font-size:.76rem;color:var(--sb);margin-bottom:14px}
.vbars{display:flex;gap:6px;align-items:stretch;height:220px;padding-top:6px}
.vb{flex:1;display:flex;flex-direction:column;align-items:center;min-width:0;cursor:default}
.vb .vv{font-size:.68rem;font-weight:700;color:var(--sb);height:16px}
.vb .vc{flex:1;width:100%;display:flex;align-items:flex-end}
.vb .vc i{display:block;width:100%;border-radius:9px 9px 4px 4px;background:#D6E8FF;transform-origin:bottom;animation:growy .8s var(--ease) both;animation-delay:calc(var(--i,0)*55ms);transition:filter .2s}
.vb:hover .vc i{filter:brightness(.94)}
.vb.pk .vc i{background:var(--bl)}.vb.pk .vv{color:var(--bl)}
.vb.me .vc i{background:#FF9F43}.vb.me .vv{color:#E07B00}
.vb .vl{font-size:.7rem;color:var(--sb);margin-top:8px;white-space:nowrap}
.lg{display:flex;gap:14px;font-size:.74rem;color:var(--sb);margin-top:12px;flex-wrap:wrap}
.lg b{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:6px}
.dn{display:flex;align-items:center;gap:22px;flex-wrap:wrap;padding:6px 0}
.dr{width:132px;height:132px;border-radius:50%;display:flex;align-items:center;justify-content:center;animation:pop .8s var(--ease) both}
.dc{width:86px;height:86px;border-radius:50%;background:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;font-weight:800;font-size:1.15rem}
.dc small{font-size:.68rem;color:var(--sb);font-weight:600}
.dl{display:flex;flex-direction:column;gap:8px;font-size:.84rem}.dl b{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px}
.insight{background:var(--soft);color:#1B4F9C;border-radius:16px;padding:14px 18px;font-size:.9rem;font-weight:600;line-height:1.6;margin:8px 0 14px;animation:rise .5s var(--ease) both}

/* ── 입력칸: 완전 불투명 흰 배경 + 진한 테두리 ── */
[data-baseweb="input"],[data-baseweb="textarea"],[data-baseweb="select"]>div{background:#fff!important;border:1.5px solid #8B95A1!important;border-radius:14px!important;box-shadow:0 1px 3px rgba(25,31,40,.10)!important}
[data-baseweb="base-input"]{background:#fff!important;border:0!important;border-radius:12px!important}
[data-baseweb="input"]:hover,[data-baseweb="textarea"]:hover,[data-baseweb="select"]>div:hover{border-color:var(--bl)!important}
[data-baseweb="input"]:focus-within,[data-baseweb="textarea"]:focus-within,[data-baseweb="select"]>div:focus-within{border-color:var(--bl)!important;box-shadow:0 0 0 3px rgba(49,130,246,.22)!important}
[data-baseweb="input"] input,[data-baseweb="textarea"] textarea{background:#fff!important;color:var(--tx)!important;-webkit-text-fill-color:var(--tx)!important;caret-color:var(--bl)}
[data-baseweb="select"] *{color:var(--tx)!important;-webkit-text-fill-color:var(--tx)!important}
input::placeholder,textarea::placeholder{color:#6B7684!important;-webkit-text-fill-color:#6B7684!important;opacity:1!important}
textarea:disabled,input:disabled{-webkit-text-fill-color:#6B7684!important;opacity:1!important;background:#F9FAFB!important}
.stNumberInput button{background:#F2F4F6!important;color:var(--tx)!important}
[data-testid="stWidgetLabel"] p{color:var(--tx)!important;font-weight:700;font-size:.88rem}
[data-testid="stButtonGroup"] button{background:#fff!important;border:1.5px solid #B0B8C1!important;color:var(--tx)!important}
[data-testid="stButtonGroup"] button[aria-checked="true"],[data-testid="stButtonGroup"] button[aria-pressed="true"],[data-testid="stButtonGroup"] button[kind*="Active"]{background:var(--bl)!important;border-color:var(--bl)!important;color:#fff!important}

/* ── 가격 비교 차트 ── */
.pm{display:flex;flex-direction:column;gap:4px;margin:4px 0}
.pr{display:grid;grid-template-columns:minmax(110px,210px) 1fr minmax(96px,130px);gap:14px;align-items:center;padding:8px 6px;border-radius:12px;transition:background .15s;animation:rise .5s var(--ease) both;animation-delay:calc(var(--i,0)*50ms)}
.pr:hover{background:#F6F8FA}
.pl{font-size:.84rem;font-weight:600;line-height:1.35;word-break:keep-all}
.pl em{display:inline-block;font-style:normal;font-size:.68rem;font-weight:700;color:var(--bl);background:var(--soft);border-radius:999px;padding:1px 7px;margin-left:6px;vertical-align:middle}
.pt{position:relative;height:22px}
.pt::before{content:"";position:absolute;left:0;right:0;top:50%;height:2px;margin-top:-1px;background:#EEF1F4;border-radius:2px}
.ps{position:absolute;left:0;top:50%;height:4px;margin-top:-2px;border-radius:4px;transform-origin:left;animation:grow .9s var(--ease) both;animation-delay:calc(var(--i,0)*50ms)}
.pd{position:absolute;top:50%;width:16px;height:16px;margin:-8px 0 0 -8px}
.pd i{display:block;width:100%;height:100%;border-radius:50%;border:3px solid #fff;box-shadow:0 1px 5px rgba(25,31,40,.3);animation:pop .6s var(--ease) both;animation-delay:calc(var(--i,0)*50ms + 450ms)}
.pd.mk i{box-shadow:0 0 0 4px rgba(49,130,246,.25),0 1px 5px rgba(25,31,40,.3)}
.pmd{position:absolute;top:0;bottom:0;width:0;border-left:2px dashed #B0B8C1}
.pv{text-align:right;font-weight:800;font-size:.9rem;white-space:nowrap}
.pv small{display:block;font-weight:700;font-size:.72rem}
.pv small.up{color:#E07B00}.pv small.dw{color:#0B8F4A}.pv small.eq{color:var(--sb)}
@media (max-width:700px){.pr{grid-template-columns:1fr;gap:4px}.pv{text-align:left}}
"""


def env(name):
    v = (os.getenv(name) or "").strip().strip('"').strip("'").strip()
    return unquote(v) if "%" in v else (v or None)


def setup(title, css=""):
    st.set_page_config(page_title=title, page_icon=None, layout="wide", initial_sidebar_state="collapsed")
    st.markdown(f"<style>{BASE_CSS}{css}</style>", unsafe_allow_html=True)


def topbar(title, sub):
    st.markdown(f'<div class="topbar"><div class="logo">콕</div><div><b>{html.escape(title)}</b><span>{html.escape(sub)}</span></div></div>',
                unsafe_allow_html=True)


def skel(n=3):
    return '<div class="sk">' + "<i></i>" * n + "</div>"


def cnt(n):
    n = int(n)
    return f'<span class="cnt" style="--to:{n}"></span>' if n < 10000 else f"{n:,}"


def kpis(items):
    """items: (라벨, 값(HTML 허용), 보조문구)"""
    cells = ""
    for i, item in enumerate(items):
        k, v = item[0], item[1]
        s = f'<div class="s">{item[2]}</div>' if len(item) > 2 and item[2] else ""
        cells += f'<div class="kpi" style="--i:{i}"><div class="k">{html.escape(k)}</div><div class="n">{v}</div>{s}</div>'
    return f'<div class="kpis">{cells}</div>'


def bars(items, color="#3182F6", unit="명", share=True, top=False):
    """items: [(라벨, 값)] → 가로 막대. top=True면 최댓값만 진하게"""
    items = [(l, float(v)) for l, v in items]
    mx = max((v for _, v in items), default=0) or 1
    tot = sum(v for _, v in items) or 1
    pick = min((v for _, v in items), default=0) if top == "min" else mx
    rows = "".join(
        f'<div class="br" style="--i:{i}"><div class="bl" title="{html.escape(str(l))}">{html.escape(str(l))}</div>'
        f'<div class="bt"><div class="bf" style="width:{v / mx * 100:.1f}%;background:{color if (not top or v == pick) else "#B9D7FF"}"></div></div>'
        f'<div class="bv">{v:,.0f}{unit}' + (f"<small>{v / tot * 100:.1f}%</small>" if share else "") + "</div></div>"
        for i, (l, v) in enumerate(items))
    return f'<div class="bars">{rows}</div>'


def pricemap(items, med=None, mark=None, unit="원"):
    """items: [(라벨, 가격)] → 가격 비교 차트(막대 + 점). 최저=초록, 최고=주황, mark 라벨=파란 링, med=중앙값 점선"""
    items = [(str(l), float(v)) for l, v in items]
    if not items:
        return ""
    vals = [v for _, v in items]
    lo, hi = min(vals), max(vals)
    axis = hi * 1.08 or 1
    med = float(med) if med else None
    rows = ""
    for i, (l, v) in enumerate(items):
        col = "#00B493" if lo != hi and v == lo else "#FF9F43" if lo != hi and v == hi else "#3182F6"
        pos = v / axis * 100
        badge = "<em>가장 가까움</em>" if mark is not None and l == mark else ""
        diff = ""
        if med:
            d = (v - med) / med * 100
            cls, txt = ("eq", "중앙값 수준") if abs(d) < 0.5 else (("up", f"중앙값 +{d:.0f}%") if d > 0 else ("dw", f"중앙값 {d:.0f}%"))
            diff = f'<small class="{cls}">{txt}</small>'
        mline = f'<u class="pmd" style="left:{med / axis * 100:.1f}%"></u>' if med else ""
        rows += (f'<div class="pr" style="--i:{i}"><div class="pl">{html.escape(l)}{badge}</div>'
                 f'<div class="pt">{mline}<i class="ps" style="width:{pos:.1f}%;background:linear-gradient(90deg,#E8F3FF,{col})"></i>'
                 f'<span class="pd{" mk" if badge else ""}" style="left:{pos:.1f}%"><i style="background:{col}"></i></span></div>'
                 f'<div class="pv">{v:,.0f}{unit}{diff}</div></div>')
    legend = ('<div class="lg"><span><b style="background:#00B493"></b>최저가</span><span><b style="background:#FF9F43"></b>최고가</span>'
              '<span><b style="background:#3182F6"></b>그 외</span>'
              + ('<span><b style="width:0;height:11px;background:none;border-left:2px dashed #B0B8C1;border-radius:0"></b>중앙값</span>' if med else "")
              + "</div>")
    return f'<div class="pm">{rows}</div>{legend}'


def vbars(items, mine=None, unit="명"):
    """items: [(라벨, 값, 툴팁라벨)] → 세로 막대. 최댓값=파랑, mine 라벨=주황"""
    vals = [float(i[1]) for i in items]
    mx, tot = (max(vals, default=0) or 1), (sum(vals) or 1)
    cols = ""
    for i, it in enumerate(items):
        l, v = it[0], float(it[1])
        tip = it[2] if len(it) > 2 else l
        cls = "vb" + (" me" if mine is not None and tip == mine else "") + (" pk" if v == mx else "")
        cols += (f'<div class="{cls}" style="--i:{i}" title="{html.escape(str(tip))}: {v:,.0f}{unit} ({v / tot * 100:.1f}%)">'
                 f'<div class="vv">{v / tot * 100:.0f}%</div><div class="vc"><i style="height:{max(v / mx * 100, 1.5):.1f}%"></i></div>'
                 f'<div class="vl">{html.escape(str(l))}</div></div>')
    legend = '<div class="lg"><span><b style="background:#3182F6"></b>가장 많은 구간</span>'
    if mine is not None:
        legend += '<span><b style="background:#FF9F43"></b>입력하신 연령대</span>'
    return f'<div class="vbars">{cols}</div>{legend}</div>'


def donut(items, colors=("#3182F6", "#FF8FB1", "#B0B8C1", "#6ED3C3")):
    """items: [(라벨, 값)] → 도넛 + 범례"""
    items = [(l, float(v)) for l, v in items]
    tot = sum(v for _, v in items) or 1
    acc, stops, legend = 0.0, [], ""
    for (l, v), c in zip(items, colors):
        p = v / tot * 100
        stops.append(f"{c} {acc:.2f}% {acc + p:.2f}%")
        legend += f'<div><b style="background:{c}"></b>{html.escape(str(l))} <span style="font-weight:800">{p:.1f}%</span></div>'
        acc += p
    lead = max(items, key=lambda x: x[1]) if items else ("", 0)
    return (f'<div class="dn"><div class="dr" style="background:conic-gradient({",".join(stops)})"><div class="dc">{lead[1] / tot * 100:.0f}%'
            f'<small>{html.escape(str(lead[0]))}</small></div></div><div class="dl">{legend}</div></div>')


def table_html(df, fmts=None, heat=None, scroll=False):
    """DataFrame → 깔끔한 HTML 표. heat={컬럼: 최대값(None이면 자동)}"""
    fmts, heat = fmts or {}, heat or {}
    df = df.loc[:, ~df.columns.duplicated()]
    num = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    mx = {c: (heat[c] or pd.to_numeric(df[c], errors="coerce").max() or 1) for c in heat}
    head = "".join(f'<th class="{"num" if c in num else ""}">{html.escape(str(c))}</th>' for c in df.columns)
    body = ""
    for _, r in df.iterrows():
        tds = ""
        for c in df.columns:
            v = r[c]
            if pd.isna(v) if not isinstance(v, (list, tuple)) else False:
                s = "-"
            else:
                s = fmts[c](v) if c in fmts else (f"{v:,.0f}" if c in num else str(v))
            style = ""
            if c in heat and not pd.isna(v):
                p = max(0, min(100, float(v) / mx[c] * 100))
                style = f' style="background:linear-gradient(90deg,#D6E8FF {p:.0f}%,transparent {p:.0f}%)"'
            tds += f'<td class="{"num" if c in num else ""}"{style}>{html.escape(s)}</td>'
        body += f"<tr>{tds}</tr>"
    return f'<div class="tw{" sc" if scroll else ""}"><table class="tbl"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def hira_get(path, params, key, timeout=15):
    r = requests.get(f"{HIRA_BASE}/{path}", timeout=timeout, params={"serviceKey": key, "_type": "json", **params})
    try:
        body = r.json()["response"]["body"]
    except Exception:
        raise RuntimeError(f"심평원 응답 오류 HTTP {r.status_code}: {r.text[:1500]}")
    items = body.get("items")
    items = items.get("item", []) if items else []
    items = [items] if isinstance(items, dict) else items
    return items, int(body.get("totalCount", 0) or 0), r.text[:1500]


def hira_get_any(path, params, key, timeout=15):
    """JSON·XML 어느 쪽으로 응답해도 처리 (비급여 서비스는 XML 전용일 수 있음). (items, totalCount) 반환"""
    r = requests.get(f"{HIRA_BASE}/{path}", timeout=timeout, params={"serviceKey": key, "_type": "json", **params})
    try:
        body = r.json()["response"]["body"]
        items = body.get("items")
        items = items.get("item", []) if items else []
        return ([items] if isinstance(items, dict) else items), int(body.get("totalCount", 0) or 0)
    except ValueError:
        pass
    except (KeyError, TypeError, AttributeError):
        raise RuntimeError(f"심평원 응답 오류 HTTP {r.status_code}: {r.text[:300]}")
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        raise RuntimeError(f"응답 해석 실패 HTTP {r.status_code}: {r.text[:300]}")
    if root.tag == "OpenAPI_ServiceResponse":
        raise RuntimeError("공공데이터포털 오류: " + (root.findtext(".//returnAuthMsg") or root.findtext(".//errMsg") or "알 수 없음"))
    code = (root.findtext(".//resultCode") or "").strip()
    if code and code not in ("00", "0"):
        raise RuntimeError(f"심평원 오류 {code}: {root.findtext('.//resultMsg') or ''}")
    items = [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("item")]
    return items, int((root.findtext(".//totalCount") or "0").strip() or 0)