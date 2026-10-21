# ZakhrafaAI — Génération de motifs artisanaux marocains par IA

Application web construite à partir du rapport *ZakhrafaAI : Génération de
Motifs Artisanaux par Intelligence Artificielle* (AIDS, FST Tanger).
Elle génère des motifs de **zellige**, **tapis** et **broderie** avec deux
moteurs — un mode **GAN** (rapide, ~256×256) et un mode **Diffusion**
(qualité supérieure, ~768×768) — via une API **FastAPI** et une interface
web (tableau de bord + atelier de réglages), comme décrit au §7 du rapport.

## Démarrage rapide

**Prérequis :** Python 3.10+.

### macOS / Linux
```bash
./run.sh
```

### Windows
```bat
run.bat
```

Puis ouvrez **http://localhost:8000** dans votre navigateur.

Le script crée un environnement virtuel, installe les dépendances
(`backend/requirements.txt`) et démarre le serveur. Aucune connexion
internet n'est nécessaire au runtime : tout le rendu se fait localement.

### Installation manuelle
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate sous Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Pourquoi un générateur procédural par défaut ?

Le rapport documente un GAN convolutionnel entraîné (`gan_<pattern>_final.pth`)
et un pipeline Stable Diffusion + LoRA. Ces deux approches nécessitent :
poids entraînés (plusieurs centaines de Mo à plusieurs Go), un GPU pour un
temps d'inférence raisonnable, et pour Stable Diffusion un téléchargement
initial depuis Hugging Face.

Pour livrer une application **qui fonctionne réellement, sans erreur, hors
ligne, sur n'importe quelle machine**, ce package inclut à la place un
moteur de synthèse géométrique procédural (`backend/app/generators/`) qui
respecte les mêmes contraintes visuelles que le rapport : symétrie,
répétition, palettes culturelles, et les résolutions cibles réellement
utilisées dans le projet (256×256 pour le mode GAN, 768×768 pour le mode
Diffusion, cf. §3.8).

L'architecture **réelle** décrite dans le rapport (cGAN avec générateur/
discriminateur, U-Net conditionnel pour la diffusion) est bien présente
dans le code, prête à être branchée :

- `backend/app/models/gan.py` — `Generator` / `Discriminator` PyTorch (§4.1, §4.3)
- `backend/app/models/diffusion.py` — wrapper Stable Diffusion + LoRA (§4.1, §7)
- `backend/app/services/engine.py` — sélectionne automatiquement les poids
  entraînés s'ils sont présents dans `backend/weights/gan_<categorie>_final.pth`,
  sinon utilise le générateur procédural.

### Brancher de vrais poids entraînés
```bash
pip install -r backend/requirements-torch.txt
mkdir -p backend/weights
cp gan_zellige_final.pth backend/weights/
cp gan_tapis_final.pth backend/weights/
cp gan_broderie_final.pth backend/weights/
```
Au prochain démarrage, l'API détecte automatiquement les poids et les
utilise pour le mode GAN (repli silencieux sur le générateur procédural en
cas d'erreur de chargement). Pour la diffusion, voir
`build_pipeline()` dans `diffusion.py`.

## Structure du projet

```
zakhrafaai/
├── run.sh / run.bat            # scripts de démarrage
├── backend/
│   ├── requirements.txt        # dépendances (FastAPI, Pillow, numpy...)
│   ├── requirements-torch.txt  # optionnel : pour de vrais poids GAN/Diffusion
│   └── app/
│       ├── main.py             # API FastAPI + sert le frontend
│       ├── services/engine.py  # sélection du moteur de génération
│       ├── generators/         # moteur procédural (zellige, tapis, broderie)
│       └── models/             # architectures GAN & Diffusion réelles (§4)
└── frontend/
    └── static/                 # HTML/CSS/JS sans build (servi par FastAPI)
        ├── index.html          # accueil / présentation du produit
        ├── studio.html         # atelier de réglages + galerie
        ├── dashboard.html      # tableau de bord
        ├── css/styles.css
        ├── js/{api,studio,dashboard}.js
        └── img/                # échantillons pré-générés
```

## API

| Méthode | Route            | Description                                   |
|---------|-------------------|------------------------------------------------|
| GET     | `/api/health`     | statut du service                              |
| GET     | `/api/meta`       | catégories, moteurs et palettes disponibles    |
| POST    | `/api/generate`   | génère une image (voir corps ci-dessous)       |
| GET     | `/api/dashboard`  | statistiques de la session en cours            |

Corps de `POST /api/generate` :
```json
{
  "category": "zellige",
  "engine": "diffusion",
  "palette": "fes_bleu",
  "seed": 42,
  "size": 768
}
```

La documentation interactive (Swagger) est disponible sur
`http://localhost:8000/docs` une fois le serveur démarré.

## Limites connues / perspectives (cf. §9 du rapport)

- Le générateur procédural donne un rendu stable et rapide, mais n'est pas
  un modèle appris : pour reproduire fidèlement les résultats entraînés du
  rapport (et leurs limites documentées, cf. §6), fournissez de vrais poids.
- Pas de persistance en base de données : l'historique du tableau de bord
  est réinitialisé à chaque redémarrage du serveur.
- Pas d'authentification utilisateur (hors périmètre de ce packaging).
