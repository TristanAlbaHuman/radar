"""
data_loader.py — Radar Mandats
Chargement, nettoyage et consolidation des 3 onglets CRM.
"""

import re
import pandas as pd
import numpy as np
from datetime import datetime, date


# ─────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────

SHEETS = {
    "evaluations": "evaluations_full",
    "mandats": "mandats_sans_ssp",
    "mandats_sans_suivi": "mandats_sans_ssp_sans_suivi",
}

TYPE_BIEN_MAP = {
    "Maison": "maison",
    "Appartement": "appartement",
    "Immeuble": "immeuble",
    "Terrain": "terrain",
    "Parking": "parking",
    "Local commercial": "local_commercial",
}

CLASSEMENT_MANDAT_MAP = {
    1: "exclusif",
    2: "simple",
    3: "co-mandat",
}


# ─────────────────────────────────────────────
# NORMALISATION — FONCTIONS ATOMIQUES
# ─────────────────────────────────────────────

def get_col(df: pd.DataFrame, possible_names: list, default_val=None) -> pd.Series:
    """
    Fonction bouclier : cherche une colonne parmi plusieurs noms possibles.
    Évite les KeyError fatals si le CRM modifie l'intitulé d'une colonne.
    """
    for col in possible_names:
        if col in df.columns:
            return df[col]
    return pd.Series([default_val] * len(df))


def normaliser_telephone(valeur) -> str | None:
    if pd.isna(valeur):
        return None
    s = re.sub(r"\D", "", str(valeur))
    if s.startswith("33") and len(s) == 11:
        s = "0" + s[2:]
    if len(s) == 9 and not s.startswith("0"):
        s = "0" + s
    if len(s) == 10 and s.startswith("0"):
        return s
    return None


def normaliser_email(valeur) -> str | None:
    if pd.isna(valeur):
        return None
    s = str(valeur).strip().lower()
    if s in (".", "", "nan", "none", "-", "#"):
        return None
    if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s):
        return s
    return None


def normaliser_nom_principal(valeur) -> str | None:
    if pd.isna(valeur):
        return None
    n = re.split(r"[/,]", str(valeur))[0].strip().upper()
    n = re.sub(
        r"\s+(SOUS|EP\.|EPOUSE|ÉPOUSE|NÉE|NEE|VVE|VEUVE|SCI|SARL|SAS)\s+.*",
        "",
        n,
        flags=re.IGNORECASE,
    )
    n = re.sub(r"\s{2,}", " ", n).strip()
    return n if n else None


def extraire_cp_ville(adresse: str) -> tuple[str | None, str | None]:
    if pd.isna(adresse):
        return None, None
    s = re.sub(r"[\n\r]+", " ", str(adresse)).strip()
    m = re.search(r"\b(\d{5})\b\s+([A-ZÀ-Ÿa-zà-ÿ\s\-]+?)(?:\s{2,}|$)", s)
    if m:
        cp = m.group(1)
        ville = m.group(2).strip().upper()
        return cp, ville
    return None, None


def normaliser_adresse_bien(adresse: str) -> str | None:
    if pd.isna(adresse):
        return None
    s = re.sub(r"[\n\r]+", " ", str(adresse)).strip()
    cp_positions = [m.start() for m in re.finditer(r"\b\d{5}\b", s)]
    if len(cp_positions) >= 2:
        second_start = cp_positions[1]
        s = s[:second_start].strip()
    s = re.sub(r"\s{2,}", " ", s).strip().upper()
    return s if s else None


# ─────────────────────────────────────────────
# NETTOYAGE PAR ONGLET
# ─────────────────────────────────────────────

