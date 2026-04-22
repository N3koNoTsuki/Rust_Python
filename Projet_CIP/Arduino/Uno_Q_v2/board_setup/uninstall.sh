#!/bin/bash
# uninstall.sh — Supprime le service de forwarding UDP

set -e

echo "[uninstall] Arrêt et désactivation du service..."
sudo systemctl stop cip-udp-forward.service 2>/dev/null || true
sudo systemctl disable cip-udp-forward.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/cip-udp-forward.service
sudo rm -f /usr/local/bin/cip-udp-forward.sh
sudo systemctl daemon-reload

echo "[uninstall] Suppression de la règle iptables si présente..."
sudo iptables -t nat -D PREROUTING -i wlan0 -p udp --dport 2222 -j DNAT --to-destination 0.0.0.0:2222 2>/dev/null || true

echo "[uninstall] Done."
