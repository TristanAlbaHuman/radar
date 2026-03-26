"""
3_Tableau_Agence.py - Radar Mandats V2
Tableau de bord directeur d'agence : santé, urgences, classement conseillers.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
from ui_utils import CSS, S, fmt_date, fmt_age, badge, kpi
from stream_estate import (
    get_tendance_secteur, get_biens_expires, badge_tendance,
    _disponible as stream_disponible, widget_configuration_sidebar,
)

st.markdown(CSS, unsafe_allow_html=True)

if st.session_state.get("df_scored") is None:
    st.warning("Chargez votre fichier CRM depuis l'accueil.")
    st.stop()

df_eval = st.session_state["df_scored"].copy()
df_mand = st.session_state.get("df_mandats", pd.DataFrame()).copy()
today   = pd.Timestamp(date.today())
df_eval["age_suivi_j"]   = (today - df_eval["date_dernier_suivi"]).dt.days
if not df_mand.empty:
    df_mand["age_suivi_j"]  = (today - df_mand["date_dernier_suivi"]).dt.days
    df_mand["age_mandat_j"] = (today - pd.to_datetime(df_mand["date_mandat"], errors="coerce")).dt.days

PL = dict(font_family="DM Sans", plot_bgcolor="white", paper_bgcolor="white",
          margin=dict(l=10, r=10, t=36, b=10))

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Agence")
    agences = sorted(df_eval["agence"].dropna().unique())
    agence  = st.selectbox("Sélectionner", agences)
    st.markdown("---")
    periode = st.selectbox("Période d'analyse",
                            ["3 derniers mois","6 derniers mois","12 derniers mois","Tout"],
                            index=2)
    jours_p = {"3 derniers mois":90,"6 derniers mois":180,
                "12 derniers mois":365,"Tout":9999}[periode]

# ── Filtrer sur l'agence ─────────────────────────────────────────
df_e = df_eval[df_eval["agence"] == agence].copy()
df_m = df_mand[df_mand["agence"] == agence].copy() if not df_mand.empty else pd.DataFrame()

# Filtrer par période
if jours_p < 9999:
    cutoff = today - pd.Timedelta(days=jours_p)
    df_e = df_e[pd.to_datetime(df_e["date_estimation"], errors="coerce") >= cutoff]

# ── En-tête ───────────────────────────────────────────────────────
st.markdown(f"## 🏢 {agence}")
st.markdown(
    f"<span style='color:#888;font-size:13px'>"
    f"Tableau de bord · {periode} · {date.today().strftime('%d/%m/%Y')}"
    f"</span>", unsafe_allow_html=True,
)
st.markdown("<hr class='sep'>", unsafe_allow_html=True)

# ── KPIs ─────────────────────────────────────────────────────────
n_mand_a  = len(df_m)
n_excl    = int(df_m["classement"].eq("exclusif").sum()) if not df_m.empty else 0
n_mand_ss = int(df_m["sans_suivi"].sum()) if not df_m.empty else 0
n_mand_90 = int((df_m["age_suivi_j"] > 90).sum()) if not df_m.empty else 0
n_urgents = int(
    df_m[(df_m["classement"]=="exclusif") &
         ((df_m["sans_suivi"]==True)|(df_m["age_suivi_j"]>60))]
    .pipe(len)
) if not df_m.empty else 0

n_eval_a  = len(df_e)
n_actifs  = int(df_e["actif"].sum())
n_ss_eval = int(df_e["sans_suivi"].sum())
n_conv    = int(df_e["match_mandat_id"].notna().sum())
taux_conv = round(100 * n_conv / n_eval_a, 1) if n_eval_a else 0

# Alerte si urgences
if n_urgents > 0:
    st.markdown(
        f'<div class="banner red"><div class="banner-icon">🔴</div>'
        f'<div class="banner-text"><b>{n_urgents} mandats exclusifs à relancer d\'urgence</b> '
        f'— sans suivi depuis plus de 60 jours</div></div>',
        unsafe_allow_html=True,
    )

st.markdown('<div class="sec">Mandats actifs</div>', unsafe_allow_html=True)
st.markdown(f"""
<div class="krow">
  {kpi("Total mandats", n_mand_a, "", "blu")}
  {kpi("Exclusifs", n_excl, f"{round(100*n_excl/n_mand_a)}%" if n_mand_a else "—", "grn")}
  {kpi("Sans suivi", n_mand_ss, "aucune action", "red")}
  {kpi("Suivi > 90j", n_mand_90, "relance urgente", "ora")}
  {kpi("🔴 Urgents", n_urgents, "exclusifs >60j", "red")}
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="sec">Pipeline évaluations</div>', unsafe_allow_html=True)
st.markdown(f"""
<div class="krow">
  {kpi("Évaluations", n_eval_a, periode, "blu")}
  {kpi("Actives", n_actifs, f"{round(100*n_actifs/n_eval_a)}%" if n_eval_a else "—", "grn")}
  {kpi("Sans suivi", n_ss_eval, "à qualifier", "ora")}
  {kpi("→ Mandats", n_conv, f"{taux_conv}% conv.", "pur")}
  {kpi("Cibles actives", int((df_e["actif"]==True).sum() - n_conv), "sans mandat", "yel")}
</div>
""", unsafe_allow_html=True)

