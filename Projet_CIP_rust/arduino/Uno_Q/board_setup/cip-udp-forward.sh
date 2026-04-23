#!/bin/bash
#
# cip-udp-forward.sh
#
# App Lab lance le code Python dans un conteneur Docker. Par défaut,
# Docker n'expose que les ports TCP définis dans app.yaml. Ce script
# ajoute dynamiquement une règle iptables DNAT pour rediriger les
# paquets UDP entrants sur le port 2222 (O->T CIP I/O) vers le
# conteneur, quelle que soit son IP.
#
# Il écoute les événements Docker : dès qu'un conteneur dont le nom
# contient "cip" démarre, il récupère son IP et (re)crée la règle.

IFACE="wlan0"
PORT=2222

echo "[cip-udp-forward] Starting, watching Docker events on interface $IFACE port $PORT..."

docker events --filter 'event=start' --format '{{.Actor.Attributes.name}}' | while read name; do
    if echo "$name" | grep -qi "cip"; then
        sleep 1  # laisser le temps au réseau Docker de s'initialiser

        IP=$(docker inspect --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$name" 2>/dev/null)
        if [ -z "$IP" ]; then
            echo "[cip-udp-forward] Container '$name' started but IP not found, skipping."
            continue
        fi

        # Supprimer l'ancienne règle si elle existe (évite les doublons au restart)
        iptables -t nat -D PREROUTING -i "$IFACE" -p udp --dport "$PORT" \
            -j DNAT --to-destination "${IP}:${PORT}" 2>/dev/null

        # Insérer la nouvelle règle en tête de PREROUTING
        iptables -t nat -I PREROUTING 1 -i "$IFACE" -p udp --dport "$PORT" \
            -j DNAT --to-destination "${IP}:${PORT}"

        echo "[cip-udp-forward] Rule applied: UDP $IFACE:$PORT -> ${IP}:${PORT} (container: $name)"
    fi
done
