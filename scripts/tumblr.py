import os
import re
from pathlib import Path

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
        self.helper = Helper()
        self.file_meta = FileMetadataHelper()
        self.oauth = OAuth1(
            client_key=os.getenv("TUMBLR_CONSUMER_KEY"),
            client_secret=os.getenv("TUMBLR_CONSUMER_SECRET"),
            resource_owner_key=os.getenv("TUMBLR_OAUTH_TOKEN"),
            resource_owner_secret=os.getenv("TUMBLR_OAUTH_SECRET"),
        )
        self.url_pattern = re.compile(r"\s*(https?://[^\s]+)\s+([0-9]+)w\s*")

    def get_followed_blogs(self) -> list[str]:
        resp = requests.get(
            "https://api.tumblr.com/v2/user/following", auth=self.oauth, timeout=10
        )
        followed_blogs = resp.json()["response"]["blogs"]
        followed_blog_names: list[str] = [blog["name"] for blog in followed_blogs]
        return followed_blog_names

    def get_files_from_blogs(self, current_blog_names: list[str]) -> list[FileMetadata]:
        files: list[FileMetadata] = []
        previous_tumblr_blogs = self.helper.get_previous_run_tumblr_blogs()
        is_first_run = len(previous_tumblr_blogs) == 0

        for blog_name in current_blog_names:
            blog_files = self._get_files_from_blog(
                blog_name, is_first_run, previous_tumblr_blogs
            )
            files.extend(blog_files)

        return files

    def _get_files_from_blog(
        self, blog_name: str, is_first_run: bool, previous_tumblr_blogs: list[str]
    ) -> list[FileMetadata]:
        blog_files: list[FileMetadata] = []
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
            content_raw = post["trail"][0]["content_raw"]

            # Split content_raw as a post can have multiple images
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
                        blog_files.append(file)

                    if len(blog_files) == self.FILE_LIMIT_PER_BLOG:
                        return blog_files

        return blog_files
