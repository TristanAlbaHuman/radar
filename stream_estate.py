"""
stream_estate.py - Radar Mandats V2
Client Stream Estate API avec cache intelligent.

Principe anti-gaspillage Streamlit :
  - Streamlit re-exécute le script entier à chaque interaction.
  - TOUTES les fonctions utilisent @st.cache_data avec TTL adapté.
  - Les appels se font uniquement à la demande (fiche ouverte, liste affichée).
  - Jamais d'appel en masse sur tout le CRM.

Endpoints utilisés :
  1. /indicators/price_per_meter    → prix marché par CP + type de bien
  2. /documents/properties          → biens expirés (signal "a essayé de vendre")
  3. /documents/properties/similar  → comparables actifs pour argumentation prix
  4. /indicators/points_of_interest → environnement du bien pour le script

TTL par type :
  prix_marche    : 86400s  (1 jour)   — données stables
  biens_expires  : 43200s  (12h)      — peuvent disparaître
  similaires     : 21600s  (6h)       — marché actif
  points_interet : 604800s (7 jours)  — très stable
"""

import os
import requests
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from typing import Optional

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

STREAM_BASE = "https://api.stream.estate"

# Mapping types de bien CRM → propertyTypes Stream Estate
TYPE_MAP = {
    "maison":      1,
    "appartement": 0,
    "immeuble":    2,
    "terrain":     5,
    "commerce":    6,
    "bureau":      4,
    "parking":     3,
}


def _get_api_key() -> Optional[str]:
    """
    Récupère la clé API depuis st.secrets ou variable d'environnement.
    Retourne None si non configurée (mode dégradé).
    """
    try:
        return st.secrets["STREAM_ESTATE_API_KEY"]
    except Exception:
        return os.environ.get("STREAM_ESTATE_API_KEY")


def _headers() -> dict:
    key = _get_api_key()
    if not key:
        return {}
    return {"Content-Type": "application/json", "X-API-KEY": key}


def _disponible() -> bool:
    """True si la clé API est configurée."""
    return bool(_get_api_key())


# ─────────────────────────────────────────────
# 1. PRIX DU MARCHÉ
# ─────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def get_prix_marche(cp: str, type_bien: str) -> dict:
    """
    Retourne les indicateurs de prix au m² pour un CP et un type de bien.

    Résultat : {
        "ok": bool,
        "moyenne": float,
        "mediane": float,
        "min": float,
        "max": float,
        "serie": dict,          # {"2024-01": 3200, ...}
        "nb_biens": int,
        "source": str,
        "erreur": str | None,
    }
    TTL cache : 24h (données stables)
    """
    if not _disponible():
        return {"ok": False, "erreur": "Clé API non configurée", "source": "stream_estate"}

    prop_type = TYPE_MAP.get(str(type_bien).lower().strip(), 1)
    params = {
        "includedZipcodes[]": cp,
        "propertyTypes[]":    prop_type,
        "transactionType":    0,
        "withCoherentPrice":  "true",
    }
    try:
        r = requests.get(
            f"{STREAM_BASE}/indicators/price_per_meter",
            headers=_headers(), params=params, timeout=10,
        )
        if r.status_code != 200:
            return {"ok": False, "erreur": f"HTTP {r.status_code}", "source": "stream_estate"}

        data = r.json()
        members = data.get("hydra:member", [])
        if not members:
            return {"ok": False, "erreur": "Aucune donnée marché", "source": "stream_estate"}

        m = members[0]
        return {
            "ok":      True,
            "moyenne": m.get("average"),
            "mediane": m.get("median"),
            "min":     m.get("average_min"),
            "max":     m.get("average_max"),
            "serie":   m.get("series", {}),
            "nb_biens": data.get("hydra:totalItems", 0),
            "erreur":  None,
            "source":  "stream_estate",
        }
    except Exception as e:
        return {"ok": False, "erreur": str(e), "source": "stream_estate"}


def fmt_prix_marche(pm: dict, surface: Optional[float] = None) -> str:
    """
    Formate les données de prix marché pour la fiche prospect.
    Si surface connue, calcule la fourchette de valeur du bien.
    """
    if not pm or not pm.get("ok"):
        return ""

    moy = pm.get("moyenne")
    med = pm.get("mediane")
    mn  = pm.get("min")
    mx  = pm.get("max")

    if not moy:
        return ""

    ligne = f"Marché actuel : **{moy:,.0f} €/m²** médiane"
    if mn and mx:
        ligne += f" (fourchette {mn:,.0f} – {mx:,.0f} €/m²)"

    if surface and surface > 0:
        val_min = mn * surface if mn else moy * 0.85 * surface
        val_max = mx * surface if mx else moy * 1.15 * surface
        ligne += f"\n→ Pour {surface:.0f} m² : **{val_min/1000:.0f} k€ – {val_max/1000:.0f} k€**"

    return ligne


