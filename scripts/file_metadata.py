import logging
from pathlib import Path

import requests
from config import settings
from pydantic import BaseModel, HttpUrl, PositiveInt


class FileMetadata(BaseModel):
    url: HttpUrl
    etag: str | None
    author: str
    local_path: Path
    mega_path: Path
    size: PositiveInt  # in bytes


class FileMetadataHelper:
    def __init__(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s]{%(filename)s:%(lineno)d}%(levelname)s - %(message)s",
            filename="logs/art_collector.log",
        )
        self.logger = logging.getLogger(__name__)

    def create_file_metadata(self, url: HttpUrl, author: str) -> FileMetadata | None:
        filename = Path(f"{author}_{Path(str(url)).name}")
        if settings.SAVE_TO_MEGA:
            local_path = settings.LOCAL_TEMP_UPLOAD_DIR / filename
        else:
            local_path = settings.LOCAL_UPLOAD_PATH / filename
        mega_path = settings.MEGA_UPLOAD_PATH / filename

        resp = requests.head(str(url), timeout=10)
        resp.raise_for_status()

        etag: str | None = (
            resp.headers["ETag"].strip('"') if resp.headers.get("ETag", None) else None
        )

        if etag is None:
            self.logger.info(f"ETag is missing for {url}")

        file_size: int | None = (
            int(resp.headers["content-length"])
            if resp.headers.get("content-length", None)
            else None
        )

        if file_size is None:
            self.logger.warning(
                f"Could not determine file size for {url}. "
                f"Content-Length header is missing. Skipping..."
            )
            return None

        return FileMetadata(
            url=url,
            etag=etag,
            author=author,
            local_path=local_path,
            mega_path=mega_path,
            size=file_size,
        )
