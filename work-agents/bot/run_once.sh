#!/bin/bash
# Une seule execution paper trading, sans boucle.
cd /Users/juliamenard/Desktop/denis-code/work-agents/bot || exit 1
python3 paper.py --once >> paper.log 2>&1
