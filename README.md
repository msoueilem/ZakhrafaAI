# ZakhrafaAI — Génération de motifs artisanaux marocains par IA

> **Note d'honnêteté.** Le mode **rapide** (id d'API `gan`) produit ses
> images avec un **générateur procédural** (`backend/app/generators/`), pas
> avec un modèle entraîné. Le mode **rendu IA** (id `diffusion`) est
> hybride : le même générateur dessine la géométrie (768 px), puis un modèle
> d'image **Google Gemini** la re-rend comme un vrai zellige, tapis ou
> broderie ; sans clé API, quota atteint ou erreur, il renvoie l'image
> procédurale (champ `notice`). Le GAN conditionnel du rapport
> (`models/gan.py`) n'est utilisé que si vous fournissez des poids
> entraînés ; le pipeline Stable Diffusion (`models/diffusion.py`) reste un
> point d'intégration prévu, non branché.

Application web construite à partir du rapport *ZakhrafaAI : Génération de
Motifs Artisanaux par Intelligence Artificielle* (AIDS, FST Tanger).
Elle génère des motifs de **zellige**, **tapis** et **broderie** avec deux
modes de rendu — **rapide** (id `gan`, procédural, ~256×256) et **rendu IA**
(id `diffusion`, géométrie procédurale + rendu Gemini, ~768×768), qui
reprennent les résolutions du GAN et du modèle de diffusion du rapport —
via une API **FastAPI** et une interface web
(tableau de bord + atelier de réglages), comme décrit au §7 du rapport.
La seed fixe à la fois la composition (structure du motif) et les couleurs :
une même seed reproduit exactement la même image.

## Démarrage rapide

**Prérequis :** Python 3.10+ (testé avec Python 3.12). Les dépendances
sont déclarées avec des bornes inférieures (`fastapi>=0.115`, `pydantic>=2.10`,
`Pillow>=11`, `numpy>=2.1`…) afin de s'installer sur les versions récentes
de Python.

### macOS / Linux
```bash
./run.sh
```

### Windows
```bat
run.bat
```

Puis ouvrez **http://127.0.0.1:8000** dans votre navigateur.

Le script crée un environnement virtuel, installe les dépendances
(`backend/requirements.txt`) et démarre le serveur. Le mode rapide
fonctionne hors ligne ; seul le rendu IA appelle l'API Gemini (voir
ci-dessous).

