"""
ademe_matcher.py - Radar Mandats
Matching adresses CRM <-> ADEME par normalisation RNVP (NF Z 10-011).

Principe :
  1. Normaliser CRM et ADEME en forme canonique RNVP
     (majuscules sans accent, abréviations développées, type de voie long)
  2. Correspondance exacte sur CP + NOM_VOIE + NUMERO
  3. En cas d'absence d'un composant d'un côté : comparaison dégradée

Aucun Levenshtein approximatif sur le nom de voie.
Aucune API externe. Compatible Python 3.9-3.14+.
"""

import re
import math
import pandas as pd
from datetime import date


# ─────────────────────────────────────────────
# CENTROÏDES DÉPARTEMENTAUX
# ─────────────────────────────────────────────

DEPT_COORDS = {
    "01":(46.07,5.32),"02":(49.53,3.60),"03":(46.33,3.34),"04":(44.10,6.23),
    "05":(44.67,6.35),"06":(43.92,7.18),"07":(44.73,4.64),"08":(49.60,4.73),
    "09":(42.95,1.54),"10":(48.30,4.08),"11":(43.19,2.35),"12":(44.35,2.57),
    "13":(43.53,5.45),"14":(49.07,-0.36),"15":(45.05,2.64),"16":(45.70,0.16),
    "17":(45.75,-0.63),"18":(47.08,2.40),"19":(45.27,1.76),"2A":(41.86,8.97),
    "2B":(42.35,9.17),"21":(47.32,4.83),"22":(48.44,-2.76),"23":(46.10,2.05),
    "24":(45.15,0.72),"25":(47.24,6.35),"26":(44.73,5.05),"27":(49.10,1.15),
    "28":(48.43,1.49),"29":(48.24,-3.98),"30":(43.98,4.17),"31":(43.60,1.44),
    "32":(43.66,0.59),"33":(44.84,-0.58),"34":(43.61,3.88),"35":(48.11,-1.68),
    "36":(46.81,1.69),"37":(47.38,0.69),"38":(45.19,5.72),"39":(46.67,5.55),
    "40":(43.89,-0.50),"41":(47.59,1.34),"42":(45.75,4.13),"43":(45.05,3.88),
    "44":(47.22,-1.55),"45":(47.90,2.16),"46":(44.62,1.63),"47":(44.35,0.63),
    "48":(44.52,3.50),"49":(47.47,-0.55),"50":(49.12,-1.27),"51":(49.05,4.39),
    "52":(47.96,5.14),"53":(48.06,-0.75),"54":(48.69,6.18),"55":(49.16,5.38),
    "56":(47.75,-2.75),"57":(49.00,6.76),"58":(47.06,3.67),"59":(50.52,3.14),
    "60":(49.40,2.44),"61":(48.56,0.09),"62":(50.50,2.63),"63":(45.74,3.17),
    "64":(43.30,-0.37),"65":(43.23,0.07),"66":(42.68,2.86),"67":(48.58,7.75),
    "68":(47.75,7.34),"69":(45.75,4.85),"70":(47.63,6.15),"71":(46.67,4.83),
    "72":(47.99,0.20),"73":(45.47,6.44),"74":(45.90,6.12),"75":(48.86,2.35),
    "76":(49.44,1.10),"77":(48.63,2.97),"78":(48.80,1.98),"79":(46.65,-0.37),
    "80":(49.90,2.30),"81":(43.93,2.15),"82":(44.02,1.35),"83":(43.42,6.13),
    "84":(43.95,5.06),"85":(46.67,-1.43),"86":(46.58,0.34),"87":(45.83,1.26),
    "88":(48.18,6.45),"89":(47.80,3.57),"90":(47.64,6.85),"91":(48.63,2.23),
    "92":(48.82,2.25),"93":(48.91,2.45),"94":(48.78,2.45),"95":(49.05,2.08),
    "971":(16.27,-61.58),"972":(14.63,-61.02),"973":(3.93,-53.13),
    "974":(-21.11,55.53),"976":(-12.83,45.17),
}


