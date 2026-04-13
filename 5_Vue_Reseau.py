"""
5_Vue_Reseau.py - Radar Mandats V2
Vue réseau pour la direction.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
from ui_utils import CSS, kpi

st.markdown(CSS, unsafe_allow_html=True)

if st.session_state.get("df_scored") is None:
    st.warning("Chargez votre fichier CRM depuis l'accueil.")
    st.stop()

df_e = st.session_state["df_scored"].copy()
df_m = st.session_state.get("df_mandats", pd.DataFrame()).copy()
today = pd.Timestamp(date.today())
df_e["age_suivi_j"] = (today - df_e["date_dernier_suivi"]).dt.days
if not df_m.empty: df_m["age_suivi_j"] = (today - df_m["date_dernier_suivi"]).dt.days

PL = dict(font_family="DM Sans", plot_bgcolor="white", paper_bgcolor="white", margin=dict(l=10,r=10,t=40,b=10))

with st.sidebar:
    st.markdown("### 🌐 Filtres réseau")
    top_n = st.slider("Top N agences", 10, 50, 20)

st.markdown("## 🌐 Vue réseau")
st.markdown(f"<span style='color:#888;font-size:13px'>{df_e['agence'].nunique()} agences · {len(df_e):,} évaluations · {len(df_m):,} mandats</span>", unsafe_allow_html=True)
st.markdown("<hr class='sep'>", unsafe_allow_html=True)

# KPIs toujours visibles
n_act, n_conv = int(df_e["actif"].sum()), int(df_e["match_mandat_id"].notna().sum())
st.markdown(f"""
<div class="krow">
  {kpi("Évaluations", f"{len(df_e):,}", "total réseau", "blu")}
  {kpi("→ Mandats", f"{n_conv:,}", f"{round(100*n_conv/len(df_e),1) if len(df_e) else 0}% conv.", "pur")}
  {kpi("Exclusifs", f"{int(df_m['classement'].eq('exclusif').sum()) if not df_m.empty else 0:,}", "mandats", "grn")}
  {kpi("SS évals", f"{int(df_e['sans_suivi'].sum()):,}", "jamais suivies", "red")}
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📊 Funnels de Conversion", "🗺️ Analyse par Agence", "📋 Données Brutes"])

with tab1:
    f1, f2 = st.columns(2)
    with f1:
        fig1 = go.Figure(go.Funnel(y=["Estimations","Actives","→ Mandat","→ Exclusif"], x=[len(df_e), n_act, n_conv, int(df_m["classement"].eq("exclusif").sum()) if not df_m.empty else 0], textinfo="value+percent initial", marker=dict(color=["#2d6cdf","#27ae60","#8e44ad","#e74c3c"])))
        fig1.update_layout(**PL, title="Estimation → Exclusif", height=300); st.plotly_chart(fig1, use_container_width=True)
    with f2:
        n_ss_e = int(df_e["sans_suivi"].sum())
        fig2 = go.Figure(go.Funnel(y=["Sans suivi","Avec suivi","Contact <90j","Contact <30j"], x=[n_ss_e, int(df_e["sans_suivi"].eq(False).sum()), int((df_e["age_suivi_j"]<=90).sum()), int((df_e["age_suivi_j"]<=30).sum())], textinfo="value+percent previous", marker=dict(color=["#e74c3c","#e67e22","#f39c12","#27ae60"])))
        fig2.update_layout(**PL, title="Efficacité du Suivi Évaluations", height=300); st.plotly_chart(fig2, use_container_width=True)

with tab2:
    ag = df_e.groupby("agence").agg(n_evals=("id_evaluation","count"), n_ss=("sans_suivi","sum"), n_conv=("match_mandat_id", lambda x: x.notna().sum())).reset_index()
    ag["taux_conv"] = (ag["n_conv"]/ag["n_evals"]*100).round(1)
    
    c1, c2 = st.columns(2)
    with c1:
        fig_ss = px.bar(ag.sort_values("n_ss", ascending=True).tail(top_n), x="n_ss", y="agence", orientation="h", title="Dossiers sans suivi", color="n_ss", color_continuous_scale=[[0,"#f9f9f9"],[1,"#e74c3c"]])
        fig_ss.update_layout(**PL, height=480, coloraxis_showscale=False); st.plotly_chart(fig_ss, use_container_width=True)
    with c2:
        fig_tc = px.scatter(ag, x="taux_conv", y="n_ss", size="n_evals", color="taux_conv", title="Sans suivi vs Conversion", color_continuous_scale=[[0,"#e74c3c"],[0.5,"#f39c12"],[1,"#27ae60"]], hover_name="agence")
        fig_tc.add_vline(x=ag["taux_conv"].mean(), line_dash="dot", line_color="#2d6cdf"); fig_tc.update_layout(**PL, height=480, coloraxis_showscale=False); st.plotly_chart(fig_tc, use_container_width=True)

with tab3:
    st.dataframe(ag.sort_values("n_evals", ascending=False), use_container_width=True, height=400)
    st.download_button("Export agences CSV", ag.to_csv(index=False, encoding="utf-8-sig"), f"reseau_{date.today().strftime('%Y%m%d')}.csv", "text/csv")