# ─────────────────────────────────────────────
# 2. BIENS EXPIRÉS (signal "a essayé de vendre")
# ─────────────────────────────────────────────

@st.cache_data(ttl=43200, show_spinner=False)
def get_biens_expires(
    cp: str,
    type_bien: str,
    mois_max: int = 18,
) -> dict:
    """
    Cherche si un bien similaire (même CP, même type) a été mis en vente
    et n'a pas trouvé preneur (annonce expirée).

    Retourne : {
        "ok": bool,
        "signal": bool,        # True si au moins 1 bien expiré trouvé
        "nb": int,
        "biens": list[dict],   # liste des biens expirés
        "dernier_prix": float | None,
        "dernier_expire_le": str | None,
        "erreur": str | None,
    }
    TTL cache : 12h
    """
    if not _disponible():
        return {"ok": False, "signal": False, "nb": 0, "biens": [], "erreur": "Clé API non configurée"}

    prop_type = TYPE_MAP.get(str(type_bien).lower().strip(), 1)
    date_from = (date.today() - timedelta(days=mois_max * 30)).isoformat()

    params = {
        "includedZipcodes[]": cp,
        "propertyTypes[]":    prop_type,
        "transactionType":    0,
        "expired":            "true",
        "fromExpiredAt":      date_from,
        "withCoherentPrice":  "true",
        "itemsPerPage":       10,
        "order[updatedAt]":   "desc",
    }
    try:
        r = requests.get(
            f"{STREAM_BASE}/documents/properties",
            headers=_headers(), params=params, timeout=10,
        )
        if r.status_code != 200:
            return {"ok": False, "signal": False, "nb": 0, "biens": [],
                    "erreur": f"HTTP {r.status_code}"}

        data    = r.json()
        biens   = data.get("hydra:member", [])
        nb      = data.get("hydra:totalItems", len(biens))

        if not biens:
            return {"ok": True, "signal": False, "nb": 0, "biens": [], "erreur": None}

        # Extraire le dernier prix et la date d'expiration
        dernier_prix = None
        dernier_expire = None
        for b in biens:
            p = b.get("price") or (b.get("adverts") or [{}])[0].get("price")
            if p and not dernier_prix:
                dernier_prix = p
            e = b.get("expiredAt") or (b.get("adverts") or [{}])[0].get("updatedAt")
            if e and not dernier_expire:
                try:
                    dernier_expire = pd.Timestamp(e).strftime("%d/%m/%Y")
                except Exception:
                    pass

        biens_fmt = []
        for b in biens[:5]:
            adv = (b.get("adverts") or [{}])[0]
            biens_fmt.append({
                "prix":        b.get("price") or adv.get("price"),
                "surface":     b.get("surface") or adv.get("surface"),
                "expire_le":   b.get("expiredAt") or adv.get("updatedAt"),
                "portail":     (adv.get("publisher") or {}).get("name",""),
                "url":         adv.get("url",""),
                "description": (b.get("description") or "")[:120],
            })

        return {
            "ok":              True,
            "signal":          nb > 0,
            "nb":              nb,
            "biens":           biens_fmt,
            "dernier_prix":    dernier_prix,
            "dernier_expire_le": dernier_expire,
            "erreur":          None,
        }
    except Exception as e:
        return {"ok": False, "signal": False, "nb": 0, "biens": [], "erreur": str(e)}


def script_biens_expires(signal: dict, prenom: str, type_bien: str) -> str:
    """Génère l'angle commercial si des biens expirés sont détectés."""
    if not signal or not signal.get("signal"):
        return ""
    nb    = signal.get("nb", 1)
    nsp   = "n'a pas trouvé preneur" if nb == 1 else "n'ont pas trouvé preneurs"
    prix  = signal.get("dernier_prix")
    date_ = signal.get("dernier_expire_le", "récemment")
    tb    = type_bien or "bien"
    prix_s = f" — dernier affiché à {prix:,.0f} €" if prix else ""

    return (
        f"J'ai vu que {nb} {'bien similaire a' if nb==1 else 'biens similaires ont'} "
        f"été {'mis en vente' if nb==1 else 'mis en vente'} sur votre secteur "
        f"et {nsp} "
        f"({date_}{prix_s}). "
        f"Je suis en mesure de vous expliquer pourquoi et de vous proposer une approche différente."
    )


