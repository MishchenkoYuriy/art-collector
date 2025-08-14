import logging
from pathlib import Path

import requests
from config import settings
from pydantic import BaseModel, HttpUrl, PositiveInt


class FileMetadata(BaseModel):
    url: HttpUrl
    etag: str | None
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

    def _create_filename(
        self, author: str, post_slug: str, numeric_suffix: int | None, file_format: str
    ) -> str:
        suffix = f"_{numeric_suffix}" if numeric_suffix else ""
        return f"{author}_{post_slug}{suffix}{file_format}"

    def create_file_metadata(
        self, url: HttpUrl, author: str, post_slug: str, numeric_suffix: int | None
    ) -> FileMetadata | None:
        filename = self._create_filename(
            author=author,
            post_slug=post_slug,
            numeric_suffix=numeric_suffix,
            file_format=Path(str(url)).suffix,  # includes a dot
        )
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
            local_path=local_path,
            mega_path=mega_path,
            size=file_size,
        )
