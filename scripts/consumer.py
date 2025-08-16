import logging
import queue

from config import settings
from file_metadata import FileMetadata
from helper import Helper
from mega import MegaSaver


class Consumer:
    def __init__(self) -> None:
        self.mega = MegaSaver()
        self.helper = Helper()
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s]{%(filename)s:%(lineno)d}%(levelname)s - %(message)s",
            filename="logs/art_collector.log",
        )
        self.logger = logging.getLogger(__name__)

    def consumer_worker(self, file_queue: queue.Queue[FileMetadata | None]) -> None:
        while True:
            file: FileMetadata | None = file_queue.get()
            if file is None:
                break

            try:
                if file.size > settings.LOCAL_FILE_SIZE_LIMIT_BYTES:
                    size_in_mb = self.helper.convert_bytes_to_mb(file.size)
                    self.logger.warning(
                        f"The file {file.url} exceeded the "
                        f"{settings.LOCAL_FILE_SIZE_LIMIT_MB} MB limit. "
                        f"The file size is {size_in_mb} MB. Skipping..."
                    )
                    continue

                if file.local_path.exists():
                    self.logger.info(f"{file.local_path} already exists. Skipping...")
                    continue

                mega_folder_size = self.mega.get_mega_folder_size()
                if mega_folder_size + file.size > settings.MEGA_FOLDER_SIZE_LIMIT_BYTES:
                    size_in_mb = self.helper.convert_bytes_to_mb(file.size)
                    self.logger.warning(
                        f"Adding file {file.url} ({size_in_mb} MB) would "
                        "exceed folder size limit of "
                        f"{settings.MEGA_FOLDER_SIZE_LIMIT_MB} MB."
                    )
                    continue

                self.logger.info(f"Processing {file.url}...")
                self.helper.download_file(file)
                self.mega.upload_local_file(file)
                self.helper.delete_local_file(file)

            except Exception:
                self.logger.exception(f"Failed to process {file.url}")

            finally:
                file_queue.task_done()
