"""
6_Pilotage.py - Radar Mandats V2
Pilotage performance : conversions réelles, impact ADEME, priorités validées.
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
today = pd.Timestamp(date.today())
df_e["age_suivi_j"] = (today - df_e["date_dernier_suivi"]).dt.days
if not df_m.empty:
    df_m["age_suivi_j"] = (today - df_m["date_dernier_suivi"]).dt.days

PL = dict(font_family="DM Sans", plot_bgcolor="white", paper_bgcolor="white",
          margin=dict(l=10,r=10,t=40,b=10))

st.markdown("## 📈 Pilotage & Conversions")
st.markdown("<hr class='sep'>", unsafe_allow_html=True)

# ── KPIs globaux ─────────────────────────────────────────────────
n_ev   = len(df_e)
n_mand = len(df_m)
n_excl = int(df_m["classement"].eq("exclusif").sum()) if not df_m.empty else 0
n_simp = int(df_m["classement"].eq("simple").sum()) if not df_m.empty else 0
n_co   = int(df_m["classement"].eq("co-mandat").sum()) if not df_m.empty else 0
n_conv = int(df_e["match_mandat_id"].notna().sum())
taux   = round(100*n_conv/n_ev,1) if n_ev else 0
taux_x = round(100*n_excl/n_mand,1) if n_mand else 0

st.markdown(f"""
<div class="krow">
  {kpi("Évaluations", f"{n_ev:,}", "total", "blu")}
  {kpi("Mandats actifs", f"{n_mand:,}", "total", "grn")}
  {kpi("Taux conv. éval→mandat", f"{taux}%", "sur tout le réseau", "pur")}
  {kpi("Exclusifs", f"{n_excl:,}", f"{taux_x}% des mandats", "grn")}
  {kpi("Simples", f"{n_simp:,}", "", "gry")}
  {kpi("Co-mandats", f"{n_co:,}", "", "gry")}