# ─────────────────────────────────────────────
# 3. COMPARABLES ACTIFS
# ─────────────────────────────────────────────

@st.cache_data(ttl=21600, show_spinner=False)
def get_comparables(
    cp: str,
    type_bien: str,
    surface: Optional[float] = None,
    nb: int = 5,
) -> dict:
    """
    Retourne les biens similaires actifs (non expirés) pour argumenter le prix.

    Retourne : {
        "ok": bool,
        "biens": list[dict],
        "prix_median": float | None,
        "erreur": str | None,
    }
    TTL cache : 6h
    """
    if not _disponible():
        return {"ok": False, "biens": [], "prix_median": None, "erreur": "Clé API non configurée"}

    prop_type = TYPE_MAP.get(str(type_bien).lower().strip(), 1)
    params = {
        "includedZipcodes[]": cp,
        "propertyTypes[]":    prop_type,
        "transactionType":    0,
        "expired":            "false",
        "withCoherentPrice":  "true",
        "withLocation":       "true",
        "itemsPerPage":       nb,
        "order[price]":       "desc",
    }
    # Filtrer par surface si disponible (±25%)
    if surface and surface > 0:
        params["surfaceMin"] = int(surface * 0.75)
        params["surfaceMax"] = int(surface * 1.25)

    try:
        r = requests.get(
            f"{STREAM_BASE}/documents/properties",
            headers=_headers(), params=params, timeout=10,
        )
        if r.status_code != 200:
            return {"ok": False, "biens": [], "prix_median": None,
                    "erreur": f"HTTP {r.status_code}"}

        data  = r.json()
        items = data.get("hydra:member", [])
        if not items:
            return {"ok": True, "biens": [], "prix_median": None, "erreur": None}

        biens_fmt = []
        prix_list = []
        for b in items:
            adv = (b.get("adverts") or [{}])[0]
            prix_b = b.get("price") or adv.get("price")
            surf_b = b.get("surface") or adv.get("surface")
            if prix_b:
                prix_list.append(float(prix_b))
            biens_fmt.append({
                "prix":        prix_b,
                "surface":     surf_b,
                "ppm":         b.get("pricePerMeter"),
                "pieces":      b.get("room"),
                "ville":       (b.get("city") or {}).get("name",""),
                "portail":     (adv.get("publisher") or {}).get("name",""),
                "url":         adv.get("url",""),
                "created_at":  b.get("createdAt",""),
                "energie":     (adv.get("energy") or {}).get("category",""),
                "description": (b.get("description") or "")[:100],
            })

        prix_median = sorted(prix_list)[len(prix_list)//2] if prix_list else None

        return {
            "ok":          True,
            "biens":       biens_fmt,
            "prix_median": prix_median,
            "erreur":      None,
        }
    except Exception as e:
        return {"ok": False, "biens": [], "prix_median": None, "erreur": str(e)}


# ─────────────────────────────────────────────
# 4. POINTS D'INTÉRÊT
# ─────────────────────────────────────────────

@st.cache_data(ttl=604800, show_spinner=False)
def get_points_interet(lat: float, lon: float, radius_km: float = 1.0) -> dict:
    """
    Retourne les commerces, transports et services autour d'un point GPS.
    Utile pour enrichir le script vendeur sur les atouts de localisation.

    Retourne : {
        "ok": bool,
        "resume": str,          # texte prêt à lire pendant l'appel
        "categories": dict,
        "erreur": str | None,
    }
    TTL cache : 7 jours (très stable)
    """
    if not _disponible():
        return {"ok": False, "resume": "", "categories": {}, "erreur": "Clé API non configurée"}
    if not lat or not lon:
        return {"ok": False, "resume": "", "categories": {}, "erreur": "Coordonnées GPS non disponibles"}

    params = {
        "lat":    lat,
        "lon":    lon,
        "radius": radius_km,
    }
    try:
        r = requests.get(
            f"{STREAM_BASE}/indicators/points_of_interest",
            headers=_headers(), params=params, timeout=10,
        )
        if r.status_code != 200:
            return {"ok": False, "resume": "", "categories": {},
                    "erreur": f"HTTP {r.status_code}"}

        data = r.json()
        pois = data.get("hydra:member", [])
        if not pois:
            return {"ok": True, "resume": "", "categories": {}, "erreur": None}

        # Grouper par catégorie
        cats = {}
        for p in pois:
            cat  = p.get("category", "Autre")
            name = p.get("name","")
            if name:
                cats.setdefault(cat, []).append(name)

        # Générer un résumé court pour le script
        resume_parts = []
        labels_fr = {
            "school":       "école",
            "transport":    "transport en commun",
            "supermarket":  "supermarché",
            "pharmacy":     "pharmacie",
            "restaurant":   "restaurant",
            "park":         "espace vert",
            "doctor":       "médecin",
        }
        for cat, noms in cats.items():
            label = labels_fr.get(cat, cat)
            nb_c  = len(noms)
            resume_parts.append(f"{nb_c} {label}{'s' if nb_c > 1 else ''} à proximité")

        resume = ", ".join(resume_parts[:4]) if resume_parts else ""

        return {
            "ok":        True,
            "resume":    resume,
            "categories": cats,
            "erreur":    None,
        }
    except Exception as e:
        return {"ok": False, "resume": "", "categories": {}, "erreur": str(e)}


# ─────────────────────────────────────────────
# 5. TENDANCES MARCHÉ PAR SECTEUR (tableau de bord agence)
# ─────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def get_tendance_secteur(
    cp: str,
    type_bien: str,
    nb_mois: int = 6,
) -> dict:
    """
    Détecte si le marché local est en hausse ou en baisse sur les derniers mois.
    Utilisé dans le tableau de bord agence pour contextualiser le marché.

    Retourne : {
        "ok": bool,
        "tendance": "hausse" | "baisse" | "stable",
        "variation_pct": float,
        "prix_actuel": float,
        "prix_debut_periode": float,
        "serie": dict,
        "erreur": str | None,
    }
    TTL cache : 24h
    """
    pm = get_prix_marche(cp, type_bien)
    if not pm.get("ok") or not pm.get("serie"):
        return {"ok": False, "tendance": "stable", "variation_pct": 0.0,
                "prix_actuel": None, "prix_debut_periode": None,
                "serie": {}, "erreur": pm.get("erreur")}

    serie = pm["serie"]
    cles  = sorted(serie.keys())

    if len(cles) < 2:
        return {"ok": True, "tendance": "stable", "variation_pct": 0.0,
                "prix_actuel": serie.get(cles[-1]) if cles else None,
                "prix_debut_periode": None, "serie": serie, "erreur": None}

    recent    = cles[-1]
    old_key   = cles[max(0, len(cles) - nb_mois)]
    p_recent  = serie[recent]
    p_old     = serie[old_key]

    if not p_old or p_old == 0:
        return {"ok": True, "tendance": "stable", "variation_pct": 0.0,
                "prix_actuel": p_recent, "prix_debut_periode": p_old,
                "serie": serie, "erreur": None}

    variation = (p_recent - p_old) / p_old * 100

    if variation > 2:
        tendance = "hausse"
    elif variation < -2:
        tendance = "baisse"
    else:
        tendance = "stable"

    return {
        "ok":               True,
        "tendance":         tendance,
        "variation_pct":    round(variation, 1),
        "prix_actuel":      p_recent,
        "prix_debut_periode": p_old,
        "serie":            serie,
        "erreur":           None,
    }


