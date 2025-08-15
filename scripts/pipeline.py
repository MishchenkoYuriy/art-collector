import concurrent.futures
import queue
import time
from typing import TYPE_CHECKING

from config import settings
from consumer import Consumer
from helper import Helper
from mega import MegaSaver
from tumblr import TumblrCollector

if TYPE_CHECKING:
    from file_metadata import FileMetadata


def main() -> None:
    mega = MegaSaver()
    mega.login()  # the first step as auth code can expire

    file_queue: queue.Queue[FileMetadata | None] = queue.Queue(
        maxsize=settings.MAX_WORKERS * 2
    )
    tumblr = TumblrCollector()
    helper = Helper()
    consumer = Consumer()
    followed_blog_names = tumblr.get_followed_blogs()

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=settings.MAX_WORKERS + 1
    ) as executor:
        # Submitting consumer workers
        for _ in range(settings.MAX_WORKERS):
            executor.submit(consumer.consumer_worker, file_queue)

        # Submitting the producer
        producer_future = executor.submit(
            tumblr.produce_files_from_blogs, followed_blog_names, file_queue
        )

        producer_future.result()
        file_queue.join()

        for _ in range(settings.MAX_WORKERS):
            file_queue.put(None)

    helper.save_runtime_config(followed_blog_names)
    mega.logout()


if __name__ == "__main__":
    start_time = time.time()

    main()

    end_time = time.time()
    runtime_seconds = end_time - start_time
    print(f"Program runtime: {runtime_seconds:.2f} seconds")  # noqa: T201
