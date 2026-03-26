"""
2_Fiche_Prospect.py - Radar Mandats V2
Fiche prospect complète : infos + scripts + boutons action.
"""

import streamlit as st
import pandas as pd
from datetime import date
from ui_utils import (
    CSS, S, fmt_date, fmt_age, badge, dpe_badge, kpi,
    generer_script, generer_objet_email, generer_sms,
    scorer_action, map_links,
)
from stream_estate import (
    section_marche_fiche, section_signal_expire, section_comparables,
    get_points_interet, _disponible as stream_disponible,
    script_biens_expires,
)

st.markdown(CSS, unsafe_allow_html=True)

if st.session_state.get("df_scored") is None:
    st.warning("Chargez votre fichier CRM depuis l'accueil.")
    st.stop()

df_eval = st.session_state["df_scored"]
df_mand = st.session_state.get("df_mandats", pd.DataFrame())
today   = pd.Timestamp(date.today())

# ── Sélection du dossier ─────────────────────────────────────────
fiche_id     = st.session_state.get("fiche_id")
fiche_source = st.session_state.get("fiche_source", "eval")

with st.sidebar:
    st.markdown("### Recherche")
    source_sel = st.radio("Type de dossier", ["Évaluation","Mandat"], index=0 if fiche_source != "mandat" else 1)
    src = "eval" if source_sel == "Évaluation" else "mandat"

    df_src = df_eval if src == "eval" else df_mand
    id_col = "id_evaluation" if src == "eval" else "id_mandat"
    nom_col = "nom_principal"

    options = df_src[[id_col, nom_col, "adresse_bien"]].dropna(subset=[id_col])
    options["label"] = (
        options[nom_col].fillna("—") + " — " +
        options["adresse_bien"].fillna("—").str[:40]
    )
    options_dict = dict(zip(options["label"], options[id_col].astype(str)))

    sel_label = st.selectbox("Dossier", list(options_dict.keys()),
                              index=0 if not fiche_id else None)
    if sel_label:
        fiche_id = str(options_dict[sel_label])

# ── Charger le dossier ────────────────────────────────────────────
df_src = df_eval if src == "eval" else df_mand
id_col = "id_evaluation" if src == "eval" else "id_mandat"
mask = df_src[id_col].astype(str) == str(fiche_id)
if not mask.any():
    st.info("Sélectionnez un dossier dans le panneau de gauche.")
    st.stop()

row = df_src[mask].iloc[0]

# ── En-tête dossier ───────────────────────────────────────────────
age_suivi_j = (today - row.get("date_dernier_suivi")).days if pd.notna(row.get("date_dernier_suivi")) else None
sc, profil, color, icon, action = scorer_action(row, src)

st.markdown(f"""
<div style="background:#fff;border:1px solid #eaeaea;border-radius:14px;
            padding:20px 24px;border-left:5px solid
            {'#e74c3c' if color=='red' else '#e67e22' if color=='ora' else '#f1c40f' if color=='yel' else '#8e44ad' if color=='pur' else '#2d6cdf'};
            margin-bottom:1.2rem;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <div style="font-size:22px;font-weight:800;color:#111;">{icon} {S(row.get('nom_principal','—'))}</div>
      <div style="font-size:13px;color:#666;margin-top:4px">{S(row.get('adresse_bien','—'))}</div>
      <div style="font-size:12px;color:#999;margin-top:3px">{S(row.get('agence',''))} · {str(row.get('type_bien','')).capitalize()}</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:28px;font-weight:800;color:#2d6cdf;">{sc}</div>
      <div style="font-size:10px;color:#aaa;">/100 urgence</div>
    </div>
  </div>
  <div style="margin-top:10px;font-size:12px;font-weight:600;
              color:{'#e74c3c' if color=='red' else '#e67e22' if color=='ora' else '#8e44ad' if color=='pur' else '#999'}">
    → {action}
  </div>
</div>
""", unsafe_allow_html=True)

# ── 3 colonnes : Contact / Bien / Dates ──────────────────────────
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown('<div class="sec">Contact</div>', unsafe_allow_html=True)
    tel    = S(row.get("client1_tel","") or row.get("tel_jointure",""))
    email  = S(row.get("client1_email",""))
    tel2   = S(row.get("client2_tel",""))
    nom2   = S(row.get("client2_nom",""))
    tel3   = S(row.get("client3_tel",""))
    nom3   = S(row.get("client3_nom",""))

    if tel != "—":
        st.markdown(f"📞 **{tel}**")
    if email != "—":
        st.markdown(f"✉️ {email}")
    if nom2 != "—":
        st.markdown(f"👤 {nom2} · {tel2}")
    if nom3 != "—":
        st.markdown(f"👤 {nom3} · {tel3}")

    addr  = S(row.get("adresse_bien",""))
    st.markdown(f"📍 {addr}")
    st.markdown(map_links(addr), unsafe_allow_html=True)

