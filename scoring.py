"""
scoring.py - Radar Mandats
Calcul du score de potentiel mandat sur 100 points (5 blocs).
Regles parametrables via config/scoring_rules.yaml.
"""

import pandas as pd
from datetime import date
from pathlib import Path
import yaml

DEFAULT_RULES_PATH = Path(__file__).parent / "config" / "scoring_rules.yaml"


def charger_regles(chemin=None):
    path = Path(chemin) if chemin else DEFAULT_RULES_PATH
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return _regles_defaut()


def _regles_defaut():
    return {
        "bloc1_crm": {
            "estimation_6_24m": 15, "estimation_24_48m": 10,
            "estimation_moins_6m": 5, "estimation_plus_48m": 3,
            "mandat_exclusif_match": 15, "mandat_simple_match": 12,
            "mandat_comandat_match": 10, "match_fiable": 3,
            "match_probable": 1, "plafond": 35,
        },
        "bloc2_timing": {
            "sans_suivi": 10, "suivi_plus_12m": 10, "suivi_6_12m": 7,
            "suivi_3_6m": 3, "suivi_moins_3m": 0,
            "mandat_sans_suivi_bonus": 5, "plafond": 25,
        },
        "bloc3_bien": {
            "maison": 8, "appartement": 6, "immeuble": 4, "terrain": 3,
            "parking": 1, "local_commercial": 1, "autre": 2,
            "cp_renseigne": 4, "adresse_complete": 3, "plafond": 20,
        },
        "bloc4_contact": {
            "telephone_valide": 4, "email_valide": 2, "multi_canal": 2,
            "telephone_manquant": -2, "email_manquant": -1, "plafond": 10,
        },
        "bloc5_ademe": {
            "dpe_match_fiable": 3, "dpe_ancien": 2, "dpe_fg": 3,
            "dpe_e": 2, "incoherence": 1, "plafond": 10,
        },
        "priorite": {"p1_min": 80, "p2_min": 65, "p3_min": 50, "p4_min": 35},
        "confiance": {
            "tel_et_email_et_adresse": 5, "tel_et_email": 4,
            "tel_ou_email": 3, "aucun_canal": 1,
            "bonus_match_mandat_n1": 1,
        },
    }


def _bloc1(row, R):
    pts, motifs = 0, []
    age = int(row.get("age_estimation_jours") or 0)
    if 180 <= age <= 730:
        pts += R["estimation_6_24m"]; motifs.append(f"Estimation 6-24 mois (+{R['estimation_6_24m']})")
    elif 730 < age <= 1460:
        pts += R["estimation_24_48m"]; motifs.append(f"Estimation 24-48 mois (+{R['estimation_24_48m']})")
    elif age < 180:
        pts += R["estimation_moins_6m"]; motifs.append(f"Estimation <6 mois (+{R['estimation_moins_6m']})")
    else:
        pts += R["estimation_plus_48m"]; motifs.append(f"Estimation >48 mois (+{R['estimation_plus_48m']})")
    classe = row.get("match_mandat_classe")
    niveau = row.get("match_mandat_niveau")
    if pd.notna(classe):
        c = int(classe)
        if c == 1:   pts += R["mandat_exclusif_match"]; motifs.append(f"Mandat exclusif (+{R['mandat_exclusif_match']})")
        elif c == 2: pts += R["mandat_simple_match"];   motifs.append(f"Mandat simple (+{R['mandat_simple_match']})")
        elif c == 3: pts += R["mandat_comandat_match"]; motifs.append(f"Co-mandat (+{R['mandat_comandat_match']})")
        if pd.notna(niveau):
            if int(niveau) == 1: pts += R["match_fiable"];   motifs.append(f"Match telephone fiable (+{R['match_fiable']})")
            elif int(niveau) == 2: pts += R["match_probable"]; motifs.append(f"Match nom probable (+{R['match_probable']})")
    return min(pts, R["plafond"]), motifs


def _bloc2(row, R):
    pts, motifs = 0, []
    today = pd.Timestamp(date.today())
    if row.get("sans_suivi") is True:
        pts += R["sans_suivi"]; motifs.append(f"Aucun suivi enregistre (+{R['sans_suivi']})")
    else:
        last = row.get("date_dernier_suivi")
        if pd.notna(last):
            d = (today - pd.Timestamp(last)).days
            if d > 365:   pts += R["suivi_plus_12m"]; motifs.append(f"Dernier contact >12m (+{R['suivi_plus_12m']})")
            elif d > 180: pts += R["suivi_6_12m"];    motifs.append(f"Dernier contact 6-12m (+{R['suivi_6_12m']})")
            elif d > 90:  pts += R["suivi_3_6m"];     motifs.append(f"Dernier contact 3-6m (+{R['suivi_3_6m']})")
            else: motifs.append("Dernier contact <3m (0)")
    if row.get("match_mandat_sans_suivi") is True:
        pts += R["mandat_sans_suivi_bonus"]; motifs.append(f"Mandat sans suivi (+{R['mandat_sans_suivi_bonus']})")
    return min(pts, R["plafond"]), motifs


def _bloc3(row, R):
    pts, motifs = 0, []
    tb = str(row.get("type_bien", "autre")).lower()
    p = R.get(tb, R["autre"])
    pts += p; motifs.append(f"Type bien : {tb} (+{p})")
    if pd.notna(row.get("code_postal")):
        pts += R["cp_renseigne"]; motifs.append(f"Code postal (+{R['cp_renseigne']})")
    if pd.notna(row.get("adresse_bien")) and len(str(row.get("adresse_bien", ""))) > 10:
        pts += R["adresse_complete"]; motifs.append(f"Adresse complete (+{R['adresse_complete']})")
    return min(pts, R["plafond"]), motifs


