# Politique au quotidien

Une leçon de ~5 min par jour + des flashcards à réviser (répétition espacée de Leitner).

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

## Serveur dédié (Hetzner)

### 1. Créer le serveur
Console Hetzner Cloud → **nouveau projet « stasis »** (séparé de celui d'alltool) → Add Server : Ubuntu 24.04, plus petit modèle Shared vCPU (≥ 2 Go de RAM conseillé pour le build), IPv4 publique, ta clé SSH dédiée (`ssh-keygen -t ed25519 -f ~/.ssh/stasis`, colle le `.pub`). Ajoute un **Firewall Cloud** : entrées 22 (idéalement limité à ton IP), 80 et 443 uniquement.

### 2. DNS
Enregistrement `A` : `politique.<ton-domaine>` → IP du serveur. Sans domaine : `<IP-avec-des-tirets>.sslip.io` fonctionne aussi (ex. `1-2-3-4.sslip.io`).

### 3. Durcissement (une fois, en root)
```
ssh root@<IP du serveur>
apt update && apt -y upgrade
apt -y install ufw fail2ban unattended-upgrades ca-certificates curl git
curl -fsSL https://get.docker.com | sh

# SSH : clé uniquement (garde cette session ouverte et teste une 2e connexion avant de la fermer)
cat > /etc/ssh/sshd_config.d/00-hardening.conf <<'EOF'
PasswordAuthentication no
PermitRootLogin prohibit-password
EOF
systemctl restart ssh

ufw default deny incoming && ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
systemctl enable --now fail2ban unattended-upgrades
```

### 4. Déployer
```
git clone https://github.com/Mrreays/stasis.git /opt/stasis && cd /opt/stasis
umask 077
printf "APP_PASSWORD=%s\nDOMAIN=politique.<ton-domaine>\n" "$(openssl rand -base64 24 | tr -d '/+=')" > .env
cat .env     # copie le mot de passe dans ton gestionnaire, une seule fois
docker compose up -d --build
```

### 5. Recevoir les leçons chaque matin
Les leçons sont montées depuis `content/` : un `git pull` suffit, sans reconstruire.
```
cat > /etc/cron.d/stasis <<'EOF'
40 6 * * * root cd /opt/stasis && git pull --ff-only -q
30 7 * * * root cd /opt/stasis && git pull --ff-only -q
EOF
```

### Mise à jour du code / relance
```
ssh root@<IP du serveur>
cd /opt/stasis && git pull && docker compose up -d --build
```
La progression est dans le volume Docker `stasis_data` : elle survit aux mises à jour.
