import html
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import unquote

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

HIRA_BASE = "https://apis.data.go.kr/B551182"

BASE_CSS = """
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css");
:root{--navy:#0B2545;--bl:#1D5FD1;--bl2:#164AA8;--tl:#0E8F81;--tx:#101E33;--sb:#5A6A7E;--ln:#DCE4EE;--bg:#F4F7FB;--soft:#E8EFFB;--ink:#9FB0C3;
--sh:0 1px 2px rgba(11,37,69,.05),0 6px 20px rgba(11,37,69,.05);--sh2:0 2px 4px rgba(11,37,69,.06),0 14px 30px rgba(11,37,69,.10);--ease:cubic-bezier(.2,.8,.2,1)}
@property --n{syntax:'<integer>';inherits:false;initial-value:0}
html,body,.stApp,[class*="css"]{font-family:"Pretendard","Malgun Gothic",sans-serif!important;color:var(--tx);letter-spacing:-.01em}
.stApp{background:var(--bg)}
.block-container{max-width:1240px;padding-top:1rem;animation:fade .5s ease both}
#MainMenu,footer{visibility:hidden}[data-testid="stStatusWidget"]{display:none}
header[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebarNav"],[data-testid="collapsedControl"],[data-testid="stSidebar"]{display:none}
h1,h2,h3,h4{color:var(--tx);letter-spacing:-.03em}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes growy{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes shine{to{background-position:-200% 0}}
@keyframes cnt{from{--n:0}to{--n:var(--to)}}
@keyframes pop{0%{transform:scale(.85);opacity:0}60%{transform:scale(1.05)}100%{transform:scale(1);opacity:1}}
@keyframes ecg{0%{stroke-dashoffset:520}55%{stroke-dashoffset:0}100%{stroke-dashoffset:-520}}
@keyframes drift{0%,100%{transform:translate(0,0)}50%{transform:translate(18px,-14px)}}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(18,183,106,.5)}100%{box-shadow:0 0 0 9px rgba(18,183,106,0)}}
@keyframes sweep{to{transform:translateX(120%)}}
.cnt{animation:cnt 1.1s var(--ease) both;counter-reset:n var(--n)}.cnt::after{content:counter(n)}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
.topbar{display:flex;align-items:center;gap:12px;padding:2px 2px 14px}
.logo{position:relative;width:38px;height:38px;border-radius:10px;background:var(--navy);animation:pop .6s var(--ease) both}
.logo::before,.logo::after{content:"";position:absolute;left:50%;top:50%;background:#fff;border-radius:2px;transform:translate(-50%,-50%)}
.logo::before{width:18px;height:5px}.logo::after{width:5px;height:18px}
.topbar b{font-size:1.15rem;font-weight:800;letter-spacing:-.03em}
.topbar span.s{color:var(--sb);font-size:.82rem;margin-left:10px;padding-left:10px;border-left:1px solid var(--ln)}
.topbar .tb{margin-left:auto;font-size:.74rem;font-weight:700;color:var(--tl);border:1px solid #BFE5DF;background:#EAF7F5;border-radius:6px;padding:5px 10px}
.hero{position:relative;overflow:hidden;border-radius:16px;background:linear-gradient(115deg,#0B2545 0%,#123A73 58%,#1D5FD1 135%);padding:34px 40px;margin:0 0 20px;animation:rise .6s var(--ease) both}
.hero::before{content:"";position:absolute;inset:0;background:radial-gradient(rgba(255,255,255,.10) 1px,transparent 1.3px) 0 0/22px 22px;mask-image:linear-gradient(90deg,#000,transparent 85%);-webkit-mask-image:linear-gradient(90deg,#000,transparent 85%)}
.hero .blob{position:absolute;right:-60px;top:-80px;width:300px;height:300px;border-radius:50%;background:radial-gradient(closest-side,rgba(127,224,210,.28),transparent);animation:drift 9s ease-in-out infinite}
.hero .eb{position:relative;font-size:.76rem;font-weight:700;letter-spacing:.12em;color:#7FE0D2!important;margin-bottom:10px;animation:rise .6s .05s var(--ease) both}
.hero h1{position:relative;font-size:1.85rem;font-weight:800;letter-spacing:-.035em;line-height:1.3;margin:0 0 10px;padding:0;color:#fff!important;max-width:620px;animation:rise .7s .12s var(--ease) both}
.hero p{position:relative;color:#C9D8EF!important;margin:0;font-size:.95rem;max-width:560px;line-height:1.65;animation:rise .7s .2s var(--ease) both}
.hero .tags{position:relative;display:flex;gap:8px;margin-top:20px;flex-wrap:wrap}
.hero .tags span{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);color:#fff;border-radius:6px;padding:6px 12px;font-size:.78rem;font-weight:600;animation:pop .5s var(--ease) both}
.hero .tags span:nth-child(1){animation-delay:.3s}.hero .tags span:nth-child(2){animation-delay:.38s}.hero .tags span:nth-child(3){animation-delay:.46s}.hero .tags span:nth-child(4){animation-delay:.54s}
.hero svg{position:absolute;right:28px;bottom:20px;width:44%;max-width:420px;opacity:.6}
.hero svg path{fill:none;stroke:#7FE0D2;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:520;animation:ecg 3.6s linear infinite}
@media(max-width:760px){.hero{padding:24px 22px}.hero svg{display:none}.hero h1{font-size:1.45rem}}
.sec{font-size:1.1rem;font-weight:800;letter-spacing:-.02em;margin:28px 0 12px;display:flex;align-items:center;gap:10px}
.sec::before{content:"";width:18px;height:3px;border-radius:2px;background:var(--bl);transform-origin:left;animation:grow .6s var(--ease) both}
.sub{font-size:.8rem;color:var(--sb);line-height:1.55}
.note{font-size:.78rem;color:var(--sb);margin-top:14px;line-height:1.6}
.ai{display:inline-block;font-size:.66rem;font-weight:800;letter-spacing:.02em;color:#6B3FD0;background:#F0EAFD;border-radius:4px;padding:1px 6px;margin-right:6px;vertical-align:middle}
.panel{background:#fff;border:1px solid var(--ln);border-radius:12px;padding:20px 22px;margin-bottom:12px;box-shadow:var(--sh);animation:rise .5s var(--ease) both;transition:box-shadow .25s,transform .25s var(--ease)}
.panel:hover{box-shadow:var(--sh2);transform:translateY(-2px)}
.chip{display:inline-block;padding:5px 12px;border-radius:6px;font-size:.82rem;font-weight:600;background:var(--soft);color:var(--bl2);margin:0 6px 6px 0;animation:pop .45s var(--ease) both}
.chip:nth-of-type(2){animation-delay:.05s}.chip:nth-of-type(3){animation-delay:.1s}.chip:nth-of-type(4){animation-delay:.15s}.chip:nth-of-type(5){animation-delay:.2s}
.chip.g{background:#EEF2F7;color:var(--sb);font-weight:500;font-size:.74rem;padding:3px 9px}
.steps{display:flex;gap:0;flex-wrap:wrap;margin:0 0 16px;background:#fff;border:1px solid var(--ln);border-radius:12px;overflow:hidden}
.steps span{flex:1;min-width:130px;font-size:.84rem;font-weight:700;color:var(--sb);padding:13px 16px;display:flex;align-items:center;border-right:1px solid var(--ln);animation:rise .5s var(--ease) both;transition:background .2s,color .2s}
.steps span:hover{background:#F6F9FD;color:var(--tx)}
.steps span:nth-child(2){animation-delay:.07s}.steps span:nth-child(3){animation-delay:.14s}.steps span:nth-child(4){animation-delay:.21s}
.steps span:last-child{border-right:0}
.steps b{display:inline-flex;width:22px;height:22px;border-radius:6px;background:var(--navy);color:#fff;font-size:.74rem;align-items:center;justify-content:center;margin-right:10px}
.rg{font-size:.78rem;color:var(--sb);font-weight:600}.rgn{font-size:1.4rem;font-weight:800;letter-spacing:-.03em;margin-top:2px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:6px 0 14px}
.kpi{background:#fff;border:1px solid var(--ln);border-radius:12px;padding:16px 18px;box-shadow:var(--sh);animation:rise .5s var(--ease) both;animation-delay:calc(var(--i,0)*70ms);border-top:3px solid var(--navy);transition:transform .25s var(--ease),box-shadow .25s}
.kpi:hover{transform:translateY(-3px);box-shadow:var(--sh2)}
.kpi:nth-child(2){border-top-color:var(--bl)}.kpi:nth-child(3){border-top-color:var(--tl)}.kpi:nth-child(4){border-top-color:#8FA3BD}
.kpi .k{font-size:.76rem;color:var(--sb);font-weight:600}.kpi .n{font-size:1.45rem;font-weight:800;margin-top:4px;letter-spacing:-.03em}
.kpi .s{font-size:.74rem;color:var(--sb);margin-top:4px}
.vf{display:inline-block;font-size:.7rem;font-weight:700;padding:2px 8px;border-radius:5px;margin-left:6px;vertical-align:middle}
.vf.ok{background:#E3F6EC;color:#0B8F4A}.vf.warn{background:#FFF1DC;color:#B96200}
.rk{display:flex;gap:14px;align-items:flex-start;padding:8px 2px;animation:rise .5s var(--ease) both;animation-delay:calc(var(--i,0)*70ms)}
.rn{flex:0 0 30px;height:30px;border-radius:8px;background:#EEF2F7;color:var(--sb);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.86rem}
.rn.top{background:var(--navy);color:#fff}
.lv{font-size:.72rem;font-weight:700;padding:3px 9px;border-radius:5px;margin-left:8px;vertical-align:middle}
.lv.h{background:var(--soft);color:var(--bl2)}.lv.m{background:#E3F4F1;color:#0A7468}.lv.l{background:#EEF2F7;color:var(--sb)}
.chart{background:#fff;border:1px solid var(--ln);border-radius:12px;padding:18px 20px 14px;box-shadow:var(--sh);animation:rise .5s var(--ease) both;height:100%;transition:box-shadow .25s}
.chart:hover{box-shadow:var(--sh2)}
.ct{font-size:.92rem;font-weight:800;margin-bottom:2px}.cs{font-size:.76rem;color:var(--sb);margin-bottom:14px}
.bars,.sb{display:flex;flex-direction:column;gap:10px;margin:6px 0 4px}
.br{display:grid;grid-template-columns:minmax(80px,180px) 1fr minmax(90px,130px);gap:12px;align-items:center;font-size:.86rem}
.sr{display:grid;grid-template-columns:minmax(90px,190px) 1fr 64px;gap:12px;align-items:center;font-size:.86rem;animation:rise .45s var(--ease) both;animation-delay:calc(var(--i,0)*45ms)}
.bl{color:var(--sb);font-weight:600;line-height:1.3;word-break:keep-all}
.sr.on .bl,.br.on .bl{color:var(--tx);font-weight:800}
.bt,.st{height:12px;border-radius:4px;background:#EAF0F6;overflow:hidden;display:flex}
.st{height:16px}
.sr.on .st{box-shadow:0 0 0 2px rgba(29,95,209,.35)}
.bf,.st i{display:block;height:100%;transform-origin:left;animation:grow .9s var(--ease) both;animation-delay:calc(var(--i,0)*60ms)}
.bf{border-radius:4px}
.bv{font-weight:700;text-align:right}.bv small{color:var(--sb);font-weight:500;margin-left:6px}
.vbars{display:flex;gap:6px;align-items:stretch;height:220px;padding-top:6px}
.vb{flex:1;display:flex;flex-direction:column;align-items:center;min-width:0;cursor:default}
.vb .vv{font-size:.68rem;font-weight:700;color:var(--sb);height:16px}
.vb .vc{flex:1;width:100%;display:flex;align-items:flex-end}
.vb .vc i{display:block;width:100%;border-radius:6px 6px 2px 2px;background:#C9D9F3;transform-origin:bottom;animation:growy .8s var(--ease) both;animation-delay:calc(var(--i,0)*55ms);transition:filter .2s}
.vb:hover .vc i{filter:brightness(.94)}
.vb.pk .vc i{background:var(--bl)}.vb.pk .vv{color:var(--bl)}
.vb.me .vc i{background:#F59E0B}.vb.me .vv{color:#C77700}
.vb .vl{font-size:.7rem;color:var(--sb);margin-top:8px;white-space:nowrap}
.lg{display:flex;gap:14px;font-size:.74rem;color:var(--sb);margin-top:12px;flex-wrap:wrap}
.lg b{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px}
.dn{display:flex;align-items:center;gap:22px;flex-wrap:wrap;padding:6px 0}
.dr{width:132px;height:132px;border-radius:50%;display:flex;align-items:center;justify-content:center;animation:pop .8s var(--ease) both}
.dc{width:86px;height:86px;border-radius:50%;background:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;font-weight:800;font-size:1.15rem}
.dc small{font-size:.68rem;color:var(--sb);font-weight:600}
.dl{display:flex;flex-direction:column;gap:8px;font-size:.84rem}.dl b{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px}
.insight{background:#fff;border:1px solid var(--ln);border-left:4px solid var(--bl);color:var(--tx);border-radius:10px;padding:14px 18px;font-size:.9rem;font-weight:600;line-height:1.6;margin:8px 0 14px;animation:rise .5s var(--ease) both}
.hh{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:12px;flex-wrap:wrap}
.ob{display:inline-flex;align-items:center;gap:8px;font-size:.8rem;font-weight:800;padding:6px 12px;border-radius:999px;border:1px solid var(--ln);background:#fff;color:var(--sb)}
.ob::before{content:"";width:8px;height:8px;border-radius:50%;background:#9AA9BB}
.ob.open{color:#0B8F4A;border-color:#BFE5CF;background:#EAF8F0}
.ob.open::before{background:#12B76A;animation:pulse 1.8s ease-out infinite}
.wh{display:flex;flex-direction:column;gap:2px}
.wr,.wa{display:grid;grid-template-columns:64px 1fr 120px;gap:12px;align-items:center}
.wr{padding:7px 8px;border-radius:8px;animation:rise .5s var(--ease) both;animation-delay:calc(var(--i,0)*45ms);transition:background .15s}
.wr:hover{background:#F6F9FD}.wr.on{background:#F1F6FE}
.wd{font-weight:800;font-size:.86rem;display:flex;align-items:center;gap:6px}
.wd em{font-style:normal;font-size:.62rem;font-weight:800;color:#fff;background:var(--bl);border-radius:4px;padding:1px 5px}
.wt{position:relative;height:14px;border-radius:4px;background:#EAF0F6}
.wb{position:absolute;top:0;bottom:0;border-radius:4px;background:linear-gradient(90deg,#6FA0EA,var(--bl));transform-origin:left;animation:grow .9s var(--ease) both;animation-delay:calc(var(--i,0)*45ms + 150ms)}
.wr.off .wt{background:repeating-linear-gradient(135deg,#F0F3F7 0 6px,#E5EAF1 6px 12px)}
.wn{position:absolute;top:-3px;bottom:-3px;width:2px;background:#F59E0B;border-radius:2px;text-decoration:none}
.wv{text-align:right;font-size:.84rem;font-weight:700;font-variant-numeric:tabular-nums}
.wr.off .wv{color:var(--sb);font-weight:600}
.wa{margin-top:4px;padding:0 8px}
.wa>div{position:relative;height:16px;font-size:.68rem;color:var(--sb)}
.wa span{position:absolute;transform:translateX(-50%)}
@media(max-width:700px){.wr,.wa{grid-template-columns:44px 1fr 96px}}
.lks{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;margin:8px 0 4px}
.lk{display:flex;align-items:center;gap:12px;background:#fff;border:1px solid var(--ln);border-radius:10px;padding:14px 16px;text-decoration:none!important;color:var(--tx)!important;transition:transform .2s var(--ease),border-color .2s,box-shadow .2s;animation:rise .5s var(--ease) both;animation-delay:calc(var(--i,0)*60ms)}
.lk:hover{border-color:var(--bl);transform:translateY(-2px);box-shadow:0 8px 20px rgba(11,37,69,.08)}
.lk b{display:block;font-size:.9rem}.lk span{font-size:.76rem;color:var(--sb)}
.lk svg{margin-left:auto;flex:0 0 16px;stroke:var(--bl);transition:transform .2s var(--ease)}
.lk:hover svg{transform:translate(3px,-3px)}
.tw{background:#fff;border:1px solid var(--ln);border-radius:12px;overflow-x:auto;box-shadow:var(--sh);animation:rise .5s var(--ease) both}
.tw.sc{max-height:380px;overflow-y:auto}
.tbl{width:100%;border-collapse:separate;border-spacing:0;font-size:.86rem}
.tbl th{position:sticky;top:0;background:#F3F6FA;color:var(--sb);font-weight:700;text-align:left;padding:12px 16px;white-space:nowrap;z-index:1;border-bottom:1px solid var(--ln)}
.tbl td{padding:12px 16px;border-top:1px solid #EEF2F7;white-space:nowrap}
.tbl td.num,.tbl th.num{text-align:right;font-variant-numeric:tabular-nums}
.tbl tbody tr{transition:background .15s;animation:fade .5s var(--ease) both;animation-delay:calc(var(--i,0)*35ms)}.tbl tbody tr:hover{background:#F3F8FF}
.tbl tbody tr:nth-child(even){background:#FAFCFE}.tbl tbody tr:nth-child(even):hover{background:#F3F8FF}
.tbl td.nm{font-weight:700}
.tbl th.rk0,.tbl td.rk0{width:46px;padding-right:0;text-align:center}
.tbl td.rk0 b{display:inline-flex;width:26px;height:26px;border-radius:50%;background:#EEF4FB;color:var(--sb);font-size:.8rem;align-items:center;justify-content:center}
.tbl tbody tr:first-child td.rk0 b{background:linear-gradient(135deg,#1E6FD9,#17A2A8);color:#fff;box-shadow:0 3px 8px rgba(30,111,217,.3)}
.tc{display:inline-block;padding:3px 11px;border-radius:99px;font-size:.76rem;font-weight:700}
.db{display:flex;flex-direction:column;gap:5px;min-width:96px}.tbl td.num .db{align-items:flex-end}
.db b{font-weight:700}
.db span{display:block;width:96px;height:5px;border-radius:99px;background:#EAF0F6;overflow:hidden}
.db i{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#6FA0EA,#1D5FD1);transform-origin:left;animation:grow .9s var(--ease) both}
.sk{display:flex;flex-direction:column;gap:12px;padding:6px 0}
.sk i{display:block;height:64px;border-radius:10px;background:linear-gradient(90deg,#E3E9F1 25%,#F3F6FA 45%,#E3E9F1 65%);background-size:200% 100%;animation:shine 1.3s linear infinite}
.sk i:nth-child(2){opacity:.75}.sk i:nth-child(3){opacity:.5}
.stButton>button,.stLinkButton>a{border-radius:10px;font-weight:700;min-height:46px;border:0;transition:transform .15s var(--ease),background .2s,box-shadow .2s}
.stButton>button:active{transform:scale(.98)}
.stButton button[kind="primary"],.stButton button[data-testid="stBaseButton-primary"]{background:var(--bl);color:#fff;position:relative;overflow:hidden}
.stButton button[kind="primary"]::after,.stButton button[data-testid="stBaseButton-primary"]::after{content:"";position:absolute;inset:0;background:linear-gradient(110deg,transparent 30%,rgba(255,255,255,.28) 50%,transparent 70%);transform:translateX(-120%);pointer-events:none}
.stButton button[kind="primary"]:hover::after,.stButton button[data-testid="stBaseButton-primary"]:hover::after{animation:sweep .8s ease}
.stButton button[kind="primary"]:hover,.stButton button[data-testid="stBaseButton-primary"]:hover{background:var(--bl2);box-shadow:0 8px 18px rgba(29,95,209,.28);transform:translateY(-1px)}
.stButton button[kind="secondary"],.stButton button[data-testid="stBaseButton-secondary"]{background:#fff;color:var(--tx);box-shadow:inset 0 0 0 1.5px var(--ink)}
.stButton button[kind="secondary"]:hover,.stButton button[data-testid="stBaseButton-secondary"]:hover{background:#F6F9FD;box-shadow:inset 0 0 0 1.5px var(--bl);color:var(--bl2)}
.stButton button:disabled{opacity:1!important;background:#E3E9F1!important;color:#8394A8!important;box-shadow:none!important;cursor:not-allowed}
[class*="_busy"] button:disabled{background:var(--bl)!important;color:#fff!important;cursor:progress}
[class*="_busy"] button:disabled::before{content:"";width:16px;height:16px;margin-right:10px;border:2.5px solid rgba(255,255,255,.35);border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite}
[data-testid="stWidgetLabel"] p,label p{color:var(--tx)!important;font-weight:700;font-size:.86rem}
[data-baseweb="input"],[data-baseweb="textarea"],[data-baseweb="select"]>div{border-radius:10px!important;background:#fff!important;border:1.5px solid var(--ink)!important;box-shadow:0 1px 2px rgba(11,37,69,.06);transition:border-color .2s,box-shadow .2s}
[data-baseweb="base-input"]{background:transparent!important;border:0!important}
[data-baseweb="input"]:hover,[data-baseweb="textarea"]:hover,[data-baseweb="select"]>div:hover{border-color:#7389A3!important}
[data-baseweb="input"]:focus-within,[data-baseweb="textarea"]:focus-within,[data-baseweb="select"]>div:focus-within{border-color:var(--bl)!important;box-shadow:0 0 0 4px rgba(29,95,209,.15)}
[data-baseweb="input"] input,[data-baseweb="textarea"] textarea,[data-baseweb="select"] input{background:transparent!important;color:var(--tx)!important;-webkit-text-fill-color:var(--tx)!important}
[data-baseweb="input"] input::placeholder,[data-baseweb="textarea"] textarea::placeholder,[data-baseweb="select"] input::placeholder{color:#7D8DA1!important;opacity:1!important;-webkit-text-fill-color:#7D8DA1!important}
[data-baseweb="input"] input:disabled,[data-baseweb="textarea"] textarea:disabled{-webkit-text-fill-color:#4A5B70!important}
[data-testid="stNumberInputStepDown"],[data-testid="stNumberInputStepUp"]{background:#EEF2F7!important;color:var(--tx)!important}
[data-baseweb="tag"]{background:var(--soft)!important}[data-baseweb="tag"] span{color:var(--bl2)!important}
button[data-testid^="stBaseButton-segmented_control"],button[data-testid^="stBaseButton-pills"]{background:#fff!important;color:#2B3D55!important;border:1.5px solid var(--ink)!important;font-weight:600}
button[data-testid^="stBaseButton-segmented_control"]:hover,button[data-testid^="stBaseButton-pills"]:hover{border-color:var(--bl)!important;color:var(--bl2)!important}
button[data-testid="stBaseButton-segmented_controlActive"],button[data-testid="stBaseButton-pillsActive"]{background:var(--soft)!important;border-color:var(--bl)!important;color:var(--bl2)!important}
[data-baseweb="tab-highlight"]{background:var(--bl)!important;transition:all .3s var(--ease)}
[data-baseweb="tab"]{font-weight:700}
[data-baseweb="tab-panel"]{animation:rise .4s var(--ease) both}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:12px!important;border:1px solid var(--ln)!important;background:#fff;box-shadow:var(--sh)}
[data-testid="stExpander"]{border:1px solid var(--ln)!important;background:#fff;border-radius:12px;box-shadow:var(--sh)}
[data-testid="stExpander"] summary{font-weight:700;transition:background .15s}
[data-testid="stExpander"] summary:hover{background:#F6F9FD}
[data-testid="stExpander"] details[open]>div:last-child{animation:rise .35s var(--ease) both}
.stAlert{border-radius:10px;animation:rise .4s var(--ease) both}
.st-key-bodycard,[data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-bodycard){background:radial-gradient(closest-side at 50% 46%,rgba(29,95,209,.14),rgba(29,95,209,0) 78%),radial-gradient(#C5D5E8 1px,transparent 1.3px) 0 0/20px 20px,linear-gradient(180deg,#F3F8FE,#FFFFFF)!important;overflow:hidden}
.st-key-bodycard iframe{background:transparent!important}
.stApp{background:radial-gradient(900px 460px at 88% -8%,rgba(23,162,168,.16),transparent 70%),radial-gradient(820px 420px at -8% 4%,rgba(29,95,209,.13),transparent 70%),var(--bg)}
.hero{padding:44px 46px;border-radius:22px;background:radial-gradient(520px 260px at 92% 8%,rgba(127,224,210,.32),transparent 70%),linear-gradient(120deg,#08203F 0%,#0F3A78 55%,#1D5FD1 130%);box-shadow:0 24px 50px -22px rgba(11,37,69,.55)}
.hero h1{font-size:2.35rem;line-height:1.25;max-width:680px}
.hero .tags span{backdrop-filter:blur(6px);border-radius:99px;padding:7px 14px}
.kpi,.chart,.panel,.tw,.steps{border-radius:18px}
.kpi{background:linear-gradient(180deg,#fff,#FBFDFF);border-top:1px solid var(--ln);position:relative;overflow:hidden}
.kpi::before{content:"";position:absolute;left:0;right:0;top:0;height:4px;background:linear-gradient(90deg,var(--bl),var(--tl))}
.panel{background:rgba(255,255,255,.84);backdrop-filter:blur(10px)}
.steps{background:rgba(255,255,255,.88)}
.steps b{background:linear-gradient(135deg,var(--bl),var(--tl))}
.sec::before{width:26px;height:4px;background:linear-gradient(90deg,var(--bl),var(--tl))}
.chip{border-radius:99px}
.stButton>button,.stLinkButton>a{border-radius:14px}
.stButton button[kind="primary"],.stButton button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,#1D5FD1,#0E8F81)}
.stButton button[kind="primary"]:hover,.stButton button[data-testid="stBaseButton-primary"]:hover{background:linear-gradient(135deg,#164AA8,#0B7A6E)}
.rk{background:#fff;border:1px solid var(--ln);border-radius:14px;padding:12px 14px;margin:6px 0;transition:transform .2s var(--ease),box-shadow .2s,border-color .2s}
.rk:hover{border-color:#BFD4EE;transform:translateY(-2px);box-shadow:var(--sh)}
.sum{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:6px 0 20px;animation:rise .6s var(--ease) both}
.sum>div{position:relative;overflow:hidden;padding:20px 22px 18px;border-radius:20px;color:#fff;background:linear-gradient(135deg,#0B2545,#134583);box-shadow:0 18px 36px -22px rgba(11,37,69,.7);transition:transform .25s var(--ease)}
.sum>div:hover{transform:translateY(-3px)}
.sum>div::after{content:"";position:absolute;right:-30px;top:-30px;width:110px;height:110px;border-radius:50%;background:radial-gradient(closest-side,rgba(127,224,210,.28),transparent)}
.sum small{display:flex;align-items:center;gap:8px;font-size:.72rem;font-weight:700;letter-spacing:.08em;color:#7FE0D2;margin-bottom:8px}
.sum small::before{content:"";width:8px;height:8px;border-radius:50%;background:#7FE0D2}
.sum b{display:block;font-size:1.35rem;font-weight:800;letter-spacing:-.025em;line-height:1.3;word-break:keep-all}
.sum em{font-style:normal;display:block;margin-top:6px;font-size:.8rem;line-height:1.5;color:#C9D8EF;word-break:keep-all}
.sum .live{background:linear-gradient(135deg,#065F46,#0E8F81)}
.sum .live small::before{background:#6EE7B7;animation:pulse 1.8s ease-out infinite}
.sum .idle{background:linear-gradient(135deg,#3A4A60,#56677E)}
.sum .idle small{color:#D5DEE9}.sum .idle small::before{background:#9AA9BB}
.st-key-tb [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:.4rem!important;align-items:center}
.st-key-tb [data-testid="stColumn"]{min-width:0!important;width:auto!important;flex:0 0 auto!important}
.st-key-tb [data-testid="stColumn"]:first-child{flex:1 1 auto!important}
.st-key-bell button,.st-key-acct button,.st-key-loginbtn button{box-shadow:none!important;transition:background .2s,color .2s,transform .15s var(--ease)}
.st-key-bell button svg,.st-key-bell button p,.st-key-bell button [data-testid="stIconMaterial"],.st-key-acct button svg,.st-key-acct button [data-testid="stIconMaterial"]{display:none!important}
.st-key-bell button{position:relative;width:42px;height:42px;min-height:42px;padding:0!important;border-radius:50%!important;background:#fff!important;border:1px solid var(--ln)!important}
.st-key-bell button::before{content:"";position:absolute;inset:0;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23101E33' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9'/%3E%3Cpath d='M10.3 21a1.94 1.94 0 0 0 3.4 0'/%3E%3C/svg%3E") center/22px 22px no-repeat;transform-origin:50% 12%}
.st-key-bell button:hover{background:#F1F6FE!important;border-color:#BFD4EE!important}
.st-key-acct button{background:#fff!important;border:1px solid var(--ln)!important;border-radius:99px!important;min-height:42px;padding:0 14px 0 5px!important;color:var(--tx)!important;font-weight:700;gap:8px}
.st-key-acct button::before{content:var(--ini,"K");flex:0 0 32px;width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#1D5FD1,#0E8F81);color:#fff;font-weight:800;font-size:.9rem;display:inline-flex;align-items:center;justify-content:center}
.st-key-acct button:hover{background:#F1F6FE!important;border-color:#BFD4EE!important}
.st-key-loginbtn button{background:var(--navy)!important;color:#fff!important;border:0!important;border-radius:99px!important;min-height:40px;padding:0 20px!important;font-size:.88rem;font-weight:700;letter-spacing:.02em}
.st-key-loginbtn button:hover{background:linear-gradient(135deg,#1D5FD1,#0E8F81)!important;transform:translateY(-1px)}
.st-key-loginbtn button p{color:#fff!important}
@keyframes ring{0%,100%{transform:rotate(0)}12%{transform:rotate(16deg)}28%{transform:rotate(-14deg)}44%{transform:rotate(10deg)}60%{transform:rotate(-8deg)}76%{transform:rotate(4deg)}}
@keyframes badgepop{0%{transform:scale(0)}60%{transform:scale(1.35)}100%{transform:scale(1)}}
.nt{padding:11px 13px;border-radius:12px;border:1px solid var(--ln);margin-bottom:8px;background:#fff;animation:rise .35s var(--ease) both}
.nt.new{background:#F1F6FE;border-color:#BFD4EE}
.nt.new b::before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:#E5484D;margin-right:7px;vertical-align:middle}
.nt b{display:block;font-size:.86rem}
.nt span{font-size:.78rem;color:var(--sb);line-height:1.5}
.nt small{float:right;font-size:.7rem;color:var(--sb)}
.op{padding:0!important;overflow:hidden;border-top:4px solid #6B3FD0}
.op-h{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 22px 12px;border-bottom:1px solid var(--ln);background:linear-gradient(180deg,#FBF9FF,#fff)}
.op-h b{font-size:1rem;font-weight:800;letter-spacing:-.02em}
.op-h .ai{margin:0;flex:0 0 auto}
.op-b{padding:16px 22px 18px;line-height:1.8;font-size:.94rem}
.op-adv{margin:0 22px 18px;padding:12px 14px;border-radius:12px;background:#F4F7FB;color:var(--sb);font-size:.86rem;line-height:1.65}
.dchips{margin:4px 0 20px}
.cta-gap{height:10px}
.login-card{background:#fff;border:1px solid var(--ln);border-radius:20px;padding:26px 28px;box-shadow:var(--sh2);margin:8px 0 18px;animation:rise .5s var(--ease) both}
.login-card h3{margin:0 0 6px;font-size:1.2rem;font-weight:800}
.login-card p{margin:0 0 14px;color:var(--sb);font-size:.9rem;line-height:1.65}
.acct{display:inline-block;font-size:.8rem;font-weight:700;color:var(--bl2);background:var(--soft);border-radius:99px;padding:5px 12px;margin-bottom:10px}
@media(max-width:640px){
.block-container{padding-left:.9rem;padding-right:.9rem}
[data-testid="stHorizontalBlock"]{flex-wrap:wrap!important;gap:.5rem!important}
[data-testid="stColumn"],[data-testid="column"]{min-width:100%!important;flex:1 1 100%!important;width:100%!important}
.hc-top{flex-wrap:wrap}.hc-name,.hc-meta,.kpi .n,.kpi .s,.bl,.rgn,.sub,.lk b,.lk span{word-break:keep-all;overflow-wrap:anywhere}
.hc-dist{margin-left:0}
.br{grid-template-columns:84px 1fr 70px;gap:8px}.sr{grid-template-columns:84px 1fr 52px;gap:8px}
.bv{font-size:.78rem}.bv small{display:none}
.kpis{grid-template-columns:repeat(2,1fr)}
.topbar{flex-wrap:wrap}.topbar .tb{margin-left:0}
.steps span{min-width:46%}
.op-h,.op-b{padding-left:16px;padding-right:16px}.op-adv{margin-left:16px;margin-right:16px}
iframe[height="640"]{height:min(640px,68vh)!important}
}
"""

