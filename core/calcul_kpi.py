# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from core.constants import QK, PK, CIBLE, ACT_MAP, KPI_RESP_MAP, LOWER_BETTER

def ckpi(n,d,sz=100): return np.where(d==0,sz,(n/d)*100)
def cpiv(df,f,c,p): return pd.pivot_table(df[f],index="Poste travail princ.",columns=c,values="Ordre",aggfunc="count",fill_value=0).reindex(p,fill_value=0)

def build_statut_pivot(df_sub, posts):
    if df_sub.empty: return pd.DataFrame(index=posts, columns=["CRÉÉ","LANC","CLOT","TCLO","Total"]).fillna(0).astype(int)
    piv=pd.pivot_table(df_sub, index="Poste travail princ.", columns="Statut OT", values="Ordre", aggfunc="count", fill_value=0)
    for s in ["CRÉÉ","LANC","CLOT","TCLO"]:
        if s not in piv.columns: piv[s]=0
    piv["Total"]=piv[["CRÉÉ","LANC","CLOT","TCLO"]].sum(axis=1)
    return piv.reindex(posts, fill_value=0).fillna(0).astype(int)

def calc_kpis(df_i, av_i, now_ts, posts):
    res={}; df=df_i.copy(); av=av_i.copy(); res['dfp']=df
    filt_corr=(df["Nº appel pl.entret."].fillna(0)==0)&(df["Contient SOPL"]==1)
    an=cpiv(df,filt_corr,"Statut OT",posts)
    for c in ["CLOT","CRÉÉ","LANC","TCLO"]: an[c]=an.get(c,0)
    an["OT_CLOTURES"]=an["CLOT"]+an["TCLO"]; an["TOTAL_OT"]=an[["CLOT","CRÉÉ","LANC","TCLO"]].sum(axis=1)
    an["TAUX_REALISATION_CORRECTIF/PT"]=np.where(an["TOTAL_OT"]==0,100.0,ckpi(an["OT_CLOTURES"],an["TOTAL_OT"]))

    pr = cpiv(df, (df["Statut OT"]=="CRÉÉ") & (df["Statut utilisateur"].str.contains(r"\bCRPR\b", case=False, na=False)), "ap", posts)
    for c in ["<1 mois",">3 mois","1 mois < <3 mois","Inconnu"]: pr[c]=pr.get(c,0)
    pr["Total"]=pr[["<1 mois","1 mois < <3 mois",">3 mois","Inconnu"]].sum(axis=1)
    pr["OT préparation <1 mois"]=ckpi(pr["<1 mois"],pr["Total"]); pr["OT préparation >3 mois"]=ckpi(pr[">3 mois"],pr["Total"],0); pr["OT préparation 1mois< <3mois"]=ckpi(pr["1 mois < <3 mois"],pr["Total"],0)

    pl=cpiv(df,(df["Statut OT"]=="LANC")&(df["Statut utilisateur"].str.contains("ATPL",case=False,na=False)),"alp",posts)
    for c in ["<1 mois",">3 mois","1 mois < <3 mois","Inconnu"]: pl[c]=pl.get(c,0)
    pl["Total"]=pl[["<1 mois","1 mois < <3 mois",">3 mois","Inconnu"]].sum(axis=1)
    pl["OT planification <1 mois"]=ckpi(pl["<1 mois"],pl["Total"]); pl["OT planification >3 mois"]=ckpi(pl[">3 mois"],pl["Total"],0); pl["OT planification 1mois< <3mois"]=ckpi(pl["1 mois < <3 mois"],pl["Total"],0)

    ex=cpiv(df,(df["Statut OT"]=="LANC")&(df["Contient SOPL"]==1),"aex",posts)
    for c in ["<1 mois",">3 mois","1 mois < <3 mois","Inconnu"]: ex[c]=ex.get(c,0)
    ex["Total"]=ex[["<1 mois","1 mois < <3 mois",">3 mois","Inconnu"]].sum(axis=1)
    ex["OT exécution <1 mois"]=ckpi(ex["<1 mois"],ex["Total"]); ex["OT exécution >3 mois"]=ckpi(ex[">3 mois"],ex["Total"],0); ex["OT exécution 1mois< <3mois"]=ckpi(ex["1 mois < <3 mois"],ex["Total"],0)

    la=pd.pivot_table(df[df["Statut OT"]=="LANC"],index="Poste travail princ.",columns="OT LANC ESTIME",values="Ordre",aggfunc="count",fill_value=0).reindex(posts,fill_value=0)
    for c in ["OUI","NON"]: la[c]=la.get(c,0)
    la["Total"]=la["OUI"]+la["NON"]; la["OT LANC ESTIME"]=ckpi(la["OUI"],la["Total"])

    pc=pd.pivot_table(df[df["Statut OT"]=="CRÉÉ"],index="Poste travail princ.",columns="Backlog preparation",values="Ordre",aggfunc="count",fill_value=0).reindex(posts,fill_value=0)
    for c in ["CARACTERISE","NON CARACTERISE"]: pc[c]=pc.get(c,0)
    pc["Total"]=pc["CARACTERISE"]+pc["NON CARACTERISE"]; pc["Backlog préparation caractérisé"]=ckpi(pc["CARACTERISE"],pc["Total"])

    plc=pd.pivot_table(df[df["Statut OT"]=="CRÉÉ"],index="Poste travail princ.",columns="Backlog planification",values="Ordre",aggfunc="count",fill_value=0).reindex(posts,fill_value=0)
    for c in ["CARACTERISE","NON CARACTERISE"]: plc[c]=plc.get(c,0)
    plc["Total"]=plc["CARACTERISE"]+plc["NON CARACTERISE"]; plc["Backlog planification caractérisé"]=ckpi(plc["CARACTERISE"],plc["Total"])

    clot_df=df[df["Statut système"].str.contains("CLOT|TCLO",na=False)]
    conf=pd.pivot_table(clot_df,index="Poste travail princ.",columns="OT CONFIME",values="Ordre",aggfunc="count",fill_value=0).reindex(posts,fill_value=0)
    for c in ["OUI","NON"]: conf[c]=conf.get(c,0)
    conf["Total"]=conf["OUI"]+conf["NON"]; conf["OT CONFIME"]=ckpi(conf["OUI"],conf["Total"])

    ce=pd.pivot_table(df,index="Poste travail princ.",columns="OT_COR_EGAL",values="Ordre",aggfunc="count",fill_value=0).reindex(posts,fill_value=0)
    for c in ["OUI","NON"]: ce[c]=ce.get(c,0)
    ce["Total"]=ce["OUI"]+ce["NON"]; ce["OT_COR_EGAL"]=ckpi(ce["OUI"],ce["Total"])

    graiss_piv=build_statut_pivot(df[df["_tw_num"]==350],posts); graiss_piv["Performance Graissage"]=np.where(graiss_piv["Total"]==0,100.0,ckpi(graiss_piv["CLOT"]+graiss_piv["TCLO"],graiss_piv["Total"]))
    insp_piv=build_statut_pivot(df[df["_tw_num"].isin([290,300,310])],posts); insp_piv["Performance Inspection"]=np.where(insp_piv["Total"]==0,100.0,ckpi(insp_piv["CLOT"]+insp_piv["TCLO"],insp_piv["Total"]))
    syst_piv=build_statut_pivot(df[df["_tw_num"]==360],posts); syst_piv["Performance Systématiques"]=np.where(syst_piv["Total"]==0,100.0,ckpi(syst_piv["CLOT"]+syst_piv["TCLO"],syst_piv["Total"]))

    res.update({'an':an,'pr':pr,'pl':pl,'ex':ex,'la':la,'pc':pc,'plc':plc,'conf':conf,'ce':ce,'graiss_piv':graiss_piv,'insp_piv':insp_piv,'syst_piv':syst_piv})

    pcols = ["Poste de travail"] + QK + ["Score Performance"]
    qcols = ["Poste de travail"] + PK + ["Score Qualite"]
    prows, qrows, ano_p_r, ano_q_r = [], [], [], []

    for poste in posts:
        rp = {"Poste de travail": poste}; sp = []
        for kpi in QK:
            v = _ext(kpi, poste, res); rp[kpi]=round(v,2)
            cible = CIBLE.get(kpi, 100)
            ratio = (cible/v*100) if v>0 and kpi in LOWER_BETTER else ((v/cible*100) if cible>0 else 100)
            sp.append(min(ratio, 100))
        rp["Score Performance"]=round(np.mean(sp),2) if sp else 0; prows.append(rp)

        rq = {"Poste de travail": poste}; sq = []
        for kpi in PK:
            v = _ext(kpi, poste, res); rq[kpi]=round(v,2)
            cible = CIBLE.get(kpi, 100)
            ratio = (cible/v*100) if v>0 and kpi in LOWER_BETTER else ((v/cible*100) if cible>0 else 100)
            sq.append(min(ratio, 100))
        rq["Score Qualite"]=round(np.mean(sq),2) if sq else 0; qrows.append(rq)

        for sec, row, kpi_list in [("P", rp, QK), ("Q", rq, PK)]:
            for kpi in kpi_list:
                v = row[kpi]; cible = CIBLE.get(kpi, 100)
                if kpi in LOWER_BETTER:
                    if v > cible + 0.5:
                        (ano_p_r if sec=="P" else ano_q_r).append({"Poste de travail":poste,"KPI":kpi,"Valeur":v,"Cible":cible,"Écart":round(v-cible,2),"Action":ACT_MAP.get(kpi,""),"Responsable":KPI_RESP_MAP.get(kpi,"")})
                else:
                    if v < cible - 0.5:
                        (ano_p_r if sec=="P" else ano_q_r).append({"Poste de travail":poste,"KPI":kpi,"Valeur":v,"Cible":cible,"Écart":round(v-cible,2),"Action":ACT_MAP.get(kpi,""),"Responsable":KPI_RESP_MAP.get(kpi,"")})

    tgp = {"Poste de travail": "Total general"}
    for kpi in QK: tgp[kpi]=round(np.mean([r[kpi] for r in prows]),2)
    tgp["Score Performance"]=round(np.mean([r["Score Performance"] for r in prows]),2); prows.append(tgp)
    tgq = {"Poste de travail": "Total general"}
    for kpi in PK: tgq[kpi]=round(np.mean([r[kpi] for r in qrows]),2)
    tgq["Score Qualite"]=round(np.mean([r["Score Qualite"] for r in qrows]),2); qrows.append(tgq)

    cp = {"Poste de travail": "CIBLE"}
    for kpi in QK: cp[kpi]=CIBLE.get(kpi,"")
    cp["Score Performance"]=100; prows.append(cp)
    cq = {"Poste de travail": "CIBLE"}
    for kpi in PK: cq[kpi]=CIBLE.get(kpi,"")
    cq["Score Qualite"]=100; qrows.append(cq)

    res.update({'prows':prows,'pcols':pcols,'qrows':qrows,'qcols':qcols,'ano_p_r':ano_p_r,'ano_q_r':ano_q_r,
                'ano_p_c':["Poste de travail","KPI","Valeur","Cible","Écart","Action","Responsable"],
                'ano_q_c':["Poste de travail","KPI","Valeur","Cible","Écart","Action","Responsable"]})
    return res