def nettoyer_evaluations(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["source"] = "evaluation"
    
    # Identifiants
    out["id_evaluation"] = get_col(df, ["NEstimation"]).astype(str)
    out["id_agence"] = get_col(df, ["NAg", "Id Agence"]).fillna("").astype(str)
    out["agence"] = get_col(df, ["txtAgence", "Nom Agence"]).fillna("").astype(str).str.strip()
    out["actif"] = get_col(df, ["Actif"]).fillna(0).astype(int) == 1

    # Dossier & Bien
    out["nom_dossier"] = get_col(df, ["NomDossierEstimation"]).fillna("").astype(str).str.strip()
    out["nom_principal"] = out["nom_dossier"].apply(normaliser_nom_principal)
    
    type_bien_brut = get_col(df, ["TypeBien", "Type de bien"])
    out["type_bien"] = type_bien_brut.map(TYPE_BIEN_MAP).fillna("autre")

    # Adresse
    out["adresse_bien_brute"] = get_col(df, ["BienAdresse_Adresse"])
    out["adresse_bien"] = out["adresse_bien_brute"].apply(normaliser_adresse_bien)
    cp_ville = out["adresse_bien_brute"].apply(
        lambda x: pd.Series(extraire_cp_ville(x), index=["cp", "ville"])
    )
    out["code_postal"] = cp_ville["cp"]
    out["ville"] = cp_ville["ville"]

    # Dates
    out["date_estimation"] = pd.to_datetime(get_col(df, ["DateSaisie"]), errors="coerce")
    out["date_dernier_suivi"] = pd.to_datetime(get_col(df, ["DateDernierSuivi"]), errors="coerce", dayfirst=True)
    out["sans_suivi"] = out["date_dernier_suivi"].isna()

    today = pd.Timestamp(date.today())
    out["age_estimation_jours"] = (today - out["date_estimation"]).dt.days

    # Contacts
    out["client1_nom"] = get_col(df, ["Client1"]).astype(str).str.strip()
    out["client1_email"] = get_col(df, ["Client1_email"]).apply(normaliser_email)
    out["client1_tel"] = get_col(df, ["Client1_Tel1"]).apply(normaliser_telephone)
    out["client1_tel2"] = get_col(df, ["Client1_Tel2"]).apply(normaliser_telephone)

    out["client2_nom"] = get_col(df, ["Client2"]).astype(str).str.strip()
    out["client2_email"] = get_col(df, ["Client2_email"]).apply(normaliser_email)
    out["client2_tel"] = get_col(df, ["Client2_Tel1"]).apply(normaliser_telephone)

    out["tel_jointure"] = out["client1_tel"].combine_first(out["client1_tel2"].combine_first(out["client2_tel"]))

    out["a_telephone"] = out["tel_jointure"].notna()
    out["a_email"] = out["client1_email"].notna()
    out["nb_canaux"] = out["a_telephone"].astype(int) + out["a_email"].astype(int)
    out["id_source"] = "eval_" + out["id_evaluation"]

    return out.reset_index(drop=True)


def nettoyer_mandats(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["source"] = "mandat"
    
    out["id_mandat"] = get_col(df, ["NVendeur"]).astype(str)
    out["id_agence"] = get_col(df, ["NAg", "Id Agence"]).fillna("").astype(str)
    out["agence"] = get_col(df, ["txtAgence", "Nom Agence"]).fillna("").astype(str).str.strip()
    out["actif"] = get_col(df, ["Actif"]).fillna(0).astype(bool)

    out["nom_dossier"] = get_col(df, ["NomDossierVendeur"]).fillna("").astype(str).str.strip()
    out["nom_principal"] = out["nom_dossier"].apply(normaliser_nom_principal)

    type_bien_brut = get_col(df, ["txtTypeBien", "Type de bien"])
    out["type_bien"] = type_bien_brut.map(TYPE_BIEN_MAP).fillna("autre")
    
    classement_code = get_col(df, ["Classement_Resultat"])
    out["classement"] = classement_code.map(CLASSEMENT_MANDAT_MAP)
    out["classement_code"] = classement_code

    out["adresse_bien_brute"] = get_col(df, ["BienAdresse_Adresse"])
    out["adresse_bien"] = out["adresse_bien_brute"].apply(normaliser_adresse_bien)
    cp_ville = out["adresse_bien_brute"].apply(
        lambda x: pd.Series(extraire_cp_ville(x), index=["cp", "ville"])
    )
    out["code_postal"] = cp_ville["cp"]
    out["ville"] = cp_ville["ville"]

    out["date_mandat"] = pd.to_datetime(get_col(df, ["DateSaisie"]), errors="coerce")
    out["date_dernier_suivi"] = pd.to_datetime(get_col(df, ["DateDernierSuivi"]), errors="coerce", dayfirst=True)
    out["sans_suivi"] = out["date_dernier_suivi"].isna()

    today = pd.Timestamp(date.today())
    out["age_mandat_jours"] = (today - out["date_mandat"]).dt.days

    out["client1_nom"] = get_col(df, ["Client1"]).astype(str).str.strip()
    out["client1_email"] = get_col(df, ["Client1_email"]).apply(normaliser_email)
    out["client1_tel"] = get_col(df, ["Client1_Tel1"]).apply(normaliser_telephone)
    out["client2_tel"] = get_col(df, ["Client2_Tel1"]).apply(normaliser_telephone)

    out["tel_jointure"] = out["client1_tel"].combine_first(out["client2_tel"])
    out["a_telephone"] = out["tel_jointure"].notna()
    out["a_email"] = out["client1_email"].notna()
    out["nb_canaux"] = out["a_telephone"].astype(int) + out["a_email"].astype(int)
    out["id_source"] = "mand_" + out["id_mandat"]

    return out.reset_index(drop=True)


def nettoyer_mandats_sans_suivi(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["source"] = "mandat_sans_suivi"
    
    out["id_mandat"] = get_col(df, ["NVendeur"]).astype(str)
    out["id_agence"] = get_col(df, ["NAg", "Id Agence"]).fillna("").astype(str)
    out["agence"] = get_col(df, ["txtAgence", "Nom Agence"]).fillna("").astype(str).str.strip()
    out["actif"] = get_col(df, ["Actif"]).fillna(0).astype(int) == 1

    out["nom_dossier"] = get_col(df, ["NomDossierVendeur"]).fillna("").astype(str).str.strip()
    out["nom_principal"] = out["nom_dossier"].apply(normaliser_nom_principal)

    type_bien_brut = get_col(df, ["txtTypeBien", "Type de bien"])
    out["type_bien"] = type_bien_brut.map(TYPE_BIEN_MAP).fillna("autre")
    
    classement_code = get_col(df, ["Classement_Resultat"])
    out["classement_code"] = classement_code
    out["classement"] = classement_code.map(CLASSEMENT_MANDAT_MAP)

    out["adresse_bien_brute"] = get_col(df, ["BienAdresse_Adresse"])
    out["adresse_bien"] = out["adresse_bien_brute"].apply(normaliser_adresse_bien)
    cp_ville = out["adresse_bien_brute"].apply(
        lambda x: pd.Series(extraire_cp_ville(x), index=["cp", "ville"])
    )
    out["code_postal"] = cp_ville["cp"]
    out["ville"] = cp_ville["ville"]

    out["date_mandat"] = pd.to_datetime(get_col(df, ["DateSaisie"]), errors="coerce")
    today = pd.Timestamp(date.today())
    out["age_mandat_jours"] = (today - out["date_mandat"]).dt.days
    out["sans_suivi"] = True

    # Récupération sécurisée des jours sans suivi (le vrai problème d'origine)
    col_jours = get_col(df, ["AGE MANDATS", "AGE MANDAT"])
    out["jours_sans_suivi"] = pd.to_numeric(col_jours, errors="coerce").fillna(0).astype(int)

    def calculer_segment_sans_suivi(jours):
        if pd.isna(jours): return None
        if jours <= 179: return "30-179j"
        if jours <= 365: return "180-365j"
        if jours <= 540: return "366-540j"
        return "+541j"

    # La fameuse typologie recréée proprement !
    out["segment_sans_suivi"] = out["jours_sans_suivi"].apply(calculer_segment_sans_suivi)
    
    out["action_recommandee_brute"] = get_col(df, ["Actions à prévoir"]).fillna("").astype(str).str.strip()

    # Contacts
    out["client1_nom"] = get_col(df, ["Client1"]).astype(str).str.strip()
    out["client1_email"] = get_col(df, ["Client1_email"]).apply(normaliser_email)
    out["client1_tel"] = get_col(df, ["Client1_Tel1"]).apply(normaliser_telephone)
    out["client2_tel"] = get_col(df, ["Client2_Tel1"]).apply(normaliser_telephone)

    out["tel_jointure"] = out["client1_tel"].combine_first(out["client2_tel"])
    out["a_telephone"] = out["tel_jointure"].notna()
    out["a_email"] = out["client1_email"].notna()
    out["nb_canaux"] = out["a_telephone"].astype(int) + out["a_email"].astype(int)
    out["id_source"] = "mss_" + out["id_mandat"]

    return out.reset_index(drop=True)


# ─────────────────────────────────────────────
# JOINTURE ÉVALUATIONS ↔ MANDATS
# ─────────────────────────────────────────────

def joindre_evaluations_mandats(
    df_eval: pd.DataFrame, df_mand: pd.DataFrame
) -> pd.DataFrame:
    mand = df_mand[
        ["id_mandat", "tel_jointure", "id_agence", "nom_principal",
         "code_postal", "age_mandat_jours", "classement_code", "sans_suivi"]
    ].copy()

    mand["key_tel"] = mand["tel_jointure"]
    mand["key_agence_nom"] = mand["id_agence"] + "_" + mand["nom_principal"].fillna("")
    mand["key_agence_cp_nom"] = (
        mand["id_agence"]
        + "_"
        + mand["code_postal"].fillna("")
        + "_"
        + mand["nom_principal"].fillna("").str[:12]
    )

    lkp_tel = mand.dropna(subset=["key_tel"]).drop_duplicates("key_tel").set_index("key_tel")
    lkp_agnom = mand.dropna(subset=["key_agence_nom"]).drop_duplicates("key_agence_nom").set_index("key_agence_nom")
    lkp_agcpnom = mand.dropna(subset=["key_agence_cp_nom"]).drop_duplicates("key_agence_cp_nom").set_index("key_agence_cp_nom")

    result_cols = ["match_mandat_niveau", "match_mandat_id",
                   "match_mandat_age", "match_mandat_classe", "match_mandat_sans_suivi"]

    def lookup_row(row):
        if row["tel_jointure"] and row["tel_jointure"] in lkp_tel.index:
            m = lkp_tel.loc[row["tel_jointure"]]
            return pd.Series([1, m["id_mandat"], m["age_mandat_jours"], m["classement_code"], m["sans_suivi"]])
        
        key2 = str(row["id_agence"]) + "_" + str(row["nom_principal"] or "")
        if key2 in lkp_agnom.index:
            m = lkp_agnom.loc[key2]
            return pd.Series([2, m["id_mandat"], m["age_mandat_jours"], m["classement_code"], m["sans_suivi"]])
            
        key3 = str(row["id_agence"]) + "_" + str(row["code_postal"] or "") + "_" + str(row["nom_principal"] or "")[:12]
        if key3 in lkp_agcpnom.index:
            m = lkp_agcpnom.loc[key3]
            return pd.Series([3, m["id_mandat"], m["age_mandat_jours"], m["classement_code"], m["sans_suivi"]])
            
        return pd.Series([None, None, None, None, None])

    df_eval[result_cols] = df_eval.apply(lookup_row, axis=1)
    return df_eval


# ─────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL
# ─────────────────────────────────────────────

def charger_et_nettoyer(chemin_fichier) -> dict[str, pd.DataFrame]:
    print(f"[data_loader] Chargement : {chemin_fichier}")

    xls = pd.ExcelFile(chemin_fichier)

    df1_raw = pd.read_excel(xls, sheet_name=SHEETS["evaluations"])
    df2_raw = pd.read_excel(xls, sheet_name=SHEETS["mandats"])
    df3_raw = pd.read_excel(xls, sheet_name=SHEETS["mandats_sans_suivi"])

    print(f"[data_loader] Lignes brutes — eval:{len(df1_raw)} | mandats:{len(df2_raw)} | sans_suivi:{len(df3_raw)}")

    df_eval = nettoyer_evaluations(df1_raw)
    df_mand = nettoyer_mandats(df2_raw)
    df_mss = nettoyer_mandats_sans_suivi(df3_raw)

    print(f"[data_loader] Nettoyage OK — eval:{len(df_eval)} | mandats:{len(df_mand)} | sans_suivi:{len(df_mss)}")

    df_radar = joindre_evaluations_mandats(df_eval.copy(), df_mand)

    n_matches = df_radar["match_mandat_niveau"].notna().sum()
    print(f"[data_loader] Jointures éval↔mandat : {n_matches} ({100*n_matches/len(df_radar):.1f}%)")

    return {
        "evaluations": df_eval,
        "mandats": df_mand,
        "mandats_sans_suivi": df_mss,
        "radar": df_radar,
    }


def stats_qualite(df: pd.DataFrame, label: str = "") -> pd.DataFrame:
    cols_cibles = [
        "agence", "nom_principal", "type_bien", "adresse_bien",
        "code_postal", "ville", "date_estimation", "date_dernier_suivi",
        "client1_tel", "client1_email", "a_telephone", "a_email",
    ]
    cols_presentes = [c for c in cols_cibles if c in df.columns]

    stats = []
    for col in cols_presentes:
        total = len(df)
        non_null = df[col].notna().sum()
        if df[col].dtype == bool:
            non_null = df[col].sum()
        stats.append({
            "champ": col,
            "rempli": non_null,
            "total": total,
            "taux_%": round(100 * non_null / total, 1),
        })

    result = pd.DataFrame(stats)
    if label:
        result.insert(0, "source", label)
    return result