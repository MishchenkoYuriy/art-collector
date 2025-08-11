import logging
import os
import re
import subprocess

from dotenv import load_dotenv
from file_metadata import FileMetadata
from helper import Helper

# https://github.com/meganz/MEGAcmd/blob/master/UserGuide.md


class MegaSaver:
    def __init__(self) -> None:
        load_dotenv()
        self.FOLDER_SIZE_LIMIT_MB = int(os.getenv("MEGA_FOLDER_SIZE_LIMIT_MB", "1000"))
        self.FOLDER_SIZE_LIMIT_BYTES = self.FOLDER_SIZE_LIMIT_MB * 1024 * 1024
        self.helper = Helper()
        path_from_env: str | None = os.getenv("MEGA_UPLOAD_PATH")
        if path_from_env:
            self.upload_path = path_from_env.rstrip("/")
        else:
            self.upload_path = "art_collector"

        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s]{%(filename)s:%(lineno)d}%(levelname)s - %(message)s",
            filename="logs/helper.log",
        )
        self.logger = logging.getLogger(__name__)

    def login(self) -> None:
        email = os.getenv("MEGA_EMAIL")
        password = os.getenv("MEGA_PASSWORD")
        if not email or not password:
            msg = "MEGA_EMAIL and/or MEGA_PASSWORD are not set or are empty."
            raise ValueError(msg)

        auth_code: str | None = (
            f"--auth-code={os.getenv('MEGA_AUTH_CODE')}"
            if os.getenv("MEGA_AUTH_CODE")
            else None
        )
        login_command = ["mega-login", email, password]

        if auth_code:  # for two-factor authentication
            login_command.append(auth_code)

        try:
            subprocess.run(
                login_command,
                check=True,  # raises a CalledProcessError if command fails
                stdin=subprocess.DEVNULL,  # prevent interactive prompts
            )

        except subprocess.CalledProcessError as e:
            if e.returncode == 54:  # Already logged in
                pass
            else:
                raise

    def logout(self) -> None:
        subprocess.run("mega-logout", check=True)

    def get_mega_folder_size(self) -> int:
        command = ["mega-du", self.upload_path]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        output_string = result.stdout
        match = re.search(r"\d+", output_string)

        if match:
            return int(match.group(0))
        return 0

    def upload_local_files(self, files: list[FileMetadata]) -> None:
        mega_folder_size = self.get_mega_folder_size()

        for file in files:
            # Check if adding this file would exceed folder size limit
            if mega_folder_size + file.size > self.FOLDER_SIZE_LIMIT_BYTES:
                self.logger.warning(
                    f"Adding file {file.url} ({file.size} MB) would "
                    f"exceed folder size limit of {self.FOLDER_SIZE_LIMIT_MB} MB."
                )
                break

            command = [
                "mega-put",
                "-c",
                str(file.local_path),
                str(file.upload_path),
            ]  # -c	Creates remote folder destination in case of not existing
            subprocess.run(command, check=True)

            mega_folder_size += file.size