def _ext(kpi, poste, res):
    try:
        if kpi=="TAUX_REALISATION_CORRECTIF/PT": return float(res['an'].loc[poste,"TAUX_REALISATION_CORRECTIF/PT"])
        elif kpi.startswith("OT préparation"): return float(res['pr'].loc[poste,kpi])
        elif kpi.startswith("OT planification"): return float(res['pl'].loc[poste,kpi])
        elif kpi.startswith("OT exécution"): return float(res['ex'].loc[poste,kpi])
        elif kpi=="OT LANC ESTIME": return float(res['la'].loc[poste,"OT LANC ESTIME"])
        elif kpi=="Backlog préparation caractérisé": return float(res['pc'].loc[poste,"Backlog préparation caractérisé"])
        elif kpi=="Backlog planification caractérisé": return float(res['plc'].loc[poste,"Backlog planification caractérisé"])
        elif kpi=="OT CONFIME": return float(res['conf'].loc[poste,"OT CONFIME"])
        elif kpi=="OT_COR_EGAL": return float(res['ce'].loc[poste,"OT_COR_EGAL"])
        elif kpi=="Taux d'approbation des Avis": return 100.0
        elif kpi=="OT Fiabilité": return 100.0
        elif kpi=="Total Avis de Panne": return 100.0
        elif kpi=="Performance Graissage": return float(res['graiss_piv'].loc[poste,"Performance Graissage"])
        elif kpi=="Performance Inspection": return float(res['insp_piv'].loc[poste,"Performance Inspection"])
        elif kpi=="Performance Systématiques": return float(res['syst_piv'].loc[poste,"Performance Systématiques"])
    except: return 0.0
    return 0.0