def cp_vers_coords(cp):
    cp = str(cp or "").strip().zfill(5)
    dept = cp[:3] if cp[:3] in DEPT_COORDS else cp[:2]
    if dept == "20":
        try:
            dept = "2A" if int(cp) <= 20190 else "2B"
        except ValueError:
            dept = "2A"
    coords = DEPT_COORDS.get(dept)
    if coords:
        import hashlib
        h = int(hashlib.md5(cp.encode()).hexdigest()[:4], 16)
        return coords[0] + (h % 100 - 50) / 5000, coords[1] + ((h >> 4) % 100 - 50) / 5000
    return None, None


def parse_coords_ademe(x_val, y_val):
    try:
        x = float(str(x_val).replace(",", ".").strip())
        y = float(str(y_val).replace(",", ".").strip())
        if not x or not y or math.isnan(x) or math.isnan(y):
            return None, None
        if -10 <= x <= 15 and 40 <= y <= 55:
            return y, x
        if 100_000 <= x <= 1_300_000 and 6_000_000 <= y <= 7_300_000:
            lat = (y - 6_600_000) / 111_320 + 46.5
            lon = (x - 700_000) / (111_320 * math.cos(math.radians(46.5))) + 3.0
            if 41 <= lat <= 52 and -6 <= lon <= 10:
                return lat, lon
    except (TypeError, ValueError, AttributeError):
        pass
    return None, None


# ─────────────────────────────────────────────
# NORMALISATION RNVP  (NF Z 10-011)
# ─────────────────────────────────────────────

# Table d'abréviations RNVP → forme longue officielle
_ABBREVS = {
    "ALL":"ALLEE","AV":"AVENUE","AVE":"AVENUE","BV":"BOULEVARD","BD":"BOULEVARD",
    "CAR":"CARREFOUR","CHE":"CHEMIN","CHS":"CHAUSSEE","COR":"CORNICHE",
    "CRS":"COURS","DOM":"DOMAINE","DSC":"DESCENTE","ECA":"ECART","ESP":"ESPLANADE",
    "FG":"FAUBOURG","GR":"GRANDE RUE","HAM":"HAMEAU","IMP":"IMPASSE",
    "LD":"LIEU-DIT","LOT":"LOTISSEMENT","MTE":"MONTEE","PAS":"PASSAGE",
    "PL":"PLACE","PRO":"PROMENADE","PRV":"PARVIS","QUAI":"QUAI",
    "RES":"RESIDENCE","RLE":"RUELLE","ROC":"ROCADE","RPT":"ROND-POINT",
    "RTE":"ROUTE","RUE":"RUE","SEN":"SENTE","SQ":"SQUARE",
    "TRA":"TRAVERSE","VLA":"VILLA","VLGE":"VILLAGE","VOI":"VOIE",
    # Saints
    "ST":"SAINT","STE":"SAINTE","STS":"SAINTS","STES":"SAINTES",
    # Titres et grades
    "DR":"DOCTEUR","GEN":"GENERAL","LT":"LIEUTENANT","CDT":"COMMANDANT",
    "CL":"COLONEL","MAL":"MARECHAL","PRF":"PROFESSEUR","SGT":"SERGENT",
    "CPT":"CAPITAINE","MGR":"MONSEIGNEUR",
}

# Types de voie reconnus (formes longues RNVP)
_TYPES_VOIE = (
    "GRANDE RUE|LIEU-DIT|LIEU DIT|ROND-POINT|"
    "ALLEE|AVENUE|BOULEVARD|CARREFOUR|CHEMIN|CHAUSSEE|CITE|CORNICHE|COURS|"
    "DOMAINE|DESCENTE|ECART|ESPLANADE|FAUBOURG|HAMEAU|IMPASSE|"
    "LOTISSEMENT|MONTEE|PASSAGE|PLACE|PROMENADE|ROUTE|RUE|RUELLE|"
    "RESIDENCE|SQUARE|SENTE|TRAVERSE|VILLA|VILLAGE|VOIE|QUAI"
)
_RE_TYPE = re.compile(rf"^({_TYPES_VOIE})\s+")


