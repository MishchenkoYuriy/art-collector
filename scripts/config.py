from pathlib import Path
from typing import Annotated

from pydantic import DirectoryPath, Field, computed_field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

SixDigitCode = Annotated[str, Field(pattern=r"^\d{6}$")]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    TUMBLR_CONSUMER_KEY: str | None = Field(default=None)
    TUMBLR_CONSUMER_SECRET: str | None = Field(default=None)
    TUMBLR_OAUTH_TOKEN: str | None = Field(default=None)
    TUMBLR_OAUTH_SECRET: str | None = Field(default=None)
    TUMBLR_FILE_LIMIT_PER_BLOG: int = Field(default=50)
    TUMBLR_COLLECT_VIDEOS: bool = Field(default=True)
    TUMBLR_BLOGS_TO_CRAWL: Annotated[set[str], NoDecode] = Field(default={"all"})
    TUMBLR_BLOGS_TO_IGNORE: Annotated[set[str], NoDecode] = Field(default=set())

    LOCAL_FILE_SIZE_LIMIT_MB: int = Field(default=10)
    LOCAL_FOLDER_SIZE_LIMIT_MB: int = Field(default=1000)
    LOCAL_UPLOAD_PATH: DirectoryPath | None = Field(default=None)
    LOCAL_TEMP_UPLOAD_DIR: Path = Path("temp")

    SAVE_TO_MEGA: bool = Field(default=True)
    MEGA_EMAIL: str | None = Field(default=None)
    MEGA_PASSWORD: str | None = Field(default=None)
    MEGA_AUTH_CODE: SixDigitCode | None = Field(default=None)
    MEGA_UPLOAD_PATH: Path = Field(default=Path("art_collector"))
    MEGA_FOLDER_SIZE_LIMIT_MB: int = Field(default=1000)

    CONFIG_FILE: Path = Path(__file__).resolve().parent.parent / "config.json"

    @field_validator("TUMBLR_BLOGS_TO_CRAWL", "TUMBLR_BLOGS_TO_IGNORE", mode="before")
    @classmethod
    def decode_tumblr_blogs_to_crawl(cls, v: str | set[str]) -> set[str]:
        if isinstance(v, set):
            return v
        return {blog.strip() for blog in v.split(",")}

    @computed_field
    def LOCAL_FILE_SIZE_LIMIT_BYTES(self) -> int:  # noqa: N802
        return self.LOCAL_FILE_SIZE_LIMIT_MB * 1024 * 1024

    @computed_field
    def LOCAL_FOLDER_SIZE_LIMIT_BYTES(self) -> int:  # noqa: N802
        return self.LOCAL_FOLDER_SIZE_LIMIT_MB * 1024 * 1024

    @computed_field
    def MEGA_FOLDER_SIZE_LIMIT_BYTES(self) -> int:  # noqa: N802
        return self.MEGA_FOLDER_SIZE_LIMIT_MB * 1024 * 1024


settings = Settings()
