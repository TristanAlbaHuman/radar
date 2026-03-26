"""
5_Vue_Reseau.py - Radar Mandats V2
Vue réseau pour la direction : opportunités dormantes, funnels, top agences.
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
df_e["age_suivi_j"]   = (today - df_e["date_dernier_suivi"]).dt.days
if not df_m.empty:
    df_m["age_suivi_j"] = (today - df_m["date_dernier_suivi"]).dt.days

PL = dict(font_family="DM Sans", plot_bgcolor="white", paper_bgcolor="white",
          margin=dict(l=10,r=10,t=40,b=10))

with st.sidebar:
    st.markdown("### Filtres réseau")
    top_n = st.slider("Top N agences", 10, 50, 20)
    st.markdown("---")
    st.markdown(f"**{df_e['agence'].nunique()} agences** dans les données")
    st.markdown(f"**{len(df_e):,} évaluations** · **{len(df_m):,} mandats**")

st.markdown("## 🌐 Vue réseau")
st.markdown(
    f"<span style='color:#888;font-size:13px'>"
    f"Données au {date.today().strftime('%d/%m/%Y')} · "
    f"{df_e['agence'].nunique()} agences · {len(df_e):,} évaluations · {len(df_m):,} mandats"
    f"</span>", unsafe_allow_html=True,
)
st.markdown("<hr class='sep'>", unsafe_allow_html=True)

# ── KPIs réseau ───────────────────────────────────────────────────
n_ev    = len(df_e)
n_act   = int(df_e["actif"].sum())
n_conv  = int(df_e["match_mandat_id"].notna().sum())
n_excl  = int(df_m["classement"].eq("exclusif").sum()) if not df_m.empty else 0
n_ss_e  = int(df_e["sans_suivi"].sum())
n_ss_m  = int(df_m["sans_suivi"].sum()) if not df_m.empty else 0
n_urgts = int(
    df_m[(df_m["classement"]=="exclusif") &
         ((df_m["sans_suivi"]==True)|(df_m["age_suivi_j"]>60))].pipe(len)
) if not df_m.empty else 0
taux    = round(100*n_conv/n_ev,1) if n_ev else 0

st.markdown(f"""
<div class="krow">
  {kpi("Évaluations", f"{n_ev:,}", "total réseau", "blu")}
  {kpi("Actives", f"{n_act:,}", f"{round(100*n_act/n_ev)}%", "grn")}
  {kpi("→ Mandats", f"{n_conv:,}", f"{taux}% conv.", "pur")}
  {kpi("Exclusifs", f"{n_excl:,}", "mandats", "grn")}
  {kpi("SS évals", f"{n_ss_e:,}", "jamais suivies", "red")}
  {kpi("SS mandats", f"{n_ss_m:,}", "sans action", "red")}
  {kpi("🔴 Urgents", f"{n_urgts:,}", "excl. >60j", "red")}
