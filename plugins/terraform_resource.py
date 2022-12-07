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

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from inmanta.agent import config
from inmanta.agent.agent import AgentInstance
from inmanta.agent.handler import CRUDHandler, HandlerContext, ResourcePurged, provider
from inmanta.agent.io.local import IOBase
from inmanta.protocol.endpoints import Client
from inmanta.resources import Id, PurgeableResource, Resource, resource
from inmanta_plugins.terraform.helpers.const import TERRAFORM_RESOURCE_STATE_PARAMETER
from inmanta_plugins.terraform.helpers.param_client import ParamClient
from inmanta_plugins.terraform.helpers.utils import (
    build_resource_state,
    dict_hash,
    parse_resource_state,
)
from inmanta_plugins.terraform.states.terraform_resource_state_inmanta import (
    TerraformResourceStateInmanta,
)
from inmanta_plugins.terraform.tf.exceptions import ResourceLookupException
from inmanta_plugins.terraform.tf.terraform_provider import TerraformProvider
from inmanta_plugins.terraform.tf.terraform_provider_installer import ProviderInstaller
from inmanta_plugins.terraform.tf.terraform_resource_client import (
    TerraformResourceClient,
)


@resource(
    "terraform::Resource",
    agent="provider.agent_config.agentname",
    id_attribute="id",
)
class TerraformResource(PurgeableResource):
    fields = (  # type: ignore
        "agent_name",
        "provider_namespace",
        "provider_type",
        "provider_version",
        "provider_alias",
        "provider_config",
        "resource_type",
        "resource_name",
        "resource_config",
        "terraform_id",
    )

    @staticmethod
    def get_id(exporter, entity):
        return f"{entity.provider.agent_config.agentname}-{entity.provider.alias}-{entity.type}-{entity.name}"

    @staticmethod
    def get_agent_name(exporter, entity) -> str:
        return entity.provider.agent_config.agentname

    @staticmethod
    def get_provider_namespace(exporter, entity) -> str:
        return entity.provider.namespace

    @staticmethod
    def get_provider_type(exporter, entity) -> str:
        return entity.provider.type

    @staticmethod
    def get_provider_version(exporter, entity) -> str:
        return entity.provider.version

    @staticmethod
    def get_provider_alias(exporter, entity) -> str:
        return entity.provider.alias

    @staticmethod
    def get_provider_config(exporter, entity) -> dict:
        return entity.provider.config

    @staticmethod
    def get_resource_type(exporter, entity) -> str:
        return entity.type

    @staticmethod
    def get_resource_name(exporter, entity) -> str:
        return entity.name

    @staticmethod
    def get_resource_config(exporter, entity) -> dict:
        return entity.config