def _rnvp_base(s):
    """Normalisation de base : majuscules, sans accents, ponctuation → espace."""
    if not s:
        return ""
    s = str(s).upper().strip()
    for src, dst in [
        ("É","E"),("È","E"),("Ê","E"),("Ë","E"),
        ("À","A"),("Â","A"),("Ä","A"),
        ("Î","I"),("Ï","I"),("Ô","O"),
        ("Ù","U"),("Û","U"),("Ü","U"),("Ç","C"),
    ]:
        s = s.replace(src, dst)
    s = re.sub(r"[,;\.:\-/\\«»\"'`\(\)]+", " ", s)
    # Développer abréviations mot par mot
    mots = s.split()
    out = []
    for m in mots:
        # "130BIS" → "130 BIS"
        m2 = re.sub(r"^(\d+)(BIS|TER|QUATER)$", r"\1 \2", m)
        if m2 != m:
            out.extend(m2.split())
        else:
            out.append(_ABBREVS.get(m, m))
    return " ".join(out).strip()


def _nettoyer_prefixes(s):
    """
    Supprimer les blocs BAT/APPT/ETAGE/RESIDENCE en préfixe
    jusqu'au vrai numéro de voie.
    Traite les cas : "BAT A APPT 15 25 RUE X" → "25 RUE X"
    """
    for _ in range(6):
        avant = s
        # Supprimer tout jusqu'à la première virgule (incluse)
        s = re.sub(r"^[^0-9]*,\s*", "", s)
        # Supprimer bloc BAT/APPT/ETAGE en début
        s = re.sub(
            r"^\s*(?:BAT|BATIMENT|APPARTEMENT|APPT?|ETAGE|RDC|"
            r"ESCALIER|ESC|CAVE|LOT|LOTISSEM|NUM)\s*[A-Z0-9]*\s*",
            "", s
        )
        s = s.strip()
        if s == avant:
            break
    return s


def rnvp_adresse(adresse_brute):
    """
    Normalise une adresse complète selon RNVP (NF Z 10-011).
    Retourne un dict :
      num       : numéro de voie (str, ex: "19")
      suffixe   : BIS / TER / QUATER (str)
      type_voie : type normalisé (ex: "RUE", "AVENUE", "IMPASSE")
      nom_voie  : nom de la voie sans article initial (ex: "ERIK SATIE")
      cp        : code postal 5 chiffres
      ville     : nom de commune normalisé
      cle       : clé de matching exacte "CP|TYPE|NOM|NUM"
    """
    s = _rnvp_base(str(adresse_brute or ""))

    # 1. Extraire CP + ville
    m_cp = re.search(r"\b(\d{5})\b\s*(.*?)$", s)
    cp    = m_cp.group(1) if m_cp else ""
    ville = _rnvp_base(m_cp.group(2)) if m_cp else ""
    avant = s[:m_cp.start()].strip() if m_cp else s

    # 2. Supprimer préfixes immeuble
    avant = _nettoyer_prefixes(avant)

    # 3. Numéro + suffixe
    m_num  = re.match(r"^(\d+)\s*(BIS|TER|QUATER)?\s*", avant)
    num    = m_num.group(1) if m_num else ""
    suffix = (m_num.group(2) or "") if m_num else ""
    reste  = avant[m_num.end():].strip() if m_num else avant

    # 4. Type de voie
    m_type    = _RE_TYPE.match(reste + " ")
    type_voie = m_type.group(1) if m_type else ""
    nom_voie  = reste[m_type.end():].strip() if m_type else reste

    # 5. Clé de matching : CP + TYPE + NOM + NUM
    cle = f"{cp}|{type_voie}|{nom_voie}|{num}"

    return {
        "num": num, "suffixe": suffix,
        "type_voie": type_voie, "nom_voie": nom_voie,
        "cp": cp, "ville": ville,
        "cle": cle,
    }


