"""
main.py - Radar Mandats V2
Navigation 3 profils : Agent / Directeur / Direction
"""

import streamlit as st

pg = st.navigation(
    {
        "": [
            st.Page("pages/0_Accueil.py", title="Accueil", icon="📡", default=True),
        ],
        "🏠 Agent terrain": [
            st.Page("pages/1_Mes_Appels.py",     title="Mes appels du jour", icon="📞"),
            st.Page("pages/2_Fiche_Prospect.py", title="Fiche prospect",     icon="👤"),
        ],
        "📊 Directeur agence": [
            st.Page("pages/3_Tableau_Agence.py", title="Tableau de bord",    icon="🏢"),
            st.Page("pages/4_Detection_DPE.py",  title="Détection DPE",      icon="🎯"),
        ],
        "🌐 Direction réseau": [
            st.Page("pages/5_Vue_Reseau.py",     title="Vue réseau",         icon="🌐"),
            st.Page("pages/6_Pilotage.py",       title="Pilotage",           icon="📈"),
        ],
    },
    position="sidebar",
    expanded=True,
)

st.set_page_config(
    page_title="Radar Mandats",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg.run()
