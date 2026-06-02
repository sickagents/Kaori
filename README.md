# Kaori

Automated Liquidity Pool agent for **Base network**. Supports Uniswap V3 and Aerodrome.

**Works with ALL tokens on Base** - no hardcoded token list. Tokens are resolved dynamically on-chain.

## Quick Start (Server)

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
| `run` | Execute LP based on config mode (auto/manual) |
| `discover --blocks N` | Scan last N blocks for new pools |
| `watch --interval N` | Real-time watch + auto-LP new pools |
| `watch --no-auto` | Detect new pools only |
| `batch --wallets file.json` | Run LP across multiple wallets |
| `positions` | Check active LP positions |
| `mode <auto\|manual>` | Switch mode |
| `show` | Show current config |

## How It Works

**Dynamic Token Resolution:**
- No hardcoded token list
- Tokens are resolved on-chain via ERC-20 `symbol()`, `decimals()`, `name()`
- Works with ANY token that has a pool on Uniswap V3 or Aerodrome
- Supports thousands to millions of tokens

**Pool Discovery:**
- Monitors `PoolCreated` events from Uniswap V3 Factory
- Monitors Aerodrome Factory events
- Resolves both tokens in each new pool on-chain
- Filters for pools with base tokens (WETH, USDC, etc.)

**Auto-LP:**
- Adds liquidity to new pools automatically
- Uses 5% of ETH balance per pool (max 0.005 ETH)
- Only targets pools with base/stable tokens
- Tracks seen pools to avoid duplicates

## Configuration (config.json)

```json
{
  "mode": "auto",
  "auto": {
    "pairs": [
      {"token0": "WETH", "token1": "USDC", "amount0": "0.01", "amount1": "35"},
      {"token0": "0x...", "token1": "USDC", "amount0": "100", "amount1": "100"}
    ]
  },
  "manual": {
    "dex": "aerodrome",
    "token0": "WETH",
    "token1": "0xSOME_TOKEN_ADDRESS",
    "amount0": "0.01",
    "amount1": "100"
  }
}
```

**Manual mode** accepts:
- Symbol: `"WETH"`, `"USDC"`, `"AERO"` (from base_tokens lookup)
- Address: `"0x532f27101965dd16442E59d40670FaF5eBB142E4"` (any ERC-20)

## Supported DEXs

| DEX | Type | Router |
|-----|------|--------|
| Uniswap V3 | Concentrated liquidity | `0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1` |
| Aerodrome | Stable/Volatile pools | `0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43` |

## Architecture

```
lp_agent.py          - CLI (run/discover/watch/batch/positions/mode/show)
config.json          - Configuration
wallet.env           - Private key (git-ignored)
core/
  wallet.py          - Wallet management
  tokens.py          - Dynamic on-chain token resolver (no hardcoded list)
  gas.py             - EIP-1559 gas estimation
  pool_scanner.py    - Event-driven pool discovery
  watcher.py         - Real-time watcher + auto-LP
dex/
  uniswap_v3.py      - Uniswap V3 position manager
  aerodrome.py       - Aerodrome router wrapper
  base_dex.py        - Abstract DEX interface
utils/
  approvals.py       - ERC-20 approval management
  formatting.py      - Amount formatting
  logging.py         - Structured logging
```

## Output Files

- `/tmp/kaori_seen_pools.json` - Tracked pool addresses
- `/tmp/kaori_discovered_pools.json` - All discovered pools with metadata
