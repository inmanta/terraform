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

    This package contains various utilities.
"""
from typing import Any, List, Union

from inmanta_plugins.terraform.helpers.const import INMANTA_MAGIC_KEY


class AttributeReference:
    def __init__(
        self, environment: str, resource_id: str, attribute_path: List[Union[str, int]]
    ) -> None:
        self.environment = environment
        self.resource_id = resource_id
        self.attribute_path = attribute_path

    def to_dict(self) -> dict:
        return {
            "environment": str(self.environment),
            "resource_id": self.resource_id,
            "attribute_path": self.attribute_path,
            INMANTA_MAGIC_KEY: True,
        }

    @staticmethod
    def from_dict(input: dict) -> "AttributeReference":
        required_keys = {
            "environment",
            "resource_id",
            "attribute_path",
            INMANTA_MAGIC_KEY,
        }
        if required_keys - set(input.keys()):
            raise ValueError(
                "Failed to parse the attribute reference dict, "
                f"it is missing at least one of the required key: {list(required_keys)}"
            )

        return AttributeReference(
            environment=input["environment"],
            resource_id=input["resource_id"],
            attribute_path=input["attribute_path"],
        )

    def extract_from_state(self, state: dict) -> Any:
        value: Any = state
        for attribute in self.attribute_path:
            if isinstance(attribute, str):
                if not isinstance(value, dict):
                    raise ValueError(
                        "A string attribute can only get an item from a dict, "
                        f"but value is of type {type(value)}"
                    )

                value = value.get(attribute)
                continue

            if isinstance(attribute, int):
                if not isinstance(value, list):
                    raise ValueError(
                        "A int attribute can only get an item from a list, "
                        f"but value is of type {type(value)}"
                    )

                if attribute < 0 or attribute >= len(value):
                    raise ValueError(
                        "Trying to get an attribute from outside the bound of the list: "
                        f"{str(attribute)} not in ]-1:{len(value) - 1}]"
                    )

                value = value[attribute]
                continue

            raise ValueError(
                f"An attribute should be of type int or str, but got {type(attribute)}"
            )

        return value
