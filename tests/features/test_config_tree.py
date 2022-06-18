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
import logging

from pytest_inmanta.plugin import Project

LOGGER = logging.getLogger(__name__)


def test_config_serialization(project: Project):
    model = """
        import terraform::config

        terraform::config::Block(
            name="root",
            attributes={"name": "Albert"},
            children=[
                terraform::config::Block(
                    name="children",
                    attributes={"name": "Bob", "age": 12},
                    nesting_mode="set",
                ),
                terraform::config::Block(
                    name="children",
                    attributes={"name": "Alice", "age": 14},
                    nesting_mode="set",
                ),
                terraform::config::Block(
                    name="pets",
                    attributes={"type": "dog"},
                    nesting_mode="dict",
                    key="Brutus",
                ),
                terraform::config::Block(
                    name="favorite_dishes",
                    attributes={"name": "Pizza"},
                    nesting_mode="list",
                    key="1",
                    children=[
                        terraform::config::Block(
                            name="content",
                            attributes={"salt": "yes", "sugar": "no"},
                        ),
                    ],
                ),
                terraform::config::Block(
                    name="favorite_dishes",
                    attributes={"name": "Pasta"},
                    nesting_mode="list",
                    key="2",
                )
            ],
            parent=null,
        )
    """
    project.compile(model, no_dedent=False)

    blocks = project.get_instances("terraform::config::Block")
    root_block = next(iter(block for block in blocks if block.name == "root"))

    assert root_block._config["name"] == "Albert"
    assert root_block._config["pets"] == {
        "Brutus": {
            "type": "dog",
        },
    }
    assert root_block._config["favorite_dishes"] == [
        {"name": "Pizza", "content": {"salt": "yes", "sugar": "no"}},
        {"name": "Pasta"},
    ]

    alice = {
        "name": "Alice",
        "age": 14,
    }
    bob = {
        "name": "Bob",
        "age": 12,
    }
    assert root_block._config["children"] == [alice, bob] or root_block._config[
        "children"
    ] == [bob, alice]
