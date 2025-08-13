import datetime
import json
import logging
import os
from pathlib import Path
from typing import TypedDict

import requests
from file_metadata import FileMetadata


class ConfigData(TypedDict):
    last_runtime: str
    current_tumblr_blogs: list[str]


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
            filename="logs/art_collector.log",
        )
        self.logger = logging.getLogger(__name__)

    def download_files(self, files: list[FileMetadata]) -> None:
        local_folder_size = 0  # track folder size incrementally in bytes
        for file in files:
            try:
                resp = requests.get(str(file.url), stream=True, timeout=10)
                resp.raise_for_status()

                if file.size > self.FILE_SIZE_LIMIT_BYTES:
                    size_in_mb = self.convert_bytes_to_mb(file.size)
                    self.logger.warning(
                        f"The file {file.url} exceeded the "
                        f"{self.FILE_SIZE_LIMIT_MB} MB limit. "
                        f"The file size is {size_in_mb} MB. Skipping..."
                    )
                    continue

                # Check if adding this file would exceed folder size limit
                if local_folder_size + file.size > self.FOLDER_SIZE_LIMIT_BYTES:
                    folder_size_mb = self.convert_bytes_to_mb(local_folder_size)
                    size_in_mb = self.convert_bytes_to_mb(file.size)
                    self.logger.warning(
                        f"Adding file {file.url} ({size_in_mb} MB) would "
                        f"exceed the folder size limit of {self.FOLDER_SIZE_LIMIT_MB} "
                        f" MB. Current folder size: {folder_size_mb} MB."
                    )
                    break

                if file.local_path.exists():
                    self.logger.info("A copy is found. Skipping...")
                    continue

                with file.local_path.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                local_folder_size += file.size

            except requests.exceptions.RequestException as e:
                self.logger.warning(
                    f"Failed to download {file.url}. Error: {e}. Skipping...\n"
                )

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

    def get_previous_run_tumblr_blogs(self) -> list[str]:
        json_content = self.config_file.read_text()
        config_data: ConfigData = json.loads(json_content)
        return config_data["current_tumblr_blogs"]

    def save_runtime_config(self, followed_blogs: set[str]) -> None:
        config_data = {
            "last_runtime": datetime.datetime.now(datetime.UTC).isoformat(),
            "current_tumblr_blogs": list(followed_blogs),
        }
        json_content = json.dumps(config_data, indent=2)
        self.config_file.write_text(json_content)

    def convert_bytes_to_mb(self, size_in_bytes: int) -> float:
        return round(size_in_bytes / (1024 * 1024), 2)
