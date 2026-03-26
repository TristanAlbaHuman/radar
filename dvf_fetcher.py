"""
dvf_fetcher.py - Radar Mandats
Telechargement DVF par departement depuis files.data.gouv.fr
Aucune annotation de type - compatible Python 3.9 a 3.14+
"""

import gzip
import io
import time
import requests
import pandas as pd
from datetime import date


DVF_BASE_URL    = "https://files.data.gouv.fr/geo-dvf/latest/csv/2025/departements/{dept}.csv.gz"
DVF_TIMEOUT     = 60
DVF_DELAY       = 0.3
DVF_COLS        = [
    "date_mutation", "nature_mutation", "valeur_fonciere",
    "adresse_numero", "adresse_suffixe", "adresse_nom_voie",
    "code_postal", "nom_commune",
    "type_local", "surface_reelle_bati", "nombre_pieces_principales",
    "latitude", "longitude",
]
DVF_TYPES = {"Maison", "Appartement"}


def telecharger_dept(dept, session):
    dept = str(dept).strip().upper().zfill(2)
    url  = DVF_BASE_URL.format(dept=dept)
    try:
        r = session.get(url, timeout=DVF_TIMEOUT)
        if r.status_code == 404:
            return pd.DataFrame()
        r.raise_for_status()
        raw = gzip.decompress(r.content)
        df  = pd.read_csv(
            io.BytesIO(raw),
            usecols=lambda c: c in DVF_COLS,
            dtype=str,
            low_memory=False,
        )
        return df
    except Exception:
        return pd.DataFrame()


def _nettoyer_df(df):
    if df.empty:
        return df

    if "type_local" in df.columns:
        df = df[df["type_local"].isin(DVF_TYPES)].copy()

    df["_prix"] = pd.to_numeric(
        df.get("valeur_fonciere", pd.Series(dtype=str))
          .str.replace(",", ".", regex=False),
        errors="coerce",
    ).fillna(0.0)
    df = df[df["_prix"] > 0].copy()

    if df.empty:
        return df

    df["_cp"] = (
        df.get("code_postal", pd.Series(dtype=str))
          .astype(str).str.strip()
          .str.replace(r"\.0$", "", regex=True)
          .str.zfill(5).str[:5]
    )

    df["_num"] = (
        df.get("adresse_numero",  pd.Series(dtype=str)).fillna("").astype(str).str.strip().str.upper()
        + df.get("adresse_suffixe", pd.Series(dtype=str)).fillna("").astype(str).str.strip().str.upper()
    )

    def _nom(s):
        import re
        if not s or (isinstance(s, float) and pd.isna(s)):
            return ""
        s = str(s).upper().strip()
        for src, dst in [('é','E'),('è','E'),('ê','E'),('à','A'),('â','A'),
                         ('î','I'),('ô','O'),('ù','U'),('û','U'),('ç','C'),
                         ('É','E'),('È','E'),('À','A'),('Î','I'),('Ô','O'),
                         ('Ù','U'),('Û','U'),('Ç','C')]:
            s = s.replace(src, dst)
        s = re.sub(r'^\d+\s*(?:BIS|TER)?\s+', '', s)
        s = re.sub(r'^(RUE|AVENUE|CHEMIN|ROUTE|IMPASSE|ALLEE|BOULEVARD|PLACE|ALL|AV|BD)\s+', '', s)
        return s.strip()

    df["_nom"]  = df.get("adresse_nom_voie", pd.Series(dtype=str)).apply(_nom)
    df["_surf"] = pd.to_numeric(
        df.get("surface_reelle_bati", pd.Series(dtype=str)), errors="coerce"
    ).fillna(0.0)
    df["_date"] = pd.to_datetime(
        df.get("date_mutation", pd.Series(dtype=str)), errors="coerce"
    )
    return df


def depts_depuis_cps(cps):
    depts = set()
    for cp in cps:
        cp = str(cp or "").strip().zfill(5)[:5]
        if not cp or not cp[:2].isdigit():
            continue
        d = cp[:2]
        if d == "20":
            try:
                depts.add("2A" if int(cp) <= 20190 else "2B")
            except ValueError:
                depts.add("2A")
        else:
            depts.add(d)
    return sorted(depts)


