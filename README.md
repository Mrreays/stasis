# Stasis

Stasis : une leçon de ~5 min par jour + des flashcards à réviser (répétition espacée de Leitner).

## Fonctionnement
- Une tâche planifiée Claude (6h20, Paris) écrit `content/AAAA-MM-JJ.json` et le pousse sur ce dépôt. Le prompt est dans `docs/prompt_tache.md`.
- L'appli (FastAPI + SQLite) importe ces fichiers. Les cartes d'une leçon arrivent en révision le lendemain.
- Boîtes de Leitner : 1 j → 3 j → 7 j → 16 j → 35 j. « Raté » ramène en boîte 1, « J'ai hésité » garde la boîte, « Su » monte d'une boîte.
- Rotation : lun/mer/ven notion de fond (suivant `content/curriculum.json`), mar/jeu actu, sam synthèse, dim débat.
- Sécurité : mot de passe unique (HTTP Basic derrière HTTPS), blocage après 5 essais ratés en 15 min, conteneur sans droits root, sans capacités, en lecture seule, 256 Mo de RAM max.

## Lancer en local
```
python -m venv .venv && .venv/bin/pip install -r requirements.txt
APP_PASSWORD=monmotdepasse .venv/bin/uvicorn app.main:app --reload
```

## Déploiement sur un serveur qui héberge déjà d'autres projets
`stasis` reste isolé : son propre dossier (`/opt/stasis`), son propre réseau Docker, sa propre base, 256 Mo de RAM max, sans droits root. Il n'écoute que sur `127.0.0.1:8010`.

```
ssh root@<IP du VPS>
git clone https://github.com/Mrreays/stasis.git /opt/stasis && cd /opt/stasis
bash scripts/mot-de-passe.sh   # génère le mot de passe, l'écrit dans .env, lance l'appli et l'affiche UNE fois
```
Le même script sert à **changer** le mot de passe plus tard (il en génère un nouveau et relance l'appli).

Accès sans exposer l'appli sur internet (tunnel SSH, depuis ton ordinateur) :
```
ssh -L 8010:127.0.0.1:8010 root@<IP du VPS>
```
puis `http://localhost:8010`.

Pour une adresse permanente en HTTPS, il faut une entrée dédiée dans le reverse proxy déjà en place (sous-domaine vers `127.0.0.1:8010`).

### Recevoir les leçons chaque matin
Les leçons sont montées depuis `content/` : un `git pull` suffit, sans reconstruire.
```
cat > /etc/cron.d/stasis <<'EOF2'
40 6 * * * root cd /opt/stasis && git pull --ff-only -q
30 7 * * * root cd /opt/stasis && git pull --ff-only -q
EOF2
```

### Mise à jour du code / relance
```
ssh root@<IP du VPS>
cd /opt/stasis && git pull && docker compose up -d --build --remove-orphans
```
La progression est dans le volume Docker `stasis_data` : elle survit aux mises à jour.

## Variante : serveur dédié avec HTTPS automatique (Caddy)
Pour un serveur qui n'héberge que `stasis` (ports 80 et 443 libres), un domaine pointant vers le serveur et `DOMAIN=politique.<ton-domaine>` dans `.env` :
```
docker compose -f docker-compose.yml -f docker-compose.caddy.yml up -d --build
```
Durcissement conseillé du serveur : SSH par clé uniquement, `ufw` (22, 80, 443), `fail2ban`, `unattended-upgrades`.