</div>
""", unsafe_allow_html=True)

# ── CONVERSION PAR ÂGE D'ESTIMATION ─────────────────────────────
st.markdown('<div class="sec">Taux de conversion par âge de l\'estimation</div>',
            unsafe_allow_html=True)

def bucket(age):
    if age < 90: return "< 3 mois"
    if age < 180: return "3-6 mois"
    if age < 270: return "6-9 mois"
    if age < 365: return "9-12 mois"
    return "> 12 mois"

df_e["_bucket"] = df_e["age_estimation_jours"].apply(lambda x: bucket(int(x or 0)))
order = ["< 3 mois","3-6 mois","6-9 mois","9-12 mois","> 12 mois"]
conv_age = df_e.groupby("_bucket").agg(
    n=("id_evaluation","count"),
    conv=("match_mandat_id", lambda x: x.notna().sum()),
).reset_index()
conv_age["taux"] = (conv_age["conv"]/conv_age["n"]*100).round(1)
conv_age["_bucket"] = pd.Categorical(conv_age["_bucket"], order)
conv_age = conv_age.sort_values("_bucket")

ca1, ca2 = st.columns(2)
with ca1:
    fig = px.bar(conv_age, x="_bucket", y="taux",
                 title="Taux de conversion par âge évaluation (%)",
                 color="taux",
                 color_continuous_scale=[[0,"#f0f0f0"],[0.5,"#2d6cdf"],[1,"#27ae60"]],
                 text="taux", labels={"_bucket":"","taux":"Taux %"})
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(**PL, height=280, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

with ca2:
    fig2 = px.bar(conv_age, x="_bucket", y=["n","conv"],
                  title="Volume évals vs mandats convertis",
                  barmode="overlay", opacity=0.85,
                  color_discrete_map={"n":"#e8f0fe","conv":"#2d6cdf"},
                  labels={"_bucket":"","value":"Nb","variable":""})
    fig2.update_layout(**PL, height=280)
    fig2.for_each_trace(lambda t: t.update(name="Évaluations" if t.name=="n" else "Mandats"))
    st.plotly_chart(fig2, use_container_width=True)

# ── RÉPARTITION CLASSEMENT MANDATS ───────────────────────────────
st.markdown('<div class="sec">Répartition des mandats</div>', unsafe_allow_html=True)
r1, r2 = st.columns(2)

with r1:
    if not df_m.empty:
        cl_d = df_m["classement"].value_counts().reset_index()
        cl_d.columns = ["Classement","Nb"]
        fig_cl = px.pie(cl_d, names="Classement", values="Nb", hole=0.45,
                        color="Classement",
                        color_discrete_map={"exclusif":"#2d6cdf","simple":"#27ae60","co-mandat":"#f39c12"},
                        title="Répartition par classement")
        fig_cl.update_traces(textposition="outside", textinfo="percent+label")
        fig_cl.update_layout(**PL, height=280, showlegend=False)
        st.plotly_chart(fig_cl, use_container_width=True)

with r2:
    if not df_m.empty:
        def urg_bucket(row):
            if row["sans_suivi"]: return "Sans suivi"
            a = row["age_suivi_j"] or 0
            if a > 90: return "> 90j"
            if a > 60: return "60-90j"
            if a > 30: return "30-60j"
            return "< 30j"
        df_m["_ub"] = df_m.apply(urg_bucket, axis=1)
        ub = df_m["_ub"].value_counts().reset_index()
        ub.columns = ["Urgence","Nb"]
        order_u = ["Sans suivi","> 90j","60-90j","30-60j","< 30j"]
        colors_u = {"Sans suivi":"#e74c3c","> 90j":"#e67e22","60-90j":"#f39c12",
                    "30-60j":"#f1c40f","< 30j":"#27ae60"}
        ub["Urgence"] = pd.Categorical(ub["Urgence"], order_u)
        ub = ub.sort_values("Urgence")
        fig_u = px.bar(ub, x="Urgence", y="Nb", color="Urgence",
                       color_discrete_map=colors_u, title="Ancienneté du dernier suivi",
                       text="Nb")
        fig_u.update_traces(textposition="outside")
        fig_u.update_layout(**PL, height=280, showlegend=False)
        st.plotly_chart(fig_u, use_container_width=True)

# ── TOP AGENCES PAR CONVERSION ────────────────────────────────────
st.markdown('<div class="sec">Top agences par taux de conversion</div>', unsafe_allow_html=True)

ag = df_e.groupby("agence").agg(
    n=("id_evaluation","count"),
    conv=("match_mandat_id", lambda x: x.notna().sum()),
).reset_index()
ag["taux"] = (ag["conv"]/ag["n"]*100).round(1)
ag = ag[ag["n"] >= 20].sort_values("taux", ascending=False).head(20)

fig_ag = px.bar(ag, x="agence", y="taux",
                title="Taux de conversion éval → mandat (agences ≥ 20 évals)",
                color="taux",
                color_continuous_scale=[[0,"#fde8e8"],[0.5,"#2d6cdf"],[1,"#27ae60"]],
                text="taux", labels={"agence":"","taux":"Taux %"})
fig_ag.update_traces(texttemplate="%{text}%", textposition="outside")
fig_ag.add_hline(y=ag["taux"].mean(), line_dash="dot",
                  line_color="#e74c3c", annotation_text=f"Moy. {ag['taux'].mean():.1f}%")
fig_ag.update_layout(**PL, height=340, coloraxis_showscale=False,
                      xaxis_tickangle=-35)
st.plotly_chart(fig_ag, use_container_width=True)

# ── IMPACT DPE ────────────────────────────────────────────────────
df_det = st.session_state.get("match_v2_df", pd.DataFrame())
if not df_det.empty:
    st.markdown('<div class="sec">Impact détection DPE</div>', unsafe_allow_html=True)
    n_match = len(df_det)
    n_fg = int(df_det["dpe_etiquette"].str.upper().isin(["F","G"]).sum()) if "dpe_etiquette" in df_det.columns else 0
    n_rec = int((df_det.get("dpe_age_mois",pd.Series(dtype=float)) <= 3).sum())
    st.markdown(f"""
    <div class="krow">
      {kpi("Matchs CRM × ADEME", n_match, "correspondances RNVP", "pur")}
      {kpi("Passoires F/G", n_fg, "signal urgent", "red")}
      {kpi("DPE très récents", n_rec, "< 3 mois", "ora")}
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown('<div class="sec">Impact détection DPE</div>', unsafe_allow_html=True)
    st.info("Lancez le matching ADEME depuis **Détection DPE** pour voir l'impact.")

# ── EXPORT GLOBAL ─────────────────────────────────────────────────
st.markdown('<div class="sec">Export données complètes</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    st.download_button(
        "Évaluations réseau CSV",
        df_e.to_csv(index=False, encoding="utf-8-sig"),
        f"evals_reseau_{date.today().strftime('%Y%m%d')}.csv", "text/csv",
    )
with c2:
    if not df_m.empty:
        st.download_button(
            "Mandats réseau CSV",
            df_m.to_csv(index=False, encoding="utf-8-sig"),
            f"mandats_reseau_{date.today().strftime('%Y%m%d')}.csv", "text/csv",
        )