ECG = ('<svg viewBox="0 0 420 90" aria-hidden="true"><path d="M0 50 H110 L124 50 L136 18 L152 80 L166 30 L176 50 H250 L262 50 L274 26 '
       'L288 66 L298 50 H420"/></svg>')
ARROW = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="2.2" stroke-linecap="round" '
         'stroke-linejoin="round"><path d="M7 17L17 7M9 7h8v8"/></svg>')

DEMO_USER = {"name": "김콕콕", "email": "demo@kokkok.kr", "age": 34, "sex": "여성"}  # 임시데이터


def esc(x):
    return html.escape(str(x))


def env(name):
    v = (os.getenv(name) or "").strip().strip("\"'").strip()
    return unquote(v) if "%" in v else (v or None)


def setup(title, css=""):
    st.set_page_config(page_title=title, page_icon=None, layout="wide", initial_sidebar_state="collapsed")
    st.markdown(f"<style>{BASE_CSS}{css}</style>", unsafe_allow_html=True)


def notify(title, body="", toast_now=False):
    ss = st.session_state
    ss.setdefault("notifs", []).insert(0, {"t": title, "b": body, "at": datetime.now().strftime("%H:%M"), "new": True})
    ss["bell_anim"] = True
    if toast_now:
        st.toast(title)
    else:
        ss["pending_toast"] = title


