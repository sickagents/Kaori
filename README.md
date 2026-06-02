# Base LP Agent

Automated liquidity pool management agent for **Base network**. Supports Uniswap V3 and Aerodrome DEX.

## Features

- **Multi-DEX support**: Uniswap V3 (concentrated liquidity) and Aerodrome (stable/volatile pools)
- **Auto token approval**: Handles ERC-20 approvals with minimal gas
- **Configurable parameters**: Slippage, fee tier, tick range, deadline
- **Pool discovery**: Auto-find best pools for token pairs
- **Position monitoring**: Track active LP positions and their PnL
- **Multi-wallet**: Rotate through multiple wallets for parallel LP positions
- **Gas optimization**: EIP-1559 gas estimation on Base

## Supported DEXs

| DEX | Router | Type |
|-----|--------|------|
| Uniswap V3 | `0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1` | Concentrated liquidity (NFT positions) |
| Aerodrome | `0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43` | Stable/Volatile pools (ve(3,3)) |

## Common Tokens (Base)

| Token | Address | Decimals |
|-------|---------|----------|
| WETH | `0x4200000000000000000000000000000000000006` | 18 |
| USDC | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` | 6 |
| USDbC | `0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA` | 6 |
| DAI | `0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb` | 18 |
| cbETH | `0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22` | 18 |
| AERO | `0x940181a94A35A4569E4529A3CDfB74e38FD98631` | 18 |

## Usage

```bash
# Single LP add (Uniswap V3)
python3 lp_agent.py add \
  --dex uniswap \
  --token0 0x4200000000000000000000000000000000000006 \
  --token1 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 \
  --amount0 0.01 \
  --amount1 35 \
  --fee 500

# Single LP add (Aerodrome)
python3 lp_agent.py add \
  --dex aerodrome \
  --token0 0x4200000000000000000000000000000000000006 \
  --token1 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 \
  --amount0 0.01 \
  --amount1 35 \
  --stable false

# Auto-LP: find best pool and add
python3 lp_agent.py auto \
  --token0 WETH \
  --token1 USDC \
  --amount0 0.01 \
  --amount1 35

# Check positions
python3 lp_agent.py positions

# Remove liquidity
python3 lp_agent.py remove --position-id 12345 --percent 100

# Multi-wallet batch LP
python3 lp_agent.py batch \
  --wallets ~/.hermes/credentials/wallet-keys-evm-tuyul.json \
  --dex aerodrome \
  --token0 WETH --token1 USDC \
  --amount0 0.005 --amount1 17
```

## Configuration

Default config in `config.yaml`:
```yaml
rpc: https://mainnet.base.org
chain_id: 8453
slippage: 0.5  # percent
deadline: 600   # seconds
gas_multiplier: 1.2
```

## Architecture

```
lp_agent.py          - CLI entry point
core/
  wallet.py          - Wallet management (single + multi)
  tokens.py          - Token registry and ERC-20 helpers
  gas.py             - EIP-1559 gas estimation
dex/
  uniswap_v3.py      - Uniswap V3 position manager
  aerodrome.py       - Aerodrome router wrapper
  base_dex.py        - Abstract DEX interface
utils/
  approvals.py       - ERC-20 approval management
  formatting.py      - Amount formatting, tick math
  logging.py         - Structured logging
```

## Requirements

- Python 3.10+
- web3>=7.0
- eth-account

## Risk Disclaimer

This tool interacts with DeFi protocols and manages real funds. Use at your own risk. Always test with small amounts first. The authors are not responsible for any financial losses.
