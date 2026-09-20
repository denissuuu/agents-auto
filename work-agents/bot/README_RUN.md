# Run économe (Mac)

## Principe
Pas de boucle permanente. 1 exécution toutes les 5 min via launchd.
Conso quasi nulle : 1 appel API / 5 min, < 1 s CPU. Mac dort entre exécutions (sauf sleep profond qui saute le tick). Pas de VPS requis pour MVP.

## Install
```bash
cp work-agents/bot/com.denis.bot.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.denis.bot.plist
```

## Start / Stop
```bash
launchctl start com.denis.bot
launchctl stop com.denis.bot
launchctl unload ~/Library/LaunchAgents/com.denis.bot.plist
```

## Logs
```bash
tail -f work-agents/bot/paper.log
```

## Option
Si besoin, passer `poll` à 300 s dans `config.json` pour cohérence.
