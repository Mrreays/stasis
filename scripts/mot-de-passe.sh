#!/usr/bin/env bash
# Génère un mot de passe aléatoire pour stasis, l'écrit dans .env (lisible par root seul)
# puis relance l'appli. Sert aussi bien à l'installation qu'au changement de mot de passe.
# Usage : bash scripts/mot-de-passe.sh
set -euo pipefail
cd "$(dirname "$0")/.."
NEW="$(openssl rand -base64 24 | tr -d '/+=')"
TMP="$(umask 077 && mktemp .env.XXXXXX)"
{ { [ -f .env ] && grep -v '^APP_PASSWORD=' .env; } || true; echo "APP_PASSWORD=$NEW"; } > "$TMP"
mv "$TMP" .env
docker compose up -d
echo
echo "Nouveau mot de passe (copie-le maintenant, il ne sera plus affiché) :"
echo "$NEW"