def rnvp_depuis_dpe(dpe_row):
    """
    Construit un dict RNVP depuis les colonnes ADEME.
    Essaie d'abord les colonnes séparées (num_ban, rue_ban),
    puis l'adresse BAN complète en fallback.
    """
    cp    = str(dpe_row.get("cp_ban") or dpe_row.get("code_postal_ban") or "").strip().zfill(5)[:5]
    ville = _rnvp_base(str(dpe_row.get("ville_ban") or dpe_row.get("nom_commune_ban") or ""))
    num   = str(dpe_row.get("num_ban") or dpe_row.get("numero_voie_ban") or "").strip()
    # Nettoyer les numéros mal formés ADEME comme "1.0m11"
    num = re.sub(r"[^0-9].*$", "", num)  # garder uniquement les chiffres en début
    rue_raw = str(dpe_row.get("rue_ban") or dpe_row.get("nom_rue_ban") or "")

    if rue_raw:
        # Normaliser la rue ADEME
        rue_n = _rnvp_base(rue_raw)
        m_type = _RE_TYPE.match(rue_n + " ")
        type_voie = m_type.group(1) if m_type else ""
        nom_voie  = rue_n[m_type.end():].strip() if m_type else rue_n
    else:
        # Fallback : parser l'adresse BAN complète
        adresse_ban = str(dpe_row.get("adresse_ban") or "")
        parsed = rnvp_adresse(adresse_ban + " " + cp + " " + ville)
        type_voie = parsed["type_voie"]
        nom_voie  = parsed["nom_voie"]
        if not num:
            num = parsed["num"]

    cle = f"{cp}|{type_voie}|{nom_voie}|{num}"
    return {
        "num": num, "suffixe": "",
        "type_voie": type_voie, "nom_voie": nom_voie,
        "cp": cp, "ville": ville, "cle": cle,
    }


# ─────────────────────────────────────────────
# SCORE DE MATCHING
# ─────────────────────────────────────────────

def score_match(adresse_crm, dpe_row):
    """
    Compare une adresse CRM (string brut) avec un DPE ADEME (dict).
    Retourne (score 0-100, niveau, detail).

    Niveaux :
      fort      >= 85  (CP + voie exacte + num exact)
      probable  >= 65  (CP + voie exacte, num absent d'un côté)
      faible    >= 40  (CP + voie exacte, pas de num)
      non_trouve < 40  (ou voie différente)
    """
    crm = rnvp_adresse(str(adresse_crm or ""))
    dpe = rnvp_depuis_dpe(dpe_row)

    # CP obligatoire
    if not crm["cp"] or crm["cp"] != dpe["cp"]:
        return 0, "non_trouve", f"CP different ({crm['cp']} vs {dpe['cp']})"

    score  = 0
    detail = [f"CP {crm['cp']}"]

    # Nom de voie : comparaison EXACTE
    nom_c = crm["nom_voie"]
    nom_d = dpe["nom_voie"]

    if nom_c and nom_d:
        if nom_c == nom_d:
            score += 50
            detail.append(f"Voie exacte (+50)")
        else:
            # Tolérance minimale : même nom sans les articles (DE LA, DU, L, D)
            def sans_articles(s):
                return re.sub(r"\b(DE LA|DE L|DU|DE|L|D|LE|LA|LES|AU|AUX|EN|SUR)\b", "", s).strip()
            nc2, nd2 = sans_articles(nom_c), sans_articles(nom_d)
            if nc2 and nd2 and nc2 == nd2:
                score += 45
                detail.append(f"Voie exacte (sans articles) (+45)")
            else:
                # Rejet : voies différentes
                return 0, "non_trouve", f"Voie differente: '{nom_c}' vs '{nom_d}'"
    elif not nom_c or not nom_d:
        # Un côté sans nom de voie (lieu-dit court, données incomplètes)
        score += 20
        detail.append("Voie partielle (+20)")

    # Type de voie (bonus cohérence)
    tv_c, tv_d = crm["type_voie"], dpe["type_voie"]
    if tv_c and tv_d:
        if tv_c == tv_d:
            score += 15
            detail.append(f"Type {tv_c} (+15)")
        else:
            # Types différents = malus léger mais pas rejet
            score -= 5
            detail.append(f"Type different {tv_c} vs {tv_d} (-5)")

    # Numéro de voie
    n_c = crm["num"]
    n_d = dpe["num"]
    if n_c and n_d:
        if n_c == n_d:
            score += 30
            detail.append(f"Num {n_c} (+30)")
        else:
            # Numéros différents : pénalité forte
            score -= 20
            detail.append(f"Num different {n_c} vs {n_d} (-20)")
    elif n_c or n_d:
        # Un côté sans numéro
        score += 10
        detail.append("Num partiel (+10)")

    # Ville (bonus)
    v_c, v_d = crm["ville"], dpe["ville"]
    if v_c and v_d:
        if v_c == v_d:
            score += 5
            detail.append(f"Ville (+5)")

    score = max(0, min(score, 100))
    if score >= 85:   niveau = "fort"
    elif score >= 65: niveau = "probable"
    elif score >= 40: niveau = "faible"
    else:             niveau = "non_trouve"

    return score, niveau, " | ".join(detail)