def login_demo():
    st.session_state["user"] = dict(DEMO_USER)
    notify("로그인됐어요", "데모 계정으로 접속했어요.")


@st.fragment
def bell_box(title):
    ss = st.session_state
    notifs = ss.get("notifs", [])
    unread = sum(n["new"] for n in notifs)
    anim = ss.pop("bell_anim", False) and unread > 0
    if unread:
        badge = (f'.st-key-bell button::after{{content:"{min(unread, 9)}{"+" if unread > 9 else ""}";position:absolute;top:2px;right:0;min-width:18px;height:18px;padding:0 5px;'
                 'border-radius:99px;background:#E5484D;color:#fff;font:800 .68rem/18px Pretendard,sans-serif;text-align:center;box-shadow:0 0 0 2px #fff;'
                 + ("animation:badgepop .5s var(--ease) both" if anim else "") + '}')
        ring = '.st-key-bell button::before{animation:ring 1s ease-in-out 2}' if anim else ""
        st.markdown(f"<style>{badge}{ring}</style>", unsafe_allow_html=True)
    with st.container(key="bell"):
        with st.popover("알림"):
            if not notifs:
                st.caption("새 알림이 없어요.")
            for n in notifs[:8]:
                st.markdown(f'<div class="nt{" new" if n["new"] else ""}"><small>{esc(n["at"])}</small><b>{esc(n["t"])}</b><span>{esc(n["b"])}</span></div>',
                            unsafe_allow_html=True)
            if unread and st.button("모두 읽음", key=f"read_{title}", use_container_width=True):
                for n in notifs:
                    n["new"] = False
                st.rerun(scope="fragment")


