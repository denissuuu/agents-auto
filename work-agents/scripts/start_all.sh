#!/bin/bash
# Lance une iteration paper trading pour chacun des 4 bots (bot, bot-btc, bot-sol, bot-xrp).
# Chaque bot possede son propre scripts/run_once.sh (1 iteration paper + dashboard).
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

for bot_dir in "$ROOT"/bot "$ROOT"/bot-btc "$ROOT"/bot-sol "$ROOT"/bot-xrp; do
  echo "==> $(basename "$bot_dir")"
  if [ -x "$bot_dir/scripts/run_once.sh" ]; then
    bash "$bot_dir/scripts/run_once.sh"
  else
    echo "    scripts/run_once.sh introuvable, ignore"
  fi
done