</div>
""", unsafe_allow_html=True)

# ── FUNNELS ───────────────────────────────────────────────────────
st.markdown('<div class="sec">Funnels de conversion</div>', unsafe_allow_html=True)
f1, f2, f3, f4 = st.columns(4)

with f1:
    fig = go.Figure(go.Funnel(
        y=["Estimations","Actives","→ Mandat","→ Exclusif"],
        x=[n_ev, n_act, n_conv, n_excl],
        textinfo="value+percent initial",
        marker=dict(color=["#2d6cdf","#27ae60","#8e44ad","#e74c3c"]),
        connector=dict(line=dict(color="#eee",width=1)),
    ))
    fig.update_layout(**PL, title="Estimation → Exclusif", title_font_size=12, height=280)
    st.plotly_chart(fig, use_container_width=True)

with f2:
    n_avec_s = int(df_e["sans_suivi"].eq(False).sum())
    n_90     = int((df_e["age_suivi_j"] <= 90).sum())
    n_30     = int((df_e["age_suivi_j"] <= 30).sum())
    fig = go.Figure(go.Funnel(
        y=["Sans suivi","Avec suivi","Contact <90j","Contact <30j"],
        x=[n_ss_e, n_avec_s, n_90, n_30],
        textinfo="value+percent previous",
        marker=dict(color=["#e74c3c","#e67e22","#f39c12","#27ae60"]),
        connector=dict(line=dict(color="#eee",width=1)),
    ))
    fig.update_layout(**PL, title="Sans suivi → Réactivé", title_font_size=12, height=280)
    st.plotly_chart(fig, use_container_width=True)

with f3:
    if not df_m.empty:
        n_ms = int(df_m["sans_suivi"].eq(False).sum())
        n_m90 = int((df_m["age_suivi_j"]<90).sum())
        n_m30 = int((df_m["age_suivi_j"]<30).sum())
        fig = go.Figure(go.Funnel(
            y=["Mandats total","Avec suivi","Suivi <90j","Suivi <30j"],
            x=[len(df_m), n_ms, n_m90, n_m30],
            textinfo="value+percent previous",
            marker=dict(color=["#bdc3c7","#e67e22","#f39c12","#27ae60"]),
            connector=dict(line=dict(color="#eee",width=1)),
        ))
        fig.update_layout(**PL, title="Mandats → Suivi actif", title_font_size=12, height=280)
        st.plotly_chart(fig, use_container_width=True)

with f4:
    df_det = st.session_state.get("match_v2_df", pd.DataFrame())
    n_cib  = int(df_e["match_mandat_id"].isna().sum())
    n_dpe  = len(df_det)
    n_fg_d = int(df_det["dpe_etiquette"].str.upper().isin(["F","G"]).sum()) if not df_det.empty and "dpe_etiquette" in df_det.columns else 0
    if n_dpe > 0:
        fig = go.Figure(go.Funnel(
            y=["Évals sans mandat","Matchs DPE","Passoires F/G"],
            x=[n_cib, n_dpe, n_fg_d],
            textinfo="value+percent initial",
            marker=dict(color=["#bdc3c7","#8e44ad","#e74c3c"]),
            connector=dict(line=dict(color="#eee",width=1)),
        ))
        fig.update_layout(**PL, title="DPE → Opportunités", title_font_size=12, height=280)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("""
        <div style="background:#f8f9fb;border:1px solid #eee;border-radius:8px;padding:20px;
             text-align:center;height:230px;display:flex;flex-direction:column;justify-content:center;">
          <div style="font-size:28px">🎯</div>
          <div style="font-size:12px;font-weight:600;color:#444;margin-top:8px">DPE → Opportunités</div>
          <div style="font-size:11px;color:#888;margin-top:6px">Lancez le matching<br/>en page Détection DPE</div>
        </div>""", unsafe_allow_html=True)

# ── CARTE DE CHALEUR AGENCES ──────────────────────────────────────
st.markdown('<div class="sec">Agences — opportunités dormantes vs conversion</div>',
            unsafe_allow_html=True)

ag = df_e.groupby("agence").agg(
    n_evals   =("id_evaluation","count"),
    n_actifs  =("actif","sum"),
    n_ss      =("sans_suivi","sum"),
    n_conv    =("match_mandat_id", lambda x: x.notna().sum()),
).reset_index()
ag["taux_conv"] = (ag["n_conv"]/ag["n_evals"]*100).round(1)
ag["opportunites"] = ag["n_actifs"] - ag["n_conv"]
ag = ag.sort_values("n_ss", ascending=False).head(top_n)

col_a, col_b = st.columns(2)
with col_a:
    fig_ss = px.bar(
        ag.sort_values("n_ss", ascending=True).tail(20),
        x="n_ss", y="agence", orientation="h",
        title=f"Top {min(20,top_n)} agences — évals sans suivi",
        color="n_ss", color_continuous_scale=[[0,"#f9f9f9"],[1,"#e74c3c"]],
        text="n_ss",
    )
    fig_ss.update_traces(textposition="outside")
    fig_ss.update_layout(**PL, height=480, showlegend=False,
                          coloraxis_showscale=False, yaxis_title=None, xaxis_title=None)
    st.plotly_chart(fig_ss, use_container_width=True)

with col_b:
    fig_tc = px.scatter(
        ag, x="taux_conv", y="n_ss",
        size="n_evals", color="taux_conv",
        color_continuous_scale=[[0,"#e74c3c"],[0.5,"#f39c12"],[1,"#27ae60"]],
        hover_name="agence",
        labels={"taux_conv":"Taux conv. %","n_ss":"Sans suivi","n_evals":"Nb évals"},
        title="Sans suivi vs Taux de conversion",
    )
    fig_tc.add_vline(x=ag["taux_conv"].mean(), line_dash="dot",
                     line_color="#2d6cdf", annotation_text="Moyenne réseau")
    fig_tc.update_layout(**PL, height=480, coloraxis_showscale=False)
    st.plotly_chart(fig_tc, use_container_width=True)

# ── TABLE TOP AGENCES ─────────────────────────────────────────────
st.markdown('<div class="sec">Classement complet des agences</div>', unsafe_allow_html=True)

ag_full = df_e.groupby("agence").agg(
    n_evals=("id_evaluation","count"),
    n_actifs=("actif","sum"),
    n_ss=("sans_suivi","sum"),
    n_conv=("match_mandat_id", lambda x: x.notna().sum()),
).reset_index()
ag_full["taux_conv"] = (ag_full["n_conv"]/ag_full["n_evals"]*100).round(1)
ag_full = ag_full.sort_values("n_ss", ascending=False).head(top_n)
ag_full.columns = ["Agence","Évaluations","Actives","Sans suivi","Mandats","Taux conv. %"]
st.dataframe(ag_full.reset_index(drop=True), use_container_width=True, height=400)

csv = ag_full.to_csv(index=False, encoding="utf-8-sig")
st.download_button("Export agences CSV", csv, f"reseau_{date.today().strftime('%Y%m%d')}.csv", "text/csv")
