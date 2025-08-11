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
        tumblr_files = tumblr.get_files_from_blogs(followed_blog_names)
        helper.download_files(tumblr_files)
        mega.upload_local_files(tumblr_files)
        helper.save_runtime_config(followed_blog_names)

    finally:
        helper.clean_temp_directory()
        mega.logout()