# ─────────────────────────────────────────────
# HELPERS UI
# ─────────────────────────────────────────────

def badge_tendance(tendance: str, variation: float) -> str:
    """Badge HTML coloré pour afficher la tendance marché."""
    couleurs = {
        "hausse": ("grn", "↑"),
        "baisse": ("red", "↓"),
        "stable": ("gry", "→"),
    }
    c, sym = couleurs.get(tendance, ("gry","→"))
    return (f'<span class="cc-badge badge-{c}">'
            f'{sym} Marché {tendance} {variation:+.1f}%</span>')


def section_marche_fiche(cp: str, type_bien: str, surface=None) -> str:
    """
    Génère le bloc HTML complet "Données marché" pour la fiche prospect.
    Inclut prix/m², fourchette de valeur et indicateur de tendance.
    """
    pm = get_prix_marche(cp, type_bien)
    if not pm.get("ok"):
        return (f'<div style="font-size:11px;color:#bbb">'
                f'Données marché non disponibles</div>')

    moy = pm.get("moyenne")
    med = pm.get("mediane")
    mn  = pm.get("min")
    mx  = pm.get("max")

    if not moy:
        return ""

    # Tendance
    td = get_tendance_secteur(cp, type_bien)
    badge_td = badge_tendance(td.get("tendance","stable"), td.get("variation_pct",0)) if td.get("ok") else ""

    # Valeur estimée si surface connue
    valeur_html = ""
    if surface and surface > 0:
        v_min = int((mn or moy*0.85) * surface / 1000)
        v_max = int((mx or moy*1.15) * surface / 1000)
        valeur_html = (
            f'<div style="margin-top:6px;padding:8px;background:#f0f5ff;border-radius:6px;">'
            f'<span style="font-size:11px;color:#555">Valeur estimée ({surface:.0f} m²) : </span>'
            f'<b style="color:#2d6cdf">{v_min} k€ – {v_max} k€</b></div>'
        )

    return (
        f'<div style="background:#f8f9fb;border:1px solid #eee;border-radius:8px;padding:12px 14px;">'
        f'<div style="font-size:10px;color:#888;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.05em;margin-bottom:6px">Marché {type_bien} · {cp}</div>'
        f'<div style="font-size:18px;font-weight:800;color:#111">{moy:,.0f} <span style="font-size:12px;font-weight:400">€/m²</span></div>'
        f'<div style="font-size:11px;color:#888">médiane {med:,.0f} · fourchette {mn:,.0f}–{mx:,.0f} €/m²</div>'
        f'<div style="margin-top:5px">{badge_td}</div>'
        f'{valeur_html}'
        f'</div>'
    )


