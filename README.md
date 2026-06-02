# Kaori

Automated Liquidity Pool agent for **Base network**. Supports Uniswap V3 and Aerodrome.

## Quick Start (Server)

```bash
# 1. Clone
git clone https://github.com/sickagents/Kaori.git
cd Kaori

# 2. Install deps
pip install -r requirements.txt

# 3. Setup wallet
cp wallet.env.example wallet.env
# Edit wallet.env with your private key

# 4. Run
python3 lp_agent.py run           # LP based on config mode
python3 lp_agent.py discover      # Scan for new pools
python3 lp_agent.py watch         # Watch + auto-LP new pools
python3 lp_agent.py positions     # Check positions
python3 lp_agent.py show          # Show config
```

## Wallet Setup

**wallet.env** (git-ignored, copy from example):
```
PRIVATE_KEY=0xYOUR_PRIVATE_KEY
ADDRESS=0xYOUR_WALLET_ADDRESS
```

For batch mode, create **wallets.json**:
```json
[
  {"address": "0x...", "private_key": "0x..."},
  {"address": "0x...", "private_key": "0x..."}
]
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
      {"token0": "WETH", "token1": "BRETT", "amount0": "0.005", "amount1": "10000"}
    ],
    "prefer_dex": "aerodrome",
    "run_interval_seconds": 3600,
    "max_positions": 10
  }
}
```

## Commands

| Command | Description |
|---------|-------------|
| `run` | Execute LP based on config mode |
| `discover --blocks N` | Scan last N blocks for new pools |
| `watch --interval N` | Real-time watch + auto-LP new pools |
| `watch --no-auto` | Detect new pools only (no auto-LP) |
| `batch --wallets file.json` | Run LP across multiple wallets |
| `positions` | Check active LP positions |
| `mode <auto\|manual>` | Switch mode in config |
| `show` | Display current config |

## Supported Tokens (30+)

**Major:** WETH, USDC, USDbC, DAI, cbETH
**DeFi:** AERO, WELL, SEAM, VIRTUAL, COMP, UNI
**Meme:** BRETT, TOSHI, DEGEN, TYBG, NORMIE, BENJI, BALD, PEPE, MOCHI, MFER, DOGINME, CHAD, MICHI, ROCK, HIGHER, KEYCAT, ANDY, MUMU, TOBY, MIGGLES, NPC

## Supported DEXs

| DEX | Type | Router |
|-----|------|--------|
| Uniswap V3 | Concentrated liquidity | `0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1` |
| Aerodrome | Stable/Volatile pools | `0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43` |

## Architecture

```
lp_agent.py          - CLI + auto/manual/discover/watch logic
config.json          - All configuration
wallet.env           - Private key (git-ignored)
core/
  wallet.py          - Wallet management
  tokens.py          - Token registry + ERC-20
  gas.py             - EIP-1559 gas estimation
  pool_scanner.py    - On-chain event scanner
  watcher.py         - Real-time pool watcher + auto-LP
dex/
  uniswap_v3.py      - Uniswap V3 position manager
  aerodrome.py       - Aerodrome router wrapper
  base_dex.py        - Abstract DEX interface
utils/
  approvals.py       - ERC-20 approval management
  formatting.py      - Amount formatting
  logging.py         - Structured logging
```

## Auto-Discover Flow

```
watch command:
  1. Monitor V3 Factory PoolCreated events
  2. Monitor Aerodrome Factory events
  3. Filter pools with known Base tokens
  4. Auto-add LP to new pools (0.005 ETH per pool)
  5. Track seen pools in /tmp/kaori_seen_pools.json
  6. V4 ready (placeholder for Initialize events)
```

## Risk Disclaimer

This tool interacts with DeFi protocols. Use at your own risk. Test with small amounts first.