@provider("terraform::Resource", name="terraform-resource")
class TerraformResourceHandler(CRUDHandler):
    def __init__(self, agent: "AgentInstance", io: "IOBase") -> None:
        super().__init__(agent, io=io)
        self.provider: Optional[TerraformProvider] = None
        self._resource_client: Optional[TerraformResourceClient] = None
        self.log_file_path = ""
        self.private_file_path = ""

    @property
    def resource_client(self) -> TerraformResourceClient:
        if self._resource_client is None:
            raise RuntimeError("The resource client is not setup")

        return self._resource_client

    def _agent_state_dir(self, resource: Resource) -> str:
        # Files used by the handler should go in state_dir/cache/<module-name>/<agent-id>/
        base_dir = config.state_dir.get()
        agent_dir = os.path.join(
            base_dir,
            "cache/terraform",
            resource.agent_name,  # type: ignore
        )
        if Path(base_dir) not in Path(os.path.realpath(agent_dir)).parents:
            raise Exception(
                f"Illegal path, {agent_dir} is not a subfolder of {base_dir}"
            )

        return agent_dir

    def _provider_state_dir(self, resource: Resource) -> str:
        # In this module, using the above path as root folder, we use one dir by provider
        # with name <provider-namespace>/<provider-type>/<provider-version>, as we have an
        # index on those three values.
        base_dir = self._agent_state_dir(resource)
        provider_dir = os.path.join(
            base_dir,
            resource.provider_namespace,  # type: ignore
            resource.provider_type,  # type: ignore
            resource.provider_version,  # type: ignore
        )
        if Path(base_dir) not in Path(os.path.realpath(provider_dir)).parents:
            raise Exception(
                f"Illegal path, {provider_dir} is not a subfolder of {base_dir}"
            )

        return provider_dir

    def _resource_state_dir(self, resource: Resource) -> str:
        # In this module, using the above path as root folder, we use one dir by resource
        # with name <resource-type>/<resource-name>, as we have an index on those two values.
        base_dir = self._provider_state_dir(resource)
        resource_dir = os.path.join(
            base_dir,
            resource.resource_type,  # type: ignore
            resource.resource_name,  # type: ignore
        )
        if Path(base_dir) not in Path(os.path.realpath(resource_dir)).parents:
            raise Exception(
                f"Illegal path, {resource_dir} is not a subfolder of {base_dir}"
            )

        return resource_dir

    def _resource_state(self, resource: TerraformResource, id: str) -> dict:
        """
        Some design choice here:
        Context: We need to save a resource state as terraform doesn't allow to get resource values
          based on any identifier amongst the attributes of the resource.  Such attributes can have
          a default value.  If we don't specify any value, Terraform will pick it automatically.
        Concern: If we save as state all the attributes with the values that Terraform picked, this
          saved state will differ from the config of the Inmanta resource.  Then, if we use this
          config in the next read operation, we will trigger an update, even if there were no
          effective changes, as the unspecified value (None) in our model will be compared to the
          the default value picked by Terraform.
        Option: We then decided to save as resource state the values set within Inmanta model with
          the addition of the resource id.  This way, we only compare values from the same origin
          ensuring consistency (as we filter this id before comparison).
        Downside: This implies that we loose track of those default values in the orchestrator.  This
          will however be solved once (if) we generate Inmanta modules automatically, setting those
          default values in the model directly.
        """
        state: dict = copy.deepcopy(resource.resource_config)  # type: ignore
        state.update({"id": id})
        return state

    def pre(self, ctx: HandlerContext, resource: Resource) -> None:
        """
        During the pre phase, we have to:
         - Install the provider binary
         - Ensure we have a state file
         - Start the provider process
        """
        provider_installer = ProviderInstaller(
            namespace=resource.provider_namespace,  # type: ignore
            type=resource.provider_type,  # type: ignore
            version=None
            if resource.provider_version == "latest"  # type: ignore
            else resource.provider_version,  # type: ignore
        )
        provider_installer.resolve()

        resource.provider_version = provider_installer.version  # type: ignore
        # We specify the download path, so that the provider is not downloaded on every handler execution
        download_path = os.path.join(
            self._provider_state_dir(resource),
            "provider.zip",
        )
        provider_installer.download(download_path)
        binary_path, _ = provider_installer.install_dry_run(
            self._provider_state_dir(resource)
        )
        if not Path(binary_path).exists():
            # We only install the binary if it is not there.  This avoids overwritting a binary that
            # might be currently used.
            binary_path = provider_installer.install(self._provider_state_dir(resource))

        # The file in which all logs from the provider will be saved during its execution
        _, self.log_file_path = tempfile.mkstemp(suffix=".log", text=True)

        log_path = Path(self.log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.touch(exist_ok=True)

        private_file_path = os.path.join(
            self._resource_state_dir(resource),
            "private",
        )
        private_path = Path(private_file_path)
        private_path.parent.mkdir(parents=True, exist_ok=True)
        private_path.touch(exist_ok=True)

        param_client = ParamClient(
            str(self._agent.environment),
            Client("agent"),
            lambda func: self.run_sync(func),
            TERRAFORM_RESOURCE_STATE_PARAMETER,
            Id.resource_str(resource.id),
        )

        terraform_resource_state = TerraformResourceStateInmanta(
            type_name=resource.resource_type,  # type: ignore
            private_file_path=private_file_path,
            param_client=param_client,
            config_hash=dict_hash(resource.resource_config),  # type: ignore
        )

        self.provider = TerraformProvider(
            binary_path,
            self.log_file_path,
        )
        ctx.debug("Starting provider process")
        self.provider.open()

        ctx.debug("Configuring provider")
        self.provider.configure(resource.provider_config)  # type: ignore

        self._resource_client = TerraformResourceClient(
            self.provider,
            terraform_resource_state,
            ctx.logger,
        )

        # The config can contain references to other resource attributes
        # We resolve any of those now and update the resource_config
        resource.resource_config = build_resource_state(
            resource.resource_config,  # type: ignore
            Client("agent"),
            lambda func: self.run_sync(func),
        )

    def post(self, ctx: HandlerContext, resource: Resource) -> None:
        """
        During the post phase we need to:
         - Stop the provider process
         - Cleanup the logs
        """
        if self.provider is not None:
            ctx.debug("Stopping provider process")
            self.provider.close()

        if self.log_file_path:
            with open(self.log_file_path, "r") as f:
                lines = f.readlines()
                if lines:
                    ctx.debug("Provider logs", logs="".join(lines))

            Path(self.log_file_path).unlink()

    def read_resource(self, ctx: HandlerContext, resource: PurgeableResource) -> None:
        """
        During the read phase, we need to:
         - Read the state, if there is none, we either:
            - Lost it, there is no way to find the resource -> resource considered purged, exit
            - Never created it -> resource considered purged, exit
         - Do a read operation with the provider process, which will return the current state of the resource
            - If it is empty, it couldn't find any -> resource considered purged, exit
            - If it is not empty, we parse the output and set our resource config
         - We save the current state
        """
        current_state = self.resource_client.read_resource()
        if current_state is None and resource.terraform_id is not None:  # type: ignore
            try:
                current_state = self.resource_client.import_resource(
                    resource.terraform_id  # type: ignore
                )
            except ResourceLookupException as e:
                # We will get this exception if the resource can not be imported because it doesn't exist.
                # We will simply consider the resource to be purged and log a warning to say to the user
                # that the id is not valid.  We expect the user not to include this id in the model anymore.
                ctx.warning(e.message)

        if not current_state:
            raise ResourcePurged()

        desired_state = resource.resource_config  # type: ignore
        current_state = parse_resource_state(
            current_state, self.resource_client.resource_schema.block
        )

        # Reduce the current state to only the keys we have a desired state about.
        # This can trigger false positive updates as we don't navigate the resource
        # config recursively.  We don't do it as it would be really complicate to
        # get the diff in lists and sets correctly.
        # This might get solved by https://github.com/inmanta/terraform/issues/7
        resource.resource_config = {  # type: ignore
            k: current_state.get(k) if v is not None else v
            for k, v in desired_state.items()
        }

        ctx.debug(
            "Resource read with config: %(config)s",
            config=json.dumps(resource.resource_config),  # type: ignore
        )

    def create_resource(self, ctx: HandlerContext, resource: PurgeableResource) -> None:
        """
        During the create phase, we need to:
         - Create the new resource with the provider process
         - Save the resource config in the state file
        """
        current_state = self.resource_client.create_resource(resource.resource_config)  # type: ignore

        if not current_state:
            raise RuntimeError(
                "Something went wrong, the plugin didn't return the current state"
            )

        resource_id = current_state.get("id")
        if not resource_id:
            raise RuntimeError(
                "Something went wrong, the plugin didn't return any id for the created resource"
            )

        ctx.debug("Resource id is %(id)s", id=resource_id)
        ctx.debug(
            "Resource created with config: %(config)s", config=json.dumps(current_state)
        )

        ctx.set_created()

    def update_resource(
        self, ctx: HandlerContext, changes: dict, resource: PurgeableResource
    ) -> None:
        """
        During the update phase, we need to:
         - Read the current state
         - Update the resource with the provider process
         - Save the new state to the state file
        """
        current_state = self.resource_client.update_resource(resource.resource_config)  # type: ignore

        if not current_state:
            raise RuntimeError(
                "Something went wrong, the plugin didn't return the current state"
            )

        resource_id = current_state.get("id")
        if not resource_id:
            raise RuntimeError(
                "Something went wrong, the plugin didn't return any id for the created resource"
            )

        ctx.debug(
            "Resource updated with config: %(config)s", config=json.dumps(current_state)
        )

        ctx.set_updated()

    def delete_resource(self, ctx: HandlerContext, resource: PurgeableResource) -> None:
        """
        During the delete phase, we need to:
         - Read the current state
         - Delete the resource with the provider process
         - Delete the state file
        """
        self.resource_client.delete_resource()

        ctx.set_purged()
