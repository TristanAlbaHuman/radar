"""
1_Mes_Appels.py - Radar Mandats V2
Page principale de l'agent : liste d'appels ordonnée par urgence.
Trois listes : 🔴 Mandats urgents · 🟠 Évals jamais suivies · 🟡 Signal DPE
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
    st.markdown("### Mon agence")
    agences = sorted(df_eval["agence"].dropna().unique())
    agence_sel = st.selectbox("Agence", ["Toutes"] + agences)
    nb_par_liste = st.slider("Contacts par liste", 10, 100, 30, step=10)
    st.markdown("---")
    st.markdown("### Afficher")
    show_mandats = st.checkbox("Mandats urgents", True)
    show_evals   = st.checkbox("Évals sans suivi", True)
    show_dpe     = st.checkbox("Signaux DPE", True)
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
# LISTE 1 : Mandats exclusifs à relancer
if not df_mand.empty:
    l1 = df_mand[
        (df_mand["classement"] == "exclusif") &
        ((df_mand["sans_suivi"] == True) | (df_mand["age_suivi_j"] > 60))
    ].copy()
    l1["_score"], l1["_profil"], l1["_color"], l1["_icon"], l1["_action"] = zip(
        *l1.apply(lambda r: scorer_action(r, "mandat"), axis=1)
    )
    l1 = l1.sort_values("_score", ascending=False).head(nb_par_liste)
else:
    l1 = pd.DataFrame()

# LISTE 2 : Évals actives jamais suivies
l2 = df_eval[
    (df_eval["actif"] == True) &
    (df_eval["match_mandat_id"].isna()) &
    (df_eval["sans_suivi"] == True)
].copy()
l2["_score"], l2["_profil"], l2["_color"], l2["_icon"], l2["_action"] = zip(
    *l2.apply(lambda r: scorer_action(r, "eval"), axis=1)
)
l2 = l2.sort_values("age_estimation_jours", ascending=False).head(nb_par_liste)

# LISTE 3 : Signaux DPE (si données ADEME disponibles)
df_det = st.session_state.get("df_detection", pd.DataFrame())
if not df_det.empty and "ademe_status" in df_det.columns:
    l3 = df_det[
        (df_det["ademe_status"] == "trouve") &
        (df_det.get("dpe_age_mois", pd.Series(dtype=float)) <= 6)
    ].copy()
    if agence_sel != "Toutes" and "agence" in l3.columns:
        l3 = l3[l3["agence"] == agence_sel]
    l3 = l3.sort_values("dpe_age_mois", ascending=True).head(nb_par_liste)
else:
    l3 = pd.DataFrame()

# ── KPIs ─────────────────────────────────────────────────────────
n1 = len(l1)
n2 = len(l2)
n3 = len(l3)
n_total = n1 + n2 + n3

st.markdown(f"""
<div class="krow">
  {kpi("Total actions", n_total, "contacts à traiter", "blu")}
  {kpi("🔴 Urgents", n1, "mandats exclusifs", "red")}
  {kpi("🟠 Chauds", n2, "jamais contactés", "ora")}
  {kpi("🟣 Signal DPE", n3, "DPE récents", "pur")}
