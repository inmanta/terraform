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
import json
from abc import abstractmethod
from textwrap import dedent, indent


class TerraformProvider:
    def __init__(
        self, namespace: str, type: str, version: str, alias: str = ""
    ) -> None:
        self.namespace = namespace
        self.type = type
        self.version = version
        self.alias = alias

    @property
    @abstractmethod
    def config(self) -> dict:
        pass

    @property
    def agent(self) -> str:
        return f"{self.namespace}-{self.type}-{self.version}"

    def model_instance(self, var_name: str) -> str:
        config = json.dumps(self.config, indent=4)
        config = indent(config, "                ").strip()
        model = f"""
            # Overwritting agent config to disable autostart.  Agents have to be started
            # manually in the tests.
            {var_name}_agent_config = std::AgentConfig(
                autostart=false,
                agentname="{self.agent}",
                uri="local:",
                provides={var_name},
            )

            {var_name} = terraform::Provider(
                namespace="{self.namespace}",
                type="{self.type}",
                version="{self.version}",
                alias="{self.alias}",
                config={config},
                auto_agent=false,
                agent_config={var_name}_agent_config,
            )
        """
        return dedent(model.strip("\n"))

    def model_reference(self) -> str:
        model = f"""
            terraform::Provider[
                namespace="{self.namespace}",
                type="{self.type}",
                version="{self.version}",
                alias="{self.alias}",
            ]
        """
        return dedent(model.strip("\n"))
