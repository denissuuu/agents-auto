#!/bin/bash
# Affiche le statut des 4 bots (bot, bot-btc, bot-sol, bot-xrp) :
#  - processus paper/dashboard actifs (grep), s'il y en a
#  - portefeuille papier (data/paper_portfolio.json) s'il est present
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

for bot_dir in "$ROOT"/bot "$ROOT"/bot-btc "$ROOT"/bot-sol "$ROOT"/bot-xrp; do
  name="$(basename "$bot_dir")"
  echo "== $name"

  # Processus lies au bot (paper.py / dashboard.py) encore actifs
  pids="$(ps -Ao pid=,command= | grep -E "work-agents/${name}/(src/)?(paper|dashboard)\.py" | grep -v grep || true)"
  if [ -n "$pids" ]; then
    echo "$pids"
  else
    echo "   aucun processus actif"
  fi

  # Portefeuille papier s'il existe
  pf="$bot_dir/data/paper_portfolio.json"
  if [ -f "$pf" ]; then
    echo "   portefeuille: $pf"
  else
    echo "   pas de portefeuille (data/paper_portfolio.json absent)"
  fi
done