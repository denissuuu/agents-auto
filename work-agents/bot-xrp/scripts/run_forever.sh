#!/usr/bin/env bash
# Boucle continue paper-only pour VPS (service systemd).
# Aucun ordre réel : le bot ne lit que ticker + klines publics Binance.
# paper.py --once effectue UN tick puis persiste le registre ; le dashboard
# est régénéré à chaque itération.
set -u
BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INTERVAL_SEC="${BOT_INTERVAL_SEC:-60}"
PYTHON="$(command -v python3 || echo /usr/bin/python3)"
cd "$BOT_DIR" || exit 1
mkdir -p data

while true; do
  # stdout vers /dev/null : les ticks sont déjà journalisés par le bot
  # (data/paper.log, data/trades.log) et le dashboard (data/dashboard.html).
  "$PYTHON" src/paper.py --once >/dev/null 2>> data/paper.err.log || true
  "$PYTHON" src/dashboard.py >/dev/null 2>> data/paper.err.log || true
  sleep "$INTERVAL_SEC"
done