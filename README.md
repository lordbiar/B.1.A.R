# BIAR Protocol - Decentralized Prediction Market

## Overview

BIAR Protocol is a full-stack, decentralized prediction market platform that enables users to trade on the outcome of future events. The protocol combines an Automated Market Maker (AMM) engine with blockchain-based settlement for trustless, transparent prediction markets.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Dashboard                        │
│           (React + Tailwind CSS + Chart.js)                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Backend API (FastAPI)                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │ AMM Engine  │  │ Market Mgmt  │  │ Oracle Integration  │ │
│  │  (LMSR/CP)  │  │   Service    │  │     Service         │ │
│  └─────────────┘  └──────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                Smart Contracts (Solidity)                    │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │   IBIARMarket.sol   │  │      IBIAROracle.sol        │   │
│  │  - Market Creation  │  │  - Price Resolution         │   │
│  │  - Liquidity Staking│  │  - Settlement Workflow      │   │
│  │  - Position Minting │  │                             │   │
│  │  - Payout Claims    │  │                             │   │
│  └─────────────────────┘  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Features

### Core Protocol Engine
- **Automated Market Maker (AMM)**: Implements Constant Product and LMSR models for dynamic pricing
- **Market Management**: Create binary and multi-outcome prediction markets
- **Order Processing**: Place orders for outcome tokens with slippage calculation
- **Oracle Integration**: Resolve markets via decentralized oracle feeds
- **Simulation Engine**: Test liquidity depth and odds recalculation

### Web Dashboard
- **Dark Mode Trading Interface**: Modern, responsive design
- **Real-time Charts**: Dynamic probability shifts and market sentiment
- **Interactive Order Modal**: Token swap estimates and slippage visualization
- **Market Categories**: Asset prices, macro indicators, governance proposals

### Smart Contracts
- **IBIARMarket**: Core market contract for position management
- **IBIAROracle**: Decentralized oracle for secure settlement

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- Solidity 0.8+
- Git

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn api.main:app --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Smart Contracts

```bash
cd contracts
# Install dependencies
npm install

# Compile contracts
npx hardhat compile

# Deploy to testnet
npx hardhat run scripts/deploy.js --network sepolia
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/markets` | Create a new prediction market |
| GET | `/api/v1/markets` | List all active markets |
| GET | `/api/v1/markets/{id}` | Get market details |
| POST | `/api/v1/markets/{id}/order` | Place an order |
| GET | `/api/v1/markets/{id}/orderbook` | Get market order book |
| POST | `/api/v1/markets/{id}/resolve` | Resolve market via oracle |
| GET | `/api/v1/simulation/slippage` | Calculate slippage |

## Configuration

### Environment Variables

Create a `.env` file in the backend directory:

```env
DATABASE_URL=sqlite:///./biar.db
ORACLE_API_KEY=your_oracle_api_key
CHAIN_ID=11155111
CONTRACT_ADDRESS=0x...
```

## Testing

```bash
# Backend tests
cd backend
pytest tests/

# Frontend tests
cd frontend
npm test

# Contract tests
cd contracts
npx hardhat test
```

## Deployment

The GitHub Actions workflow automatically deploys the frontend to GitHub Pages on every push to main:

```yaml
# .github/workflows/deploy.yml
```

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

---

**BIAR Protocol** - Building the future of decentralized prediction markets.
