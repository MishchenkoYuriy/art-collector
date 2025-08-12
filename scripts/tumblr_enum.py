from enum import Enum


class TumblrPostType(Enum):
    TEXT = "text"
    QUOTE = "quote"
    LINK = "link"
    ANSWER = "answer"
    VIDEO = "video"
    AUDIO = "audio"
    PHOTO = "photo"
    CHAT = "chat"