</div>
""", unsafe_allow_html=True)

if n_total == 0:
    st.success("✅ Aucune action urgente pour cette agence. Bon travail !")
    st.stop()

# ── Fonction carte contact ────────────────────────────────────────
def render_card(row, source, color, icon, action, key_prefix):
    nom    = S(row.get("nom_principal","—"))
    tel    = S(row.get("client1_tel","") or row.get("tel_jointure",""))
    email  = S(row.get("client1_email",""))
    addr   = S(row.get("adresse_bien","—"))
    ag     = S(row.get("agence",""))
    tb     = str(row.get("type_bien","")).capitalize()

    if source == "mandat":
        age_s  = fmt_age(row.get("age_suivi_j"))
        d_mand = fmt_date(row.get("date_mandat"))
        cl     = str(row.get("classement","")).upper()
        meta   = f"Mandat {cl} · signé {d_mand} · dernier suivi : {age_s}"
        b1     = badge(cl, "red" if cl=="EXCLUSIF" else "gry")
        b2     = badge(f"Suivi {age_s}", "red" if float(row.get("age_suivi_j") or 0)>90 else "ora")
        row_id = str(row.get("id_mandat",""))
        src_key = "mandat"
    else:
        age_e  = fmt_age(row.get("age_estimation_jours"))
        d_eval = fmt_date(row.get("date_estimation"))
        dpe_l  = str(row.get("dpe_label","") or "")
        meta   = f"Éval du {d_eval} · {age_e} · {tb}"
        b1     = badge("SANS SUIVI", "ora") if row.get("sans_suivi") else badge(f"Suivi {fmt_age(row.get('age_suivi_j'))}", "yel")
        b2     = dpe_badge(dpe_l) if dpe_l else ""
        row_id = str(row.get("id_evaluation",""))
        src_key = "eval"

    contact_html = f"📞 {tel}" if tel and tel != "—" else ""
    email_html   = f" · ✉️ {email}" if email and email != "—" else ""

    # Stream Estate : badges contextuels (avec cache → pas de surcharge)
    stream_badges_html = ""
    if stream_disponible():
        cp_card = str(row.get("code_postal","") or "")
        tb_card = str(row.get("type_bien","") or "")
        if cp_card and tb_card:
            td_card = get_tendance_secteur(cp_card, tb_card)
            if td_card.get("ok") and td_card.get("tendance") == "baisse":
                v_td = td_card.get("variation_pct", 0)
                stream_badges_html += f'<span class="cc-badge badge-red">↓ Marché en baisse {v_td:+.1f}% — vendre maintenant</span> '
            exp_card = get_biens_expires(cp_card, tb_card, mois_max=12)
            if exp_card.get("signal"):
                nb_exp = exp_card.get("nb", 0)
                stream_badges_html += f'<span class="cc-badge badge-ora">⚠️ {nb_exp} bien(s) expiré(s) ce secteur</span>'

    col_card, col_btn = st.columns([5, 1])
    with col_card:
        st.markdown(f"""
        <div class="call-card {color}">
          <div class="cc-icon">{icon}</div>
          <div class="cc-body">
            <div class="cc-name">{nom}</div>
            <div class="cc-addr">{addr} · {ag}</div>
            <div class="cc-meta">
              {b1} {b2}
              <span>{meta}</span>
            </div>
            <div class="cc-meta" style="margin-top:4px">
              <span style="font-weight:600;color:#111">{contact_html}{email_html}</span>
            </div>
            <div class="cc-action">→ {action}</div>
            {stream_badges_html}
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col_btn:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.button("Voir fiche", key=f"{key_prefix}_{row_id}", type="primary"):
            st.session_state["fiche_id"]     = row_id
            st.session_state["fiche_source"] = src_key
            st.switch_page("pages/2_Fiche_Prospect.py")


# ── LISTE 1 — Mandats urgents ─────────────────────────────────────
if show_mandats and not l1.empty:
    st.markdown(
        f'<div class="sec">🔴 Mandats exclusifs à relancer — {len(l1)} contacts</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-size:12px;color:#e74c3c;margin-bottom:10px;font-weight:600'>"
        "⚠️ Ces mandats exclusifs n'ont pas été suivis depuis plus de 60 jours — "
        "risque de perte ou de non-renouvellement."
        "</div>", unsafe_allow_html=True,
    )
    for i, (_, row) in enumerate(l1.iterrows()):
        sc, profil, color, icon, action = scorer_action(row, "mandat")
        render_card(row, "mandat", color, icon, action, f"m_{i}")

# ── LISTE 2 — Évals jamais suivies ───────────────────────────────
if show_evals and not l2.empty:
    st.markdown(
        f'<div class="sec">🟠 Évaluations actives — jamais recontactées — {len(l2)} contacts</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-size:12px;color:#e67e22;margin-bottom:10px;font-weight:600'>"
        "Ces propriétaires ont demandé une estimation mais n'ont reçu aucun suivi. "
        "Qualification rapide — 5 minutes par appel."
        "</div>", unsafe_allow_html=True,
    )
    for i, (_, row) in enumerate(l2.iterrows()):
        sc, profil, color, icon, action = scorer_action(row, "eval")
        render_card(row, "eval", color, icon, action, f"e_{i}")

# ── LISTE 3 — Signaux DPE ────────────────────────────────────────
if show_dpe:
    if not l3.empty:
        st.markdown(
            f'<div class="sec">🟣 Signaux DPE récents — {len(l3)} biens</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='font-size:12px;color:#8e44ad;margin-bottom:10px;font-weight:600'>"
            "Ces biens ont un DPE récent (< 6 mois). Le DPE est un signal fort de projet vendeur."
            "</div>", unsafe_allow_html=True,
        )
        for i, (_, row) in enumerate(l3.iterrows()):
            sc, profil, color, icon, action = scorer_action(row, "eval")
            render_card(row, "eval", "pur", "🟣", "Signal DPE — appeler", f"d_{i}")
    else:
        with st.expander("🟣 Signaux DPE — non disponible"):
            st.markdown(
                "Lancez l'analyse ADEME depuis **Détection DPE** pour voir les signaux DPE "
                "correspondant à vos évaluations actives.",
            )

# ── Footer ────────────────────────────────────────────────────────
st.markdown("<hr class='sep'>", unsafe_allow_html=True)
st.markdown(
    f"<span style='font-size:11px;color:#aaa'>"
    f"Liste générée le {date.today().strftime('%d/%m/%Y')} · "
    f"Données CRM : {st.session_state.get('filename','—')}</span>",
    unsafe_allow_html=True,
)