# ── Stream Estate : tendance marché agence ───────────────────────
if not stream_disponible():
    st.markdown(
        '<div style="background:#fef0e0;border:1px solid #fad4a8;border-radius:8px;'
        'padding:12px 16px;font-size:12px;color:#b7600d;">'
        '🔑 <b>Données marché Stream Estate non disponibles</b> — '
        'Saisissez votre clé API dans la sidebar pour voir les prix du marché, '
        'la tendance et les biens expirés sur votre secteur.'
        '</div>',
        unsafe_allow_html=True,
    )
if stream_disponible():
    # Récupérer les CP de l'agence et les types de biens dominants
    cp_agence   = df_e["code_postal"].dropna().mode()
    type_agence = df_e["type_bien"].dropna().mode()
    if not cp_agence.empty and not type_agence.empty:
        cp_ref  = str(cp_agence.iloc[0]).zfill(5)[:5]
        tb_ref  = str(type_agence.iloc[0]).lower()
        st.markdown('<div class="sec">Tendance marché — Stream Estate</div>',
                    unsafe_allow_html=True)
        td = get_tendance_secteur(cp_ref, tb_ref)
        exp_data = get_biens_expires(cp_ref, tb_ref, mois_max=12)

        col_td1, col_td2, col_td3 = st.columns(3)
        with col_td1:
            if td.get("ok") and td.get("prix_actuel"):
                tendance_badge = badge_tendance(td["tendance"], td["variation_pct"])
                st.markdown(
                    f'<div class="kc blu">'
                    f'<div class="kl">Prix marché {tb_ref} · {cp_ref}</div>'
                    f'<div class="kv">{td["prix_actuel"]:,.0f}</div>'
                    f'<div class="ks">€/m² · {tendance_badge}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="kc gry"><div class="kl">Prix marché</div>'
                    f'<div class="kv">—</div>'
                    f'<div class="ks">Non disponible</div></div>',
                    unsafe_allow_html=True,
                )

        with col_td2:
            if td.get("ok") and td.get("variation_pct") is not None:
                v  = td["variation_pct"]
                cl = "grn" if v > 0 else "red" if v < 0 else "gry"
                st.markdown(
                    f'<div class="kc {cl}">'
                    f'<div class="kl">Évolution 6 mois</div>'
                    f'<div class="kv">{v:+.1f}%</div>'
                    f'<div class="ks">variation prix/m²</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        with col_td3:
            if exp_data.get("ok"):
                nb_exp = exp_data.get("nb", 0)
                cl_exp = "ora" if nb_exp > 0 else "grn"
                lbl_exp = f"{nb_exp} bien{'s' if nb_exp>1 else ''} expiré{'s' if nb_exp>1 else ''}" if nb_exp > 0 else "Aucun bien expiré"
                st.markdown(
                    f'<div class="kc {cl_exp}">'
                    f'<div class="kl">Biens expirés (12 mois)</div>'
                    f'<div class="kv">{nb_exp}</div>'
                    f'<div class="ks">{lbl_exp} — opportunité relance</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        if exp_data.get("signal"):
            st.markdown(
                f'<div class="banner ora"><div class="banner-icon">⚠️</div>'
                f'<div class="banner-text">'
                f'<b>{exp_data["nb"]} bien(s) similaire(s) ont été mis en vente sans succès</b> '
                f'sur le CP {cp_ref} ces 12 derniers mois. '
                f'Ces propriétaires sont potentiellement prêts à changer d\'agence.'
                f'</div></div>',
                unsafe_allow_html=True,
            )

# ── GRAPHIQUES ────────────────────────────────────────────────────
st.markdown('<div class="sec">Analyse</div>', unsafe_allow_html=True)
g1, g2 = st.columns(2)

with g1:
    # Répartition urgence mandats
    if not df_m.empty:
        def bucket_urg(row):
            if row["sans_suivi"]: return "Sans suivi"
            a = row["age_suivi_j"] or 0
            if a > 90: return "> 90j"
            if a > 60: return "60-90j"
            if a > 30: return "30-60j"
            return "< 30j"
        df_m["_urg"] = df_m.apply(bucket_urg, axis=1)
        ug = df_m["_urg"].value_counts().reset_index()
        ug.columns = ["Urgence","Nb"]
        order = ["Sans suivi","> 90j","60-90j","30-60j","< 30j"]
        colors = {"Sans suivi":"#e74c3c","> 90j":"#e67e22","60-90j":"#f39c12",
                  "30-60j":"#f1c40f","< 30j":"#27ae60"}
        ug["Urgence"] = pd.Categorical(ug["Urgence"], order)
        ug = ug.sort_values("Urgence")
        fig = px.bar(ug, x="Urgence", y="Nb", color="Urgence",
                     color_discrete_map=colors, title="Mandats par ancienneté de suivi",
                     text="Nb")
        fig.update_traces(textposition="outside")
        fig.update_layout(**PL, height=260, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

with g2:
    # Âge des évaluations
    def bucket_age(age):
        if age < 90: return "< 3m"
        if age < 180: return "3-6m"
        if age < 270: return "6-9m"
        if age < 365: return "9-12m"
        return "> 12m"
    df_e["_ba"] = df_e["age_estimation_jours"].apply(lambda x: bucket_age(int(x or 0)))
    order_a = ["< 3m","3-6m","6-9m","9-12m","> 12m"]
    bd = df_e["_ba"].value_counts().reset_index()
    bd.columns = ["Âge","Nb"]
    bd["Âge"] = pd.Categorical(bd["Âge"], order_a)
    bd = bd.sort_values("Âge")
    fig2 = px.bar(bd, x="Âge", y="Nb", title="Âge des estimations",
                  color_discrete_sequence=["#2d6cdf"], text="Nb")
    fig2.update_traces(textposition="outside")
    fig2.update_layout(**PL, height=260, showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

# ── TOP 10 DOSSIERS URGENTS ───────────────────────────────────────
st.markdown('<div class="sec">Top 10 — actions prioritaires de l\'agence</div>', unsafe_allow_html=True)

# Combiner mandats urgents + évals jamais suivies
urgent_m = pd.DataFrame()
if not df_m.empty:
    urgent_m = df_m[
        (df_m["classement"]=="exclusif") &
        ((df_m["sans_suivi"]==True)|(df_m["age_suivi_j"]>60))
    ].assign(_type="Mandat exclusif", _prio=1).head(5)

urgent_e = df_e[
    (df_e["actif"]==True) &
    (df_e["match_mandat_id"].isna()) &
    (df_e["sans_suivi"]==True)
].assign(_type="Éval sans suivi", _prio=2).sort_values("age_estimation_jours", ascending=False).head(5)

df_top = pd.concat([urgent_m, urgent_e]).sort_values(["_prio","age_suivi_j"], ascending=[True,False]).head(10)

rows_html = []
for i, (_, r) in enumerate(df_top.iterrows()):
    ptype = r.get("_type","")
    nom   = S(r.get("nom_principal","—"))
    addr  = S(r.get("adresse_bien","—"))
    tel   = S(r.get("client1_tel","") or r.get("tel_jointure",""))
    age_s = fmt_age(r.get("age_suivi_j"))
    color = "priority-1" if ptype == "Mandat exclusif" else "priority-2"
    b_type = f'<span class="cc-badge badge-{"red" if ptype=="Mandat exclusif" else "ora"}">{ptype}</span>'
    rows_html.append(
        f'<tr class="{color}">'
        f'<td><b>{nom}</b><br/><span style="font-size:11px;color:#888">{addr}</span></td>'
        f'<td>{b_type}</td>'
        f'<td style="font-weight:600;color:#e74c3c">{age_s} sans suivi</td>'
        f'<td style="font-weight:600">{tel}</td>'
        f'</tr>'
    )

st.markdown(
    '<div style="overflow-x:auto;border:1px solid #e0e0e0;border-radius:8px;">'
    '<table class="tbl"><thead><tr>'
    '<th>Contact / Adresse</th><th>Type</th><th>Sans suivi depuis</th><th>Téléphone</th>'
    '</tr></thead><tbody>' + "".join(rows_html) + '</tbody></table></div>',
    unsafe_allow_html=True,
)

# ── CLASSEMENT CONSEILLERS (si données disponibles) ───────────────
# Les données CRM ne contiennent pas de colonne conseiller — on le note
st.markdown('<div class="sec">Note</div>', unsafe_allow_html=True)
st.info(
    "Le classement par conseiller n'est pas disponible car le fichier CRM "
    "ne contient pas de colonne 'conseiller'. Si cette donnée est disponible "
    "dans votre export CRM, elle sera automatiquement prise en compte.",
)

# ── EXPORT ────────────────────────────────────────────────────────
st.markdown('<div class="sec">Export</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    csv_e = df_e.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("Évaluations agence CSV", csv_e,
                        f"evals_{agence.replace(' ','_')}_{date.today().strftime('%Y%m%d')}.csv",
                        "text/csv")
with c2:
    if not df_m.empty:
        csv_m = df_m.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("Mandats agence CSV", csv_m,
                            f"mandats_{agence.replace(' ','_')}_{date.today().strftime('%Y%m%d')}.csv",
                            "text/csv")
