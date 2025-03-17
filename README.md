# Paradexbot

Automated XP farming bot that randomly selects 2 accounts from a provided list to open hedge positions on Paradex.

## Features
- 🎯 Random account pairing from available accounts
- ⚖️ Automated hedge order placement
- 🐳 Dockerized deployment


## Usage
- Build Docker image
```
make build
```

- Start the bot
```
make run
```

## Configuration
### 1. Secrets setup
Create `.secrets` file from template
```
cp .secrets.template .secrets
```
Fill in your private keys (one per line)

### 2. Trading configuration
Edit `config.json`

Key configuration notes:
- 🔄 The bot will randomly select 2 private keys from your `.secrets` file for hedging
- ⚖️ Order sizes are randomly selected within the specified range
- ⏱️ Cooldown periods help avoid detection patterns
- 🛡️ For mainnet use, change `paradex_http_url` to production endpoint

## Safety Notes
- 🔑 Never commit your `.secrets` file
- ⚠️ Mainnet operations involve real funds