### Installation manuelle
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate sous Windows
pip install -r requirements.txt
uvicorn app.main:app              # ajoutez --reload pour le développement
```

### Docker
```bash
docker compose up -d --build     # http://127.0.0.1:8000 (ZAKHRAFAAI_PORT pour changer le port)
```
L'image (`python:3.12-slim`, utilisateur non root, sans torch) embarque le
générateur procédural et le client Gemini ; le port n'est publié que sur
`127.0.0.1`, à exposer via un reverse proxy (qui doit poser `X-Real-IP`,
utilisé pour la limite par adresse). Le compteur journalier des rendus IA
est conservé dans le volume nommé `zakhrafaai-data` (`/data`). Bilan de
santé : `GET /api/health`.

## Rendu IA (Gemini)

Le mode `diffusion` envoie le motif procédural 768 px à l'API REST Gemini
(`models/{modèle}:generateContent`, appelée avec `httpx`) avec un prompt
propre à la catégorie (zellige : carreaux d'argile émaillée taillés à la
main et joints ; tapis : laine berbère nouée main ; broderie : fils brodés
sur lin), en exigeant la même composition, la même géométrie et la même
palette, vue de dessus, sans texte. Un souhait de style libre (`prompt`,
300 caractères max) peut être ajouté : il est encadré par ces contraintes
et ignoré en mode rapide.

Configuration par variables d'environnement (voir `.env.example`, à copier
en `.env` à la racine — fichier ignoré par git et par l'image Docker ;
`docker compose` le lit automatiquement pour l'interpolation ; en lancement
local via `run.sh` ou `uvicorn`, exportez simplement les variables dans le
shell) :

| Variable              | Défaut                          | Rôle |
|-----------------------|---------------------------------|------|
| `GEMINI_API_KEY`      | *(vide)*                        | clé API Gemini ; vide ⇒ rendu IA désactivé (repli procédural) |
| `GEMINI_IMAGE_MODEL`  | `gemini-3.1-flash-image`        | modèle d'image (`gemini-3.1-flash-lite-image` moins cher mais rendu du zellige trop plat, `gemini-3-pro-image`…) |
| `GEMINI_DAILY_LIMIT`  | `30`                            | rendus IA réussis max par jour UTC (≈ 2 $ avec le modèle par défaut) |
| `GEMINI_PER_IP_LIMIT` | `5`                             | tentatives max par adresse IP sur 10 min |
| `GEMINI_TIMEOUT`      | `90`                            | délai max d'un appel, en secondes |
| `ZAKHRAFAAI_DATA_DIR` | `/data` (Docker), `backend/data` | dossier du compteur journalier persistant |

Garde-fous : seuls les rendus réussis comptent dans le quota journalier
(persisté, il survit aux redémarrages) ; les tentatives comptent pour la
limite par IP ; un cache LRU (64 entrées, clé catégorie/palette/seed/taille/
souhait/modèle) évite de payer deux fois la même image. Toute indisponibilité
(clé absente, quota, limite IP, délai, erreur HTTP, réponse sans image)
renvoie l'image procédurale avec `source: "procedural"` et un `notice`
explicatif — jamais d'erreur 500. La clé n'est ni journalisée ni exposée :
`/api/meta` ne publie que `ai: {enabled, model, remaining_today}`.

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
utilise pour le mode `gan` (sortie 64×64 agrandie à 256 px par défaut ; repli
journalisé sur le générateur procédural en cas d'erreur de chargement). Pour la diffusion, voir
`build_pipeline()` dans `diffusion.py`.

## Structure du projet

```
zakhrafaai/
├── run.sh / run.bat            # scripts de démarrage
├── Dockerfile / docker-compose.yml
├── backend/
│   ├── requirements.txt        # dépendances (FastAPI, Pillow, numpy...)
│   ├── requirements-torch.txt  # optionnel : pour de vrais poids GAN/Diffusion
│   └── app/
│       ├── main.py             # API FastAPI + sert le frontend
│       ├── services/engine.py  # sélection du moteur de génération
│       ├── services/gemini.py  # rendu IA Gemini (quotas, cache, repli)
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
| GET     | `/api/meta`       | catégories, moteurs, palettes, état du rendu IA |
| POST    | `/api/generate`   | génère une image (voir corps ci-dessous)       |
| GET     | `/api/dashboard`  | statistiques globales du serveur (en mémoire)  |

Corps de `POST /api/generate` :
```json
{
  "category": "zellige",
  "engine": "diffusion",
  "palette": "fes_bleu",
  "seed": 42,
  "size": 768,
  "prompt": "émail plus brillant, bleu plus profond"
}
```

`seed` est un entier de 0 à 2^53 − 1 (au-delà : 422, la valeur ne serait
pas relue exactement par un navigateur) ; `size` est bornée à 128–1024 px.

La réponse contient l'image (data URL PNG), `source` (`gemini`,
`procedural` ou `trained_weights`), `model` (modèle Gemini si
`source == "gemini"`) et `notice` (raison d'un repli procédural en mode IA).

La documentation interactive (Swagger) est disponible sur
`http://localhost:8000/docs` une fois le serveur démarré.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

Les tests couvrent l'API (santé, métadonnées, toutes les combinaisons
catégorie × moteur, déterminisme par seed, variation structurelle entre
seeds, validation 422, bornage de la taille, compteurs du tableau de bord,
pages statiques) et le rendu IA avec une API Gemini simulée (succès, replis,
quotas journalier et par IP, cache, persistance du compteur) — aucun appel
réseau réel. Les tests de l'architecture GAN (`tests/test_gan_model.py`)
sont ignorés si `torch` n'est pas installé.

## Limites connues / perspectives (cf. §9 du rapport)

- Le générateur procédural donne un rendu stable et rapide, mais n'est pas
  un modèle appris : pour reproduire fidèlement les résultats entraînés du
  rapport (et leurs limites documentées, cf. §6), fournissez de vrais poids.
- Le rendu IA dépend d'un service externe payant (Gemini) : il n'est pas
  déterministe d'un appel à l'autre (seul le cache rend la même image pour
  la même requête) et peut s'écarter légèrement de la géométrie d'origine.
- Pas de persistance en base de données : l'historique du tableau de bord
  est réinitialisé à chaque redémarrage du serveur.
- Pas d'authentification utilisateur (hors périmètre de ce packaging).
