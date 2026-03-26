# 📡 Radar Mandats

Identifiez, scorez et priorisez les contacts CRM les plus susceptibles de générer une rentrée de mandat.

## Démarrage rapide

```bash
pip install -r requirements.txt
streamlit run main.py
```

## Déploiement Streamlit Cloud

1. Pousser ce repo sur GitHub
2. Connecter sur [share.streamlit.io](https://share.streamlit.io)
3. **Main file path** : `main.py`
4. Deploy → uploader votre `.xlsx` directement dans l'interface web

## Structure

```
radar-mandats/
├── main.py                  ← point d'entrée (upload CRM)
├── pages/
│   ├── 1_Vue_Reseau.py      ← dashboard direction
│   ├── 2_Vue_Agence.py      ← vue manager
│   ├── 3_Fiche_Prospect.py  ← fiche terrain
│   └── 4_Pilotage.py        ← pilotage performance
├── components/
│   ├── data_loader.py       ← nettoyage + jointure CRM
│   └── scoring.py           ← moteur scoring 5 blocs
├── config/
│   └── scoring_rules.yaml   ← règles métier paramétrables
├── .streamlit/config.toml
└── requirements.txt
```

## Format du fichier CRM attendu

Fichier Excel `.xlsx` avec 3 onglets :
- `evaluations_full`
- `mandats_sans_ssp`
- `mandats_sans_ssp_sans_suivi`
