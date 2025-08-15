import logging
import queue
import re
from typing import Any

import requests
from config import settings
from file_metadata import FileMetadata, FileMetadataHelper
from helper import Helper
from pydantic import HttpUrl
from requests_oauthlib import OAuth1
from tumblr_enum import TumblrPostType

# https://www.tumblr.com/docs/en/api/v2
# https://api.tumblr.com/v2/user/info


class TumblrCollector:
    def __init__(self) -> None:
        self.tumblr_api_limit = 20
        self.url_pattern = re.compile(r"\s*(https?://[^\s]+)\s+([0-9]+)w\s*")
        self.helper = Helper()
        self.file_meta = FileMetadataHelper()
        self.oauth = OAuth1(
            client_key=settings.TUMBLR_CONSUMER_KEY,
            client_secret=settings.TUMBLR_CONSUMER_SECRET,
            resource_owner_key=settings.TUMBLR_OAUTH_TOKEN,
            resource_owner_secret=settings.TUMBLR_OAUTH_SECRET,
        )
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s]{%(filename)s:%(lineno)d}%(levelname)s - %(message)s",
            filename="logs/art_collector.log",
        )
        self.logger = logging.getLogger(__name__)

    def get_current_user_followed_blog_cnt(self) -> int:
        resp = requests.get(
            "https://api.tumblr.com/v2/user/info", auth=self.oauth, timeout=10
        )
        return int(resp.json()["response"]["user"]["following"])

    def get_followed_blogs(self) -> set[str]:
        self.logger.info("Start extracting followed blogs...")

        followed_blog_names: set[str] = set()
        page_blog_names: set[str] = set()
        offset = 0

        while True:
            resp = requests.get(
                "https://api.tumblr.com/v2/user/following",
                auth=self.oauth,
                timeout=10,
                params={"offset": offset, "limit": self.tumblr_api_limit},
            )
            page_followed_blogs = resp.json()["response"]["blogs"]
            page_blog_names = {blog["name"] for blog in page_followed_blogs}
            followed_blog_names.update(page_blog_names)

            if len(page_blog_names) < self.tumblr_api_limit:  # while "page" is full
                break

            offset += self.tumblr_api_limit

        followed_blog_cnt = self.get_current_user_followed_blog_cnt()
        self.logger.info(f"{len(followed_blog_names)} blogs have been extracted.")
        if followed_blog_cnt != len(followed_blog_names):
            self.logger.warning(
                "The number of followed blogs from the API does not match, "
                f"{followed_blog_cnt} from the account info, "
                f"{len(followed_blog_names)} from over iterating over following."
            )

        return self._filter_blogs(followed_blog_names)

    def _filter_blogs(self, blogs: set[str]) -> set[str]:
        if settings.TUMBLR_BLOGS_TO_CRAWL == {"all"}:  # noqa: SIM300
            blogs_to_crawl = blogs
        else:
            blogs_to_crawl = blogs.intersection(settings.TUMBLR_BLOGS_TO_CRAWL)

        filtered_blogs = blogs_to_crawl.difference(settings.TUMBLR_BLOGS_TO_IGNORE)
        self.logger.info(
            "The blog filters were applied. "
            f"{len(filtered_blogs)} blogs will be processed."
        )
        return filtered_blogs

    def produce_files_from_blogs(
        self, blog_names: set[str], file_queue: queue.Queue[FileMetadata | None]
    ) -> None:
        self.logger.info("Start extracting files...")
        # url or etag as a key handles duplicates from different posts
        processed_keys: dict[str, set[str]] = {
            blog_name: set() for blog_name in blog_names
        }
        previous_tumblr_blogs = self.helper.get_previous_run_tumblr_blogs()
        is_first_run = len(previous_tumblr_blogs) == 0
        if is_first_run:
            self.logger.info(
                "The first run detected. "
                "`last_runtime` form `config.json` will be ignored."
            )

        for blog_name in blog_names:
            self._add_blog_files(
                file_queue=file_queue,
                processed_keys=processed_keys,
                blog_name=blog_name,
                is_first_run=is_first_run,
                previous_tumblr_blogs=previous_tumblr_blogs,
            )

        self.logger.info("All files have been produced.")

    def _add_blog_files(
        self,
        file_queue: queue.Queue[FileMetadata | None],
        processed_keys: dict[str, set[str]],
        blog_name: str,
        is_first_run: bool,
        previous_tumblr_blogs: list[str],
    ) -> None:
        offset = 0
        is_new_blog = blog_name not in previous_tumblr_blogs
        if is_new_blog and not is_first_run:
            self.logger.info(
                f"{blog_name} is a new blog. "
                "`last_runtime` form `config.json` will be ignored for it."
            )

        while len(processed_keys[blog_name]) < settings.TUMBLR_FILE_LIMIT_PER_BLOG:
            params = {"limit": self.tumblr_api_limit, "offset": offset}

            if is_first_run or is_new_blog:
                # Don't use 'after' parameter for the first run or new blogs
                pass
            else:
                last_runtime = self.helper.get_last_runtime_in_unix()
                params["after"] = last_runtime

            resp = requests.get(
                f"https://api.tumblr.com/v2/blog/{blog_name}.tumblr.com/posts",
                auth=self.oauth,
                params=params,
                timeout=10,
            )
            posts = resp.json()["response"]["posts"]

            if not posts:
                self.logger.warning(
                    f"The end of the blog {blog_name} has been reached."
                )
                break

            for post in posts:
                is_repost = "parent_post_url" in post
                if is_repost:
                    continue

                match post["type"]:
                    case TumblrPostType.TEXT.value:
                        self._add_files_from_text_post(
                            file_queue=file_queue,
                            processed_keys=processed_keys,
                            post_html=post,
                            blog_name=blog_name,
                        )

                    case TumblrPostType.PHOTO.value:
                        self._add_files_from_photo_post(
                            file_queue=file_queue,
                            processed_keys=processed_keys,
                            post_html=post,
                            blog_name=blog_name,
                        )

                    case TumblrPostType.ANSWER.value:
                        continue  # /posts does not support filtering by multiple types

                    case _:
                        self.logger.info(f"Not supported post type: {post['type']}.")

            if len(posts) < self.tumblr_api_limit:
                self.logger.warning(
                    f"The end of the blog {blog_name} has been reached."
                )
                break

            offset += self.tumblr_api_limit

    def _add_file(
        self,
        file_queue: queue.Queue[FileMetadata | None],
        processed_keys: dict[str, set[str]],
        file: FileMetadata | None,
        blog_name: str,
    ) -> None:
        blog_file_cnt = len(processed_keys[blog_name])
        if blog_file_cnt < settings.TUMBLR_FILE_LIMIT_PER_BLOG and file:
            file_key = file.etag if file.etag else file.url
            if file_key in processed_keys[blog_name]:
                self.logger.info(f"A duplicate found, key: {file_key}. Skipping...")
            else:
                processed_keys[blog_name].add(file_key)
                file_queue.put(file)

    def _add_files_from_text_post(
        self,
        file_queue: queue.Queue[FileMetadata | None],
        processed_keys: dict[str, set[str]],
        post_html: dict[str, Any],
        blog_name: str,
    ) -> None:
        content_raw: str = post_html["trail"][0]["content_raw"]
        post_slug: str | None = post_html["slug"]

        # Split content_raw as a post can have multiple images/gifs
        srcset_matches = re.findall(r'srcset="([^"]+)"', content_raw)
        if srcset_matches:
            # If the post has more than one image/gif,
            # use numeric_suffix to distinguish them
            numeric_suffix = 1 if len(srcset_matches) > 1 else None
            for srcset_content in srcset_matches:
                file_candidates = srcset_content.split(",")
                # Get the file with the highest resolution
                last_candidate_url = HttpUrl(file_candidates[-1].split()[0])

                file = self.file_meta.create_file_metadata(
                    url=last_candidate_url,
                    author=blog_name,
                    post_slug=post_slug,
                    numeric_suffix=numeric_suffix,
                )
                self._add_file(file_queue, processed_keys, file, blog_name)
                if numeric_suffix is not None:
                    numeric_suffix += 1

        # Some text blogs have videos
        if settings.TUMBLR_COLLECT_VIDEOS:
            srcset_matches = re.findall(r'<source src="([^"]+)"', content_raw)
            if srcset_matches:
                numeric_suffix = 1 if len(srcset_matches) > 1 else None
                for video_url in srcset_matches:
                    file = self.file_meta.create_file_metadata(
                        url=video_url,
                        author=blog_name,
                        post_slug=post_slug,
                        numeric_suffix=numeric_suffix,
                    )
                    self._add_file(file_queue, processed_keys, file, blog_name)
                    if numeric_suffix is not None:
                        numeric_suffix += 1

    def _add_files_from_photo_post(
        self,
        file_queue: queue.Queue[FileMetadata | None],
        processed_keys: dict[str, set[str]],
        post_html: dict[str, Any],
        blog_name: str,
    ) -> None:
        # Get the photo with the highest resolution
        url: str = post_html["photos"][0]["original_size"]["url"]
        post_slug: str | None = post_html["slug"]

        file = self.file_meta.create_file_metadata(
            url=url,
            author=blog_name,
            post_slug=post_slug,
            numeric_suffix=None,  # a single photo does not require numbering
        )
        self._add_file(file_queue, processed_keys, file, blog_name)