# ─────────────────────────────────────────────
# MAPPING COLONNES ADEME
# ─────────────────────────────────────────────

COL_MAP = {
    "numero_dpe":                       "N_DPE",
    "date_etablissement_dpe":           "date_dpe",
    "etiquette_dpe":                    "etiquette_dpe",
    "etiquette_ges":                    "etiquette_ges",
    "conso_5_usages_par_m2_ep":         "conso_ep_m2",
    "surface_habitable_logement":       "surface",
    "annee_construction":               "annee_construction",
    "type_batiment":                    "type_batiment",
    "adresse_ban":                      "adresse_ban",
    "code_postal_ban":                  "cp_ban",
    "nom_commune_ban":                  "ville_ban",
    "numero_voie_ban":                  "num_ban",
    "nom_rue_ban":                      "rue_ban",
    "score_ban":                        "score_ban",
    "coordonnee_cartographique_x_ban":  "x_ban",
    "coordonnee_cartographique_y_ban":  "y_ban",
}



def charger_fichiers_ademe(fichiers):
    """
    Charge et concatene plusieurs fichiers ADEME CSV (jusqu'a 10 x 200 Mo).
    Ne conserve que les colonnes utiles pour reduire la RAM.
    Deduplique sur N_DPE si la colonne est presente.
    Retourne un DataFrame normalise pret a l'emploi.
    """
    COLS_UTILES = {
        "numero_dpe","date_etablissement_dpe",
        "etiquette_dpe","etiquette_ges",
        "conso_5_usages_par_m2_ep","emission_ges_5_usages",
        "surface_habitable_logement","annee_construction",
        "type_batiment","type_energie_principale_chauffage",
        "type_installation_chauffage","type_installation_ecs",
        "adresse_ban","code_postal_ban","nom_commune_ban",
        "numero_voie_ban","nom_rue_ban","score_ban",
        "coordonnee_cartographique_x_ban","coordonnee_cartographique_y_ban",
        "version_dpe","methode_application_dpe_log",
    }
    dfs = []
    for f in fichiers:
        df_raw = None
        for enc in ["utf-8-sig","utf-8","latin-1","cp1252"]:
            for sep in [",",";"]:
                try:
                    f.seek(0)
                    tmp = pd.read_csv(f, sep=sep, encoding=enc,
                                      low_memory=False, on_bad_lines="skip", dtype=str)
                    if len(tmp.columns) >= 5:
                        df_raw = tmp; break
                except Exception: pass
            if df_raw is not None: break
        if df_raw is None:
            try:
                f.seek(0); df_raw = pd.read_excel(f, dtype=str)
            except Exception: continue
        # Nettoyer colonnes
        df_raw.columns = [c.lstrip("\ufeff").strip().lower() for c in df_raw.columns]
        # Garder uniquement les colonnes utiles
        df_raw = df_raw[[c for c in df_raw.columns if c in COLS_UTILES]]
        # Appliquer COL_MAP
        df_raw = df_raw.rename(columns={k: v for k, v in COL_MAP.items() if k in df_raw.columns})
        dfs.append(df_raw)
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)
    if "N_DPE" in df.columns:
        avant = len(df)
        df = df.drop_duplicates(subset=["N_DPE"], keep="first")
        if avant > len(df):
            print(f"[ademe] Deduplication : {avant-len(df):,} doublons supprimes")
    print(f"[ademe] {len(df):,} DPE charges ({len(fichiers)} fichier(s))")
    return df

def normaliser_df_ademe(df):
    df = df.copy()
    df.columns = [c.lstrip("\ufeff").strip().lower() for c in df.columns]
    return df.rename(columns={k: v for k, v in COL_MAP.items() if k in df.columns})


# ─────────────────────────────────────────────
# SCORE DE MATURITÉ
# ─────────────────────────────────────────────