def _bloc4(row, R):
    pts, motifs = 0, []
    a_t = row.get("a_telephone") is True
    a_e = row.get("a_email") is True
    a_a = pd.notna(row.get("adresse_bien"))
    if a_t:  pts += R["telephone_valide"];   motifs.append(f"Telephone valide (+{R['telephone_valide']})")
    else:    pts += R["telephone_manquant"]; motifs.append(f"Telephone manquant ({R['telephone_manquant']})")
    if a_e:  pts += R["email_valide"];       motifs.append(f"Email valide (+{R['email_valide']})")
    else:    pts += R["email_manquant"];     motifs.append(f"Email manquant ({R['email_manquant']})")
    if a_t and a_e and a_a:
        pts += R["multi_canal"]; motifs.append(f"Multi-canal (+{R['multi_canal']})")
    return min(max(pts, 0), R["plafond"]), motifs


def _bloc5(row, R):
    if pd.isna(row.get("dpe_label")):
        return 0, ["ADEME : enrichissement V2"]
    pts, motifs = 0, []
    if row.get("ademe_match_niveau") == "fort":
        pts += R["dpe_match_fiable"]; motifs.append(f"DPE fiable (+{R['dpe_match_fiable']})")
    lbl = str(row.get("dpe_label", "")).upper()
    if lbl in ("F","G"): pts += R["dpe_fg"]; motifs.append(f"DPE {lbl} (+{R['dpe_fg']})")
    elif lbl == "E":     pts += R["dpe_e"];  motifs.append(f"DPE E (+{R['dpe_e']})")
    return min(pts, R["plafond"]), motifs


def _confiance(row, R):
    a_t = row.get("a_telephone") is True
    a_e = row.get("a_email") is True
    a_a = pd.notna(row.get("adresse_bien"))
    n1  = row.get("match_mandat_niveau") == 1.0
    if a_t and a_e and a_a: s, l = R["tel_et_email_et_adresse"], "Donnees completes"
    elif a_t and a_e:       s, l = R["tel_et_email"],             "Contact exploitable"
    elif a_t or a_e:        s, l = R["tel_ou_email"],             "Donnees partielles"
    else:                   s, l = R["aucun_canal"],              "Donnees faibles"
    if n1: s = min(s + R["bonus_match_mandat_n1"], 5); l += " + mandat verifie"
    return s, l


def _priorite(total, P):
    if total >= P["p1_min"]: return "P1", "A appeler immediatement"
    if total >= P["p2_min"]: return "P2", "A traiter cette semaine"
    if total >= P["p3_min"]: return "P3", "Relance douce"
    if total >= P["p4_min"]: return "P4", "Opportunite faible"
    return "P5", "Non prioritaire"


def _next_action(row):
    a_t  = row.get("a_telephone") is True
    a_e  = row.get("a_email") is True
    ss   = row.get("sans_suivi") is True
    mand = pd.notna(row.get("match_mandat_id"))
    mss  = row.get("match_mandat_sans_suivi") is True
    age  = int(row.get("age_estimation_jours") or 0)
    if not a_t and not a_e:
        return "Enrichir les coordonnees avant toute action"
    if mand and mss:
        return "Appel bilan de commercialisation — mandat actif sans suivi"
    if mand:
        return "Appel de relance — avenant ou reorientation du mandat"
    if ss and age > 180:
        return "Appel de reactivation — jamais relance depuis l'estimation" if a_t else "Email de reactivation"
    if age > 365:
        return "Appel conseil — faire le point sur le projet vendeur"
    return "Appel de suivi" if a_t else "Email de suivi"


def _scorer_ligne(row, regles):
    s1, m1 = _bloc1(row, regles["bloc1_crm"])
    s2, m2 = _bloc2(row, regles["bloc2_timing"])
    s3, m3 = _bloc3(row, regles["bloc3_bien"])
    s4, m4 = _bloc4(row, regles["bloc4_contact"])
    s5, m5 = _bloc5(row, regles["bloc5_ademe"])
    total = s1 + s2 + s3 + s4 + s5
    pcode, plabel = _priorite(total, regles["priorite"])
    cscore, clabel = _confiance(row, regles["confiance"])
    return pd.Series({
        "score_total": total, "score_bloc1_crm": s1, "score_bloc2_timing": s2,
        "score_bloc3_bien": s3, "score_bloc4_contact": s4, "score_bloc5_ademe": s5,
        "priorite_code": pcode, "priorite_label": plabel,
        "confiance_score": cscore, "confiance_label": clabel,
        "next_action": _next_action(row),
        "motifs_score": " | ".join(m1 + m2 + m3 + m4 + m5),
    })


def calculer_scores(df_radar, chemin_regles=None):
    regles = charger_regles(chemin_regles)
    print(f"[scoring] {len(df_radar)} dossiers...")
    scores = df_radar.apply(lambda r: _scorer_ligne(r, regles), axis=1)
    df = pd.concat([df_radar.reset_index(drop=True), scores], axis=1)
    df = df.sort_values("score_total", ascending=False).reset_index(drop=True)
    print("[scoring]", df["priorite_code"].value_counts().to_dict())
    return df
