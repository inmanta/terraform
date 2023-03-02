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
import logging
from abc import abstractmethod
from textwrap import dedent, indent
from typing import List, Optional
from uuid import UUID

from helpers.resource import Resource
from helpers.terraform_provider import TerraformProvider

from inmanta.const import ParameterSource
from inmanta.protocol.endpoints import Client
from inmanta.resources import Id

LOGGER = logging.getLogger(__name__)


class TerraformResource(Resource):
    def __init__(
        self,
        type: str,
        name: str,
        provider: TerraformProvider,
        terraform_id: Optional[str] = None,
        send_event: bool = False,
    ) -> None:
        entity_id = f"{provider.agent}-{provider.alias}-{type}-{name}"
        super().__init__(
            Id.parse_id(f"terraform::Resource[{provider.agent},id={entity_id}]")
        )
        self.type = type
        self.name = name
        self.provider = provider
        self.terraform_id = terraform_id
        self.send_event = send_event

    @property
    @abstractmethod
    def config(self) -> dict:
        pass

    def model_instance(
        self,
        var_name: str,
        purged: bool = False,
        requires: Optional[List[str]] = None,
        provides: Optional[List[str]] = None,
    ) -> str:
        provider_reference = self.provider.model_reference()
        provider_reference = indent(provider_reference, "                ").strip()
        config = json.dumps(self.config, indent=4)
        config = indent(config, "                ").strip()
        requires = requires or []
        provides = provides or []
        terraform_id = '"' + self.terraform_id + '"' if self.terraform_id else "null"
        model = f"""
            {var_name} = terraform::Resource(
                type="{self.type}",
                name="{self.name}",
                terraform_id={terraform_id},
                config={config},
                purged={str(purged).lower()},
                send_event={str(self.send_event).lower()},
                provider={provider_reference},
                requires={'[' + ', '.join(requires) + ']'},
                provides={'[' + ', '.join(provides) + ']'},
            )
        """
        return dedent(model.strip("\n"))

    async def set_state(self, client: Client, environment: UUID, state: dict) -> None:
        """
        Manually set a new state for this resource in the parameters of the server.
        """
        result = await client.set_param(
            tid=environment,
            id="terraform-resource-state",
            source=ParameterSource.user,
            value=json.dumps(state),
            resource_id=str(self.id),
            recompile=True,
        )
        if result.code == 200:
            return

        assert (
            False
        ), f"Bad response while trying to set parameter: {result.code}, {result.message}"

    async def get_state(self, client: Client, environment: UUID) -> Optional[dict]:
        """
        Get the state dict from the server, if it exists, None otherwise.
        """
        result = await client.get_param(
            tid=environment,
            id="terraform-resource-state",
            resource_id=self.id,
        )
        if result.code == 200:
            return json.loads(result.result["parameter"]["value"])

        if result.code == 404:
            return None

        if result.code == 503:
            # In our specific case, we might get a 503 if the parameter is not set yet
            # https://github.com/inmanta/inmanta-core/blob/5bfe60683f7e21657794eaf222f43e4c53540bb5/src/inmanta/server/agentmanager.py#L799
            return None

        assert (
            False
        ), f"Unexpected response from server: {result.code}, {result.message}"

    async def purge_state(self, client: Client, environment: UUID) -> None:
        """
        Purge the state dict of this resource from the server, if it exists.  This method
        is idempotent.
        """
        result = await client.delete_param(
            tid=environment,
            id="terraform-resource-state",
            resource_id=self.id,
        )
        if result.code == 200 or result.code == 404:
            return

        assert (
            False
        ), f"Unexpected response from server: {result.code}, {result.message}"
