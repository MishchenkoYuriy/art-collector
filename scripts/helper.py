import datetime
import json
import logging
from typing import TypedDict

import requests
from config import settings
from file_metadata import FileMetadata


class ConfigData(TypedDict):
    last_runtime: str
    current_tumblr_blogs: list[str]


class Helper:
    def __init__(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s]{%(filename)s:%(lineno)d}%(levelname)s - %(message)s",
            filename="logs/art_collector.log",
        )
        self.logger = logging.getLogger(__name__)

    def download_file(self, file: FileMetadata) -> None:
        try:
            resp = requests.get(str(file.url), stream=True, timeout=10)
            resp.raise_for_status()

            with file.local_path.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

        except requests.exceptions.RequestException as e:
            self.logger.warning(
                f"Failed to download {file.url}. Error: {e}. Skipping...\n"
            )

    def delete_local_file(self, file: FileMetadata) -> None:
        if settings.SAVE_TO_MEGA and file.local_path.is_file():
            file.local_path.unlink()

    def clean_temp_directory(self) -> None:
        if settings.SAVE_TO_MEGA:
            for file_path in settings.LOCAL_TEMP_UPLOAD_DIR.iterdir():
                if file_path.name == ".gitkeep":
                    continue

                if file_path.is_file():
                    file_path.unlink()

    def get_last_runtime_in_unix(self) -> int:
        json_content = settings.CONFIG_FILE.read_text()
        config_data: ConfigData = json.loads(json_content)
        last_runtime = datetime.datetime.fromisoformat(config_data["last_runtime"])
        return int(last_runtime.timestamp())

    def get_previous_run_tumblr_blogs(self) -> list[str]:
        json_content = settings.CONFIG_FILE.read_text()
        config_data: ConfigData = json.loads(json_content)
        return config_data["current_tumblr_blogs"]

    def save_runtime_config(self, followed_blogs: set[str]) -> None:
        config_data = {
            "last_runtime": datetime.datetime.now(datetime.UTC).isoformat(),
            "current_tumblr_blogs": list(followed_blogs),
        }
        json_content = json.dumps(config_data, indent=2)
        settings.CONFIG_FILE.write_text(json_content)

    def convert_bytes_to_mb(self, size_in_bytes: int) -> float:
        return round(size_in_bytes / (1024 * 1024), 2)