def topbar(title, sub=""):
    ss = st.session_state
    if ss.get("pending_toast"):
        st.toast(ss.pop("pending_toast"))
    with st.container(key="tb"):
        left, bell, acct = st.columns([10, 1, 2], vertical_alignment="center")
        left.markdown(f'<div class="topbar"><div class="logo"></div><b>{esc(title)}</b>' + (f'<span class="s">{esc(sub)}</span>' if sub else "")
                      + '<span class="tb">공공데이터 + AI 참고용</span></div>', unsafe_allow_html=True)
        with bell:
            bell_box(title)
        user = ss.get("user")
        if user:
            st.markdown(f'<style>.st-key-acct button{{--ini:"{esc(user["name"][:1])}"}}</style>', unsafe_allow_html=True)
            with acct.container(key="acct"):
                with st.popover(user["name"]):
                    st.markdown(f"**{esc(user['name'])}**  \n{esc(user['email'])}")
                    if st.button("로그아웃", key=f"out_{title}", use_container_width=True):
                        ss.pop("user", None)
                        st.rerun()
        else:
            with acct.container(key="loginbtn"):
                if st.button("로그인", key=f"in_{title}"):
                    login_demo()
                    st.rerun()


def hero(eyebrow, title, desc, tags=()):
    tg = "".join(f"<span>{esc(t)}</span>" for t in tags)
    st.markdown(f'<div class="hero"><div class="blob"></div>{ECG}<div class="eb">{esc(eyebrow)}</div>'
                f'<h1>{esc(title).replace(chr(10), "<br>")}</h1><p>{esc(desc)}</p>' + (f'<div class="tags">{tg}</div>' if tg else "") + "</div>",
                unsafe_allow_html=True)