def construire_index_dvf(depts, progress_callback=None):
    depts   = sorted({str(d).strip().upper().zfill(2) for d in depts if d})
    session = requests.Session()
    session.headers.update({"User-Agent": "RadarMandats/1.0"})

    index  = {}
    n_muts = 0
    total  = len(depts)

    for i, dept in enumerate(depts):
        if progress_callback:
            progress_callback(i + 1, total, dept, n_muts)

        df = telecharger_dept(dept, session)
        if not df.empty:
            df = _nettoyer_df(df)
            if not df.empty:
                df = df.sort_values("_date", ascending=False, na_position="last")
                for row in df.to_dict("records"):
                    cp = row.get("_cp", "")
                    if cp:
                        index.setdefault(cp, []).append(row)
                        n_muts += 1

        time.sleep(DVF_DELAY)

    return index


def _lev_ratio(a, b):
    if a == b: return 1.0
    if not a or not b: return 0.0
    la, lb = len(a), len(b)
    if la > lb: a, b, la, lb = b, a, lb, la
    row = list(range(la + 1))
    for cb in b:
        nr = [row[0] + 1]
        for j, ca in enumerate(a, 1):
            nr.append(min(row[j]+1, nr[-1]+1, row[j-1]+(ca != cb)))
        row = nr
    return 1.0 - row[-1] / max(la, lb)


def chercher_dvf(cp_crm, num_crm, nom_crm, dvf_index, seuil_score=50):
    import re
    candidats = dvf_index.get(cp_crm, [])
    if not candidats:
        return None

    best_score = -1
    best_mut   = None

    for m in candidats:
        rue_dvf = m.get("_nom", "")
        sim = _lev_ratio(nom_crm.upper(), rue_dvf.upper()) if nom_crm and rue_dvf else 0.0

        # Rejet si rues incompatibles
        if nom_crm and rue_dvf and sim < 0.40:
            continue

        sc = 0
        if sim >= 0.90: sc += 50
        elif sim >= 0.75: sc += 38
        elif sim >= 0.60: sc += 25
        elif sim >= 0.40: sc += 12

        n_crm = re.sub(r"\s", "", str(num_crm or "").upper())
        n_dvf = re.sub(r"\s", "", str(m.get("_num", "") or "").upper())
        if n_crm and n_dvf:
            if n_crm == n_dvf: sc += 30
            elif n_crm.rstrip("BISTERQUATER") == n_dvf.rstrip("BISTERQUATER"): sc += 18
        elif not n_crm or not n_dvf:
            sc += 10

        if sc >= seuil_score and sc > best_score:
            best_score = sc
            best_mut   = m
            if sc >= 80:
                break

    return best_mut


def fmt_prix_dvf(m):
    if not m:
        return ""
    prix = m.get("_prix", 0) or 0
    if prix <= 0:
        return ""
    if prix >= 1_000_000:
        return f"{prix/1_000_000:.2f} M€"
    return f"{prix/1_000:.0f} k€"


def fmt_pm2_dvf(m):
    if not m:
        return ""
    prix = m.get("_prix", 0) or 0
    surf = m.get("_surf", 0) or 0
    if prix <= 0 or surf <= 0:
        return ""
    return f"{prix/surf:,.0f} €/m²"


def fmt_date_dvf(m):
    if not m:
        return ""
    d = m.get("date_mutation", "")
    if not d:
        return ""
    try:
        return pd.Timestamp(d).strftime("%d/%m/%Y")
    except Exception:
        return str(d)


def age_achat_label(m):
    if not m:
        return ""
    try:
        d   = pd.Timestamp(m.get("date_mutation", "")).date()
        ans = (date.today() - d).days // 365
        return "< 1 an" if ans == 0 else f"{ans} an{'s' if ans > 1 else ''}"
    except Exception:
        return ""