with c2:
    st.markdown('<div class="sec">Bien</div>', unsafe_allow_html=True)
    tb = str(row.get("type_bien","—")).capitalize()
    cp = S(row.get("code_postal",""))
    vi = S(row.get("ville",""))
    st.markdown(f"**{tb}** · {cp} {vi}")

    # DPE si disponible
    df_det = st.session_state.get("df_detection", pd.DataFrame())
    dpe_info = None
    if not df_det.empty and src == "eval":
        eid = row.get("id_evaluation")
        if eid is not None:
            m = df_det[df_det.get("id_evaluation","") == eid]
            if not m.empty and m.iloc[0].get("ademe_status") == "trouve":
                dpe_info = m.iloc[0]

    if dpe_info is not None:
        lbl = str(dpe_info.get("dpe_label","") or "")
        age = dpe_info.get("dpe_age_mois")
        surf = dpe_info.get("dpe_surface")
        conso = dpe_info.get("dpe_conso")
        st.markdown(
            f"DPE {dpe_badge(lbl)} "
            f"· {f'{age:.0f} mois' if age else '—'} "
            f"· {f'{float(surf):.0f} m²' if surf and surf != '—' else '—'} "
            f"· {f'{float(conso):.0f} kWh/m²' if conso and conso != '—' else '—'}",
            unsafe_allow_html=True,
        )

    # ── Stream Estate : prix marché ──────────────────────────────
    if stream_disponible():
        cp_row = str(row.get("code_postal","") or "")
        tb_row = str(row.get("type_bien","") or "maison")
        marche_html = section_marche_fiche(cp_row, tb_row)
        if marche_html:
            st.markdown(marche_html, unsafe_allow_html=True)
    else:
        st.caption("Configurez STREAM_ESTATE_API_KEY pour les données marché.")

with c3:
    st.markdown('<div class="sec">Historique</div>', unsafe_allow_html=True)
    if src == "eval":
        d_eval = fmt_date(row.get("date_estimation"))
        age_e  = fmt_age(row.get("age_estimation_jours"))
        st.markdown(f"Estimation : **{d_eval}** ({age_e})")
        d_suivi = fmt_date(row.get("date_dernier_suivi"))
        age_s   = fmt_age(age_suivi_j) if age_suivi_j else "jamais"
        st.markdown(f"Dernier suivi : **{d_suivi}** ({age_s})")
        if pd.notna(row.get("match_mandat_id")):
            st.markdown(badge("Mandat associé", "grn"), unsafe_allow_html=True)
        elif row.get("sans_suivi"):
            st.markdown(badge("Jamais contacté", "ora"), unsafe_allow_html=True)
    else:
        d_mand = fmt_date(row.get("date_mandat"))
        cl = str(row.get("classement","")).upper()
        age_m  = fmt_age(row.get("age_mandat_j"))
        st.markdown(f"Mandat {badge(cl, 'red' if cl=='EXCLUSIF' else 'gry')} : **{d_mand}** ({age_m})", unsafe_allow_html=True)
        d_suivi = fmt_date(row.get("date_dernier_suivi"))
        age_s   = fmt_age(age_suivi_j) if age_suivi_j else "jamais"
        st.markdown(f"Dernier suivi : **{d_suivi}** ({age_s})")
        if row.get("sans_suivi"):
            st.markdown(badge("Aucun suivi enregistré", "red"), unsafe_allow_html=True)

# ── Stream Estate : signal biens expirés + comparables ──────────
if stream_disponible():
    cp_row  = str(row.get("code_postal","") or "")
    tb_row  = str(row.get("type_bien","") or "maison")
    badge_exp, angle_exp = section_signal_expire(cp_row, tb_row)
    comp_html = section_comparables(cp_row, tb_row)

    if badge_exp or comp_html:
        st.markdown('<div class="sec">Données marché — Stream Estate</div>', unsafe_allow_html=True)
        col_se1, col_se2 = st.columns([1, 2])
        with col_se1:
            if badge_exp:
                st.markdown(badge_exp, unsafe_allow_html=True)
                if angle_exp:
                    st.markdown(
                        f'<div class="script-box" style="margin-top:8px">'
                        f'<div class="script-label">Angle commercial (bien expiré)</div>'
                        f'<div class="script-text">{angle_exp}</div></div>',
                        unsafe_allow_html=True,
                    )
        with col_se2:
            if comp_html:
                st.markdown(comp_html, unsafe_allow_html=True)

st.markdown("<hr class='sep'>", unsafe_allow_html=True)

# ── SCRIPTS ───────────────────────────────────────────────────────
st.markdown('<div class="sec">Scripts de contact personnalisés</div>', unsafe_allow_html=True)

prenom = str(row.get("client1_nom","") or "").split()[0] if row.get("client1_nom") else ""
bien   = str(row.get("type_bien","") or "")
addr   = str(row.get("adresse_bien","") or "")
ville  = str(row.get("ville","") or "")
dpe_l  = str((dpe_info.get("dpe_label","") if dpe_info is not None else "") or "")
age_e_m = int(row.get("age_estimation_jours",0) or 0) // 30
age_m_m = int(row.get("age_mandat_jours",0) or 0) // 30 if src == "mandat" else None
age_s_m = int(age_suivi_j or 0) // 30