def section_signal_expire(cp: str, type_bien: str) -> tuple:
    """
    Retourne (html_badge, angle_script) si un signal d'annonce expirée est détecté.
    """
    signal = get_biens_expires(cp, type_bien)
    if not signal.get("ok") or not signal.get("signal"):
        return "", ""

    nb = signal.get("nb", 0)
    date_ = signal.get("dernier_expire_le","")
    prix  = signal.get("dernier_prix")
    prix_s = f" · dernier prix {prix:,.0f} €" if prix else ""

    badge_html = (
        f'<span class="cc-badge badge-ora">⚠️ {nb} bien{"s" if nb>1 else ""} '
        f'expiré{"s" if nb>1 else ""} sur ce CP{prix_s}</span>'
    )
    angle = script_biens_expires(signal, "", type_bien)
    return badge_html, angle


def section_comparables(cp: str, type_bien: str, surface=None) -> str:
    """Génère le tableau HTML des comparables actifs pour la fiche."""
    comp = get_comparables(cp, type_bien, surface)
    if not comp.get("ok") or not comp.get("biens"):
        return ""

    biens = comp["biens"]
    med   = comp.get("prix_median")

    rows = ""
    for b in biens:
        prix_s = f"{b['prix']:,.0f} €" if b.get("prix") else "—"
        surf_s = f"{b['surface']} m²" if b.get("surface") else "—"
        ppm_s  = f"{b['ppm']:,.0f} €/m²" if b.get("ppm") else "—"
        nrj    = b.get("energie","")
        port   = b.get("portail","")
        url    = b.get("url","")
        lien   = (f'<a href="{url}" target="_blank" class="map-link">Voir</a>'
                  if url else "")
        rows += (
            f"<tr>"
            f"<td style='padding:6px 10px'>{prix_s}</td>"
            f"<td style='padding:6px 10px'>{surf_s}</td>"
            f"<td style='padding:6px 10px'>{ppm_s}</td>"
            f"<td style='padding:6px 10px'>{nrj}</td>"
            f"<td style='padding:6px 10px'>{port}</td>"
            f"<td style='padding:6px 10px'>{lien}</td>"
            f"</tr>"
        )

    med_s = f"Médiane : {med:,.0f} €" if med else ""

    return (
        f'<div style="margin-top:8px">'
        f'<div style="font-size:10px;color:#888;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.05em;margin-bottom:6px">Comparables actifs · {med_s}</div>'
        f'<div style="overflow-x:auto;border:1px solid #eee;border-radius:6px;">'
        f'<table style="width:100%;font-size:12px;border-collapse:collapse;">'
        f'<thead><tr style="background:#f8f9fb;">'
        f'<th style="padding:6px 10px;text-align:left;font-size:10px;color:#555">Prix</th>'
        f'<th style="padding:6px 10px;text-align:left;font-size:10px;color:#555">Surface</th>'
        f'<th style="padding:6px 10px;text-align:left;font-size:10px;color:#555">€/m²</th>'
        f'<th style="padding:6px 10px;text-align:left;font-size:10px;color:#555">DPE</th>'
        f'<th style="padding:6px 10px;text-align:left;font-size:10px;color:#555">Source</th>'
        f'<th style="padding:6px 10px;text-align:left;font-size:10px;color:#555">Lien</th>'
        f'</tr></thead><tbody>{rows}</tbody></table></div></div>'
    )
