""" API-key authenticatie voor de dashboard-API zelf.

Agents gebruiken ook een API-key — dat wordt afgehandeld in agent_client.py.
Hier beveiligen we de central-dashboard endpoints.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from ..config import API_KEY_HEADER, DASHBOARD_API_KEY

api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


async def verify_api_key(api_key: str = Depends(api_key_header)) -> str:
    """Dependency die checkt of de dashboard API-key klopt."""
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API-key ontbreekt",
        )
    if api_key != DASHBOARD_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ongeldige API-key",
        )
    return api_key
