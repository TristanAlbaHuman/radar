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

def normaliser_telephone(valeur) -> str | None:
    """
    Normalise un numéro de téléphone vers format 0XXXXXXXXX (10 chiffres).
    Gère les formats : '0612345678', '612345678', '33612345678',
                       '06 12 34 56 78', '06-12-34-56-78'
    Retourne None si non normalisable.
    """
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
    """
    Retourne l'email nettoyé ou None si invalide/vide/point.
    """
    if pd.isna(valeur):
        return None
    s = str(valeur).strip().lower()
    if s in (".", "", "nan", "none", "-", "#"):
        return None
    if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s):
        return s
    return None


def normaliser_nom_principal(valeur) -> str | None:
    """
    Extrait et normalise le NOM PRINCIPAL d'un champ NomDossier.
    - Prend le premier segment avant '/' ou ','
    - Retire les mentions légales (sous curatelle, ep., épouse, née...)
    - Met en majuscules sans accents parasites
    """
    if pd.isna(valeur):
        return None
    # Premier segment
    n = re.split(r"[/,]", str(valeur))[0].strip().upper()
    # Retirer annotations légales
    n = re.sub(
        r"\s+(SOUS|EP\.|EPOUSE|ÉPOUSE|NÉE|NEE|VVE|VEUVE|SCI|SARL|SAS)\s+.*",
        "",
        n,
        flags=re.IGNORECASE,
    )
    # Nettoyer espaces multiples
    n = re.sub(r"\s{2,}", " ", n).strip()
    return n if n else None


def extraire_cp_ville(adresse: str) -> tuple[str | None, str | None]:
    """
    Extrait (code_postal, ville) depuis une chaîne adresse.
    Gère les séparateurs espace, virgule, \\n.
    Exemple : '34 AVENUE DE TIVOLI  33110 LE BOUSCAT' → ('33110', 'LE BOUSCAT')
    """
    if pd.isna(adresse):
        return None, None
    # Normaliser les séparateurs
    s = re.sub(r"[\n\r]+", " ", str(adresse)).strip()
    # Chercher un CP à 5 chiffres
    m = re.search(r"\b(\d{5})\b\s+([A-ZÀ-Ÿa-zà-ÿ\s\-]+?)(?:\s{2,}|$)", s)
    if m:
        cp = m.group(1)
        ville = m.group(2).strip().upper()
        return cp, ville
    return None, None


def normaliser_adresse_bien(adresse: str) -> str | None:
    """
    Nettoie l'adresse : retire les doublons d'adresse dans la même chaîne,
    normalise les séparateurs, met en majuscules.
    Cas particulier : '4 CHEMIN DE BERRI 33160 ... 4 CHEMIN DE BERRY 33160 ...'
    """
    if pd.isna(adresse):
        return None
    # Normaliser séparateurs
    s = re.sub(r"[\n\r]+", " ", str(adresse)).strip()
    # Détecter doublons d'adresse (même CP deux fois) → garder première occurrence
    cp_positions = [m.start() for m in re.finditer(r"\b\d{5}\b", s)]
    if len(cp_positions) >= 2:
        # Couper après le premier bloc CP + ville
        second_start = cp_positions[1]
        # Reculer pour ne pas couper au milieu d'une ville
        s = s[:second_start].strip()
    # Retirer espaces multiples
    s = re.sub(r"\s{2,}", " ", s).strip().upper()
    return s if s else None


# ─────────────────────────────────────────────
# NETTOYAGE PAR ONGLET
# ─────────────────────────────────────────────

