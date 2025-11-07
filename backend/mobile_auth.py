"""
Mobile Authentication Module for DiaryML
JWT-based authentication for mobile app access with secure token management
"""

from datetime import datetime, timedelta
from typing import Optional
import secrets
import hashlib
from pathlib import Path
import json

try:
    from jose import JWTError, jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False
    print("⚠ WARNING: python-jose not installed - mobile auth will not work!")
    print("  Install with: pip install python-jose[cryptography]")

from pydantic import BaseModel


# Configuration
CONFIG_DIR = Path(__file__).parent.parent
SECRET_KEY_FILE = CONFIG_DIR / ".mobile_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30  # 30 days for mobile convenience


class Token(BaseModel):
    """JWT Token response"""
    access_token: str
    token_type: str
    expires_in: int


class TokenData(BaseModel):
    """JWT Token payload data"""
    password_hash: Optional[str] = None
    created_at: Optional[str] = None


class MobileAuthError(Exception):
    """Mobile authentication error"""
    pass


def _get_or_create_secret_key() -> str:
    """
    Get or create a persistent secret key for JWT signing

    Returns:
        Secret key string
    """
    if SECRET_KEY_FILE.exists():
        return SECRET_KEY_FILE.read_text().strip()

    # Generate new secret key
    secret_key = secrets.token_urlsafe(32)
    SECRET_KEY_FILE.write_text(secret_key)

    # Make it read-only
    SECRET_KEY_FILE.chmod(0o600)

    print(f"✓ Created new mobile authentication secret key")
    return secret_key


def create_access_token(password: str, expires_delta: Optional[timedelta] = None) -> Token:
    """
    Create JWT access token for mobile authentication

    Args:
        password: The diary password (will be hashed in token)
        expires_delta: Token expiration time (default: 30 days)

    Returns:
        Token object with access_token and metadata

    Raises:
        MobileAuthError: If JWT library not available
    """
    if not HAS_JWT:
        raise MobileAuthError("JWT library not available - install python-jose[cryptography]")

    if expires_delta is None:
        expires_delta = timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)

    expire = datetime.utcnow() + expires_delta

    # Hash the password for the token payload (never store plaintext)
    password_hash = hashlib.sha256(password.encode()).hexdigest()

    to_encode = {
        "password_hash": password_hash,
        "created_at": datetime.utcnow().isoformat(),
        "exp": expire,
        "iat": datetime.utcnow()
    }

    secret_key = _get_or_create_secret_key()
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)

    return Token(
        access_token=encoded_jwt,
        token_type="bearer",
        expires_in=int(expires_delta.total_seconds())
    )


def verify_token(token: str) -> Optional[str]:
    """
    Verify JWT token and extract password hash

    Args:
        token: JWT token string

    Returns:
        Password hash if valid, None if invalid

    Raises:
        MobileAuthError: If JWT library not available
    """
    if not HAS_JWT:
        raise MobileAuthError("JWT library not available - install python-jose[cryptography]")

    try:
        secret_key = _get_or_create_secret_key()
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])

        password_hash: str = payload.get("password_hash")
        if password_hash is None:
            return None

        return password_hash

    except JWTError as e:
        print(f"Token verification failed: {e}")
        return None


def hash_password(password: str) -> str:
    """
    Hash a password for comparison

    Args:
        password: Plain text password

    Returns:
        SHA256 hash of password
    """
    return hashlib.sha256(password.encode()).hexdigest()


def extract_password_from_token(token: str) -> Optional[str]:
    """
    Extract password hash from token without full verification
    (used for database unlock after token validation)

    Args:
        token: JWT token string

    Returns:
        Password hash if token is structurally valid, None otherwise
    """
    if not HAS_JWT:
        return None

    try:
        # Don't verify signature, just decode
        secret_key = _get_or_create_secret_key()
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[ALGORITHM],
            options={"verify_signature": True, "verify_exp": True}
        )

        return payload.get("password_hash")

    except JWTError:
        return None
