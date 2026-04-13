"""
3_Tableau_Agence.py - Radar Mandats V2
Tableau de bord directeur d'agence : santé, urgences, classement.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from ui_utils import CSS, S, fmt_date, fmt_age, badge, kpi, widget_configuration_sidebar
from stream_estate import get_tendance_secteur, get_biens_expires, badge_tendance, _disponible as stream_disponible

st.markdown(CSS, unsafe_allow_html=True)

if st.session_state.get("df_scored") is None:
    st.warning("Chargez votre fichier CRM depuis l'accueil.")
    st.stop()

df_eval = st.session_state["df_scored"].copy()
df_mand = st.session_state.get("df_mandats", pd.DataFrame()).copy()
today = pd.Timestamp(date.today())
df_eval["age_suivi_j"] = (today - df_eval["date_dernier_suivi"]).dt.days
if not df_mand.empty:
    df_mand["age_suivi_j"] = (today - df_mand["date_dernier_suivi"]).dt.days

PL = dict(font_family="DM Sans", plot_bgcolor="white", paper_bgcolor="white", margin=dict(l=10, r=10, t=36, b=10))

with st.sidebar:
    st.markdown("### 🏢 Agence")
    agence = st.selectbox("Sélectionner", sorted(df_eval["agence"].dropna().unique()))
    periode = st.selectbox("Période d'analyse", ["3 derniers mois","6 derniers mois","12 derniers mois","Tout"], index=2)
    jours_p = {"3 derniers mois":90, "6 derniers mois":180, "12 derniers mois":365, "Tout":9999}[periode]

df_e = df_eval[df_eval["agence"] == agence].copy()
df_m = df_mand[df_mand["agence"] == agence].copy() if not df_mand.empty else pd.DataFrame()
if jours_p < 9999: df_e = df_e[pd.to_datetime(df_e["date_estimation"], errors="coerce") >= today - pd.Timedelta(days=jours_p)]

st.markdown(f"## 🏢 {agence}")
st.markdown(f"<span style='color:#888;font-size:13px'>Tableau de bord · {periode}</span>", unsafe_allow_html=True)
st.markdown("<hr class='sep'>", unsafe_allow_html=True)

n_urgents = int(df_m[(df_m["classement"]=="exclusif") & ((df_m["sans_suivi"]==True)|(df_m["age_suivi_j"]>60))].pipe(len)) if not df_m.empty else 0
if n_urgents > 0:
    st.markdown(f'<div class="banner red"><div class="banner-icon">🔴</div><div class="banner-text"><b>{n_urgents} mandats exclusifs à relancer d\'urgence</b> — sans suivi > 60j</div></div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📊 Vue d'ensemble & KPIs", "📈 Analyse & Marché", "🚨 Actions Prioritaires"])

with tab1:
    st.markdown('<div class="sec">Mandats actifs</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="krow">
      {kpi("Total mandats", len(df_m), "", "blu")}
      {kpi("Exclusifs", int(df_m["classement"].eq("exclusif").sum()) if not df_m.empty else 0, "", "grn")}
      {kpi("Sans suivi", int(df_m["sans_suivi"].sum()) if not df_m.empty else 0, "aucune action", "red")}
      {kpi("🔴 Urgents", n_urgents, "exclusifs >60j", "red")}
    </div>
    """, unsafe_allow_html=True)

    n_eval_a, n_actifs = len(df_e), int(df_e["actif"].sum())
    n_conv = int(df_e["match_mandat_id"].notna().sum())
    st.markdown('<div class="sec">Pipeline évaluations</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="krow">
      {kpi("Évaluations", n_eval_a, periode, "blu")}
      {kpi("Actives", n_actifs, "", "grn")}
      {kpi("Sans suivi", int(df_e["sans_suivi"].sum()), "à qualifier", "ora")}
      {kpi("→ Mandats", n_conv, f"{round(100*n_conv/n_eval_a,1) if n_eval_a else 0}% conv.", "pur")}
    </div>
    """, unsafe_allow_html=True)

with tab2:
    g1, g2 = st.columns(2)
    with g1:
        if not df_m.empty:
            df_m["_urg"] = df_m.apply(lambda r: "Sans suivi" if r["sans_suivi"] else ("> 90j" if (r["age_suivi_j"] or 0)>90 else ("60-90j" if (r["age_suivi_j"] or 0)>60 else ("30-60j" if (r["age_suivi_j"] or 0)>30 else "< 30j"))), axis=1)
            fig = px.bar(df_m["_urg"].value_counts().reset_index().rename(columns={"count":"Nb","_urg":"Urgence"}), x="Urgence", y="Nb", color="Urgence", color_discrete_map={"Sans suivi":"#e74c3c","> 90j":"#e67e22","60-90j":"#f39c12","30-60j":"#f1c40f","< 30j":"#27ae60"}, title="Mandats par ancienneté de suivi", text="Nb")
            fig.update_layout(**PL, height=260, showlegend=False); st.plotly_chart(fig, use_container_width=True)
    with g2:
        df_e["_ba"] = df_e["age_estimation_jours"].apply(lambda age: "< 3m" if age<90 else ("3-6m" if age<180 else ("6-9m" if age<270 else ("9-12m" if age<365 else "> 12m"))))
        fig2 = px.bar(df_e["_ba"].value_counts().reset_index().rename(columns={"count":"Nb","_ba":"Âge"}), x="Âge", y="Nb", title="Âge des estimations", color_discrete_sequence=["#2d6cdf"], text="Nb")
        fig2.update_layout(**PL, height=260, showlegend=False); st.plotly_chart(fig2, use_container_width=True)

with tab3:
    urgent_m = df_m[(df_m["classement"]=="exclusif") & ((df_m["sans_suivi"]==True)|(df_m["age_suivi_j"]>60))].assign(_type="Mandat exclusif", _prio=1).head(5) if not df_m.empty else pd.DataFrame()
    urgent_e = df_e[(df_e["actif"]==True) & (df_e["match_mandat_id"].isna()) & (df_e["sans_suivi"]==True)].assign(_type="Éval sans suivi", _prio=2).sort_values("age_estimation_jours", ascending=False).head(5)
    df_top = pd.concat([urgent_m, urgent_e]).sort_values(["_prio","age_suivi_j"], ascending=[True,False]).head(10)
    
    if not df_top.empty:
        rows_html = [f'<tr class="{"priority-1" if r.get("_type")=="Mandat exclusif" else "priority-2"}"><td><b>{S(r.get("nom_principal","—"))}</b><br/><span style="font-size:11px;color:#888">{S(r.get("adresse_bien","—"))}</span></td><td><span class="cc-badge badge-{"red" if r.get("_type")=="Mandat exclusif" else "ora"}">{r.get("_type")}</span></td><td style="font-weight:600;color:#e74c3c">{fmt_age(r.get("age_suivi_j"))} sans suivi</td><td style="font-weight:600">{S(r.get("client1_tel","") or r.get("tel_jointure",""))}</td></tr>' for i, (_, r) in enumerate(df_top.iterrows())]
        st.markdown('<div style="overflow-x:auto;border:1px solid #e0e0e0;border-radius:8px;"><table class="tbl"><thead><tr><th>Contact / Adresse</th><th>Type</th><th>Sans suivi</th><th>Téléphone</th></tr></thead><tbody>' + "".join(rows_html) + '</tbody></table></div>', unsafe_allow_html=True)
    else:
        st.success("Aucune action prioritaire en attente.")