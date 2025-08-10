import datetime
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import requests


@dataclass
class ImageMetadata:
    url: str
    author: str


class Helper:
    def __init__(self) -> None:
        self.save_dir = Path("temp")
        self.config_file = Path(__file__).resolve().parent.parent / "config.json"
        self.SIZE_LIMIT_MB = 10
        self.SIZE_LIMIT_BYTES = self.SIZE_LIMIT_MB * 1024 * 1024

        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s]{%(filename)s:%(lineno)d}%(levelname)s - %(message)s",
            filename="logs/helper.log",
        )
        self.logger = logging.getLogger(__name__)

    def download_from_urls(self, image_metadata_list: list[ImageMetadata]) -> list[str]:
        local_paths: list[str] = []
        for image_meta in image_metadata_list:
            try:
                resp = requests.get(image_meta.url, stream=True, timeout=10)
                resp.raise_for_status()

                file_size: str | None = resp.headers.get("content-length", None)
                if file_size and int(file_size) > self.SIZE_LIMIT_BYTES:
                    size_in_mb = round(int(file_size) / (1024 * 1024), 2)
                    self.logger.warning(
                        f"The file {image_meta.url} exceeded the "
                        f"{self.SIZE_LIMIT_MB} MB limit. "
                        f"The file size is {size_in_mb} MB. Skipping..."
                    )
                    continue

                filename = self.get_filename_with_author(
                    image_meta.url, image_meta.author
                )
                full_local_path = self.save_dir / filename
                local_paths.append(str(full_local_path))

                with full_local_path.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

            except requests.exceptions.RequestException as e:
                self.logger.warning(
                    f"Failed to download {image_meta.url}. Error: {e}. Skipping...\n"
                )

        return local_paths

    def get_filename_with_author(self, url: str, author: str) -> str:
        original_filename = Path(url).name
        # Prepend author name to filename
        return f"{author}_{original_filename}"

    def get_filename(self, url: str) -> str:
        return Path(url).name

    def clean_temp_directory(self) -> None:
        for file_path in self.save_dir.iterdir():
            if file_path.name == ".gitkeep":
                continue

            if file_path.is_file():
                file_path.unlink()

    def get_last_runtime_in_unix(self) -> int:
        json_content = self.config_file.read_text()
        config_data: dict[str, str] = json.loads(json_content)
        last_runtime = datetime.datetime.fromisoformat(config_data["last_runtime"])
        return int(last_runtime.timestamp())

    def save_runtime_config(self, followed_blogs: list[str]) -> None:
        config_data = {
            "last_runtime": datetime.datetime.now(datetime.UTC).isoformat(),
            "current_tumblr_blogs": followed_blogs
        }
        json_content = json.dumps(config_data, indent=2)
        self.config_file.write_text(json_content)

    def get_current_tumblr_blogs(self) -> list[str]:
        json_content = self.config_file.read_text()
        config_data: dict[str, str] = json.loads(json_content)
        return config_data["current_tumblr_blogs"]
