# Kaori

Autonomous LP agent for **Base network**. Inspired by [Meridian](https://github.com/yunus-0x/meridian) (Solana DLMM agent).

Supports Uniswap V3 and Aerodrome. Works with **ALL tokens** on Base - no hardcoded list.

## Quick Start

```bash
git clone https://github.com/sickagents/Kaori.git
cd Kaori
pip install -r requirements.txt
cp wallet.env.example wallet.env
# Edit wallet.env with your private key
python3 lp_agent.py run
```

## Commands

| Command | Description |
|---------|-------------|
| `run` | Execute LP (auto/manual based on config) |
| `discover --blocks N` | Scan for new pools |
| `watch --interval N` | Real-time watch + auto-LP |
| `manage` | Monitor positions, check exits, auto-close |
| `learn --evolve` | Show performance, evolve thresholds |
| `batch --wallets file.json` | Multi-wallet LP |
| `positions` | Check LP positions |
| `safety --amount 0.01` | Run pre-deploy safety checks |
| `test-notify` | Test Telegram |
| `mode <auto\|manual>` | Switch mode |
| `show` | Show config |

## Position Lifecycle (Meridian-style)

```
1. DISCOVER  -> Scan Factory events for new pools
2. SCREEN    -> Score by fee/TVL, volume, holders
3. SAFETY    -> 9 checks (balance, cooldowns, duplicates)
4. DEPLOY    -> Add liquidity with slippage protection
5. MONITOR   -> Track PnL, peak, OOR status
6. EXIT      -> Stop loss / trailing TP / OOR timeout / low yield
7. LEARN     -> Record performance, evolve thresholds
```

## Exit Conditions

| Condition | Default | Description |
|-----------|---------|-------------|
| Stop loss | -15% | Close if PnL drops below threshold |
| Trailing TP | 10% peak, 3% drop | Close if peak PnL drops by trailing % |
| OOR timeout | 30 min | Close if out-of-range too long |
| Low yield | <1% after 60min | Close if fees too low |

## Safety Checks (9 checks before deploy)

1. Max positions not exceeded
2. No duplicate pool
3. No duplicate token
4. Pool not on cooldown
5. Token not on cooldown
6. Amount > minimum
7. Amount < maximum
8. Balance covers amount + gas reserve
9. Pool TVL within range

## Lessons Engine

Records every closed position and derives lessons:
- Win rate tracking
- Per-pair performance
- Threshold evolution (max 20% per step)
- Auto-adjusts screening parameters

```bash
python3 lp_agent.py learn           # Show stats
python3 lp_agent.py learn --evolve  # Evolve thresholds
```

## Telegram Notifications

```json
{
  "telegram": {
    "enabled": true,
    "bot_token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
  }
}
```

Events: deploy, close, error, new pool, daily summary.

## Dynamic Token Support

No hardcoded token list. Any ERC-20 on Base works:
- Address: `"0x532f27101965dd16442E59d40670FaF5eBB142E4"`
- Symbol: `"WETH"`, `"USDC"` (from base_tokens lookup)

## Architecture

```
lp_agent.py          - CLI (12 commands)
config.json          - All configuration
wallet.env           - Private key (git-ignored)
core/
  wallet.py          - Wallet management
  tokens.py          - Dynamic on-chain token resolver
  gas.py             - EIP-1559 gas estimation
  pool_scanner.py    - Event-driven pool discovery
  watcher.py         - Real-time watcher + auto-LP
  state.py           - Position lifecycle tracking
  lessons.py         - Performance engine + threshold evolution
  safety.py          - Pre-deploy safety checks
dex/
  uniswap_v3.py      - Uniswap V3 position manager
  aerodrome.py       - Aerodrome router wrapper
  base_dex.py        - Abstract DEX interface
utils/
  approvals.py       - ERC-20 approval management
  formatting.py      - Amount formatting
  logging.py         - Structured logging
  telegram.py        - Telegram notifications
```

## Risk Disclaimer

This tool interacts with DeFi protocols and manages real funds. Use at your own risk.
