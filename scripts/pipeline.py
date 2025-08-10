from helper import Helper
from mega import MegaSaver
from tumblr import TumblrCollector

if __name__ == "__main__":
    mega = MegaSaver()
    mega.login()  # the first step as auth code can expire

    try:
        tumblr = TumblrCollector()
        helper = Helper()
        followed_blog_names = tumblr.get_followed_blogs()
        all_image_urls: list[str] = []
        for blog_name in followed_blog_names:
            image_urls = tumblr.get_image_urls_by_blog(blog_name)
            all_image_urls.extend(image_urls)
            break  ## TODO: remove

        helper.clean_temp_directory()
        local_paths = helper.download_from_urls(all_image_urls)
        mega.upload_local_files(local_paths)

    finally:
        mega.logout()
