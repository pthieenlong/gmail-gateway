import hashlib
import os
from pathlib import Path

import aiofiles

from app.config import settings

ALLOWED_EXTENSIONS = {
    ".pdf", ".zip", ".docx", ".xlsx",
    ".csv", ".txt", ".png", ".jpg", ".jpeg",
}


class AttachmentStorageService:
    def __init__(self):
        self.root = Path(settings.STORAGE_PATH)
        self.root.mkdir(parents=True, exist_ok=True)

    def is_allowed(self, filename: str) -> bool:
        return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS

    async def save(self, email_id: int, filename: str, content: bytes) -> dict:
        safe_name = self._safe_filename(filename)
        email_dir = self.root / f"email_{email_id}"
        email_dir.mkdir(parents=True, exist_ok=True)

        filepath = email_dir / safe_name
        # Avoid overwriting existing files
        counter = 1
        while filepath.exists():
            stem, suffix = Path(safe_name).stem, Path(safe_name).suffix
            filepath = email_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        async with aiofiles.open(filepath, "wb") as f:
            await f.write(content)

        return {
            "filepath": str(filepath),
            "filename": filepath.name,
            "file_size": len(content),
            "checksum": hashlib.sha256(content).hexdigest(),
        }

    @staticmethod
    def _safe_filename(filename: str) -> str:
        name = os.path.basename(filename)
        for bad in ["\0", ".."]:
            name = name.replace(bad, "_")
        return name or "attachment"