def skel(n=3):
    return '<div class="sk">' + "<i></i>" * n + "</div>"


def cnt(n):
    n = int(n)
    return f'<span class="cnt" style="--to:{n}"></span>' if n < 10000 else f"{n:,}"


def kpis(items):
    cells = ""
    for i, item in enumerate(items):
        s = f'<div class="s">{item[2]}</div>' if len(item) > 2 and item[2] else ""
        cells += f'<div class="kpi" style="--i:{i}"><div class="k">{esc(item[0])}</div><div class="n">{item[1]}</div>{s}</div>'
    return f'<div class="kpis">{cells}</div>'


def bars(items, color="#1D5FD1", unit="명", share=True, top=False, mark=None):
    items = [(l, float(v)) for l, v in items]
    mx = max((v for _, v in items), default=0) or 1
    tot = sum(v for _, v in items) or 1
    pick = min((v for _, v in items), default=0) if top == "min" else mx
    rows = "".join(
        f'<div class="br{" on" if mark is not None and l == mark else ""}" style="--i:{i}"><div class="bl" title="{esc(l)}">{esc(l)}</div>'
        f'<div class="bt"><div class="bf" style="width:{v / mx * 100:.1f}%;background:{color if (not top or v == pick) else "#C5D6F2"}"></div></div>'
        f'<div class="bv">{v:,.0f}{unit}' + (f"<small>{v / tot * 100:.1f}%</small>" if share else "") + "</div></div>"
        for i, (l, v) in enumerate(items))
    return f'<div class="bars">{rows}</div>'


