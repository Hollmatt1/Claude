#!/usr/bin/env bash
# One-shot installer for SwingCheck on a fresh or existing Ubuntu/Debian server.
# Usage: curl -fsSL https://raw.githubusercontent.com/Hollmatt1/Claude/swingcheck/install.sh | bash
set -euo pipefail
REPO=https://github.com/Hollmatt1/Claude.git
BRANCH=swingcheck
DIR="$HOME/swingcheck"

echo "==> Installing prerequisites"
if ! command -v git >/dev/null; then sudo apt-get update -qq && sudo apt-get install -y -qq git; fi
if ! command -v docker >/dev/null; then curl -fsSL https://get.docker.com | sudo sh; fi
if ! sudo docker compose version >/dev/null 2>&1; then sudo apt-get install -y -qq docker-compose-plugin; fi

# A 2 GB swap file keeps the image build and video processing from running out of memory.
if [ "$(swapon --show | wc -l)" -eq 0 ]; then
  echo "==> Adding 2 GB swap file"
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "==> Getting the code"
if [ -d "$DIR/.git" ]; then git -C "$DIR" pull -q; else git clone -q --depth 1 -b "$BRANCH" "$REPO" "$DIR"; fi
cd "$DIR"

if [ ! -f .env ]; then
  PW=$(tr -dc 'a-zA-Z0-9' </dev/urandom | head -c 16 || true)
  sed -e "s/^APP_PASSWORD=.*/APP_PASSWORD=$PW/" -e "s/^BIND=.*/BIND=0.0.0.0/" .env.example > .env
  chmod 600 .env
fi
mkdir -p data

echo "==> Building and starting (first build takes a few minutes)"
sudo docker compose up -d --build

IP=$(curl -fsS https://checkip.amazonaws.com || echo SERVER_IP)
USER_=$(grep '^APP_USER=' .env | cut -d= -f2)
PASS=$(grep '^APP_PASSWORD=' .env | cut -d= -f2)
echo
echo "============================================================"
echo " SwingCheck is running."
echo " Open:     http://$IP:8077"
echo " Username: $USER_"
echo " Password: $PASS"
echo
echo " If the page doesn't load, open port 8077 (TCP) in the"
echo " Lightsail console: your instance > Networking > IPv4 firewall."
echo " To update later, run this same command again."
echo "============================================================"
