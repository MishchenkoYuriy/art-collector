from helper import Helper, ImageMetadata
from mega import MegaSaver
from tumblr import TumblrCollector

if __name__ == "__main__":
    mega = MegaSaver()
    mega.login()  # the first step as auth code can expire

    try:
        tumblr = TumblrCollector()
        helper = Helper()
        followed_blog_names = tumblr.get_followed_blogs()
        all_image_metadata: list[ImageMetadata] = []
        for blog_name in followed_blog_names:
            image_metadata = tumblr.get_image_urls_by_blog(blog_name)
            all_image_metadata.extend(image_metadata)

        local_paths = helper.download_from_urls(all_image_metadata)
        mega.upload_local_files(local_paths)
        helper.save_runtime_config(followed_blog_names)

    finally:
        helper.clean_temp_directory()
        mega.logout()
