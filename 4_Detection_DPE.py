"""
4_Detection_DPE.py - Radar Mandats V2
Détection DPE & Statistiques Agence.
Graphiques analytiques, listes CRM, et matching croisé ADEME.
"""

import streamlit as st
import pandas as pd
import urllib.parse
import html as _html
import plotly.express as px
from datetime import date
from ademe_matcher import (
    rnvp_adresse, score_match, normaliser_df_ademe,
    charger_fichiers_ademe, calculer_score_maturite,
)
from ui_utils import CSS, S, fmt_date, dpe_badge, kpi, badge, map_links

st.markdown(CSS, unsafe_allow_html=True)

# ── 1. CHARGEMENT DES DONNÉES CRM ─────────────────────────────────
# On récupère les dataframes stockés en session (evaluations et mandats)
df_eval = st.session_state.get("df_scored", st.session_state.get("df_s", pd.DataFrame()))
df_mand = st.session_state.get("df_m", st.session_state.get("df_mandats", pd.DataFrame()))

if df_eval.empty and df_mand.empty:
    st.warning("⚠️ Chargez votre fichier CRM depuis l'accueil pour accéder aux données.")
    st.stop()

# ── 2. SIDEBAR : PARAMÈTRES ET FILTRES ────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Paramètres DPE")
    age_dpe_max  = st.slider("DPE de moins de X mois", 1, 36, 6)
    seuil_match  = st.slider("Score RNVP minimum (matchs)", 85, 100, 90, step=5)
    
    st.markdown("---")
    st.markdown("### 🔍 Filtres CRM")
    # Liste des agences uniques (combinée entre eval et mandats)
    agences_dispos = set(df_eval["agence"].dropna().unique()) | set(df_mand["agence"].dropna().unique())
    ag_sel = st.multiselect("Agences", sorted(list(agences_dispos)), placeholder="Toutes les agences")
    
    dpe_labels = st.multiselect("Étiquettes DPE (Filtre)", list("ABCDEFG"), default=[])

# ── FILTRAGE DES DATAFRAMES CRM ───────────────────────────────────
if ag_sel:
    df_eval_f = df_eval[df_eval["agence"].isin(ag_sel)].copy()
    df_mand_f = df_mand[df_mand["agence"].isin(ag_sel)].copy()
else:
    df_eval_f = df_eval.copy()
    df_mand_f = df_mand.copy()

# ── EN-TÊTE ───────────────────────────────────────────────────────
st.markdown("## 🎯 Détection DPE & Analyse Agence")
st.markdown(
    "<span style='color:#888;font-size:13px'>"
    "Analysez votre portefeuille et identifiez les vendeurs sur le marché grâce aux DPE récents."
    "</span>", unsafe_allow_html=True,
)
st.markdown("<hr class='sep'>", unsafe_allow_html=True)

# ── UPLOAD ADEME ──────────────────────────────────────────────────
st.markdown('<div class="sec">1. Charger la base ADEME (DPE)</div>', unsafe_allow_html=True)
ademe_files = st.file_uploader(
    "Importez vos exports CSV de l'ADEME", type=["csv","xlsx"],
    accept_multiple_files=True, key="ademe_det", label_visibility="collapsed",
)

df_ademe = None
if ademe_files:
    noms = "_".join(f.name for f in ademe_files)
    ck   = f"det_{noms}"
    if st.session_state.get("det_ademe_key") != ck:
        with st.spinner(f"Chargement de {len(ademe_files)} fichier(s) ADEME..."):
            df_ademe = charger_fichiers_ademe(ademe_files)
        st.session_state["det_ademe_df"]  = df_ademe
        st.session_state["det_ademe_key"] = ck
    else:
        df_ademe = st.session_state["det_ademe_df"]

if df_ademe is None:
    df_ademe = st.session_state.get("det_ademe_df")

# Nettoyage et préparation ADEME
df_a = pd.DataFrame()
if df_ademe is not None and not df_ademe.empty:
    df_a = df_ademe.copy()
    df_a["_temp_id"] = range(len(df_a)) # ID unique temporaire pour le matching
    
    col_date = next((c for c in ["date_dpe","date_etablissement_dpe"] if c in df_a.columns), None)
    if col_date:
        df_a["_date"] = pd.to_datetime(df_a[col_date], errors="coerce")
        df_a["_age"]  = ((pd.Timestamp(date.today()) - df_a["_date"]).dt.days / 30.44).round(1)
        df_a = df_a[df_a["_age"] <= age_dpe_max].copy()

    col_etiq = next((c for c in ["etiquette_dpe"] if c in df_a.columns), None)
    if dpe_labels and col_etiq:
        df_a = df_a[df_a[col_etiq].str.upper().str.strip().isin(dpe_labels)]

    df_a = df_a.sort_values("_date", ascending=False, na_position="last").reset_index(drop=True)

    def adresse_complete_ademe(row):
        ban   = str(row.get("adresse_ban","") or "")
        cp    = str(row.get("cp_ban") or row.get("code_postal_ban","") or "")
        ville = str(row.get("ville_ban") or row.get("nom_commune_ban","") or "")
        return f"{ban} {cp} {ville}".strip()

    df_a["_addr_full"] = df_a.apply(adresse_complete_ademe, axis=1)

# ── ONGLETS DE L'INTERFACE ────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Statistiques", "📋 Listes CRM", "🎯 Matchs & Opportunités DPE"])

# ═════════════════════════════════════════════════════════════════
with tab1: # 📊 STATISTIQUES
# ═════════════════════════════════════════════════════════════════
    st.markdown('<div class="sec">Analyse des Évaluations</div>', unsafe_allow_html=True)
    if not df_eval_f.empty and "date_estimation" in df_eval_f.columns:
        c1, c2 = st.columns(2)
        
        # Graphique 1 : Éval par Mois-Année
        df_e_plot = df_eval_f.dropna(subset=["date_estimation"]).copy()
        df_e_plot['Mois'] = df_e_plot['date_estimation'].dt.to_period('M').astype(str)
        counts_e_mois = df_e_plot.groupby('Mois').size().reset_index(name='Nombre')
        fig_e_mois = px.bar(counts_e_mois, x='Mois', y='Nombre', title="Évaluations par mois", text_auto=True, color_discrete_sequence=['#3498db'])
        fig_e_mois.update_layout(xaxis_title="Mois", yaxis_title="Nb Évaluations")
        c1.plotly_chart(fig_e_mois, use_container_width=True)
        
        # Graphique 2 : Éval par Statut
        if "actif" in df_e_plot.columns:
            df_e_plot['Statut'] = df_e_plot['actif'].apply(lambda x: 'Actif' if x else 'Inactif')
            counts_e_statut = df_e_plot.groupby('Statut').size().reset_index(name='Nombre')
            fig_e_statut = px.pie(counts_e_statut, names='Statut', values='Nombre', title="Répartition des statuts (Évaluations)", color='Statut', color_discrete_map={'Actif':'#2ecc71', 'Inactif':'#e74c3c'})
            c2.plotly_chart(fig_e_statut, use_container_width=True)
    else:
        st.info("Pas assez de données pour afficher les statistiques d'évaluations.")

    st.markdown('<div class="sec">Analyse des Mandats</div>', unsafe_allow_html=True)
    if not df_mand_f.empty and "date_mandat" in df_mand_f.columns:
        c3, c4 = st.columns(2)