def nettoyer_evaluations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nettoyage de l'onglet evaluations_full.
    Colonnes exclues : Colonne1, Ecart Saisie / Suivi.
    """
    # Copie propre
    out = pd.DataFrame()

    out["source"] = "evaluation"
    out["id_evaluation"] = df["NEstimation"].astype(str)
    out["id_agence"] = df["Id Agence"].astype(str)
    out["agence"] = df["Nom Agence"].str.strip()
    out["actif"] = df["Actif"].astype(int) == 1

    # Nom dossier
    out["nom_dossier"] = df["NomDossierEstimation"].str.strip()
    out["nom_principal"] = df["NomDossierEstimation"].apply(normaliser_nom_principal)

    # Type de bien
    out["type_bien"] = df["Type de bien"].map(TYPE_BIEN_MAP).fillna("autre")

    # Adresse normalisée
    out["adresse_bien_brute"] = df["BienAdresse_Adresse"]
    out["adresse_bien"] = df["BienAdresse_Adresse"].apply(normaliser_adresse_bien)
    cp_ville = df["BienAdresse_Adresse"].apply(
        lambda x: pd.Series(extraire_cp_ville(x), index=["cp", "ville"])
    )
    out["code_postal"] = cp_ville["cp"]
    out["ville"] = cp_ville["ville"]

    # Dates
    out["date_estimation"] = pd.to_datetime(df["DateSaisie"], errors="coerce")
    out["date_dernier_suivi"] = pd.to_datetime(df["DateDernierSuivi"], errors="coerce", dayfirst=True)

    # Flag sans suivi — dérivé de la date, pas de l'écart bugué
    out["sans_suivi"] = out["date_dernier_suivi"].isna()

    # Ancienneté estimation en jours (depuis aujourd'hui)
    today = pd.Timestamp(date.today())
    out["age_estimation_jours"] = (today - out["date_estimation"]).dt.days

    # Contacts — Client1 (principal)
    out["client1_nom"] = df["Client1"].str.strip()
    out["client1_email"] = df["Client1_email"].apply(normaliser_email)
    out["client1_tel"] = df["Client1_Tel1"].apply(normaliser_telephone)
    out["client1_tel2"] = df["Client1_Tel2"].apply(normaliser_telephone) if "Client1_Tel2" in df.columns else None

    # Contacts — Client2 et Client3 (si présents)
    out["client2_nom"] = df["Client2"].str.strip() if "Client2" in df.columns else None
    out["client2_email"] = df["Client2_email"].apply(normaliser_email) if "Client2_email" in df.columns else None
    out["client2_tel"] = df["Client2_Tel1"].apply(normaliser_telephone) if "Client2_Tel1" in df.columns else None

    out["client3_nom"] = df["Client3"].str.strip() if "Client3" in df.columns else None
    out["client3_email"] = df["Client3_email"].apply(normaliser_email) if "Client3_email" in df.columns else None
    out["client3_tel"] = df["Client3_Tel1"].apply(normaliser_telephone) if "Client3_Tel1" in df.columns else None

    # Téléphone de jointure (le plus fiable disponible)
    if "client1_tel2" in out.columns:
        out["tel_jointure"] = out["client1_tel"].combine_first(out["client1_tel2"].combine_first(out["client2_tel"]))
    else:
        out["tel_jointure"] = out["client1_tel"].combine_first(out["client2_tel"])

    # Flags qualité contact
    out["a_telephone"] = out["tel_jointure"].notna()
    out["a_email"] = out["client1_email"].notna()
    out["nb_canaux"] = out["a_telephone"].astype(int) + out["a_email"].astype(int)

    # Colonne d'origine (pour debug)
    out["id_source"] = "eval_" + out["id_evaluation"]

    return out.reset_index(drop=True)


def nettoyer_mandats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nettoyage de l'onglet mandats_sans_ssp.
    Colonnes exclues : NbJours (buguée).
    """
    out = pd.DataFrame()

    out["source"] = "mandat"
    out["id_mandat"] = df["NVendeur"].astype(str)
    out["id_agence"] = df["Id Agence"].astype(str)
    out["agence"] = df["Nom Agence"].str.strip()
    out["actif"] = df["Actif"].astype(bool)

    out["nom_dossier"] = df["NomDossierVendeur"].str.strip()
    out["nom_principal"] = df["NomDossierVendeur"].apply(normaliser_nom_principal)

    out["type_bien"] = df["Type de bien"].map(TYPE_BIEN_MAP).fillna("autre")
    out["classement"] = df["Classement_Resultat"].map(CLASSEMENT_MANDAT_MAP)
    out["classement_code"] = df["Classement_Resultat"]

    out["adresse_bien"] = df["BienAdresse_Adresse"].apply(normaliser_adresse_bien)
    cp_ville = df["BienAdresse_Adresse"].apply(
        lambda x: pd.Series(extraire_cp_ville(x), index=["cp", "ville"])
    )
    out["code_postal"] = cp_ville["cp"]
    out["ville"] = cp_ville["ville"]

    out["date_mandat"] = pd.to_datetime(df["DateSaisie"], errors="coerce")
    out["date_dernier_suivi"] = pd.to_datetime(df["DateDernierSuivi"], errors="coerce", dayfirst=True)
    out["sans_suivi"] = out["date_dernier_suivi"].isna()

    # Age mandat en jours depuis signature
    today = pd.Timestamp(date.today())
    out["age_mandat_jours"] = (today - out["date_mandat"]).dt.days

    # Contacts
    out["client1_nom"] = df["Client1"].str.strip()
    out["client1_email"] = df["Client1_email"].apply(normaliser_email)
    out["client1_tel"] = df["Client1_Tel1"].apply(normaliser_telephone)
    out["client2_nom"] = df["Client2"].str.strip() if "Client2" in df.columns else None
    out["client2_email"] = df["Client2_email"].apply(normaliser_email) if "Client2_email" in df.columns else None
    out["client2_tel"] = df["Client2_Tel1"].apply(normaliser_telephone) if "Client2_Tel1" in df.columns else None
    out["client3_nom"] = df["Client3"].str.strip() if "Client3" in df.columns else None
    out["client3_email"] = df["Client3_email"].apply(normaliser_email) if "Client3_email" in df.columns else None
    out["client3_tel"] = df["Client3_Tel1"].apply(normaliser_telephone) if "Client3_Tel1" in df.columns else None

    out["tel_jointure"] = out["client1_tel"].combine_first(out["client2_tel"])
    out["a_telephone"] = out["tel_jointure"].notna()
    out["a_email"] = out["client1_email"].notna()
    out["nb_canaux"] = out["a_telephone"].astype(int) + out["a_email"].astype(int)

    out["id_source"] = "mand_" + out["id_mandat"]

    return out.reset_index(drop=True)


