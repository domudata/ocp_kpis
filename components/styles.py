# -*- coding: utf-8 -*-
"""Injection du CSS personnalisé."""
import streamlit as st


def inject_custom_css():
    st.markdown("""<style>
    section[data-testid="stSidebar"]{width:260px!important}
    .main .block-container{max-width:100%!important;width:100%!important;padding-left:0.5rem!important;padding-right:0.5rem!important}
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

    :root{
        --primary:#1e3a5f;
        --primary-light:#2c5282;
        --success:#10b981;
        --danger:#ef4444;
        --warning:#f59e0b;
        --info:#3b82f6;
        --border:#e2e8f0;
        --radius:10px;
    }

    *{box-sizing:border-box;margin:0;padding:0}
    .stApp{background:#f8fafc;font-family:'Inter',sans-serif}
    .main .block-container{padding-top:.8rem;padding-bottom:.8rem}

    /* ═══ HEADER ═══ */
    .mh{
        background:linear-gradient(135deg,#1e3a5f 0%,#2563eb 100%);
        padding:14px 24px;border-radius:12px;margin-bottom:12px;
        box-shadow:0 8px 24px rgba(30,58,95,0.15);
        display:flex;align-items:center;gap:16px;
    }
    .mh h1{color:#fff;font-size:38px;font-weight:800;margin:0;flex:1}
    .mh .logo{height:50px;width:auto;max-width:150px;object-fit:contain;border-radius:6px}
    .mh .db{
        background:rgba(255,255,255,0.2);padding:6px 16px;border-radius:16px;
        color:#fff;font-size:18px;font-weight:600;
        border:1px solid rgba(255,255,255,0.3);backdrop-filter:blur(10px);
    }

    /* ═══ CARTES ═══ */
    .cr{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:10px}
    .cc{
        background:#fff;border-radius:12px;padding:16px 14px;
        box-shadow:0 4px 12px rgba(0,0,0,0.06);border-left:4px solid;
        transition:transform 0.2s,box-shadow 0.2s;text-align:center;
    }
    .cc:hover{transform:translateY(-2px);box-shadow:0 8px 20px rgba(0,0,0,0.1)}
    .cc .cv{font-size:30px;font-weight:900;line-height:1.1}
    .cc .cl{font-size:14px;color:#1e293b;font-weight:800;text-transform:uppercase;letter-spacing:.5px;margin-top:6px}
    .cc.c1{border-left-color:#3b82f6}.cc.c1 .cv{color:#2563eb}
    .cc.c2{border-left-color:#10b981}.cc.c2 .cv{color:#059669}
    .cc.c3{border-left-color:#8b5cf6}.cc.c3 .cv{color:#7c3aed}
    .cc.c4{border-left-color:#ef4444}.cc.c4 .cv{color:#dc2626}
    .cc.c5{border-left-color:#3b82f6}.cc.c5 .cv{color:#2563eb}
    .cc.c6{border-left-color:#06b6d4}.cc.c6 .cv{color:#0891b2}
    .cc.c7{border-left-color:#f59e0b}.cc.c7 .cv{color:#d97706}
    .cc.c8{border-left-color:#f97316}.cc.c8 .cv{color:#ea580c}
    .cc .cv-var{font-size:12px;font-weight:800;margin-top:5px;line-height:1.2;min-height:15px}
    .cc .cv-var.positive{color:#10b981}
    .cc .cv-var.negative{color:#ef4444}
    .cc .cv-var.neutral{color:#eab308}

    /* ═══ ONGLETS — STYLE CAPTURE D'ÉCRAN ═══ */
    .stTabs [data-baseweb="tab-list"]{
        gap:0!important;
        background:transparent!important;
        padding:0!important;
        border-bottom:2px solid #e2e8f0;
        margin-bottom:12px;
    }
    .stTabs [data-baseweb="tab"]{
        border-radius:0!important;
        padding:10px 20px!important;
        font-weight:600!important;
        font-size:15px!important;
        line-height:1.4!important;
        min-height:42px!important;
        color:#64748b!important;
        background:transparent!important;
        border:none!important;
        border-bottom:3px solid transparent!important;
        margin-bottom:-2px;
        transition:color 0.2s, border-color 0.2s;
    }
    .stTabs [data-baseweb="tab"]:hover{
        color:#1e3a5f!important;
        background:rgba(30,58,95,0.04)!important;
    }
    .stTabs [aria-selected="true"]{
        background:transparent!important;
        color:#1e3a5f!important;
        font-weight:700!important;
        border-bottom:3px solid #ef4444!important;
        box-shadow:none!important;
    }
    .stTabs [data-baseweb="tab"] span,
    .stTabs [data-baseweb="tab"] > div{
        font-size:15px !important;
    }
    .stTabs [data-baseweb="tab"] svg{
        width:18px!important;height:18px!important;
    }

    /* ═══ TITRES SECTIONS ═══ */
    .stl{font-size:15px;font-weight:800;color:var(--primary);margin:10px 0 5px 0;padding-left:12px;border-left:4px solid var(--info)}

    /* ═══ TABLEAUX ═══ */
    .tw{width:100%;border-collapse:collapse;font-family:'Inter',sans-serif;font-size:13px;display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0}
    .tw thead th{background:var(--primary);color:#fff;font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.3px;padding:6px 8px;border:none;white-space:nowrap;position:sticky;top:0;z-index:10}
    .tw.qt thead th{background:linear-gradient(135deg,#2563eb,#3b82f6)}
    .tw.pt thead th{background:linear-gradient(135deg,#059669,#10b981)}
    .tw.at thead th{background:linear-gradient(135deg,#dc2626,#ef4444)}
    .tw.st thead th{background:linear-gradient(135deg,#d97706,#f59e0b)}
    .tw thead th:first-child{z-index:11;left:0}
    .tw tbody td:first-child{position:sticky;left:0;background:#fff;z-index:5;border-right:1px solid var(--border);color:#1e293b!important}
    .tw tbody tr:nth-child(even) td:first-child{background:#f8fafc}
    .tw tbody tr:hover td:first-child{background:#eff6ff}
    .tw tbody td{padding:5px 8px;border-bottom:1px solid var(--border);white-space:nowrap;color:#1e293b!important}
    .tw tbody tr:nth-child(even) td{background:#f8fafc}
    .tw tbody tr:hover td{background:#eff6ff!important}
    .cb td{background:#2563eb!important;color:#fff!important;font-weight:700!important;font-size:12px!important}

    /* ═══ TABLEAU PLAN D'ACTION ═══ */
    .plan-action-table{width:100%;border-collapse:collapse;font-family:Inter,sans-serif;font-size:12px;border:1px solid #cbd5e1}
    .plan-action-table th{background:#1e3a5f;color:#fff;font-weight:700;padding:8px 6px;border:1px solid #1e3a5f}
    .plan-action-table td{padding:6px 8px;border:1px solid #cbd5e1;text-align:center;vertical-align:middle}
    .plan-action-table td:first-child{text-align:left;font-weight:800}

    /* ═══ COMPOSANTS GRAPHIQUES ═══ */
    .ca{background:#fff;border-radius:var(--radius);padding:12px;margin-top:6px;border:1px solid var(--border);box-shadow:0 1px 4px rgba(0,0,0,.02)}
    .ca .ct{font-size:14px;font-weight:700;margin-bottom:8px;padding-bottom:5px;border-bottom:1px solid var(--border)}
    .car{display:flex;align-items:center;margin-bottom:6px;font-size:12px}
    .car:last-child{margin-bottom:0}
    .car .cal{width:260px;font-weight:600;color:var(--primary);text-align:right;padding-right:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .car .cab{flex:1;height:26px;background:#edf2f7;border-radius:4px;overflow:visible;position:relative}
    .car .caf{height:100%;border-radius:4px;transition:width .3s}
    .car .target-mark{position:absolute;top:-4px;bottom:-4px;width:3px;background:var(--info)!important;z-index:20;transform:translateX(-50%);box-shadow:0 0 6px rgba(59,130,246,.9);border-radius:2px}
    .car .cav-out{font-size:12px;font-weight:800;color:#1e293b;min-width:55px;text-align:right;padding-left:6px}
    .car .cav-tgt{font-size:10px;font-weight:700;color:#1e293b;min-width:42px;text-align:right;padding-left:4px;opacity:.7}

    .gbr{display:flex;align-items:center;padding:3px 0;font-size:12px;border-bottom:1px solid #f1f5f9}
    .gbr:last-child{border:none}
    .gbr-l{width:160px;font-weight:600;color:#1e293b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px;padding-right:10px}
    .gbr-g{display:flex;align-items:center;gap:4px;flex:1;position:relative}
    .gbr-target{position:absolute;left:90%;top:-4px;bottom:-4px;width:3px;background:var(--primary)!important;z-index:10;box-shadow:0 0 6px rgba(30,58,95,.8);border-radius:2px}
    .gbr-w{flex:1;height:22px;background:#f1f5f9;border-radius:3px;overflow:hidden}
    .gbr-f{height:100%;border-radius:3px}
    .gbr-v{font-size:11px;font-weight:800;min-width:48px;text-align:right;color:#1e293b}

    .cg{display:grid;grid-template-columns:1fr 1fr;gap:6px}
    .cg>div{background:#fff;border-radius:var(--radius);padding:8px 10px;border:1px solid var(--border)}
    .cg .ct{font-size:13px;font-weight:700;margin-bottom:4px;padding-bottom:3px;border-bottom:1px solid var(--border)}
    .cgr{display:flex;align-items:center;padding:3px 0;font-size:12px;border-bottom:1px solid #f1f5f9}
    .cgr:last-child{border:none}
    .cgr .rk{width:18px;font-weight:800;text-align:center}
    .cgr .pn{flex:1;font-weight:600;color:#1e293b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .cgr .ps{font-weight:800;min-width:55px;text-align:right}

    .es{text-align:center;padding:14px;color:#64748b;font-size:14px}

    /* ═══ SIDEBAR ═══ */
    div[data-testid="stSidebar"]{background:linear-gradient(180deg,#1e40af 0%,#1e3a8a 50%,#1e3a5f 100%)!important}
    div[data-testid="stSidebar"]*{color:rgba(255,255,255,.9)!important}
    div[data-testid="stSidebar"] .stSelectbox label,div[data-testid="stSidebar"] .stMultiSelect label,
    div[data-testid="stSidebar"] .stDateInput label{
        color:rgba(255,255,255,.9)!important;font-weight:600;font-size:13px;text-transform:uppercase;letter-spacing:.5px
    }
    div[data-testid="stSidebar"] div[data-testid="stWidget"]{
        background:rgba(255,255,255,.1);border-radius:6px;padding:5px 10px;margin-bottom:5px;
        border:1px solid rgba(255,255,255,.15)
    }
    div[data-testid="stSidebar"] .stSelectbox>div>div,div[data-testid="stSidebar"] .stMultiSelect>div>div,
    div[data-testid="stSidebar"] .stDateInput>div>div{background:rgba(255,255,255,.95)!important;border-radius:5px}

    /* ═══ MASQUAGES ═══ */
    [data-testid="stHeaderActionElements"]{display:none!important}
    [data-testid="stActionButtonContainer"]{display:none!important}

    .footer{text-align:center;margin-top:30px;padding:15px;color:#64748b;font-size:13px;border-top:1px solid var(--border);font-weight:600}

    /* ═══ SCROLLBAR ═══ */
    ::-webkit-scrollbar{width:5px;height:5px}
    ::-webkit-scrollbar-track{background:#f1f1f1}
    ::-webkit-scrollbar-thumb{background:#cbd5e0;border-radius:3px}

    /* ═══ RESPONSIVE ═══ */
    @media(max-width:768px){
        .cr{grid-template-columns:repeat(2,1fr)}
        .mh{padding:8px 10px;gap:8px}
        .mh h1{font-size:18px}
        .mh .logo{height:35px;max-width:70px}
        .mh .db{font-size:11px;padding:2px 8px}
        .cg{grid-template-columns:1fr}
        .car{flex-wrap:wrap;gap:2px}
        .car .cal{width:100%;text-align:left;padding-right:0;margin-bottom:2px}
        .tw{font-size:10px}
        .stTabs [data-baseweb="tab"]{padding:8px 12px!important;font-size:13px!important}
        .stTabs [data-baseweb="tab"] span{font-size:13px!important}
    }

    @media print {
        section[data-testid="stSidebar"],header[data-testid="stHeader"],div[data-testid="stToolbar"],
        div[data-testid="stHeaderActionElements"],footer,.stDeployButton,#MainMenu{display:none!important}
        .main .block-container{padding-top:0!important;padding-left:0!important;padding-right:0!important;max-width:100%!important}
        .stButton,.stDownloadButton{display:none!important}
        *{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}
        .tw{page-break-inside:avoid;overflow:visible!important}
    }
    </style>""", unsafe_allow_html=True)