script = generer_script(
    profil=profil,
    prenom=prenom,
    bien_type=bien,
    adresse=addr,
    age_eval_mois=age_e_m if src == "eval" else None,
    age_mandat_mois=age_m_m,
    dpe_label=dpe_l or None,
    age_suivi_mois=age_s_m,
)
objet  = generer_objet_email(profil, bien, ville, prenom)
sms    = generer_sms(profil, prenom)

tab1, tab2, tab3 = st.tabs(["📞 Script appel", "✉️ Objet email", "💬 SMS"])

with tab1:
    # Enrichir le script si un bien expiré a été détecté
    script_enrichi = script
    if stream_disponible():
        cp_row = str(row.get("code_postal","") or "")
        tb_row = str(row.get("type_bien","") or "")
        from stream_estate import get_biens_expires
        sig_exp = get_biens_expires(cp_row, tb_row)
        if sig_exp.get("signal"):
            angle_inj = script_biens_expires(sig_exp, prenom, tb_row)
            if angle_inj:
                script_enrichi += f"\n\n💡 {angle_inj}"
    st.markdown(
        f'<div class="script-box"><div class="script-label">Script d\'appel</div>'
        f'<div class="script-text">{script_enrichi}</div></div>',
        unsafe_allow_html=True,
    )
    st.caption("Personnalisez [votre prénom] avant d'appeler.")

with tab2:
    st.markdown(
        f'<div class="script-box"><div class="script-label">Objet email</div>'
        f'<div class="script-text">{objet}</div></div>',
        unsafe_allow_html=True,
    )

with tab3:
    st.markdown(
        f'<div class="script-box"><div class="script-label">SMS de relance</div>'
        f'<div class="script-text">{sms}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("<hr class='sep'>", unsafe_allow_html=True)

# ── ACTIONS ───────────────────────────────────────────────────────
st.markdown('<div class="sec">Enregistrer une action</div>', unsafe_allow_html=True)

statuts_key = f"statut_{src}_{fiche_id}"
commentaire_key = f"comm_{src}_{fiche_id}"

col_a, col_b = st.columns([3, 2])
with col_a:
    statut_options = [
        "— Choisir un statut —",
        "📞 Appelé — pas de réponse",
        "📞 Appelé — message laissé",
        "✅ Contact abouti",
        "📅 RDV pris",
        "🔄 À relancer dans X jours",
        "🏠 Mandat signé",
        "🏆 Exclusif signé",
        "❌ Refus — pas intéressé",
        "🔒 Dossier clôturé",
    ]
    statut = st.selectbox("Statut", statut_options,
                           key=statuts_key,
                           index=statut_options.index(st.session_state.get(statuts_key, statut_options[0])) if st.session_state.get(statuts_key) in statut_options else 0)

with col_b:
    relance = st.date_input("Date de relance", value=None, key=f"relance_{src}_{fiche_id}")

commentaire = st.text_area("Commentaire libre", key=commentaire_key, height=80,
                            placeholder="Notes sur l'appel, objections, informations recueillies...")

if st.button("💾 Enregistrer", type="primary"):
    if statut != statut_options[0]:
        st.session_state[statuts_key] = statut
        st.success(f"Statut enregistré : **{statut}**")
        if relance:
            st.info(f"Relance programmée le {relance.strftime('%d/%m/%Y')}")
    else:
        st.warning("Sélectionnez un statut avant d'enregistrer.")

st.markdown("<hr class='sep'>", unsafe_allow_html=True)

# ── Score détaillé ────────────────────────────────────────────────
if src == "eval":
    with st.expander("📊 Détail du score CRM"):
        total = int(row.get("score_total",0) or 0)
        blocs = {
            "Historique CRM":   int(row.get("score_bloc1_crm",0) or 0),
            "Timing/réactivation": int(row.get("score_bloc2_timing",0) or 0),
            "Potentiel bien":   int(row.get("score_bloc3_bien",0) or 0),
            "Qualité contact":  int(row.get("score_bloc4_contact",0) or 0),
            "ADEME/DPE":        int(row.get("score_bloc5_ademe",0) or 0),
        }
        maxs = [35, 25, 20, 10, 10]
        st.markdown(f"**Score total : {total}/100** · {S(row.get('priorite_label',''))}")
        for (label, sc_b), mx in zip(blocs.items(), maxs):
            pct = int(100 * sc_b / mx) if mx > 0 else 0
            st.markdown(
                f"<div style='margin-bottom:6px'>"
                f"<div style='display:flex;justify-content:space-between;font-size:12px'>"
                f"<span>{label}</span><span style='font-weight:700'>{sc_b}/{mx}</span></div>"
                f"<div class='prog-bar-wrap'><div class='prog-bar' style='width:{pct}%'></div></div>"
                f"</div>", unsafe_allow_html=True,
            )
        motifs = str(row.get("motifs_score","") or "")
        if motifs:
            st.caption(f"Motifs : {motifs}")
