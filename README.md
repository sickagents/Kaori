# Kaori

Automated Liquidity Pool agent for **Base network**. Supports Uniswap V3 and Aerodrome.

## Quick Start

```bash
pip install -r requirements.txt

# Run (reads mode from config.json)
python3 lp_agent.py run

# Check positions
python3 lp_agent.py positions

# Switch mode
python3 lp_agent.py mode auto
python3 lp_agent.py mode manual

# Show config
python3 lp_agent.py show

# Batch across wallets
python3 lp_agent.py batch --wallets wallets.json
```

## Configuration (config.json)

**Mode:** Set `mode` to `"auto"` or `"manual"`.

### Manual Mode
Single pair, single run:
```json
{
  "mode": "manual",
  "manual": {
    "dex": "aerodrome",
    "token0": "WETH",
    "token1": "USDC",
    "amount0": "0.01",
    "amount1": "35",
    "stable": false
  }
}
```

### Auto Mode
Multiple pairs, optional loop:
```json
{
  "mode": "auto",
  "auto": {
    "pairs": [
      {"token0": "WETH", "token1": "USDC", "amount0": "0.01", "amount1": "35"},
      {"token0": "WETH", "token1": "AERO", "amount0": "0.01", "amount1": "50"}
    ],
    "prefer_dex": "aerodrome",
    "run_interval_seconds": 3600,
    "max_positions": 5
  }
}
```

## Supported DEXs

| DEX | Type | Router |
|-----|------|--------|
| Uniswap V3 | Concentrated liquidity | `0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1` |
| Aerodrome | Stable/Volatile pools | `0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43` |

## Tokens (Base)

WETH, USDC, USDbC, DAI, cbETH, AERO — all pre-configured in `config.json`.

## Commands

| Command | Description |
|---------|-------------|
| `run` | Execute LP based on config mode |
| `batch` | Run LP across multiple wallets |
| `positions` | Check active LP positions |
| `mode <auto\|manual>` | Switch mode in config |
| `show` | Display current config |

## Architecture

```
lp_agent.py        - CLI + auto/manual logic
config.json        - All configuration
core/
  wallet.py        - Wallet management
  tokens.py        - Token registry + ERC-20
  gas.py           - EIP-1559 gas estimation
dex/
  uniswap_v3.py    - Uniswap V3 position manager
  aerodrome.py     - Aerodrome router wrapper
  base_dex.py      - Abstract DEX interface
utils/
  approvals.py     - ERC-20 approval management
  formatting.py    - Amount formatting
  logging.py       - Structured logging
```
