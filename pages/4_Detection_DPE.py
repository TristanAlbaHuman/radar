"""
4_Detection_DPE.py - Radar Mandats V2
Détection DPE : DPE récents × CRM × matchs parfaits.
Un seul workflow intégré. Chaque match génère une action commerciale.
"""

import streamlit as st
import pandas as pd
import urllib.parse
import html as _html
from datetime import date
from ademe_matcher import (
    rnvp_adresse, score_match, normaliser_df_ademe,
    charger_fichiers_ademe, calculer_score_maturite,
)
from ui_utils import CSS, S, fmt_date, dpe_badge, kpi, badge, map_links

st.markdown(CSS, unsafe_allow_html=True)

if st.session_state.get("df_scored") is None:
    st.warning("Chargez votre fichier CRM depuis l'accueil.")
    st.stop()

df_crm = st.session_state["df_scored"]

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Paramètres")
    age_dpe_max  = st.slider("DPE de moins de X mois", 1, 36, 6)
    seuil_match  = st.slider("Score RNVP minimum (matchs)", 85, 100, 90, step=5)
    st.markdown("---")
    st.markdown("### Filtres")
    ag_sel       = st.multiselect("Agences", sorted(df_crm["agence"].dropna().unique()), placeholder="Toutes")
    dpe_labels   = st.multiselect("Étiquettes DPE", list("ABCDEFG"), default=[])
    sans_mandat  = st.checkbox("Sans mandat uniquement", True)
    nb_lignes    = st.slider("Nb lignes", 25, 500, 100, step=25)
    st.markdown("---")
    st.markdown("### Vue")
    vue          = st.radio("Afficher", ["DPE récents ADEME","Matchs CRM × ADEME"])

# ── En-tête ───────────────────────────────────────────────────────
st.markdown("## 🎯 Détection DPE")
st.markdown(
    "<span style='color:#888;font-size:13px'>"
    "Croiser les DPE récents ADEME avec votre CRM pour identifier les signaux vendeurs"
    "</span>", unsafe_allow_html=True,
)
st.markdown("<hr class='sep'>", unsafe_allow_html=True)

# ── Upload ADEME ──────────────────────────────────────────────────
st.markdown('<div class="sec">Fichiers ADEME (plusieurs fichiers acceptés)</div>',
            unsafe_allow_html=True)
ademe_files = st.file_uploader(
    "Fichiers DPE ADEME (CSV)", type=["csv","xlsx"],
    accept_multiple_files=True, key="ademe_det", label_visibility="collapsed",
)

df_ademe = None
if ademe_files:
    noms = "_".join(f.name for f in ademe_files)
    ck   = f"det_{noms}"
    if st.session_state.get("det_ademe_key") != ck:
        with st.spinner(f"Chargement {len(ademe_files)} fichier(s) ADEME..."):
            df_ademe = charger_fichiers_ademe(ademe_files)
        st.session_state["det_ademe_df"]  = df_ademe
        st.session_state["det_ademe_key"] = ck
    else:
        df_ademe = st.session_state["det_ademe_df"]
    st.success(f"{len(df_ademe):,} DPE chargés ({len(ademe_files)} fichier(s))")

if df_ademe is None:
    df_ademe = st.session_state.get("det_ademe_df")

if df_ademe is None:
    st.info("📂 Importez vos fichiers ADEME (CSV) pour commencer l'analyse.")
    st.stop()

# ── Préparer ADEME ────────────────────────────────────────────────
df_a = df_ademe.copy()
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

def angle_commercial(etiq, age_mois):
    e = str(etiq or "").upper().strip()
    a = float(age_mois or 99)
    if e in ("F","G"):
        return "🔥 Passoire thermique — angle travaux / arbitrage patrimonial / obligation légale"
    if e == "E":
        return "⚠️ DPE E — commencer à anticiper la dépréciation"
    if a <= 2:
        return "📋 DPE très récent — propriétaire possiblement en projet de vente"
    if a <= 6:
        return "📋 DPE récent — qualifier le projet de vente"
    return "📋 DPE disponible — angle valorisation / mise en marché"

df_a["_angle"] = df_a.apply(
    lambda r: angle_commercial(r.get(col_etiq,"") if col_etiq else "", r.get("_age")), axis=1
)

