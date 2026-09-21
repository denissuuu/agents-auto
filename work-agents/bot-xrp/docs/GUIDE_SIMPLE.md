# Guide simple — Bot crypto BTC (simulé, sans argent)

## 1. C'est quoi ?
Un petit robot qui regarde le prix du Bitcoin toutes les 5 minutes et te dit : ACHETER, VENDRE ou ATTENDRE.
Il ne touche jamais à ton argent. Il joue avec 1000 $ fictifs pour s'entraîner.

## 2. Où aller ?
Ouvre le Terminal sur ton Mac, puis va dans le projet :
```bash
cd /Users/juliamenard/Desktop/denis-code
```

## 3. Lancer en 2 minutes (copie-colle)
Étape A — Voir le prix en direct :
```bash
python3 work-agents/bot/price.py
```
Tu vois : `BTC/USDT: 80848.48` = 1 Bitcoin vaut 80848 $.

Étape B — Voir le conseil :
```bash
python3 work-agents/bot/paper.py --once
```
Tu vois : `prix=80848 signal=BUY valeur=998.46`
- prix = prix actuel
- signal = BUY (acheter) / SELL (vendre) / HOLD (attendre)
- valeur = combien valent tes 1000 $ fictifs maintenant

Étape C — Voir l'historique :
```bash
tail work-agents/bot/paper.log
```
Chaque ligne = 1 conseil passé. Si valeur monte, la stratégie gagne. Si elle descend, elle perd.

## 4. Mode automatique (tu ne fais plus rien)
Déjà actif : le bot tourne en fond toutes les 15 secondes.
Pour voir ce qu'il fait en direct :
```bash
tail -f work-agents/bot/paper.log
```
Pour l'arrêter :
```bash
pkill -f "run_once.sh" ; echo stoppé
```
Pour le relancer (après reboot par ex.) :
```bash
nohup bash -c 'while true; do /bin/bash work-agents/bot/run_once.sh; sleep 15; done' > work-agents/bot/loop.out.log 2>&1 &
```

## 5. Combien attendre ?
- 2 secondes : 1er résultat avec les commandes ci-dessus.
- 1 heure : 12 conseils (1 toutes les 5 min).
- 7 à 14 jours : assez de recul pour juger. Ne juge pas en 10 minutes.
- Exemple réel d'hier : backtest +4.79% contre +6.9% si on n'avait rien fait. Donc le robot ne gagne pas toujours.

## 6. Comment il réfléchit ? (très simple)
1. Il télécharge le prix sur Binance (bourse publique, gratuite).
2. Il calcule 2 moyennes : prix moyen 7h et 25h + un score de stress (RSI).
3. Si courbe courte passe au-dessus de la longue = BUY. Inverse = SELL. Sinon HOLD.
4. Il note le trade sur papier, sans acheter pour de vrai.

## 7. Questions fréquentes
- Ça consomme ? Non. 1 seconde de travail toutes les 5 min, rien entre.
- Faut-il laisser VSCode ouvert ? Non. Juste le Mac allumé. S'il dort, ça saute un tour, pas grave.
- Je peux perdre de l'argent ? Non, tant que tu restes en `paper.py`. Ne mets jamais de clé API réelle.
- Quand gagnerai-je ? Jamais garanti. C'est un entraînement, pas un distributeur.
