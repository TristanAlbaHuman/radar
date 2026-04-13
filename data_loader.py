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

SEGMENT_SANS_SUIVI_MAP = {
    "segment 1": "30-179j",
    "segment 2": "180-365j",
    "segment 3": "366-540j",
    "segment 4": "+541j",
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


def extraire_segment_sans_suivi(typologie: str) -> str | None:
    """Mappe la colonne Typologie vers un label court."""
    if pd.isna(typologie):
        return None
    t = str(typologie).lower()
    for key, label in SEGMENT_SANS_SUIVI_MAP.items():
        if key in t:
            return label
    return None


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
    out["client3_email"] = df["Client3_email"].apply(normaliser_