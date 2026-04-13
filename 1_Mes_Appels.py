"""
1_Mes_Appels.py - Radar Mandats V2
Page principale de l'agent : liste d'appels ordonnée par urgence.
"""

import streamlit as st
import pandas as pd
from datetime import date
from ui_utils import (
    CSS, S, fmt_date, fmt_age, badge, dpe_badge, kpi, scorer_action,
    widget_configuration_sidebar,
)
from stream_estate import (
    get_tendance_secteur, get_biens_expires, badge_tendance,
    _disponible as stream_disponible,
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

# ── Sidebar filtres ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏢 Mon agence")
    agences = sorted(df_eval["agence"].dropna().unique())
    agence_sel = st.selectbox("Agence", ["Toutes"] + agences)
    nb_par_liste = st.slider("Contacts par liste", 10, 100, 30, step=10)
    st.markdown("---")
    st.info("💡 Cliquez sur **Voir la fiche** pour accéder au script d'appel complet.")
    widget_configuration_sidebar()

# ── Filtres ───────────────────────────────────────────────────────
if agence_sel != "Toutes":
    df_eval = df_eval[df_eval["agence"] == agence_sel]
    if not df_mand.empty:
        df_mand = df_mand[df_mand["agence"] == agence_sel]

# ── En-tête ───────────────────────────────────────────────────────
ag_label = agence_sel if agence_sel != "Toutes" else "tout le réseau"
st.markdown(f"## 📞 Mes appels du jour")
st.markdown(
    f"<span style='color:#888;font-size:13px'>"
    f"{ag_label} · {date.today().strftime('%A %d %B %Y').capitalize()}"
    f"</span>", unsafe_allow_html=True,
)
st.markdown("<hr class='sep'>", unsafe_allow_html=True)

# ── Construire les 3 listes ───────────────────────────────────────
if not df_mand.empty:
    l1 = df_mand[(df_mand["classement"] == "exclusif") & ((df_mand["sans_suivi"] == True) | (df_mand["age_suivi_j"] > 60))].copy()
    if not l1.empty:
        l1["_score"], l1["_profil"], l1["_color"], l1["_icon"], l1["_action"] = zip(*l1.apply(lambda r: scorer_action(r, "mandat"), axis=1))
        l1 = l1.sort_values("_score", ascending=False).head(nb_par_liste)
else:
    l1 = pd.DataFrame()

l2 = df_eval[(df_eval["actif"] == True) & (df_eval["match_mandat_id"].isna()) & (df_eval["sans_suivi"] == True)].copy()
if not l2.empty:
    l2["_score"], l2["_profil"], l2["_color"], l2["_icon"], l2["_action"] = zip(*l2.apply(lambda r: scorer_action(r, "eval"), axis=1))
    l2 = l2.sort_values("age_estimation_jours", ascending=False).head(nb_par_liste)

df_det = st.session_state.get("df_detection", pd.DataFrame())
if not df_det.empty and "ademe_status" in df_det.columns:
    l3 = df_det[(df_det["ademe_status"] == "trouve") & (df_det.get("dpe_age_mois", pd.Series(dtype=float)) <= 6)].copy()
    if agence_sel != "Toutes" and "agence" in l3.columns:
        l3 = l3[l3["agence"] == agence_sel]
    l3 = l3.sort_values("dpe_age_mois", ascending=True).head(nb_par_liste)
else:
    l3 = pd.DataFrame()

# ── KPIs ─────────────────────────────────────────────────────────
n_total = len(l1) + len(l2) + len(l3)
st.markdown(f"""
<div class="krow">
  {kpi("Total actions", n_total, "contacts à traiter", "blu")}
  {kpi("🔴 Urgents", len(l1), "mandats exclusifs", "red")}
  {kpi("🟠 Chauds", len(l2), "jamais contactés", "ora")}
  {kpi("🟣 Signal DPE", len(l3), "DPE récents", "pur")}
</div>
""", unsafe_allow_html=True)

if n_total == 0:
    st.success("✅ Aucune action urgente pour cette agence. Bon travail !")
    st.stop()

# ── Fonction carte contact ────────────────────────────────────────
def render_card(row, source, color, icon, action, key_prefix):
    nom = S(row.get("nom_principal","—"))
    tel = S(row.get("client1_tel","") or row.get("tel_jointure",""))
    email = S(row.get("client1_email",""))
    addr = S(row.get("adresse_bien","—"))
    ag = S(row.get("agence",""))
    
    if source == "mandat":
        age_s = fmt_age(row.get("age_suivi_j"))
        meta = f"Mandat {str(row.get('classement','')).upper()} · dernier suivi : {age_s}"
        b1 = badge(str(row.get("classement","")).upper(), "red" if str(row.get("classement","")).upper()=="EXCLUSIF" else "gry")
        b2 = badge(f"Suivi {age_s}", "red" if float(row.get("age_suivi_j") or 0)>90 else "ora")
        row_id, src_key = str(row.get("id_mandat","")), "mandat"
    else:
        age_e = fmt_age(row.get("age_estimation_jours"))
        meta = f"Éval · {age_e} · {str(row.get('type_bien','')).capitalize()}"
        b1 = badge("SANS SUIVI", "ora") if row.get("sans_suivi") else badge(f"Suivi {fmt_age(row.get('age_suivi_j'))}", "yel")
        b2 = dpe_badge(str(row.get("dpe_label","") or "")) if row.get("dpe_label") else ""
        row_id, src_key = str(row.get("id_evaluation","")), "eval"

    stream_badges_html = ""
    if stream_disponible() and row.get("code_postal") and row.get("type_bien"):
        td_card = get_tendance_secteur(str(row.get("code_postal")), str(row.get("type_bien")))
        if td_card.get("ok") and td_card.get("tendance") == "baisse":
            stream_badges_html += f'<span class="cc-badge badge-red">↓ Marché en baisse {td_card.get("variation_pct",0):+.1f}%</span> '

    col_card, col_btn = st.columns([5, 1])
    with col_card:
        st.markdown(f"""
        <div class="call-card {color}">
          <div class="cc-icon">{icon}</div>
          <div class="cc-body">
            <div class="cc-name">{nom}</div><div class="cc-addr">{addr} · {ag}</div>
            <div class="cc-meta">{b1} {b2} <span>{meta}</span></div>
            <div class="cc-meta" style="margin-top:4px"><span style="font-weight:600;color:#111">📞 {tel} {f'· ✉️ {email}' if email else ''}</span></div>
            <div class="cc-action">→ {action}</div>{stream_badges_html}
          </div>
        </div>""", unsafe_allow_html=True)
    with col_btn:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.button("Voir fiche", key=f"{key_prefix}_{row_id}", type="primary", use_container_width=True):
            st.session_state["fiche_id"], st.session_state["fiche_source"] = row_id, src_key
            st.switch_page("pages/2_Fiche_Prospect.py")

# ── ONGLETS ───────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    f"🔴 Mandats Urgents ({len(l1)})", 
    f"🟠 Évals Sans Suivi ({len(l2)})", 
    f"🟣 Signaux DPE ({len(l3)})"
])

with tab1:
    if l1.empty: st.info("Aucun mandat exclusif en souffrance.")
    else:
        st.caption("⚠️ Ces mandats exclusifs n'ont pas été suivis depuis plus de 60 jours.")
        for i, (_, row) in enumerate(l1.iterrows()): render_card(row, "mandat", row["_color"], row["_icon"], row["_action"], f"m_{i}")

with tab2:
    if l2.empty: st.info("Aucune évaluation en attente de suivi.")
    else:
        st.caption("Ces propriétaires ont demandé une estimation mais n'ont reçu aucun suivi.")
        for i, (_, row) in enumerate(l2.iterrows()): render_card(row, "eval", row["_color"], row["_icon"], row["_action"], f"e_{i}")

with tab3:
    if l3.empty: st.info("Lancez l'analyse ADEME depuis **Détection DPE** pour voir les signaux.")
    else:
        st.caption("Ces biens ont un DPE récent (< 6 mois). Le DPE est un signal fort de projet vendeur.")
        for i, (_, row) in enumerate(l3.iterrows()):
            sc, profil, color, icon, action = scorer_action(row, "eval")
            render_card(row, "eval", "pur", "🟣", "Signal DPE — appeler", f"d_{i}")