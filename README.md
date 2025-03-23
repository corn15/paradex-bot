# Paradexbot

Automated XP farming bot that randomly selects 2 accounts from a provided list to open hedge positions on Paradex.

## Features
- 🎯 Random account pairing from available accounts
- ⚖️ Automated hedge order placement
- ⏱️ Randomized timing for position opening
- 🎲 Randomized order size within configured range
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

## 💖 Support & Development
If this project brings you value, you can help ensure its continued development:

🛠️ **Development Support**
- ETH: `0xDe95B45Ebd1e09f5e7040edC0B11223cB7cCB9e4`
- SOL: `5rWmb4p2oKK6djE8xDvsZLB7ndynspBU4vot7WERsvYF`

🌱 _Your support helps maintain and improve this project!_