def vbars(items, mine=None, unit="명"):
    vals = [float(i[1]) for i in items]
    mx, tot = (max(vals, default=0) or 1), (sum(vals) or 1)
    cols = ""
    for i, it in enumerate(items):
        l, v = it[0], float(it[1])
        tip = it[2] if len(it) > 2 else l
        cls = "vb" + (" me" if mine is not None and tip == mine else "") + (" pk" if v == mx else "")
        cols += (f'<div class="{cls}" style="--i:{i}" title="{esc(tip)}: {v:,.0f}{unit} ({v / tot * 100:.1f}%)">'
                 f'<div class="vv">{v / tot * 100:.0f}%</div><div class="vc"><i style="height:{max(v / mx * 100, 1.5):.1f}%"></i></div>'
                 f'<div class="vl">{esc(l)}</div></div>')
    legend = '<span><b style="background:#1D5FD1"></b>가장 많은 구간</span>' + (
        '<span><b style="background:#F59E0B"></b>입력하신 연령대</span>' if mine is not None else "")
    return f'<div class="vbars">{cols}</div><div class="lg">{legend}</div>'


def donut(items, colors=("#1D5FD1", "#E5739A", "#9AA9BB", "#0E8F81")):
    items = [(l, float(v)) for l, v in items]
    tot = sum(v for _, v in items) or 1
    acc, stops, legend = 0.0, [], ""
    for (l, v), c in zip(items, colors):
        p = v / tot * 100
        stops.append(f"{c} {acc:.2f}% {acc + p:.2f}%")
        legend += f'<div><b style="background:{c}"></b>{esc(l)} <span style="font-weight:800">{p:.1f}%</span></div>'
        acc += p
    lead = max(items, key=lambda x: x[1]) if items else ("", 0)
    return (f'<div class="dn"><div class="dr" style="background:conic-gradient({",".join(stops)})"><div class="dc">{lead[1] / tot * 100:.0f}%'
            f'<small>{esc(lead[0])}</small></div></div><div class="dl">{legend}</div></div>')


