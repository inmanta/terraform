"""
    Copyright 2021 Inmanta

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

    Contact: code@inmanta.com
"""
import urllib.parse
from typing import Optional

import requests


class GitlabClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url
        self.token = token

    def get_project(self, path: str) -> Optional[dict]:
        urlencoded_path = urllib.parse.quote_plus(path)
        response = requests.get(
            f"{self.base_url}/projects/{urlencoded_path}",
            headers={"PRIVATE-TOKEN": self.token},
        )
        if response.status_code == 404:
            return None

        response.raise_for_status()
        return response.json()

    def delete_project(self, path: str) -> None:
        urlencoded_path = urllib.parse.quote_plus(path)
        response = requests.delete(
            f"{self.base_url}/projects/{urlencoded_path}",
            headers={"PRIVATE-TOKEN": self.token},
        )
        if response.status_code == 404:
            return

        response.raise_for_status()