def calculer_score_maturite(row, seuil_recence_mois=12):
    score, motifs = 0, []
    dpe_trouve  = row.get("ademe_status") == "trouve"
    age_dpe     = row.get("dpe_age_mois")
    dpe_label   = str(row.get("dpe_label") or "").upper().strip()
    match_score = int(row.get("ademe_match_score") or 0)

    if not dpe_trouve:
        motifs.append("DPE non trouve")
        age_est = int(row.get("age_estimation_jours") or 0)
        if age_est > 365: motifs.append(f"Estimation ancienne ({age_est//30}m)")
        if not pd.notna(row.get("match_mandat_id")): motifs.append("Pas de mandat")
        return 0, motifs, "Pas de DPE"

    if match_score >= 85:   score += 12; motifs.append(f"Match fort ({match_score}) (+12)")
    elif match_score >= 65: score += 7;  motifs.append(f"Match probable ({match_score}) (+7)")
    else:                   score += 2;  motifs.append(f"Match faible ({match_score}) (+2)")

    if age_dpe is not None:
        if age_dpe <= 3:
            score += 45; motifs.append(f"DPE tres recent ({age_dpe}m) (+45)")
        elif age_dpe <= 6:
            score += 38; motifs.append(f"DPE recent ({age_dpe}m) (+38)")
        elif age_dpe <= 12:
            score += 28; motifs.append(f"DPE <12m ({age_dpe}m) (+28)")
        elif age_dpe <= seuil_recence_mois:
            score += 18; motifs.append(f"DPE dans seuil ({age_dpe}m) (+18)")
        else:
            score += 5;  motifs.append(f"DPE ancien ({age_dpe}m) (+5)")

    if dpe_label in ("F","G"):
        score += 10; motifs.append(f"DPE {dpe_label} passoire (+10)")
    elif dpe_label == "E":
        score += 5; motifs.append("DPE E (+5)")

    age_est  = int(row.get("age_estimation_jours") or 0)
    a_mandat = pd.notna(row.get("match_mandat_id"))
    if age_est > 365:   score += 20; motifs.append(f"Estimation ancienne ({age_est//30}m) (+20)")
    elif age_est > 180: score += 12; motifs.append(f"Estimation >6m (+12)")
    score += 8 if a_mandat else 20
    motifs.append("Mandat existant (+8)" if a_mandat else "Pas de mandat (+20)")
    if row.get("a_telephone") and row.get("a_email"):
        score += 8; motifs.append("Joignable tel+email (+8)")
    elif row.get("a_telephone"):
        score += 4; motifs.append("Telephone (+4)")

    score = min(score, 100)
    if score >= 75:   niveau = "Tres urgent"
    elif score >= 55: niveau = "Signal fort"
    elif score >= 35: niveau = "Signal modere"
    else:             niveau = "Signal faible"

    return score, motifs, niveau


# ─────────────────────────────────────────────
# ENRICHISSEMENT BATCH CSV
# ─────────────────────────────────────────────

