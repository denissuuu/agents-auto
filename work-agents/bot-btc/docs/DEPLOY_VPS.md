# Déploiement VPS — Bot BTC paper (Ubuntu / Debian)

Le bot tourne **en continu** sur le VPS, **sans aucun ordre réel** : il lit
chaque minute le prix et les klines publics Binance (`BTCEUR`), exécute un
tick paper, persiste le registre (`data/paper_portfolio.json`) et régénère le
dashboard (`data/dashboard.html`).

> Rappel : `git push` est exclu du projet. On copie les fichiers, on ne pousse rien.

## 1. Copier les fichiers sur le VPS

Depuis ton Mac :

```bash
cd ~/Desktop/denis-code/work-agents
scp -r bot-btc USER@IP_VPS:/opt/trading-bots/
```

Remplacer `USER@IP_VPS` par tes identifiants SSH. Si `/opt/trading-bots` n'existe
pas : `ssh USER@IP_VPS "sudo mkdir -p /opt/trading-bots && sudo chown $USER /opt/trading-bots"`.

Rendre les scripts exécutables :

```bash
ssh USER@IP_VPS "chmod +x /opt/trading-bots/bot-btc/scripts/run_forever.sh"
```

## 2. Installer les services systemd

Deux services :

| Service | Rôle |
|---|---|
| `bot-btc.service` | boucle continue : tick paper + dashboard toutes les 60 s |
| `bot-btc-dashboard.service` | serveur HTTP local du dashboard (port 8080, 127.0.0.1) |

```bash
ssh USER@IP_VPS
sudo cp /opt/trading-bots/bot-btc/deploy/bot-btc.service /etc/systemd/system/
sudo cp /opt/trading-bots/bot-btc/deploy/bot-btc-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bot-btc.service
sudo systemctl enable --now bot-btc-dashboard.service
```

## 3. Vérifier

```bash
sudo systemctl status bot-btc.service        # actif (running) ?
tail -f /opt/trading-bots/bot-btc/data/paper.log   # ticks réels
cat /opt/trading-bots/bot-btc/data/paper_portfolio.json  # état du registre
```

Panne éventuelle : `journalctl -u bot-btc.service -e` et
`cat /opt/trading-bots/bot-btc/data/paper.err.log`.

## 4. Voir le dashboard

Le dashboard est sur `127.0.0.1:8080` (pas exposé à internet par sécurité).
Depuis ton Mac, tunnel SSH :

```bash
ssh -L 8080:127.0.0.1:8080 USER@IP_VPS
# puis dans le navigateur : http://127.0.0.1:8080/dashboard.html
```

## 5. Arrêt / reprise / kill switch

```bash
sudo systemctl stop bot-btc.service          # pause
sudo systemctl start bot-btc.service         # reprise
/opt/trading-bots/bot-btc/src/...            # non : passer par le service
# Kill switch (bloque les nouveaux achats paper) depuis le répertoire :
cd /opt/trading-bots/bot-btc && python3 src/paper.py --kill
cd /opt/trading-bots/bot-btc && python3 src/paper.py --resume
```

## 6. Sécurité

- Aucune clé API, aucun endpoint d'ordres, aucun dépôt/retrait : le code est
  **paper-only** (`mode: paper`, `paper: true`). Vérifiable :
  `grep -rn "api" src/` → seuls `api.binance.com` publics (ticker/klines).
- Le dashboard n'écoute que sur `127.0.0.1` ; ne pas ouvrir le port 8080 au
  pare-feu sans reverse proxy + auth.
- Garder le système à jour : `sudo apt update && sudo apt upgrade`.

## 7. Multi-crypto (ex. BTC)

Le projet interdit de remplacer un bot existant : on **duplique par symbole**.
Créer `bot-btc/` comme copie de `bot-btc/` avec sa propre comptabilité :

```bash
cd /opt/trading-bots
cp -r bot-btc bot-btc
# Dans bot-btc :
#  - config/config.json : symbol "BTCEUR", garder strategy_mode, frais, risques
#  - supprimer data/* (registre, logs) pour un départ propre à 1000 EUR
#  - dupliquer le service : cp deploy/bot-btc.service deploy/bot-btc.service
#    (adapter Description, WorkingDirectory, ExecStart, Label)
```

Chaque bot garde son historique, son portefeuille et ses logs séparés.