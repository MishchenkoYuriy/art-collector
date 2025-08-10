import datetime
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

import requests


class ConfigData(TypedDict):
    last_runtime: str
    current_tumblr_blogs: list[str]


@dataclass
class ImageMetadata:
    url: str
    author: str


class Helper:
    def __init__(self) -> None:
        self.save_dir = Path("temp")
        self.config_file = Path(__file__).resolve().parent.parent / "config.json"
        self.FILE_SIZE_LIMIT_MB = int(os.getenv("LOCAL_FILE_SIZE_LIMIT_MB", "10"))
        self.FILE_SIZE_LIMIT_BYTES = self.FILE_SIZE_LIMIT_MB * 1024 * 1024
        self.FOLDER_SIZE_LIMIT_MB = int(os.getenv("LOCAL_FOLDER_SIZE_LIMIT_MB", "1000"))
        self.FOLDER_SIZE_LIMIT_BYTES = self.FOLDER_SIZE_LIMIT_MB * 1024 * 1024

        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s]{%(filename)s:%(lineno)d}%(levelname)s - %(message)s",
            filename="logs/helper.log",
        )
        self.logger = logging.getLogger(__name__)

    def download_from_urls(self, image_metadata_list: list[ImageMetadata]) -> list[str]:
        local_paths: list[str] = []
        local_folder_size = 0  # track folder size incrementally in bytes
        for image_meta in image_metadata_list:
            try:
                resp = requests.get(image_meta.url, stream=True, timeout=10)
                resp.raise_for_status()

                file_size: int | None = (
                    int(resp.headers["content-length"])
                    if resp.headers.get("content-length", None)
                    else None
                )
                if file_size is None:
                    self.logger.warning(
                        f"Could not determine file size for {image_meta.url}. "
                        f"Content-Length header is missing. Skipping..."
                    )
                    continue

                if file_size > self.FILE_SIZE_LIMIT_BYTES:
                    size_in_mb = self.convert_bytes_to_mb(file_size)
                    self.logger.warning(
                        f"The file {image_meta.url} exceeded the "
                        f"{self.FILE_SIZE_LIMIT_MB} MB limit. "
                        f"The file size is {size_in_mb} MB. Skipping..."
                    )
                    continue

                # Check if adding this file would exceed folder size limit
                if local_folder_size + file_size > self.FOLDER_SIZE_LIMIT_BYTES:
                    folder_size_mb = self.convert_bytes_to_mb(local_folder_size)
                    file_size_mb = self.convert_bytes_to_mb(file_size)
                    self.logger.warning(
                        f"Adding file {image_meta.url} ({file_size_mb} MB) would "
                        f"exceed the folder size limit of {self.FOLDER_SIZE_LIMIT_MB} "
                        f" MB. Current folder size: {folder_size_mb} MB."
                    )
                    break

                filename = self.get_filename_with_author(
                    image_meta.url, image_meta.author
                )
                full_local_path = self.save_dir / filename

                if full_local_path.exists():
                    self.logger.info("A copy is found. Skipping...")
                    continue

                local_paths.append(str(full_local_path))

                with full_local_path.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                local_folder_size += file_size

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
        config_data: ConfigData = json.loads(json_content)
        last_runtime = datetime.datetime.fromisoformat(config_data["last_runtime"])
        return int(last_runtime.timestamp())

    def save_runtime_config(self, followed_blogs: list[str]) -> None:
        config_data = {
            "last_runtime": datetime.datetime.now(datetime.UTC).isoformat(),
            "current_tumblr_blogs": followed_blogs,
        }
        json_content = json.dumps(config_data, indent=2)
        self.config_file.write_text(json_content)

    def get_current_tumblr_blogs(self) -> list[str]:
        json_content = self.config_file.read_text()
        config_data: ConfigData = json.loads(json_content)
        return config_data["current_tumblr_blogs"]

    def convert_bytes_to_mb(self, size_in_bytes: int) -> float:
        return round(size_in_bytes / (1024 * 1024), 2)
