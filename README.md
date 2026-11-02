# Politique au quotidien

Une leçon de ~5 min par jour + des flashcards à réviser (répétition espacée de Leitner).

## Fonctionnement
- Une tâche planifiée Claude (6h30, Paris) écrit `content/AAAA-MM-JJ.json` et le pousse sur ce dépôt. Le prompt est dans `docs/prompt_tache.md`.
- L'appli (FastAPI + SQLite) importe ces fichiers. Les cartes d'une leçon arrivent en révision le lendemain.
- Boîtes de Leitner : 1 j → 3 j → 7 j → 16 j → 35 j. « Raté » ramène en boîte 1, « J'ai hésité » garde la boîte, « Su » monte d'une boîte.
- Rotation : lun/mer/ven notion de fond (suivant `content/curriculum.json`), mar/jeu actu, sam synthèse, dim débat.

## Lancer en local
```
python -m venv .venv && .venv/bin/pip install -r requirements.txt
APP_PASSWORD=monmotdepasse .venv/bin/uvicorn app.main:app --reload
```

## Déploiement sur le VPS Hetzner
```
ssh root@<IP du VPS>
git clone git@github.com:Mrreays/stasis.git /opt/stasis && cd /opt/stasis
echo "APP_PASSWORD=choisis-un-mot-de-passe-long" > .env
docker compose up -d --build
```
Pour relancer : `cd /opt/stasis && git pull && docker compose up -d --build`.
Le conteneur écoute sur `127.0.0.1:8010` : à exposer via ton reverse proxy (Caddy/Nginx) avec HTTPS.
La base est dans `data/` (à sauvegarder, c'est ta progression).