def enrichir_via_csv(df_crm, df_ademe, seuil_recence_mois=12, progress_callback=None):
    df_ademe = normaliser_df_ademe(df_ademe)

    col_cp = next((c for c in ["cp_ban","code_postal_ban"] if c in df_ademe.columns), None)
    if col_cp is None:
        raise ValueError(
            "Colonne 'code_postal_ban' introuvable. Colonnes: "
            + ", ".join(df_ademe.columns[:15].tolist())
        )
    df_ademe["_cp"] = (
        df_ademe[col_cp].astype(str).str.strip()
        .str.replace(r"\.0$","",regex=True)
        .str.zfill(5).str[:5]
    )

    print(f"[matcher] Index sur {len(df_ademe):,} DPE...")
    cp_index = {}
    for row_a in df_ademe.to_dict("records"):
        cp = row_a.get("_cp","")
        if cp:
            cp_index.setdefault(cp,[]).append(row_a)
    print(f"[matcher] {len(cp_index):,} CP indexes")

    df_cibles = df_crm[df_crm["match_mandat_id"].isna()].copy()
    total = len(df_cibles)
    print(f"[matcher] {total:,} dossiers a enrichir...")

    resultats = []
    for i, (_, row) in enumerate(df_cibles.iterrows()):
        if progress_callback and i % 100 == 0:
            progress_callback(i + 1, total)

        adresse_crm = str(row.get("adresse_bien") or "")
        # CP de fallback depuis colonne dédiée si absent de l'adresse
        cp_fallback = str(row.get("code_postal") or "").strip().zfill(5)[:5]
        crm_parsed  = rnvp_adresse(adresse_crm)
        cp_crm      = crm_parsed["cp"] or cp_fallback

        candidats = cp_index.get(cp_crm, [])

        if not candidats:
            lat, lon = cp_vers_coords(cp_crm)
            info = {
                "ademe_status": "non_trouve",
                "ademe_match_score": 0,
                "ademe_match_niveau": "non_trouve",
                "ademe_match_detail": f"Aucun DPE pour CP {cp_crm}",
                "lat": lat, "lon": lon,
            }
        else:
            best_sc, best_niv, best_det, best_dpe = 0, "non_trouve", "", None
            for dpe in candidats:
                sc, niv, det = score_match(adresse_crm, dpe)
                if sc > best_sc:
                    best_sc, best_niv, best_det, best_dpe = sc, niv, det, dpe

            if best_dpe is None or best_sc < 40:
                lat, lon = cp_vers_coords(cp_crm)
                info = {
                    "ademe_status": "non_trouve",
                    "ademe_match_score": best_sc,
                    "ademe_match_niveau": "non_trouve",
                    "ademe_match_detail": f"Meilleur score insuffisant: {best_sc}/100",
                    "lat": lat, "lon": lon,
                }
            else:
                lat, lon = parse_coords_ademe(
                    best_dpe.get("x_ban"), best_dpe.get("y_ban")
                )
                if lat is None:
                    lat, lon = cp_vers_coords(cp_crm)

                date_str = str(best_dpe.get("date_dpe") or "")
                try:    dpe_date = pd.Timestamp(date_str).date()
                except: dpe_date = None
                age_mois = (date.today() - dpe_date).days // 30 if dpe_date else None

                info = {
                    "ademe_status":       "trouve",
                    "ademe_match_score":  best_sc,
                    "ademe_match_niveau": best_niv,
                    "ademe_match_detail": best_det,
                    "lat": lat, "lon": lon,
                    "dpe_label":        best_dpe.get("etiquette_dpe"),
                    "dpe_ges":          best_dpe.get("etiquette_ges"),
                    "dpe_date":         dpe_date,
                    "dpe_age_mois":     age_mois,
                    "dpe_conso":        best_dpe.get("conso_ep_m2"),
                    "dpe_surface":      best_dpe.get("surface"),
                    "dpe_annee_constr": best_dpe.get("annee_construction"),
                    "dpe_type_bat":     best_dpe.get("type_batiment"),
                    "dpe_adresse_ban":  best_dpe.get("adresse_ban"),
                    "dpe_recent":       age_mois is not None and age_mois <= seuil_recence_mois,
                }

        enriched = row.to_dict()
        enriched.update(info)
        sc, mo, nv = calculer_score_maturite(pd.Series(enriched), seuil_recence_mois)
        enriched["score_maturite"]  = sc
        enriched["motifs_maturite"] = " | ".join(mo)
        enriched["niveau_maturite"] = nv
        resultats.append(enriched)

        if i % 2000 == 0 and i > 0:
            n_ok = sum(1 for r in resultats if r.get("ademe_status") == "trouve")
            print(f"[matcher] {i}/{total} | matches: {n_ok} ({100*n_ok/i:.0f}%)")

    if progress_callback:
        progress_callback(total, total)

    df_result = pd.DataFrame(resultats)
    n_ok = int((df_result["ademe_status"] == "trouve").sum())
    print(f"[matcher] Termine: {n_ok:,}/{total:,} ({100*n_ok/total:.1f}%)")
    return df_result.sort_values("score_maturite", ascending=False).reset_index(drop=True)


# ─────────────────────────────────────────────
# ALIASES (compatibilité dvf_fetcher et pages)
# ─────────────────────────────────────────────

def normaliser(s):
    return _rnvp_base(str(s or ""))

def extraire_composants(s):
    s = str(s or "").strip()
    m = re.match(r"^(\d+\s*(?:BIS|TER|QUATER)?)\s+", s + " ")
    num = re.sub(r"\s","", m.group(1)).upper() if m else ""
    rue = s[m.end():].strip() if m else s
    return num, rue

def parser_adresse_crm(adresse_brute):
    p = rnvp_adresse(adresse_brute)
    return p["num"], p["nom_voie"], p["cp"], p["ville"]
