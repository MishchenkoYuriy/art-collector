import logging
from pathlib import Path
from urllib.parse import urlparse

import requests


class Helper:
    def __init__(self) -> None:
        self.save_dir = Path("temp")
        self.SIZE_LIMIT_MB = 10
        self.SIZE_LIMIT_BYTES = self.SIZE_LIMIT_MB * 1024 * 1024

        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s]{%(filename)s:%(lineno)d}%(levelname)s - %(message)s",
            filename="logs/helper.log",
        )
        self.logger = logging.getLogger(__name__)

    def download_from_urls(self, urls: list[str]) -> None:
        for url in urls:
            try:
                resp = requests.get(url, stream=True, timeout=10)
                resp.raise_for_status()

                file_size: str | None = resp.headers.get("content-length", None)
                if file_size and int(file_size) > self.SIZE_LIMIT_BYTES:
                    size_in_mb = round(int(file_size) / (1024 * 1024), 2)
                    self.logger.warning(
                        f"The file {url} exceeded the {self.SIZE_LIMIT_MB} MB limit. "
                        f"The file size is {size_in_mb} MB. Skipping..."
                    )
                    continue

                filename = Path(urlparse(url).path).name
                full_local_path = self.save_dir / filename

                with full_local_path.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

            except requests.exceptions.RequestException as e:
                self.logger.warning(
                    f"Failed to download {url}. Error: {e}. Skipping...\n"
                )
