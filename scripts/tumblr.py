import logging
import os
import re
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from file_metadata import FileMetadata, FileMetadataHelper
from helper import Helper
from requests_oauthlib import OAuth1

# TODO: look into type, date, post_url attibutes of the post
# TODO: look into https://www.tumblr.com/docs/en/api/v2#postsdraft--retrieve-draft-posts
# TODO: look into https://www.tumblr.com/docs/en/api/v2#postsqueue--retrieve-queued-posts

# https://github.com/tumblr/pytumblr
# https://api.tumblr.com/v2/user/info


class TumblrCollector:
    def __init__(self) -> None:
        load_dotenv()
        self.config_file = Path(__file__).resolve().parent.parent / "config.json"
        self.FILE_LIMIT_PER_BLOG = int(os.getenv("TUMBLR_FILE_LIMIT", "50"))
        self.COLLECT_VIDEOS = bool(os.getenv("TUMBLR_COLLECT_VIDEOS", "False"))
        self.BLOGS_TO_CRAWL = set(os.getenv("TUMBLR_BLOGS_TO_CRAWL", "all").split(","))
        self.BLOGS_TO_IGNORE = (
            set(os.getenv("TUMBLR_BLOGS_TO_IGNORE", "").split(","))
            if os.getenv("TUMBLR_BLOGS_TO_IGNORE")
            else set()
        )
        self.helper = Helper()
        self.file_meta = FileMetadataHelper()
        self.oauth = OAuth1(
            client_key=os.getenv("TUMBLR_CONSUMER_KEY"),
            client_secret=os.getenv("TUMBLR_CONSUMER_SECRET"),
            resource_owner_key=os.getenv("TUMBLR_OAUTH_TOKEN"),
            resource_owner_secret=os.getenv("TUMBLR_OAUTH_SECRET"),
        )
        self.url_pattern = re.compile(r"\s*(https?://[^\s]+)\s+([0-9]+)w\s*")

        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s]{%(filename)s:%(lineno)d}%(levelname)s - %(message)s",
            filename="logs/tumblr.log",
        )
        self.logger = logging.getLogger(__name__)

    def get_followed_blogs(self) -> set[str]:
        resp = requests.get(
            "https://api.tumblr.com/v2/user/following", auth=self.oauth, timeout=10
        )
        followed_blogs = resp.json()["response"]["blogs"]
        followed_blog_names: set[str] = {blog["name"] for blog in followed_blogs}
        return self._filter_blogs(followed_blog_names)

    def _filter_blogs(self, blogs: set[str]) -> set[str]:
        if self.BLOGS_TO_CRAWL == {"all"}:  # noqa: SIM300
            filtered_blogs = blogs
        else:
            filtered_blogs = blogs.intersection(self.BLOGS_TO_CRAWL)

        return filtered_blogs.difference(self.BLOGS_TO_IGNORE)

    def get_files_from_blogs(self, current_blog_names: set[str]) -> list[FileMetadata]:
        # url as a key handles duplicates from different posts
        files: dict[str, FileMetadata] = {}
        previous_tumblr_blogs = self.helper.get_previous_run_tumblr_blogs()
        is_first_run = len(previous_tumblr_blogs) == 0

        for blog_name in current_blog_names:
            files = self._populate_files_from_blog(
                files=files,
                blog_name=blog_name,
                is_first_run=is_first_run,
                previous_tumblr_blogs=previous_tumblr_blogs,
            )

        return list(files.values())

    def _populate_files_from_blog(
        self,
        files: dict[str, FileMetadata],
        blog_name: str,
        is_first_run: bool,
        previous_tumblr_blogs: list[str],
    ) -> dict[str, FileMetadata]:
        params = {}
        is_new_blog = blog_name not in previous_tumblr_blogs

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

        for post in posts:
            match post["type"]:
                case "text":
                    files = self._populate_files_from_text_post(
                        files=files, post_html=post, blog_name=blog_name
                    )

                case "photo":
                    files = self._populate_files_from_photo_post(
                        files=files, post_html=post, blog_name=blog_name
                    )

                case _:
                    self.logger.info(f"Not supported post type: {post['type']}")

            if len(files) >= self.FILE_LIMIT_PER_BLOG:
                self.logger.info(
                    "The FILE_LIMIT_PER_BLOG is reached in `_get_files_from_blog`, "
                    f"len(files) = {len(files)}"
                )
                return files

        return files

    def _populate_files_from_text_post(
        self, files: dict[str, FileMetadata], post_html: dict[str, Any], blog_name: str
    ) -> dict[str, FileMetadata]:
        content_raw: str = post_html["trail"][0]["content_raw"]

        # Split content_raw as a post can have multiple images/gifs
        srcset_matches = re.findall(r'srcset="([^"]+)"', content_raw)
        if srcset_matches:
            for srcset_content in srcset_matches:
                file_candidates = srcset_content.split(",")
                # Get the file with the highest resolution
                last_candidate_url = file_candidates[-1].split()[0]

                file = self.file_meta.populate_file_metadata(
                    url=last_candidate_url, author=blog_name
                )

                if file:
                    files[file.url] = file

                if len(files) >= self.FILE_LIMIT_PER_BLOG:
                    self.logger.info(
                        "The FILE_LIMIT_PER_BLOG is reached in "
                        "`_get_files_from_text_post` (image/gif clause), "
                        f"len(files) = {len(files)}"
                    )
                    return files

        # Some text blogs have videos
        if self.COLLECT_VIDEOS:
            srcset_matches = re.findall(r'<source src="([^"]+)"', content_raw)
            if srcset_matches:
                for video_url in srcset_matches:
                    file = self.file_meta.populate_file_metadata(
                        url=video_url, author=blog_name
                    )

                    if file:
                        files[file.url] = file

                    if len(files) >= self.FILE_LIMIT_PER_BLOG:
                        self.logger.info(
                            "The FILE_LIMIT_PER_BLOG is reached in "
                            "`_get_files_from_text_post` (video clause), "
                            f"len(files) = {len(files)}"
                        )
                        return files

        return files

    def _populate_files_from_photo_post(
        self, files: dict[str, FileMetadata], post_html: dict[str, Any], blog_name: str
    ) -> dict[str, FileMetadata]:
        # Get the photo with the highest resolution
        url: str = post_html["photos"][0]["original_size"]["url"]

        file = self.file_meta.populate_file_metadata(url=url, author=blog_name)

        if file:
            files[file.url] = file

        if len(files) >= self.FILE_LIMIT_PER_BLOG:
            self.logger.info(
                "The FILE_LIMIT_PER_BLOG is reached in `_get_files_from_photo_post`, "
                f"len(files) = {len(files)}"
            )
            return files

        return files
