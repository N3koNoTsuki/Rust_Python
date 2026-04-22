#!/bin/bash
# install.sh — Installe le service de forwarding UDP sur la board Arduino Uno Q
# À exécuter une seule fois sur la board : bash install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[install] Copie du script..."
sudo cp "$SCRIPT_DIR/cip-udp-forward.sh" /usr/local/bin/cip-udp-forward.sh
sudo chmod +x /usr/local/bin/cip-udp-forward.sh

echo "[install] Copie du service systemd..."
sudo cp "$SCRIPT_DIR/cip-udp-forward.service" /etc/systemd/system/cip-udp-forward.service

echo "[install] Activation du service..."
sudo systemctl daemon-reload
sudo systemctl enable cip-udp-forward.service
sudo systemctl start cip-udp-forward.service

echo "[install] Done. Status :"
sudo systemctl status cip-udp-forward.service --no-pager
