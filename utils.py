"""
utils.py — Radar Mandats
Path resolver : à importer en premier dans toutes les pages.
Garantit que la racine du repo est dans sys.path quelle que soit
la façon dont Streamlit Cloud exécute le fichier.
"""
import sys
from pathlib import Path

def setup_path():
    """
    Ajoute la racine du repo dans sys.path.
    Fonctionne que __file__ soit dans pages/, à la racine, ou ailleurs.
    """
    candidates = [
        Path(__file__).parent,                  # si utils.py est à la racine
        Path(__file__).parent.parent,           # si appelé depuis pages/
        Path(__file__).parent.parent.parent,    # sécurité supplémentaire
    ]
    for p in candidates:
        if (p / "components").exists() and (p / "main.py").exists():
            root = str(p)
            if root not in sys.path:
                sys.path.insert(0, root)
            return root
    # Fallback : ajouter tous les candidats
    for p in candidates:
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
    return str(candidates[0])
