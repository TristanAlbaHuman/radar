"""
0_Accueil.py - Radar Mandats V2
Onboarding : upload CRM + sélection profil.
"""

import streamlit as st
import pandas as pd
import io
from datetime import date
from data_loader import charger_et_nettoyer
from scoring import calculer_scores
from ui_utils import CSS, banner

st.markdown(CSS, unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def process_file(file_bytes):
    buf = io.BytesIO(file_bytes)
    data = charger_et_nettoyer(buf)
    df_scored = calculer_scores(data["radar"])
    return df_scored, data["mandats"], data["mandats_sans_suivi"]

def validate_sheets(file_bytes):
    xl = pd.ExcelFile(io.BytesIO(file_bytes))
    required = {
        "evaluations_full":            "Estimations",
        "mandats_sans_ssp":            "Mandats actifs",
        "mandats_sans_ssp_sans_suivi": "Mandats urgents",
    }
    return {s: {"label": l, "found": s in xl.sheet_names} for s, l in required.items()}

# ── Hero ─────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;padding:2.5rem 0 1.5rem;">
  <div style="font-size:52px;margin-bottom:10px">📡</div>
  <h1 style="font-size:2.4rem;font-weight:800;color:#111;margin-bottom:.5rem;">Radar Mandats</h1>
  <p style="font-size:1rem;color:#666;max-width:480px;margin:auto;line-height:1.6;">
    Détectez, priorisez et activez vos vendeurs potentiels.<br/>
    Chaque agent sait exactement qui appeler.
  </p>
  <div style="font-size:12px;color:#bbb;margin-top:10px">{date.today().strftime('%d %B %Y')}</div>
</div>
<hr class="sep">
""", unsafe_allow_html=True)

# ── Statut données ────────────────────────────────────────────────
data_loaded = st.session_state.get("df_scored") is not None

if data_loaded:
    df    = st.session_state["df_scored"]
    df_m  = st.session_state.get("df_mandats", pd.DataFrame())
    today = pd.Timestamp(date.today())
    df["age_suivi_j"] = (today - df["date_dernier_suivi"]).dt.days
    df_m["age_suivi_j"] = (today - df_m["date_dernier_suivi"]).dt.days if not df_m.empty else 0

    n_urgent = int(
        df_m[(df_m.get("classement","") == "exclusif") &
             ((df_m.get("sans_suivi",False)==True) | (df_m.get("age_suivi_j",0)>60))
        ].pipe(len) if not df_m.empty else 0
    )
    n_chaud = int((df["actif"]==True & df["match_mandat_id"].isna() & df["sans_suivi"]==True).sum())

    st.markdown(banner(
        f"Données chargées — <b>{st.session_state.get('filename','')}</b> · "
        f"{len(df):,} évaluations · {len(df_m):,} mandats · "
        f"{df['agence'].nunique()} agences",
        color="grn", icon="✅"
    ), unsafe_allow_html=True)

    if n_urgent > 0:
        st.markdown(banner(
            f"<b>{n_urgent:,} mandats exclusifs</b> à relancer d'urgence (>60j sans suivi)",
            color="red", icon="🔴"
        ), unsafe_allow_html=True)

    if st.button("Charger un nouveau fichier", type="secondary"):
        for k in ["df_scored","df_mandats","df_mss","filename"]:
            st.session_state.pop(k, None)
        st.cache_data.clear()
        st.rerun()

    # ── Navigation rapide selon profil ────────────────────────────
    st.markdown('<div class="sec">Accès rapide par profil</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div style="background:#fff;border:1px solid #eaeaea;border-radius:12px;padding:22px;
                    border-top:4px solid #e74c3c;text-align:center;">
          <div style="font-size:32px;margin-bottom:8px">📞</div>
          <div style="font-size:15px;font-weight:700;color:#111;margin-bottom:6px">Agent terrain</div>
          <div style="font-size:12px;color:#888;line-height:1.5">
            Mes appels du jour<br/>Fiche prospect complète<br/>Scripts personnalisés
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style="background:#fff;border:1px solid #eaeaea;border-radius:12px;padding:22px;
                    border-top:4px solid #2d6cdf;text-align:center;">
          <div style="font-size:32px;margin-bottom:8px">🏢</div>
          <div style="font-size:15px;font-weight:700;color:#111;margin-bottom:6px">Directeur agence</div>
          <div style="font-size:12px;color:#888;line-height:1.5">
            Tableau de bord agence<br/>Opportunités dormantes<br/>Classement conseillers
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div style="background:#fff;border:1px solid #eaeaea;border-radius:12px;padding:22px;
                    border-top:4px solid #27ae60;text-align:center;">
          <div style="font-size:32px;margin-bottom:8px">🌐</div>
          <div style="font-size:15px;font-weight:700;color:#111;margin-bottom:6px">Direction réseau</div>
          <div style="font-size:12px;color:#888;line-height:1.5">
            Vue macro réseau<br/>Funnels de conversion<br/>Pilotage performance
          </div>
        </div>
        """, unsafe_allow_html=True)

else:
    # ── Upload ────────────────────────────────────────────────────
    st.markdown("### Chargez votre fichier CRM")
    st.markdown(
        "<p style='color:#888;font-size:13px'>Format Excel — "
        "3 onglets : <code>evaluations_full</code>, <code>mandats_sans_ssp</code>, "
        "<code>mandats_sans_ssp_sans_suivi</code></p>",
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader("Fichier CRM", type=["xlsx"], label_visibility="collapsed")

    if uploaded is not None:
        file_bytes = uploaded.read()
        with st.spinner("Vérification..."):
            sheets = validate_sheets(file_bytes)
        chips_html = " ".join(
            f'<span style="display:inline-block;padding:3px 10px;border-radius:6px;'
            f'font-size:12px;margin:2px;background:{"#eafaf1;color:#1e8449" if v["found"] else "#fde8e8;color:#c0392b"};">'
            f'{"✓" if v["found"] else "✗"} {v["label"]}</span>'
            for v in sheets.values()
        )
        st.markdown(chips_html, unsafe_allow_html=True)

        if not all(v["found"] for v in sheets.values()):
            st.error(f"Onglets manquants : {', '.join(v['label'] for v in sheets.values() if not v['found'])}")
        else:
            with st.spinner("Chargement et scoring..."):
                try:
                    df_s, df_m, df_mss = process_file(file_bytes)
                    st.session_state["df_scored"]  = df_s
                    st.session_state["df_mandats"] = df_m
                    st.session_state["df_mss"]     = df_mss
                    st.session_state["filename"]   = uploaded.name
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")
                    st.exception(e)
