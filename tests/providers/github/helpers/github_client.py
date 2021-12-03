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
from typing import Optional

import requests


class GithubClient:
    def __init__(self, owner: str, token: str) -> None:
        self.owner = owner
        self.token = token

    def get_repository(self, repository_name: str) -> Optional[dict]:
        response = requests.get(
            f"https://api.github.com/repos/{self.owner}/{repository_name}",
            headers={"Authorization": f"token {self.token}"},
        )
        if response.status_code == 404:
            return None

        response.raise_for_status()
        return response.json()

    def delete_repository(self, repository_name: str) -> None:
        response = requests.delete(
            f"https://api.github.com/repos/{self.owner}/{repository_name}",
            headers={"Authorization": f"token {self.token}"},
        )
        if response.status_code == 404:
            return

        response.raise_for_status()
