import logging
import queue

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
            file_meta: FileMetadata | None = file_queue.get()
            if file_meta is None:
                break

            try:
                self.logger.info(f"Processing {file_meta.url}...")
                self.helper.download_file(file_meta)
                self.mega.upload_local_file(file_meta)
                self.helper.delete_local_file(file_meta)

            except Exception:
                self.logger.exception(f"Failed to process {file_meta.url}")

            finally:
                file_queue.task_done()
