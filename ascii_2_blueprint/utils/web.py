import re
import requests
import webbrowser
from typing import Optional

class Teoxoy:
    PASTEBIN = "https://pst.innomi.net"

    @staticmethod
    def create_paste(blueprint_data: str) -> Optional[str]:
        data = {
            "lang": "text",
            "expire": "10m",
            "text": blueprint_data
        }
        response = requests.post(f"{Teoxoy.PASTEBIN}/paste/new", data=data)
        if response.status_code != 200 or not response.text:
            return None
        raw_paste_match = re.search(r"href=\"(/paste/\w+/raw)\"", response.text)
        if not raw_paste_match:
            return None
        return Teoxoy.PASTEBIN + raw_paste_match.group(1)

    @staticmethod
    def open_in_browser(url: str) -> None:
        webbrowser.open(f"https://fbe.teoxoy.com/?source={url}")