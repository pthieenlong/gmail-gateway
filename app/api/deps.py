from fastapi import Header, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(x_api_key: str | None = Security(_api_key_header)) -> None:
    """
    Bảo vệ endpoint quản trị bằng API Key.

    - Nếu ADMIN_API_KEY chưa set trong .env → bỏ qua (dev mode).
    - Nếu đã set → client phải gửi header:  X-API-Key: <key>
    """
    if not settings.ADMIN_API_KEY:
        return  # dev mode — không enforce
    if x_api_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Send header: X-API-Key: <your-key>",
        )