def nettoyer_mandats_sans_suivi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nettoyage de l'onglet mandats_sans_ssp_sans_suivi.
    Sous-ensemble critique : mandats actifs sans aucun suivi ni avenant.
    """
    out = pd.DataFrame()

    out["source"] = "mandat_sans_suivi"
    out["id_mandat"] = df["NVendeur"].astype(str)
    out["id_agence"] = df["Id Agence"].astype(str)
    out["agence"] = df["Nom Agence"].str.strip()
    out["actif"] = df["Actif"].astype(int) == 1

    out["nom_dossier"] = df["NomDossierVendeur"].str.strip()
    out["nom_principal"] = df["NomDossierVendeur"].apply(normaliser_nom_principal)

    out["type_bien"] = df["Type de bien"].map(TYPE_BIEN_MAP).fillna("autre")
    out["classement_code"] = df["Classement_Resultat"]
    out["classement"] = df["Classement_Resultat"].map(CLASSEMENT_MANDAT_MAP)

    out["adresse_bien"] = df["BienAdresse_Adresse"].apply(normaliser_adresse_bien)
    cp_ville = df["BienAdresse_Adresse"].apply(
        lambda x: pd.Series(extraire_cp_ville(x), index=["cp", "ville"])
    )
    out["code_postal"] = cp_ville["cp"]
    out["ville"] = cp_ville["ville"]

    # ─────────────────────────────────────────────────────────
    # CORRECTION : Le vrai âge du mandat vs Jours sans suivi
    # ─────────────────────────────────────────────────────────
    out["date_mandat"] = pd.to_datetime(df["DateSaisie"], errors="coerce")
    
    # 1. Calcul du véritable âge du mandat depuis la saisie
    today = pd.Timestamp(date.today())
    out["age_mandat_jours"] = (today - out["date_mandat"]).dt.days
    
    out["sans_suivi"] = True

    # 2. Récupération des jours sans suivi (la colonne trompeuse du CRM)
    # On gère "AGE MANDATS" ou "AGE MANDAT" pour être robuste
    nom_col_jours = "AGE MANDATS" if "AGE MANDATS" in df.columns else "AGE MANDAT"
    if nom_col_jours in df.columns:
        out["jours_sans_suivi"] = pd.to_numeric(df[nom_col_jours], errors="coerce").fillna(0).astype(int)
    else:
        out["jours_sans_suivi"] = None

    # 3. Segmentation basée sur le nombre de jours sans suivi
    def calculer_segment_sans_suivi(jours):
        if pd.isna(jours): return None
        if jours <= 179: return "30-179j"
        if jours <= 365: return "180-365j"
        if jours <= 540: return "366-540j"
        return "+541j"

    out["segment_sans_suivi"] = out["jours_sans_suivi"].apply(calculer_segment_sans_suivi)

    # Protection supplémentaire : vérifier si "Actions à prévoir" existe
    if "Actions à prévoir" in df.columns:
        out["action_recommandee_brute"] = df["Actions à prévoir"].str.strip()
    else:
        out["action_recommandee_brute"] = None
    # ─────────────────────────────────────────────────────────

    # Contacts
    out["client1_nom"] = df["Client1"].str.strip()
    out["client1_email"] = df["Client1_email"].apply(normaliser_email)
    out["client1_tel"] = df["Client1_Tel1"].apply(normaliser_telephone)
    out["client2_nom"] = df["Client2"].str.strip() if "Client2" in df.columns else None
    out["client2_email"] = df["Client2_email"].apply(normaliser_email) if "Client2_email" in df.columns else None
    out["client2_tel"] = df["Client2_Tel1"].apply(normaliser_telephone) if "Client2_Tel1" in df.columns else None
    out["client3_nom"] = df["Client3"].str.strip() if "Client3" in df.columns else None
    out["client3_email"] = df["Client3_email"].apply(normaliser_email) if "Client3_email" in df.columns else None
    out["client3_tel"] = df["Client3_Tel1"].apply(normaliser_telephone) if "Client3_Tel1" in df.columns else None

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
    """
    Enrichit les évaluations avec les informations de mandat associé.
    Stratégie en cascade (ordre de fiabilité décroissant) :

    Niveau 1 : tel_jointure exact (identique dans les 2 tables)
    Niveau 2 : id_agence + nom_principal normalisé
    Niveau 3 : id_agence + code_postal + début nom_principal (12 chars)

    Retourne df_eval enrichi avec :
      - match_mandat_niveau : 1/2/3/None
      - match_mandat_id     : NVendeur associé
      - match_mandat_age    : âge du mandat associé en jours
      - match_mandat_classe : classement du mandat associé
      - match_mandat_sans_suivi : True si le mandat n'a pas de suivi
    """
    # Index de lookup pour chaque niveau
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

    # Dicts de lookup (premier match conservé)
    lkp_tel = mand.dropna(subset=["key_tel"]).drop_duplicates("key_tel").set_index("key_tel")
    lkp_agnom = mand.dropna(subset=["key_agence_nom"]).drop_duplicates("key_agence_nom").set_index("key_agence_nom")
    lkp_agcpnom = mand.dropna(subset=["key_agence_cp_nom"]).drop_duplicates("key_agence_cp_nom").set_index("key_agence_cp_nom")

    result_cols = ["match_mandat_niveau", "match_mandat_id",
                   "match_mandat_age", "match_mandat_classe", "match_mandat_sans_suivi"]

    def lookup_row(row):
        # Niveau 1 — téléphone
        if row["tel_jointure"] and row["tel_jointure"] in lkp_tel.index:
            m = lkp_tel.loc[row["tel_jointure"]]
            return pd.Series([1, m["id_mandat"], m["age_mandat_jours"],
                              m["classement_code"], m["sans_suivi"]])
        # Niveau 2 — agence + nom
        key2 = str(row["id_agence"]) + "_" + str(row["nom_principal"] or "")
        if key2 in lkp_agnom.index:
            m = lkp_agnom.loc[key2]
            return pd.Series([2, m["id_mandat"], m["age_mandat_jours"],
                              m["classement_code"], m["sans_suivi"]])
        # Niveau 3 — agence + CP + début nom
        key3 = (
            str(row["id_agence"])
            + "_"
            + str(row["code_postal"] or "")
            + "_"
            + str(row["nom_principal"] or "")[:12]
        )
        if key3 in lkp_agcpnom.index:
            m = lkp_agcpnom.loc[key3]
            return pd.Series([3, m["id_mandat"], m["age_mandat_jours"],
                              m["classement_code"], m["sans_suivi"]])
        return pd.Series([None, None, None, None, None])

    df_eval[result_cols] = df_eval.apply(lookup_row, axis=1)
    return df_eval


# ─────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL
# ─────────────────────────────────────────────

def charger_et_nettoyer(chemin_fichier) -> dict[str, pd.DataFrame]:
    """
    Charge le fichier CRM, nettoie les 3 onglets, effectue la jointure.
    Retourne un dict avec les DataFrames nettoyés et enrichis.

    Usage :
        from components.data_loader import charger_et_nettoyer
        data = charger_et_nettoyer("data/crm.xlsx")
        df_eval    = data["evaluations"]
        df_mand    = data["mandats"]
        df_urgents = data["mandats_sans_suivi"]
        df_radar   = data["radar"]   # évaluations enrichies, prêtes pour scoring
    """
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

    # Jointure évaluations → mandats
    df_radar = joindre_evaluations_mandats(df_eval.copy(), df_mand)

    n_matches = df_radar["match_mandat_niveau"].notna().sum()
    print(f"[data_loader] Jointures éval↔mandat : {n_matches} ({100*n_matches/len(df_radar):.1f}%)")
    for niv in [1, 2, 3]:
        n = (df_radar["match_mandat_niveau"] == niv).sum()
        print(f"  Niveau {niv} : {n}")

    # Stats sans suivi
    print(f"[data_loader] Sans suivi — eval:{df_eval['sans_suivi'].sum()} | mandats:{df_mand['sans_suivi'].sum()}")

    return {
        "evaluations": df_eval,
        "mandats": df_mand,
        "mandats_sans_suivi": df_mss,
        "radar": df_radar,
    }


def stats_qualite(df: pd.DataFrame, label: str = "") -> pd.DataFrame:
    """
    Calcule un rapport de qualité des données pour un DataFrame nettoyé.
    Utile pour affichage dans la page Admin de l'app Streamlit.
    """
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