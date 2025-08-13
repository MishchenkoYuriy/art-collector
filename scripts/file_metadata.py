import logging
import os
from pathlib import Path

import requests
from pydantic import BaseModel, HttpUrl, PositiveInt


class FileMetadata(BaseModel):
    url: HttpUrl
    author: str
    local_path: Path
    mega_path: Path
    size: PositiveInt  # in bytes


class FileMetadataHelper:
    def __init__(self) -> None:
        self.local_upload_path = Path(os.getenv("LOCAL_UPLOAD_PATH") or "temp")
        self.local_temp_upload_dir = Path("temp")
        self.mega_upload_path = Path(os.getenv("MEGA_UPLOAD_PATH", ""))
        self.SAVE_TO_MEGA = os.getenv("SAVE_TO_MEGA", "True") == "True"
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s]{%(filename)s:%(lineno)d}%(levelname)s - %(message)s",
            filename="logs/art_collector.log",
        )
        self.logger = logging.getLogger(__name__)

    def populate_file_metadata(self, url: HttpUrl, author: str) -> FileMetadata | None:
        filename = Path(f"{author}_{Path(str(url)).name}")
        if self.SAVE_TO_MEGA:
            local_path = self.local_temp_upload_dir / filename
        else:
            local_path = self.local_upload_path / filename
        mega_path = self.mega_upload_path / filename

        resp = requests.head(url, timeout=10)
        resp.raise_for_status()
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
            author=author,
            local_path=local_path,
            mega_path=mega_path,
            size=file_size,
        )
