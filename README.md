# Gestion Stock Vision

Prototype local de gestion de stock pharmacie: recherche d'article, vente,
ajustement de stock, selection d'une image simulee et interface web Flask pour
le poste pharmacien.

## Installation locale

Python 3.12 est utilise pendant le developpement.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Lancer la web app Flask

```powershell
.venv\Scripts\python web_app.py
```

Sur Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python web_app.py
```

Ouvrir ensuite:

```text
http://127.0.0.1:5000
```

La web app contient:

- une liste du stock chargee depuis `data/pharmacy.sqlite`;
- une zone de demande client avec recherche par nom ou ID;
- une page inventaire en cartes produit;
- une simulation de selection d'image et de deplacement robot;
- un bouton `Vendre` qui decremente le stock dans SQLite;
- un panneau `Ajuster le stock` avec choix `Ajouter` ou `Retirer` et validation;
- des confirmations visibles apres selection, simulation, modification de
  quantite, rechargement et preparation LLM;
- une zone "Assistant pharmacien LLM - futur" qui prepare le contexte a envoyer
  a un LLM, sans delivrer automatiquement un medicament.

## Base de donnees SQLite

La source active du projet est `data/pharmacy.sqlite`. Elle est creee
automatiquement au premier lancement a partir de `data/inventory.csv`.

Tables principales:

- `articles`: stock courant, prix, rayon et image associee.
- `transactions`: historique des confirmations et refus de delivrance.

Le fichier `data/inventory.csv` reste une graine de demonstration. Les
modifications de stock se font dans SQLite.

Pour utiliser une autre base pendant un test ou une demo:

```bash
PHARMASTOCK_DB_PATH=/tmp/pharmacy-demo.sqlite .venv/bin/python web_app.py
```

## Lancer la simulation console

Afficher l'inventaire:

```powershell
python app.py --list
```

Rechercher un article par ID:

```powershell
python app.py --query MED-001 --quantity 2
```

Rechercher un article par nom:

```powershell
python app.py --query amoxicilline
```

Confirmer une delivrance et modifier le stock SQLite:

```powershell
python app.py --query MED-001 --quantity 2 --confirm
```

Ajuster le stock SQLite:

```powershell
python app.py --query MED-001 --quantity 5 --adjust ajouter
python app.py --query MED-001 --quantity 2 --adjust retirer
```

Lancer le mode interactif:

```powershell
python app.py
```

## Point d'integration prioritaire: vision par ordinateur

Le premier branchement a faire apres l'etape 1 est dans `vision.py`, fonction:

```python
process_image(image_path)
```

Flux attendu:

1. `app.py` verifie l'article et le stock avec `prepare_selection(...)`.
2. `web_app.py` recupere `article.image_path`.
3. `web_app.py` appelle `vision.process_image(image_path)`.
4. Le futur modele de vision confirme ou refuse la detection du medicament.
5. La delivrance est confirmee explicitement par le pharmacien avant
   modification du stock.

Pour l'instant, `vision.py` retourne volontairement "module non configure".
C'est le point exact a remplacer par YOLO, Qwen-VL, Llama Vision ou un modele
medical specialise quand le projet sera deploye sur le Cloud AMD.

## Ouverture LLM

Le fichier `llm_assistant.py` prepare un prompt pour un futur assistant
conversationnel. Role prevu: aider le pharmacien a structurer l'echange quand
le client n'a pas d'ordonnance et decrit seulement des symptomes.

Regle importante: le LLM doit assister le pharmacien, pas remplacer son avis.
La recommandation finale et la delivrance restent validees par le pharmacien.

## Tester

```powershell
.venv\Scripts\python -m unittest discover -s tests
```

La suite couvre la logique stock/SQLite et les routes Flask principales.

## Structure

- `app.py`: logique de simulation, persistance SQLite et confirmations.
- `web_app.py`: routes Flask de la web app.
- `templates/index.html`: interface web.
- `static/styles.css`: design de la web app.
- `vision.py`: point d'integration du futur module de vision par ordinateur.
- `llm_assistant.py`: preparation du contexte pour un futur LLM pharmacien.
- `data/pharmacy.sqlite`: base active du projet, creee automatiquement.
- `data/inventory.csv`: inventaire de depart pour initialiser SQLite.
- `images/`: visuels SVG generes pour la demonstration.
- `tests/`: tests des scenarios principaux.
