import os
import subprocess

from dotenv import load_dotenv
from helper import Helper

# https://github.com/meganz/MEGAcmd/blob/master/UserGuide.md

class MegaSaver:
    def __init__(self) -> None:
        load_dotenv()
        self.helper = Helper()
        path_from_env: str | None = os.getenv("MEGA_UPLOAD_PATH")
        if path_from_env:
            self.upload_path = path_from_env.rstrip("/")
        else:
            self.upload_path = "art_collector"

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

    def upload_local_files(self, local_files: list[str]) -> None:
        for file_path in local_files:
            filename = self.helper.get_filename(file_path)
            command = [
                "mega-put",
                "-c",
                file_path,
                f"{self.upload_path}/{filename}",
            ]  # -c	Creates remote folder destination in case of not existing
            subprocess.run(command, check=True)
