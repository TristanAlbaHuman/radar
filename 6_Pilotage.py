"""
6_Pilotage.py - Radar Mandats V2
Pilotage performance : conversions, impact DPE.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from ui_utils import CSS, kpi

st.markdown(CSS, unsafe_allow_html=True)

if st.session_state.get("df_scored") is None:
    st.warning("Chargez votre fichier CRM depuis l'accueil.")
    st.stop()

df_e = st.session_state["df_scored"].copy()
df_m = st.session_state.get("df_mandats", pd.DataFrame()).copy()
df_e["age_suivi_j"] = (pd.Timestamp(date.today()) - df_e["date_dernier_suivi"]).dt.days

PL = dict(font_family="DM Sans", plot_bgcolor="white", paper_bgcolor="white", margin=dict(l=10,r=10,t=40,b=10))

st.markdown("## 📈 Pilotage & Conversions")
st.markdown("<hr class='sep'>", unsafe_allow_html=True)

n_conv, n_ev = int(df_e["match_mandat_id"].notna().sum()), len(df_e)
st.markdown(f"""
<div class="krow">
  {kpi("Taux conv. éval→mandat", f"{round(100*n_conv/n_ev,1) if n_ev else 0}%", "sur tout le réseau", "pur")}
  {kpi("Exclusifs", f"{int(df_m['classement'].eq('exclusif').sum()) if not df_m.empty else 0:,}", "mandats", "grn")}
</div>
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📈 Conversion & Mandats", "🎯 Impact DPE & Actions"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        df_e["_bucket"] = df_e["age_estimation_jours"].apply(lambda age: "< 3m" if age<90 else ("3-6m" if age<180 else ("6-9m" if age<270 else ("9-12m" if age<365 else "> 12m"))))
        conv_age = df_e.groupby("_bucket").agg(n=("id_evaluation","count"), conv=("match_mandat_id", lambda x: x.notna().sum())).reset_index()
        conv_age["taux"] = (conv_age["conv"]/conv_age["n"]*100).round(1)
        conv_age["_bucket"] = pd.Categorical(conv_age["_bucket"], ["< 3m","3-6m","6-9m","9-12m","> 12m"])
        fig = px.bar(conv_age.sort_values("_bucket"), x="_bucket", y="taux", title="Taux de conversion par âge évaluation (%)", color="taux", color_continuous_scale=[[0,"#f0f0f0"],[0.5,"#2d6cdf"],[1,"#27ae60"]], text="taux")
        fig.update_layout(**PL, height=280, coloraxis_showscale=False); st.plotly_chart(fig, use_container_width=True)
    with c2:
        if not df_m.empty:
            cl_d = df_m["classement"].value_counts().reset_index().rename(columns={"count":"Nb", "classement":"Classement"})
            fig_cl = px.pie(cl_d, names="Classement", values="Nb", hole=0.45, color="Classement", color_discrete_map={"exclusif":"#2d6cdf","simple":"#27ae60","co-mandat":"#f39c12"}, title="Répartition des mandats")
            fig_cl.update_layout(**PL, height=280); st.plotly_chart(fig_cl, use_container_width=True)

with tab2:
    df_det = st.session_state.get("match_v2_df", pd.DataFrame())
    if not df_det.empty:
        st.markdown(f"""
        <div class="krow">
          {kpi("Matchs CRM × ADEME", len(df_det), "correspondances RNVP", "pur")}
          {kpi("Passoires F/G", int(df_det["dpe_etiquette"].str.upper().isin(["F","G"]).sum()) if "dpe_etiquette" in df_det.columns else 0, "signal urgent", "red")}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Lancez le matching ADEME depuis **Détection DPE** pour voir l'impact.")