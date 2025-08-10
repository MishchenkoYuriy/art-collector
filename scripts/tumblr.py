import os
import re

import requests
from dotenv import load_dotenv
from helper import Helper, ImageMetadata
from requests_oauthlib import OAuth1

# TODO: find method to get oauth_token
# TODO: Set the configuration to determine the art resolution, default: max
# TODO: look into type, date, post_url attibutes of the post
# TODO: look into https://www.tumblr.com/docs/en/api/v2#postsdraft--retrieve-draft-posts
# TODO: look into https://www.tumblr.com/docs/en/api/v2#postsqueue--retrieve-queued-posts

# https://github.com/tumblr/pytumblr
# https://api.tumblr.com/v2/user/info


class TumblrCollector:
    def __init__(self) -> None:
        load_dotenv()
        self.POST_LIMIT = 50
        self.helper = Helper()
        self.oauth = OAuth1(
            client_key=os.getenv("TUMBLR_CONSUMER_KEY"),
            client_secret=os.getenv("TUMBLR_CONSUMER_SECRET"),
            resource_owner_key=os.getenv("TUMBLR_OAUTH_TOKEN"),
            resource_owner_secret=os.getenv("TUMBLR_OAUTH_SECRET"),
        )

    def get_followed_blogs(self) -> list[str]:
        resp = requests.get(
            "https://api.tumblr.com/v2/user/following", auth=self.oauth, timeout=10
        )
        followed_blogs = resp.json()["response"]["blogs"]
        followed_blog_names: list[str] = [blog["name"] for blog in followed_blogs]
        return followed_blog_names

    def get_image_urls_by_blog(self, blog_name: str) -> list[ImageMetadata]:
        image_metadata_list: list[ImageMetadata] = []
        current_tumblr_blogs = self.helper.get_current_tumblr_blogs()
        
        is_first_run = len(current_tumblr_blogs) == 0
        is_new_blog = blog_name not in current_tumblr_blogs
        params = {}
        
        if is_first_run or is_new_blog:
            # Don't use 'after' parameter for the first run or new blogs
            params["limit"] = self.POST_LIMIT
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
            image_url = self.extract_image_url_from_html(
                post["trail"][0]["content_raw"]
            )
            if image_url:  # if image is found
                image_metadata_list.append(
                    ImageMetadata(url=image_url, author=blog_name)
                )

        return image_metadata_list

    def extract_image_url_from_html(self, html: str) -> str | None:
        srcset_match = re.search(r'srcset="([^"]+)"', html)
        if srcset_match:
            srcset_content = srcset_match.group(1)
            image_candidates = srcset_content.split(",")

            highest_res_url: str | None = None
            max_width: int = 0

            pattern = re.compile(r"\s*(https?://[^\s]+)\s+([0-9]+)w\s*")

            for candidate in image_candidates:
                match = pattern.match(candidate)
                if match:
                    url = match.group(1)
                    width = int(match.group(2))

                    if width > max_width:
                        max_width = width
                        highest_res_url = url

            return highest_res_url

        return None
