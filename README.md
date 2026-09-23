# Denis Code — Bots de trading crypto multi-monnaies

Projet de bots de trading crypto pédagogiques, un bot par symbole (multi-crypto).
Chaque bot fonctionne en paper trading simulé : aucun ordre réel n'est envoyé,
portefeuille fictif, stratégies basées sur des indicateurs techniques et suivi
local de l'historique et du portefeuille de chaque monnaie.

## Bots disponibles

| Dossier | Monnaie | Rôle |
|---------|---------|------|
| [`work-agents/bot/`](work-agents/bot/) | — | Base commune du projet |
| [`work-agents/bot-btc/`](work-agents/bot-btc/) | BTC | Bot dédié Bitcoin |
| [`work-agents/bot-sol/`](work-agents/bot-sol/) | SOL | Bot dédié Solana |
| [`work-agents/bot-xrp/`](work-agents/bot-xrp/) | XRP | Bot dédié XRP |

Chaque dossier `bot-*/` contient sa propre structure : `src/` (code), `config/`
(paramétrage), `scripts/` (lancement), `docs/`, `tests/` et `data/` (historique
et portefeuille locaux), ainsi qu'un fichier `com.denis.bot.plist` pour le
lancement via launchd (macOS).

## Pré-requis

- Python 3 (les bots s'exécutent avec `/usr/bin/python3`)
- macOS (fichiers launchd fournis pour l'automatisation)

## Démarrage rapide

1. Cloner le dépôt : `git clone <url-du-depot>` puis se placer dans le dossier du bot souhaité (`work-agents/bot-*/`).
2. Copier les fichiers de configuration d'exemple présents dans `config/` et renseigner ses propres valeurs.
3. Lancer le bot en mode manuel via son script de lancement dans `scripts/` (ex. `scripts/run_once.sh` pour une exécution unique, ajuster le chemin absolu qu'il contient à votre machine).
4. Consulter les logs et l'historique écrits dans `data/` (non poussés sur GitHub).

> Note : vérifier le contenu des scripts `run_once.sh` — ils contiennent un chemin
> absolu propre à la machine d'origine à adapter avant exécution.

## Configuration et secrets

- La configuration utilisateur se fait via les fichiers de `config/` et un fichier
  `.env` local (référence : `.env.example`, non poussé).
- Les secrets (`.env`, clés `*.key`, `*.pem`) ainsi que les données locales
  (`data/`, logs) sont exclus de Git via `.gitignore` : ils ne doivent jamais
  être commités.

## Règles du projet

- Multi-crypto : ne jamais remplacer un bot existant — dupliquer par symbole
  (ex. `bot-btc/`, `bot-sol/`) en conservant l'historique et le portefeuille de
  chaque monnaie.
- Voir [`work-agents/AGENTS.md`](work-agents/AGENTS.md) pour les conventions
  de développement.