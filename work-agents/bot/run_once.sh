#!/bin/bash
# Une seule execution paper trading, sans boucle.
# paper.py écrit déjà dans paper.log ; stdout redirigé vers /dev/null pour éviter les doublons.
cd /Users/juliamenard/Desktop/denis-code/work-agents/bot || exit 1
/usr/bin/python3 paper.py --once >/dev/null 2>> paper.err.log
/usr/bin/python3 dashboard.py >/dev/null 2>> paper.err.log || true
