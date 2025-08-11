import logging
import os
from dataclasses import dataclass
from pathlib import Path

import requests


@dataclass
class FileMetadata:
    url: str
    author: str
    local_path: Path
    upload_path: Path
    size: int  # in bytes
    # TODO: resolution: str


class FileMetadataHelper:
    def __init__(self) -> None:
        self.save_dir = Path("temp")
        path_from_env: str | None = os.getenv("MEGA_UPLOAD_PATH")
        if path_from_env:
            self.upload_path = Path(path_from_env.rstrip("/"))
        else:
            self.upload_path = Path("art_collector")
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s]{%(filename)s:%(lineno)d}%(levelname)s - %(message)s",
            filename="logs/file_metadata.log",
        )
        self.logger = logging.getLogger(__name__)

    def populate_file_metadata(self, url: str, author: str) -> FileMetadata | None:
        filename = Path(f"{author}_{Path(url).name}")
        local_path = self.save_dir / filename
        upload_path = self.upload_path / filename

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
            upload_path=upload_path,
            size=file_size,
        )
