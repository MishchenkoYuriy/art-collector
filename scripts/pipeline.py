from helper import Helper
from tumblr import TumblrCollector

if __name__ == "__main__":
    tumblr = TumblrCollector()
    helper = Helper()
    followed_blog_names = tumblr.get_followed_blogs()
    all_image_urls: list[str] = []
    for blog_name in followed_blog_names:
        image_urls = tumblr.get_image_urls_by_blog(blog_name)
        all_image_urls.extend(image_urls)
        break  ## TODO: remove

    helper.download_from_urls(all_image_urls)
