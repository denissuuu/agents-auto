#!/bin/bash
# Une seule execution paper trading, sans boucle.
# paper.py écrit déjà dans data/paper.log ; stdout redirigé vers /dev/null pour éviter les doublons.
BOT=/Users/juliamenard/Desktop/denis-code/work-agents/bot
cd "$BOT" || exit 1
/usr/bin/python3 "$BOT/src/paper.py" --once >/dev/null 2>> "$BOT/data/paper.err.log"
/usr/bin/python3 "$BOT/src/dashboard.py" >/dev/null 2>> "$BOT/data/paper.err.log" || true
