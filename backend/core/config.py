"""BIAR Protocol - Central configuration with security-first defaults."""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings. All values overridable via environment."""

    APP_NAME: str = "BIAR Protocol"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./biar.db")

    # CORS - restrict in production. Never use "*" with credentials.
    CORS_ORIGINS: list = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if o.strip()
    ]

    # Chain / contracts
    CHAIN_ID: int = int(os.getenv("CHAIN_ID", "11155111"))  # Sepolia
    CONTRACT_ADDRESS: str = os.getenv("CONTRACT_ADDRESS", "")
    RPC_URL: str = os.getenv("RPC_URL", "")
    ORACLE_ADDRESS: str = os.getenv("ORACLE_ADDRESS", "")

    # AMM parameters
    LMSR_LIQUIDITY_B: float = float(os.getenv("LMSR_LIQUIDITY_B", "200"))  # liquidity param
    MAX_TRADE_AMOUNT: float = float(os.getenv("MAX_TRADE_AMOUNT", "100000"))
    MIN_TRADE_AMOUNT: float = float(os.getenv("MIN_TRADE_AMOUNT", "0.01"))
    MAX_SLIPPAGE: float = float(os.getenv("MAX_SLIPPAGE", "0.25"))  # 25% hard cap

    # Rate limiting (requests per window per IP)
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

    # Market limits
    MAX_OUTCOMES: int = int(os.getenv("MAX_OUTCOMES", "8"))
    MAX_TITLE_LENGTH: int = 200
    MAX_DESCRIPTION_LENGTH: int = 2000

    # Cache TTLs (seconds)
    CACHE_TTL_MARKETS: int = 5
    CACHE_TTL_ORDERBOOK: int = 2
    CACHE_TTL_STATS: int = 10

    # Auth (SIWE-style wallet sign-in + JWT sessions)
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_SECONDS: int = int(os.getenv("JWT_EXPIRY_SECONDS", str(24 * 3600)))
    NONCE_TTL_SECONDS: int = int(os.getenv("NONCE_TTL_SECONDS", "300"))
    AUTH_REQUIRED: bool = os.getenv("AUTH_REQUIRED", "false").lower() == "true"


settings = Settings()