def stack_bars(rows, parts, on=None):
    mx = max((sum(d.values()) for _, d in rows), default=0) or 1
    out = ""
    for i, (l, d) in enumerate(rows):
        segs = "".join(f'<i title="{esc(n)} {d.get(n, 0):,.0f}명" style="width:{d.get(n, 0) / mx * 100:.2f}%;background:{col}"></i>'
                       for n, col in parts if d.get(n, 0) > 0)
        out += (f'<div class="sr{" on" if l == on else ""}" style="--i:{i}"><div class="bl" title="{esc(l)}">{esc(l)}</div>'
                f'<div class="st">{segs}</div><div class="bv">{sum(d.values()):,.0f}명</div></div>')
    legend = "".join(f'<span><b style="background:{col}"></b>{esc(n)}</span>' for n, col in parts)
    return f'<div class="sb">{out}</div><div class="lg">{legend}</div>'


def open_badge(state, text):
    return f'<span class="ob{" open" if state == "open" else ""}">{esc(text)}</span>'


def week_hours(rows, today=None, now_min=None):
    spans = [(s, e) for _, s, e in rows if s is not None and e is not None and e > s]
    if not spans:
        return ""
    lo = min(s for s, _ in spans) // 60 * 60
    hi = min(-(-max(e for _, e in spans) // 60) * 60, 1440)
    if hi - lo < 360:
        hi = min(lo + 360, 1440)
        lo = hi - 360
    rng = hi - lo
    out = ""
    for i, (d, s, e) in enumerate(rows):
        on = " on" if today == i else ""
        badge = "<em>오늘</em>" if today == i else ""
        if s is None or e is None:
            out += f'<div class="wr off{on}" style="--i:{i}"><div class="wd">{esc(d)}{badge}</div><div class="wt"></div><div class="wv">휴진·미신고</div></div>'
            continue
        now = f'<u class="wn" style="left:{(now_min - lo) / rng * 100:.1f}%"></u>' if today == i and now_min is not None and lo <= now_min <= hi else ""
        out += (f'<div class="wr{on}" style="--i:{i}"><div class="wd">{esc(d)}{badge}</div><div class="wt">'
                f'<i class="wb" style="left:{(s - lo) / rng * 100:.1f}%;width:{(e - s) / rng * 100:.1f}%"></i>{now}</div>'
                f'<div class="wv">{s // 60:02d}:{s % 60:02d} – {e // 60:02d}:{e % 60:02d}</div></div>')
    step = 2 if rng / 60 > 8 else 1
    ticks = "".join(f'<span style="left:{(h * 60 - lo) / rng * 100:.1f}%">{h:02d}</span>' for h in range(lo // 60, hi // 60 + 1, step))
    return f'<div class="wh">{out}</div><div class="wa"><div></div><div>{ticks}</div><div></div></div>'


def link_cards(items):
    cells = "".join(f'<a class="lk" style="--i:{i}" target="_blank" rel="noopener" href="{esc(h)}"><div><b>{esc(t)}</b><span>{esc(d)}</span></div>{ARROW}</a>'
                    for i, (t, d, h) in enumerate(items))
    return f'<div class="lks">{cells}</div>'


def table_html(df, fmts=None, heat=None, scroll=False, rank=False, chips=None):
    fmts, heat, chips = fmts or {}, heat or {}, chips or {}
    df = df.loc[:, ~df.columns.duplicated()]
    num = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    mx = {c: (heat[c] or pd.to_numeric(df[c], errors="coerce").max() or 1) for c in heat}
    head = ('<th class="rk0">#</th>' if rank else "") + "".join(f'<th class="{"num" if c in num else ""}">{esc(c)}</th>' for c in df.columns)
    body = ""
    for i, (_, r) in enumerate(df.iterrows()):
        tds = f'<td class="rk0"><b>{i + 1}</b></td>' if rank else ""
        for j, c in enumerate(df.columns):
            v = r[c]
            na = not isinstance(v, (list, tuple)) and pd.isna(v)
            s = "-" if na else fmts[c](v) if c in fmts else f"{v:,.0f}" if c in num else str(v)
            if c in chips and not na:
                col = chips[c].get(v, "#8FA3BD")
                cell = f'<span class="tc" style="background:{col}1F;color:{col}">{esc(s)}</span>'
            elif c in heat and not na:
                cell = f'<div class="db"><b>{esc(s)}</b><span><i style="width:{max(0, min(100, float(v) / mx[c] * 100)):.0f}%"></i></span></div>'
            else:
                cell = esc(s)
            tds += f'<td class="{"num" if c in num else ""}{" nm" if j == 0 and c not in num else ""}">{cell}</td>'
        body += f'<tr style="--i:{i}">{tds}</tr>'
    return f'<div class="tw{" sc" if scroll else ""}"><table class="tbl"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _gw_err(d):
    h = (d.get("OpenAPI_ServiceResponse") or {}).get("cmmMsgHeader") or {}
    return " ".join(x for x in [h.get("errMsg", ""), h.get("returnAuthMsg", ""), f"(코드 {h.get('returnReasonCode', '?')})"] if x)


_OK = {}


def _variants(path):
    svc, op = path.split("/", 1)
    alts = [path]
    if svc.endswith("1") and op.endswith("1"):
        alts.append(f"{svc[:-1]}/{op[:-1]}")
    elif svc.endswith("v2"):
        alts.append(f"{svc[:-2]}/{op}")
    elif not svc[-1].isdigit():
        alts.append(f"{svc}1/{op}1")
    return alts


def _hira_once(path, params, key, timeout, scheme):
    url = f"{scheme}://{HIRA_BASE.split('://', 1)[1]}/{path}"
    r = requests.get(url, timeout=timeout, params={"serviceKey": key, "_type": "json", **params})
    raw, head = r.text[:1500], f"HTTP {r.status_code}"
    try:
        data = r.json()
    except ValueError:
        data = None
    if data is not None:
        if "OpenAPI_ServiceResponse" in data:
            raise RuntimeError(f"공공데이터포털 오류 {head}: {_gw_err(data)}")
        try:
            body = data["response"]["body"]
        except (KeyError, TypeError):
            raise RuntimeError(f"심평원 응답 오류 {head}: {raw}")
        items = (body.get("items") or {}).get("item", [])
        return ([items] if isinstance(items, dict) else items), int(body.get("totalCount", 0) or 0), raw
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        raise RuntimeError(f"응답 해석 실패 {head}: {raw[:300]}")
    if root.tag == "OpenAPI_ServiceResponse":
        raise RuntimeError("공공데이터포털 오류: " + (root.findtext(".//returnAuthMsg") or root.findtext(".//errMsg") or "알 수 없음"))
    code = (root.findtext(".//resultCode") or "").strip()
    if code and code not in ("00", "0"):
        raise RuntimeError(f"심평원 오류 {code}: {root.findtext('.//resultMsg') or ''}")
    items = [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("item")]
    return items, int((root.findtext(".//totalCount") or "0").strip() or 0), raw


def hira_get(path, params, key, timeout=15):
    first = None
    for n in range(3):
        if path in _OK:
            tries = [_OK[path]]
        elif n == 0:
            tries = [(p, s) for p in _variants(path) for s in ("https", "http")]
        else:
            tries = [(path, "https")]
        for p, s in tries:
            try:
                out = _hira_once(p, params, key, timeout, s)
                _OK[path] = (p, s)
                return out
            except requests.exceptions.RequestException as e:
                first = first or e
            except RuntimeError as e:
                first = first or e
                if not re.search(r"NO_OPENAPI|코드 (12|04|05|23)\)|HTTP 5\d\d", str(e)):
                    raise
        if n < 2:
            time.sleep(0.8 * (n + 1))
    raise first