"""
ui_utils.py - Radar Mandats V2
Utilitaires partagés : CSS, helpers, générateur de scripts, logique d'action.
"""

import re
import pandas as pd
import html as _html
from datetime import date

# ─────────────────────────────────────────────
# CSS GLOBAL
# ─────────────────────────────────────────────

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700;9..40,800&display=swap');
*, *::before, *::after { font-family: 'DM Sans', sans-serif; box-sizing: border-box; }
.block-container { padding: 1.5rem 2rem 4rem !important; max-width: 1500px !important; }

/* KPI ROW */
.krow { display:grid; grid-template-columns:repeat(auto-fill,minmax(130px,1fr)); gap:10px; margin:0 0 1.2rem; }
.kc { background:#fff; border:1px solid #eaeaea; border-radius:10px; padding:14px 16px; }
.kc.red  { border-top:3px solid #e74c3c; }
.kc.ora  { border-top:3px solid #e67e22; }
.kc.yel  { border-top:3px solid #f1c40f; }
.kc.grn  { border-top:3px solid #27ae60; }
.kc.blu  { border-top:3px solid #2d6cdf; }
.kc.pur  { border-top:3px solid #8e44ad; }
.kc.gry  { border-top:3px solid #bdc3c7; }
.kl { font-size:10px; color:#999; font-weight:700; text-transform:uppercase; letter-spacing:.06em; margin-bottom:5px; }
.kv { font-size:1.55rem; font-weight:800; color:#111; line-height:1; }
.ks { font-size:10px; color:#bbb; margin-top:4px; }

/* SECTION TITLE */
.sec { font-size:11px; font-weight:700; color:#555; text-transform:uppercase;
       letter-spacing:.07em; padding-bottom:6px; margin:1.6rem 0 .8rem;
       border-bottom:2px solid #f0f0f0; }

/* CALL LIST CARDS */
.call-card { background:#fff; border:1px solid #eaeaea; border-radius:12px;
             padding:16px 18px; margin-bottom:8px; display:flex;
             align-items:flex-start; gap:14px; transition:box-shadow .15s; }
.call-card:hover { box-shadow:0 3px 12px rgba(0,0,0,.08); }
.call-card.red  { border-left:4px solid #e74c3c; }
.call-card.ora  { border-left:4px solid #e67e22; }
.call-card.yel  { border-left:4px solid #f1c40f; }
.call-card.pur  { border-left:4px solid #8e44ad; }
.cc-icon { font-size:22px; flex-shrink:0; margin-top:2px; }
.cc-body { flex:1; min-width:0; }
.cc-name { font-size:15px; font-weight:700; color:#111; margin-bottom:3px; }
.cc-addr { font-size:12px; color:#666; margin-bottom:4px; white-space:nowrap;
           overflow:hidden; text-overflow:ellipsis; }
.cc-meta { font-size:11px; color:#999; display:flex; gap:12px; flex-wrap:wrap; }
.cc-badge { display:inline-block; padding:2px 8px; border-radius:4px;
            font-size:10px; font-weight:700; }
.badge-red { background:#fde8e8; color:#c0392b; }
.badge-ora { background:#fef0e0; color:#b7600d; }
.badge-yel { background:#fef9e0; color:#8a6d00; }
.badge-grn { background:#eafaf1; color:#1e8449; }
.badge-blu { background:#ebf2ff; color:#1a56db; }
.badge-pur { background:#f4ecff; color:#6b21a8; }
.badge-gry { background:#f5f5f5; color:#666; }
.cc-action { font-size:11px; font-weight:700; color:#2d6cdf; margin-top:6px; }

/* DPE BADGE */
.dpe { display:inline-flex; align-items:center; justify-content:center;
       width:24px; height:24px; border-radius:5px; font-size:11px; font-weight:800; }
.dA{background:#1e8449;color:#fff;} .dB{background:#27ae60;color:#fff;}
.dC{background:#a9dfbf;color:#1a5c2e;} .dD{background:#f9e79f;color:#6b5900;}
.dE{background:#f0b27a;color:#7d3c00;} .dF{background:#e74c3c;color:#fff;}
.dG{background:#7b241c;color:#fff;} .dX{background:#eee;color:#888;}

/* SCRIPT BOX */
.script-box { background:#f8faff; border:1px solid #dbe8ff; border-radius:10px;
              padding:16px 18px; margin:8px 0; }
.script-label { font-size:10px; font-weight:700; color:#2d6cdf; text-transform:uppercase;
                letter-spacing:.06em; margin-bottom:8px; }
.script-text { font-size:13px; color:#222; line-height:1.6; white-space:pre-wrap; }

/* TABLE */
.tbl { width:100%; border-collapse:separate; border-spacing:0; font-size:12.5px; }
.tbl th { background:#f8f9fb; color:#555; font-size:10px; font-weight:700;
          text-transform:uppercase; letter-spacing:.05em; padding:9px 12px;
          border-bottom:2px solid #e0e0e0; white-space:nowrap;
          position:sticky; top:0; z-index:1; }
.tbl td { padding:10px 12px; border-bottom:1px solid #f2f2f2; vertical-align:top; }
.tbl tr:hover td { background:#fafbff; }
.tbl tr.priority-1 td:first-child { border-left:3px solid #e74c3c; }
.tbl tr.priority-2 td:first-child { border-left:3px solid #e67e22; }
.tbl tr.priority-3 td:first-child { border-left:3px solid #f1c40f; }

/* MAP LINK */
.map-link { display:inline-block; padding:2px 7px; background:#f0f5ff; color:#2d6cdf;
            border-radius:4px; font-size:10px; font-weight:600; text-decoration:none; }

/* PROGRESS BAR */
.prog-bar-wrap { background:#f0f0f0; border-radius:4px; height:6px; margin:4px 0; }
.prog-bar { height:6px; border-radius:4px; background:#2d6cdf; }

/* ALERT BANNER */
.banner { border-radius:10px; padding:14px 18px; margin-bottom:12px;
          display:flex; align-items:center; gap:12px; }
.banner.red  { background:#fde8e8; border:1px solid #f5c6cb; }
.banner.ora  { background:#fef0e0; border:1px solid #fad4a8; }
.banner.grn  { background:#eafaf1; border:1px solid #a9dfbf; }
.banner-icon { font-size:20px; flex-shrink:0; }
.banner-text { font-size:13px; font-weight:600; }

hr.sep { border:none; border-top:1px solid #eee; margin:.6rem 0; }
[data-testid="stSidebar"] { background:#fafafa; }
</style>
"""

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def S(v, d="—"):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return d
    return _html.escape(str(v))

def fmt_date(d, fmt="%d/%m/%Y", default="—"):
    if not d or (isinstance(d, float) and pd.isna(d)):
        return default
    try:
        return pd.Timestamp(d).strftime(fmt)
    except Exception:
        return str(d)

def fmt_age(jours):
    if not jours or pd.isna(jours):
        return "—"
    j = int(jours)
    if j < 30:
        return f"{j}j"
    if j < 365:
        return f"{j//30}m"
    return f"{j//365}a {(j%365)//30}m"

def fmt_prix(v):
    if not v or pd.isna(v):
        return "—"
    try:
        n = float(v)
        if n >= 1_000_000:
            return f"{n/1_000_000:.2f} M€"
        return f"{n/1_000:.0f} k€"
    except Exception:
        return "—"

def dpe_badge(l):
    l = str(l or "").upper().strip()
    c = l if l in list("ABCDEFG") else "X"
    return f'<span class="dpe d{c}">{l if c != "X" else "?"}</span>'

def kpi(label, value, sub="", color="blu"):
    return (f'<div class="kc {color}">'
            f'<div class="kl">{label}</div>'
            f'<div class="kv">{value}</div>'
            f'{"<div class=ks>" + sub + "</div>" if sub else ""}'
            f'</div>')

def badge(text, color="gry"):
    return f'<span class="cc-badge badge-{color}">{_html.escape(str(text))}</span>'

def banner(text, color="grn", icon="✅"):
    return (f'<div class="banner {color}">'
            f'<div class="banner-icon">{icon}</div>'
            f'<div class="banner-text">{text}</div></div>')

import urllib.parse
def map_links(adresse):
    q = urllib.parse.quote(str(adresse or ""))
    return (f'<a class="map-link" href="https://www.openstreetmap.org/search?query={q}" target="_blank">OSM</a> '
            f'<a class="map-link" href="https://maps.google.com/maps?q={q}" target="_blank">GMaps</a>')


# ─────────────────────────────────────────────
# GÉNÉRATEUR DE SCRIPTS D'APPEL
# ─────────────────────────────────────────────

def generer_script(profil, prenom, bien_type, adresse, age_eval_mois=None,
                   age_mandat_mois=None, dpe_label=None, age_suivi_mois=None):
    """
    Génère un script d'appel court et personnalisé selon le profil.
    profil : 'mandat_exclusif' | 'eval_sans_suivi' | 'eval_ancienne' | 'signal_dpe'
    """
    p = prenom or "M./Mme"
    b = (bien_type or "bien").lower()
    a = adresse or ""
    ville = a.split(" ")[-1] if a else ""

    if profil == "mandat_exclusif":
        duree = f"{age_mandat_mois} mois" if age_mandat_mois else "quelques mois"
        return f"""Bonjour {p}, je suis [votre prénom] de l'agence Human Immobilier.

Je vous appelle au sujet de votre {b} situé {a}.

Votre mandat exclusif est en cours depuis {duree} et je souhaitais faire un point avec vous sur les visites effectuées et les retours du marché.

→ Avez-vous 5 minutes pour qu'on fasse le bilan ensemble ?"""

    if profil == "eval_sans_suivi":
        date_s = f"il y a {age_eval_mois} mois" if age_eval_mois else "récemment"
        return f"""Bonjour {p}, je suis [votre prénom] de Human Immobilier.

Nous avons réalisé ensemble une estimation de votre {b} {("à " + ville) if ville else ""} {date_s}.

Je vous rappelle aujourd'hui car votre projet était encore à l'étude et je voulais savoir où vous en étiez.

→ Est-ce que votre projet de vente est toujours d'actualité ?"""

    if profil == "eval_ancienne":
        suivi = f"depuis {age_suivi_mois} mois" if age_suivi_mois else "depuis un moment"
        return f"""Bonjour {p}, je suis [votre prénom] de Human Immobilier.

Nous nous étions rencontrés pour votre {b} {("à " + ville) if ville else ""} et nous n'avons pas eu l'occasion d'échanger {suivi}.

Le marché a évolué sur votre secteur et j'ai des éléments intéressants à vous partager.

→ Seriez-vous disponible cette semaine pour qu'on en discute ?"""

    if profil == "signal_dpe":
        label = dpe_label or "F"
        conseil = {
            "F": "Les biens en DPE F sont aujourd'hui sous pression. C'est le bon moment pour anticiper.",
            "G": "Les passoires thermiques (DPE G) sont soumises à de nouvelles contraintes légales. Beaucoup de propriétaires choisissent de vendre avant les travaux.",
            "E": "Le DPE E commence à impacter les prix. Certains propriétaires préfèrent vendre avant que cela s'accentue.",
        }.get(label, "Votre bien a fait l'objet d'un nouveau diagnostic énergétique récent.")
        return f"""Bonjour {p}, je suis [votre prénom] de Human Immobilier.

Votre {b} {("à " + ville) if ville else ""} vient de faire l'objet d'un nouveau DPE — classé {label}.

{conseil}

→ Avez-vous réfléchi à la valorisation ou à la revente de ce bien ?"""

    return f"Bonjour {p}, je suis [votre prénom] de Human Immobilier. Je vous appelle au sujet de votre bien. Avez-vous quelques minutes ?"


def generer_objet_email(profil, bien_type, ville, prenom):
    p = prenom or ""
    b = (bien_type or "bien").capitalize()
    v = ville or ""
    sujets = {
        "mandat_exclusif":  f"Point sur votre mandat — {b} {v}",
        "eval_sans_suivi":  f"Suite à notre estimation — {b} {v}",
        "eval_ancienne":    f"Votre projet {v} — évolution du marché",
        "signal_dpe":       f"Votre {b} {v} — opportunité à saisir",
    }
    return sujets.get(profil, f"Votre bien {v} — Human Immobilier")


def generer_sms(profil, prenom, agence_tel=""):
    p = prenom or "M./Mme"
    contact = f" Rappelable au {agence_tel}." if agence_tel else ""
    textes = {
        "mandat_exclusif": f"Bonjour {p}, [prénom] de Human Immobilier. Je souhaitais faire un point sur votre mandat.{contact} Bonne journée.",
        "eval_sans_suivi": f"Bonjour {p}, [prénom] de Human Immo. Votre projet de vente est-il toujours d'actualité ?{contact}",
        "eval_ancienne":   f"Bonjour {p}, [prénom] Human Immo. Le marché a évolué dans votre secteur — je peux vous partager des infos.{contact}",
        "signal_dpe":      f"Bonjour {p}, [prénom] Human Immo. Votre bien vient d'avoir un nouveau DPE — à discuter ?{contact}",
    }
    return textes.get(profil, f"Bonjour {p}, [prénom] Human Immobilier.{contact}")


# ─────────────────────────────────────────────
# LOGIQUE DE PRIORISATION TERRAIN
# ─────────────────────────────────────────────

def scorer_action(row, source="eval"):
    """
    Score d'urgence d'action pour une ligne CRM.
    Retourne (score 0-100, profil, couleur, icone, action_label).
    """
    score = 0

    if source == "mandat":
        cl  = str(row.get("classement","")).lower()
        ss  = row.get("sans_suivi", False)
        age = float(row.get("age_suivi_j") or 0)
        age_m = float(row.get("age_mandat_j") or 0)

        if cl == "exclusif":   score += 40
        elif cl == "simple":   score += 25
        if ss:                 score += 35
        elif age > 90:         score += 28
        elif age > 60:         score += 18
        elif age > 30:         score += 8
        if age_m > 300:        score += 15
        elif age_m > 180:      score += 10
        if row.get("a_telephone"): score += 10

        if score >= 70:
            return score, "mandat_exclusif", "red", "🔴", "Relancer mandat d'urgence"
        return score, "mandat_exclusif", "ora", "🟠", "Relancer mandat"

    else:  # eval
        ss    = row.get("sans_suivi", False)
        age_e = float(row.get("age_estimation_jours") or 0)
        age_s = float(row.get("age_suivi_j") or 0)
        actif = row.get("actif", False)
        dpe   = str(row.get("dpe_label") or "").upper().strip()

        if dpe in ("F","G"):   score += 30; profil = "signal_dpe"
        elif dpe == "E":       score += 15; profil = "signal_dpe"
        else:                  profil = "eval_sans_suivi" if ss else "eval_ancienne"

        if actif:              score += 20
        if ss:                 score += 25
        elif age_s > 180:      score += 20
        elif age_s > 90:       score += 12
        if 90 < age_e <= 365:  score += 15
        elif age_e > 365:      score += 10
        if row.get("a_telephone"): score += 10

        if dpe in ("F","G"):
            return score, "signal_dpe", "pur", "🟣", "Signal DPE — appeler"
        if ss:
            return score, "eval_sans_suivi", "ora", "🟠", "Jamais contacté — qualifier"
        return score, "eval_ancienne", "yel", "🟡", "Relance — projet toujours actif ?"


def determiner_profil(row, source="eval"):
    _, profil, couleur, icone, action = scorer_action(row, source)
    return profil, couleur, icone, action


# ─────────────────────────────────────────────
# WIDGET STREAM ESTATE (sidebar)
# ─────────────────────────────────────────────

def widget_configuration_sidebar():
    """
    Widget sidebar pour configurer la clé API Stream Estate.
    Affiche un badge vert si connecté, un champ de saisie sinon.
    Importer depuis ui_utils pour éviter la dépendance circulaire.
    """
    import os
    st.markdown("---")
    st.markdown("### 📡 Stream Estate")
    # Lire la clé depuis session_state, secrets ou env
    key = ""
    try:
        key = st.session_state.get("stream_api_key", "").strip()
    except Exception:
        pass
    if not key:
        try:
            key = st.secrets.get("STREAM_ESTATE_API_KEY", "")
        except Exception:
            pass
    if not key:
        key = os.environ.get("STREAM_ESTATE_API_KEY", "")

    if key:
        st.markdown(
            '<span style="background:#eafaf1;color:#1e8449;padding:3px 10px;'
            'border-radius:4px;font-size:11px;font-weight:700">✅ API connectée</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span style="background:#fef0e0;color:#b7600d;padding:3px 10px;'
            'border-radius:4px;font-size:11px;font-weight:700">⚠️ Clé API requise</span>',
            unsafe_allow_html=True,
        )
        key_input = st.text_input(
            "Clé API Stream Estate",
            type="password",
            key="stream_api_key_input",
            placeholder="Votre clé X-API-KEY",
            help="Obtenez votre clé sur stream.estate",
        )
        if key_input:
            st.session_state["stream_api_key"] = key_input
            st.rerun()
