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

from providers.local.helpers.local_file import LocalFile
from providers.local.helpers.local_provider import LocalProvider
from pytest_inmanta.plugin import Project

LOGGER = logging.getLogger(__name__)


def test_plugin(project: Project):
    first_provider = LocalProvider()
    second_provider = LocalProvider(alias="duplicate")

    first_file = LocalFile("file1", "/tmp/file1.txt", "content", first_provider)
    second_file = LocalFile(
        "file2", "/tmp/file2.txt", "another content", second_provider
    )

    model = "import terraform"

    model += "\n\n" + first_provider.model_instance("first_provider")
    model += "\n\n" + second_provider.model_instance("second_provider")
    model += "\n\n" + first_file.model_instance("first_file")
    model += "\n\n" + second_file.model_instance("second_file")

    project.compile(model)

    providers = project.get_instances("terraform::Provider")
    assert len(providers) == 2, "There should be two providers in this model"

    resources = project.get_instances("terraform::Resource")
    assert len(resources) == 2, "There should be two resources in this model"

    agents = project.get_instances("std::AgentConfig")
    assert len(agents) == 1, "Both providers should use the same agent"
