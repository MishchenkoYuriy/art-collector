import logging
import re
import subprocess

from config import settings
from file_metadata import FileMetadata

# https://github.com/meganz/MEGAcmd/blob/master/UserGuide.md


class MegaSaver:
    def __init__(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s]{%(filename)s:%(lineno)d}%(levelname)s - %(message)s",
            filename="logs/art_collector.log",
        )
        self.logger = logging.getLogger(__name__)

    def login(self) -> None:
        if settings.SAVE_TO_MEGA:
            if not settings.MEGA_EMAIL or not settings.MEGA_PASSWORD:
                msg = "MEGA_EMAIL and/or MEGA_PASSWORD are not set or are empty."
                raise ValueError(msg)

            auth_code: str | None = (
                f"--auth-code={settings.MEGA_AUTH_CODE}"
                if settings.MEGA_AUTH_CODE
                else None
            )
            login_command = ["mega-login", settings.MEGA_EMAIL, settings.MEGA_PASSWORD]

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
        if settings.SAVE_TO_MEGA:
            subprocess.run("mega-logout", check=True)

    def _get_mega_folder_size(self) -> int:
        if settings.MEGA_UPLOAD_PATH:
            command = ["mega-du", settings.MEGA_UPLOAD_PATH]
            try:
                result = subprocess.run(
                    command, capture_output=True, text=True, check=True
                )
            except subprocess.CalledProcessError as e:
                if e.returncode == 53:
                    self.logger.info(
                        f"The path `{settings.MEGA_UPLOAD_PATH}` does not exist."
                    )
                    return 0
                raise

            output_string = result.stdout
            match = re.search(r"\d+", output_string)

            if match:
                return int(match.group(0))
        return 0

    def upload_local_file(self, file: FileMetadata) -> None:
        if settings.SAVE_TO_MEGA:
            mega_folder_size = self._get_mega_folder_size()

            # Check if adding this file would exceed folder size limit
            if mega_folder_size + file.size > settings.MEGA_FOLDER_SIZE_LIMIT_BYTES:
                self.logger.warning(
                    f"Adding file {file.url} ({file.size} MB) would "
                    "exceed folder size limit of "
                    f"{settings.MEGA_FOLDER_SIZE_LIMIT_MB} MB."
                )
                return

            command = [
                "mega-put",
                "-c",
                str(file.local_path),
                str(file.mega_path),
            ]  # -c	Creates remote folder destination in case of not existing
            subprocess.run(command, check=True)