# ── KPIs globaux ─────────────────────────────────────────────────
n_fg  = int(df_a[col_etiq].str.upper().isin(["F","G"]).sum()) if col_etiq else 0
n_rec = int((df_a["_age"] <= 2).sum()) if "_age" in df_a.columns else 0
st.markdown(f"""
<div class="krow">
  {kpi("DPE dans la sélection", len(df_a), f"< {age_dpe_max} mois", "blu")}
  {kpi("Très récents (< 2m)", n_rec, "signal fort", "ora")}
  {kpi("Passoires F/G", n_fg, "angle travaux", "red")}
</div>
""", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════
if vue == "DPE récents ADEME":
# ═════════════════════════════════════════════════════════════════
    st.markdown(
        f'<div class="sec">DPE récents (< {age_dpe_max} mois) — {len(df_a):,} biens — {nb_lignes} affichés</div>',
        unsafe_allow_html=True,
    )

    df_show = df_a.head(nb_lignes)
    surf_col  = next((c for c in ["surface","surface_habitable_logement"] if c in df_show.columns), None)
    conso_col = next((c for c in ["conso_ep_m2","conso_5_usages_par_m2_ep"] if c in df_show.columns), None)
    ges_col   = next((c for c in ["etiquette_ges"] if c in df_show.columns), None)
    annee_col = next((c for c in ["annee_construction"] if c in df_show.columns), None)
    type_col  = next((c for c in ["type_batiment"] if c in df_show.columns), None)
    ndpe_col  = next((c for c in ["N_DPE","numero_dpe"] if c in df_show.columns), None)

    rows = []
    for _, row in df_show.iterrows():
        etiq  = str(row.get(col_etiq,"") or "").upper() if col_etiq else "?"
        ges   = str(row.get(ges_col,"") or "").upper() if ges_col else "—"
        age_m = row.get("_age")
        d_dpe = fmt_date(row.get("_date"))
        addr  = row.get("_addr_full","")
        p = rnvp_adresse(addr)
        addr_rnvp = p["cle"]
        surf  = row.get(surf_col,"") if surf_col else "—"
        conso = row.get(conso_col,"") if conso_col else "—"
        annee = row.get(annee_col,"") if annee_col else "—"
        typeb = row.get(type_col,"") if type_col else "—"
        ndpe  = row.get(ndpe_col,"") if ndpe_col else "—"
        angle = row.get("_angle","")

        try: surf_s  = f"{float(surf):.0f} m²" if surf and surf!="—" else "—"
        except: surf_s = str(surf)
        try: conso_s = f"{float(conso):.0f} kWh" if conso and conso!="—" else "—"
        except: conso_s = str(conso)
        age_s = f"{age_m:.1f}m" if age_m is not None and not (isinstance(age_m,float) and pd.isna(age_m)) else "—"

        rows.append({
            "DPE":      dpe_badge(etiq) + (f" {ges}" if ges!="—" else ""),
            "Date":     f"{d_dpe} ({age_s})",
            "Adresse":  S(addr),
            "RNVP":     S(addr_rnvp),
            "Surface":  surf_s,
            "Conso EP": conso_s,
            "Année":    S(annee),
            "Type":     S(typeb),
            "N° DPE":   S(ndpe),
            "Angle commercial": S(angle),
            "Carte":    (f'<a class="map-link" href="https://www.openstreetmap.org/search?query={urllib.parse.quote(addr)}" target="_blank">OSM</a> '
                         f'<a class="map-link" href="https://maps.google.com/maps?q={urllib.parse.quote(addr)}" target="_blank">GMaps</a>'),
        })

    HTML_COLS = {"DPE","Carte"}
    table_html = "<div style='overflow-x:auto;overflow-y:auto;max-height:600px;border:1px solid #e0e0e0;border-radius:8px;'>"
    table_html += "<table class='tbl'><thead><tr>"
    for col in rows[0].keys() if rows else []:
        table_html += f"<th>{col}</th>"
    table_html += "</tr></thead><tbody>"
    for i, r in enumerate(rows):
        bg = "background:#fffdf5;" if i%2==0 else ""
        table_html += f"<tr style='{bg}'>"
        for col, val in r.items():
            if col in HTML_COLS:
                table_html += f"<td style='white-space:nowrap'>{val}</td>"
            else:
                table_html += f"<td style='white-space:nowrap'>{_html.escape(str(val)) if val else '—'}</td>"
        table_html += "</tr>"
    table_html += "</tbody></table></div>"
    if rows:
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.info("Aucun DPE dans cette sélection.")

    # Export
    df_exp = df_a.head(nb_lignes).copy()
    df_exp["adresse_rnvp"] = df_exp["_addr_full"].apply(lambda x: rnvp_adresse(x)["cle"])
    df_exp["lien_osm"]     = df_exp["_addr_full"].apply(lambda x: f"https://www.openstreetmap.org/search?query={urllib.parse.quote(str(x))}")
    st.download_button("Télécharger CSV", df_exp.to_csv(index=False, encoding="utf-8-sig"),
                        f"dpe_recents_{date.today().strftime('%Y%m%d')}.csv", "text/csv")

# ═════════════════════════════════════════════════════════════════
else:  # Matchs CRM × ADEME
# ═════════════════════════════════════════════════════════════════
    st.markdown(
        f'<div class="sec">Matchs CRM × ADEME — correspondances RNVP ≥ {seuil_match}/100</div>',
        unsafe_allow_html=True,
    )

    df_cib = df_crm.copy()
    if ag_sel: df_cib = df_cib[df_cib["agence"].isin(ag_sel)]
    if sans_mandat: df_cib = df_cib[df_cib["match_mandat_id"].isna()]

    col_cp = next((c for c in ["cp_ban","code_postal_ban"] if c in df_ademe.columns), None)
    if col_cp is None:
        st.error("Colonne CP introuvable dans le fichier ADEME.")
        st.stop()

    df_ademe["_cp_idx"] = (
        df_ademe[col_cp].astype(str).str.strip()
        .str.replace(r"\.0$","",regex=True).str.zfill(5).str[:5]
    )

    cache_id = f"match_{st.session_state.get('det_ademe_key','')}_{seuil_match}_{sans_mandat}"

    if st.session_state.get("match_v2_id") != cache_id:
        c1, c2, c3 = st.columns(3)
        c1.metric("Dossiers CRM", f"{len(df_cib):,}")
        c2.metric("DPE ADEME", f"{len(df_ademe):,}")
        c3.metric("Seuil RNVP", f"≥ {seuil_match}/100")

        if st.button(f"🔍 Lancer le matching sur {len(df_cib):,} dossiers", type="primary"):
            cp_index = {}
            for r in df_ademe.to_dict("records"):
                cp_index.setdefault(r["_cp_idx"],[]).append(r)

            prog = st.progress(0, text="Matching RNVP...")
            resultats = []
            total = len(df_cib)

            for i, (_, row) in enumerate(df_cib.iterrows()):
                if i % 300 == 0:
                    prog.progress(min(i/total,1.0), text=f"{i:,}/{total:,}...")
                addr_crm = str(row.get("adresse_bien","") or "")
                cp_crm   = rnvp_adresse(addr_crm)["cp"] or str(row.get("code_postal","")).zfill(5)[:5]
                best_sc, best_dpe = 0, None
                for dpe in cp_index.get(cp_crm,[]):
                    sc, _, _ = score_match(addr_crm, dpe)
                    if sc > best_sc: best_sc, best_dpe = sc, dpe
                if best_sc >= seuil_match and best_dpe:
                    date_str = str(best_dpe.get("date_dpe") or best_dpe.get("date_etablissement_dpe",""))
                    try:    dpe_date = pd.Timestamp(date_str).date()
                    except: dpe_date = None
                    age_mois = (date.today() - dpe_date).days // 30 if dpe_date else None
                    rec = row.to_dict()
                    rec.update({
                        "match_score":      best_sc,
                        "dpe_etiquette":    best_dpe.get("etiquette_dpe"),
                        "dpe_date":         dpe_date,
                        "dpe_age_mois":     age_mois,
                        "dpe_surface":      best_dpe.get("surface") or best_dpe.get("surface_habitable_logement"),
                        "dpe_conso":        best_dpe.get("conso_ep_m2") or best_dpe.get("conso_5_usages_par_m2_ep"),
                        "dpe_ges":          best_dpe.get("etiquette_ges"),
                        "dpe_annee":        best_dpe.get("annee_construction"),
                        "dpe_type_bat":     best_dpe.get("type_batiment"),
                        "dpe_adresse_ban":  best_dpe.get("adresse_ban"),
                        "dpe_cp":           best_dpe.get("cp_ban") or best_dpe.get("code_postal_ban"),
                        "dpe_ville":        best_dpe.get("ville_ban") or best_dpe.get("nom_commune_ban"),
                        "dpe_numero":       best_dpe.get("N_DPE") or best_dpe.get("numero_dpe"),
                        "_angle":           angle_commercial(best_dpe.get("etiquette_dpe",""), age_mois),
                    })
                    resultats.append(rec)

            prog.empty()
            df_r = pd.DataFrame(resultats) if resultats else pd.DataFrame()
            # Trier par angle commercial urgent + DPE récent
            if not df_r.empty and "dpe_age_mois" in df_r.columns:
                df_r = df_r.sort_values("dpe_age_mois", ascending=True, na_position="last")
            st.session_state["match_v2_df"] = df_r
            st.session_state["match_v2_id"] = cache_id
            st.rerun()
        else:
            st.stop()
    else:
        if st.button("Relancer le matching"):
            st.session_state.pop("match_v2_id",None)
            st.session_state.pop("match_v2_df",None)
            st.rerun()

    df_matchs = st.session_state.get("match_v2_df", pd.DataFrame())
    if df_matchs.empty:
        st.warning("Aucun match trouvé. Essayez de baisser le seuil ou d'élargir les filtres.")
        st.stop()

    if dpe_labels and "dpe_etiquette" in df_matchs.columns:
        df_matchs = df_matchs[df_matchs["dpe_etiquette"].str.upper().str.strip().isin(dpe_labels)]

    n_m = len(df_matchs)
    n_fg_m = int(df_matchs["dpe_etiquette"].str.upper().isin(["F","G"]).sum()) if "dpe_etiquette" in df_matchs.columns else 0

    st.markdown(f"""
    <div class="krow">
      {kpi("Matchs parfaits", n_m, f"≥ {seuil_match}/100", "grn")}
      {kpi("Passoires F/G", n_fg_m, "signal fort", "red")}
    </div>
    """, unsafe_allow_html=True)

    df_show = df_matchs.head(nb_lignes)
    rows_m = []
    for _, row in df_show.iterrows():
        sc_v = int(row.get("match_score",0) or 0)
        nom  = S(row.get("nom_principal","—"))
        ag_v = S(row.get("agence",""))
        tel  = S(row.get("client1_tel","") or row.get("tel_jointure",""))
        addr_crm = S(row.get("adresse_bien",""))
        addr_dpe = S(row.get("dpe_adresse_ban",""))
        cp_v = S(row.get("dpe_cp",""))
        vi_v = S(row.get("dpe_ville",""))
        addr_full_dpe = f"{addr_dpe} {cp_v} {vi_v}".strip()
        etiq = str(row.get("dpe_etiquette","") or "")
        age_dpe = row.get("dpe_age_mois")
        age_s = f"{age_dpe:.0f}m" if age_dpe is not None and not pd.isna(age_dpe) else "—"
        surf = row.get("dpe_surface","")
        try: surf_s = f"{float(surf):.0f} m²"
        except: surf_s = "—"
        angle = S(row.get("_angle",""))
        d_eval = fmt_date(row.get("date_estimation"))

        rows_m.append({
            "Score":   f'<b style="color:#27ae60">{sc_v}/100</b>',
            "Contact": f"<b>{nom}</b><br/><span style='font-size:11px;color:#888'>{ag_v} · {tel}</span>",
            "Adresse CRM": S(addr_crm),
            "DPE":     dpe_badge(etiq) + f" <span style='font-size:11px'>{age_s}</span>",
            "Surface": surf_s,
            "Éval":    d_eval,
            "Angle":   angle,
            "Carte":   (f'<a class="map-link" href="https://maps.google.com/maps?q={urllib.parse.quote(addr_full_dpe)}" target="_blank">GMaps</a>'),
        })

    HTML_COLS = {"Score","Contact","DPE","Carte"}
    t = "<div style='overflow-x:auto;overflow-y:auto;max-height:600px;border:1px solid #e0e0e0;border-radius:8px;'>"
    t += "<table class='tbl'><thead><tr>"
    for col in rows_m[0].keys() if rows_m else []:
        t += f"<th>{col}</th>"
    t += "</tr></thead><tbody>"
    for i, r in enumerate(rows_m):
        t += "<tr>"
        for col, val in r.items():
            if col in HTML_COLS: t += f"<td style='white-space:nowrap'>{val}</td>"
            else: t += f"<td style='white-space:nowrap'>{_html.escape(str(val))}</td>"
        t += "</tr>"
    t += "</tbody></table></div>"
    if rows_m: st.markdown(t, unsafe_allow_html=True)

    csv = df_matchs.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("Télécharger matchs CSV", csv,
                        f"matchs_crm_ademe_{date.today().strftime('%Y%m%d')}.csv", "text/csv")
