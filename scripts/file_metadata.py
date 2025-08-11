import logging
import os
import re
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
            filename="logs/helper.log",
        )
        self.logger = logging.getLogger(__name__)

    def populate_file_metadata(
        self, raw_content: str, author: str
    ) -> FileMetadata | None:
        srcset_match = re.search(r'srcset="([^"]+)"', raw_content)
        if srcset_match:
            srcset_content = srcset_match.group(1)
            image_candidates = srcset_content.split(",")

            highest_res_url: str | None = None
            max_width: int = 0

            pattern = re.compile(r"\s*(https?://[^\s]+)\s+([0-9]+)w\s*")

            for candidate in image_candidates:
                match = pattern.match(candidate)
                if match:
                    url = match.group(1)
                    width = int(match.group(2))

                    if width > max_width:
                        max_width = width
                        highest_res_url = url

            if highest_res_url is None:
                return None

            filename = Path(f"{author}_{Path(highest_res_url).name}")
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
                    f"Could not determine file size for {highest_res_url}. "
                    f"Content-Length header is missing. Skipping..."
                )
                return None

            return FileMetadata(
                url=highest_res_url,
                author=author,
                local_path=local_path,
                upload_path=upload_path,
                size=file_size,
            )

        return None
