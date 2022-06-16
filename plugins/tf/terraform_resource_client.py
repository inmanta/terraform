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
from typing import Any, Optional

import inmanta_tfplugin.tfplugin5_pb2 as tfplugin5_pb2  # type: ignore

"""
The import statement above SHOULD NOT BE REMOVED without proper consideration.
Because of a design choice of the protobuf library, we can not simply copy the generated code
in this module's plugins (as the inmanta agent will rename them):

    https://github.com/protocolbuffers/protobuf/issues/9535

Also note that this limitation can not be discovered by simply running this module's test suite
as pytest-inmanta doesn't run a real agent.
Changing those imports and having a successfull test run IS NOT ENOUGH to assume the module
will work.
"""

import msgpack  # type: ignore

from inmanta_plugins.terraform.helpers.utils import fill_partial_state
from inmanta_plugins.terraform.tf.exceptions import PluginException
from inmanta_plugins.terraform.tf.terraform_provider import (
    TerraformProvider,
    raise_for_diagnostics,
)
from inmanta_plugins.terraform.tf.terraform_resource_state import TerraformResourceState

MAGIC_NAME = "TF_PLUGIN_MAGIC_COOKIE"
MAGIC_VALUE = "d602bf8f470bc67ca7faa0386276bbdd4330efaf76d1a219cb4d6991ca9872b2"
CORE_PROTOCOL_VERSION = 1
SUPPORTED_VERSIONS = (4, 5)
TERRAFORM_VERSION = "0.14.10"


def parse_response(input: Optional[Any]) -> Optional[Any]:
    if input is None:
        return None

    def decode_if_bytes(x):
        return x.decode("utf-8") if isinstance(x, bytes) else x

    if isinstance(input, bytes):
        return input.decode("utf-8")

    if isinstance(input, list):
        return [parse_response(item) for item in input]

    if isinstance(input, dict):
        return {
            decode_if_bytes(key): parse_response(value) for key, value in input.items()
        }

    if isinstance(input, set):
        raise Exception("A response from msgpack shouldn't contain any set")

    return input


class TerraformResourceClient:
    def __init__(
        self,
        provider: TerraformProvider,
        resource_state: TerraformResourceState,
        logger: logging.Logger,
    ) -> None:
        self.provider = provider
        self.logger = logger
        self.resource_state = resource_state

        if not self.provider.ready:
            raise RuntimeError("The provider received is not ready to be used")

    @property
    def resource_schema(self) -> Any:
        return self.provider.schema.resource_schemas.get(self.resource_state.type_name)

    def import_resource(self, id: str) -> Optional[dict]:
        if (
            self.resource_state.state is not None
            and self.resource_state.state.get("id") != id
        ):
            raise PluginException(
                "Can not import a resource which already has a state and has "
                f"a different id: {self.resource_state.state.get('id')} != {id}"
            )

        result = self.provider.stub.ImportResourceState(
            tfplugin5_pb2.ImportResourceState.Request(
                type_name=self.resource_state.type_name,
                id=id,
            )
        )

        self.logger.debug(f"Import resource response: {str(result)}")

        raise_for_diagnostics(result.diagnostics, "Failed to import the resource")

        imported = list(result.imported_resources)

        if len(imported) != 1:
            raise PluginException(
                "The resource import failed, wrong amount of resources returned: "
                f"got {len(imported)} (expected 1)"
            )

        self.resource_state.state = parse_response(
            msgpack.unpackb(imported[0].state.msgpack)
        )
        self.resource_state.private = imported[0].private

        return self.resource_state.state

    def read_resource(self) -> Optional[dict]:
        if self.resource_state.state is None:
            return None

        self.resource_state.raise_if_not_complete()

        result = self.provider.stub.ReadResource(
            tfplugin5_pb2.ReadResource.Request(
                type_name=self.resource_state.type_name,
                current_state=tfplugin5_pb2.DynamicValue(
                    msgpack=msgpack.packb(self.resource_state.state)
                ),
                private=self.resource_state.private,
            )
        )

        self.logger.debug(f"Read resource response: {str(result)}")

        raise_for_diagnostics(result.diagnostics, "Failed to read the resource")

        self.resource_state.state = parse_response(
            msgpack.unpackb(result.new_state.msgpack)
        )
        self.resource_state.private = result.private

        self.logger.info(
            f"Read resource with state: {json.dumps(self.resource_state.state, indent=2)}"
        )

        return self.resource_state.state

    def create_resource(self, desired: dict) -> Optional[dict]:
        base_conf = fill_partial_state(desired, self.resource_schema.block)

        # Plan
        result = self.provider.stub.PlanResourceChange(
            tfplugin5_pb2.PlanResourceChange.Request(
                type_name=self.resource_state.type_name,
                prior_state=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb(None)),
                proposed_new_state=tfplugin5_pb2.DynamicValue(
                    msgpack=msgpack.packb(base_conf)
                ),
                config=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb(base_conf)),
                prior_private=None,
            )
        )

        self.logger.debug(f"Plan create resource response: {str(result)}")

        raise_for_diagnostics(
            result.diagnostics, "Failed to plan creation of the resource"
        )

        # Apply
        result = self.provider.stub.ApplyResourceChange(
            tfplugin5_pb2.ApplyResourceChange.Request(
                type_name=self.resource_state.type_name,
                prior_state=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb(None)),
                planned_state=result.planned_state,
                config=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb(base_conf)),
                planned_private=result.planned_private,
            )
        )

        self.logger.debug(f"Create resource response: {str(result)}")

        self.resource_state.private = result.private
        self.resource_state.state = parse_response(
            msgpack.unpackb(result.new_state.msgpack)
        )

        raise_for_diagnostics(result.diagnostics, "Failed to create the resource")

        return self.resource_state.state

    def update_resource(self, desired: dict) -> Optional[dict]:
        """
        Perform an update (or a replace if required) of the specified resource.
        The following document's comments were a great help in the process of wiring this
        all up.
        https://github.com/hashicorp/terraform/blob/main/providers/provider.go
        """
        self.resource_state.raise_if_not_complete()

        desired_conf = fill_partial_state(desired, self.resource_schema.block)

        prior_state = msgpack.packb(self.resource_state.state)

        # Plan
        result = self.provider.stub.PlanResourceChange(
            tfplugin5_pb2.PlanResourceChange.Request(
                type_name=self.resource_state.type_name,
                prior_state=tfplugin5_pb2.DynamicValue(msgpack=prior_state),
                proposed_new_state=tfplugin5_pb2.DynamicValue(
                    msgpack=msgpack.packb(desired_conf)
                ),
                config=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb(desired_conf)),
                prior_private=self.resource_state.private,
            )
        )

        self.logger.debug(f"Plan update resource response: {str(result)}")

        raise_for_diagnostics(
            result.diagnostics, "Failed to plan update of the resource"
        )

        # Checking if the plan detected any changes to apply, this condition will only
        # be true if we failed some things in our diff computation.  This can happen
        # as the diff is currently computed with the attributes of the entities and the
        # state deployed, and the attributes of the entities might not contain some values
        # which have default assignments in the provider.
        if result.planned_state.msgpack == prior_state:
            self.logger.warning(
                "The client had to skip an update because there was no difference between the desired and current state."
            )
            return self.resource_state.state

        if result.requires_replace:
            self.delete_resource()
            return self.create_resource(desired)

        # Apply
        result = self.provider.stub.ApplyResourceChange(
            tfplugin5_pb2.ApplyResourceChange.Request(
                type_name=self.resource_state.type_name,
                prior_state=tfplugin5_pb2.DynamicValue(
                    msgpack=msgpack.packb(self.resource_state.state)
                ),
                planned_state=result.planned_state,
                config=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb(desired_conf)),
                planned_private=result.planned_private,
            )
        )

        self.logger.debug(f"Update resource response: {str(result)}")

        self.resource_state.state = parse_response(
            msgpack.unpackb(result.new_state.msgpack)
        )
        self.resource_state.private = result.private

        raise_for_diagnostics(result.diagnostics, "Failed to update the resource")

        return self.resource_state.state

    def delete_resource(self) -> None:
        self.resource_state.raise_if_not_complete()

        # Plan
        result = self.provider.stub.PlanResourceChange(
            tfplugin5_pb2.PlanResourceChange.Request(
                type_name=self.resource_state.type_name,
                prior_state=tfplugin5_pb2.DynamicValue(
                    msgpack=msgpack.packb(self.resource_state.state)
                ),
                proposed_new_state=tfplugin5_pb2.DynamicValue(
                    msgpack=msgpack.packb(None)
                ),
                config=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb({})),
                prior_private=self.resource_state.private,
            )
        )

        self.logger.debug(f"Plan delete resource response: {str(result)}")

        raise_for_diagnostics(
            result.diagnostics, "Failed to plan deleting of the resource"
        )

        # Apply
        result = self.provider.stub.ApplyResourceChange(
            tfplugin5_pb2.ApplyResourceChange.Request(
                type_name=self.resource_state.type_name,
                prior_state=tfplugin5_pb2.DynamicValue(
                    msgpack=msgpack.packb(self.resource_state.state)
                ),
                planned_state=result.planned_state,
                config=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb({})),
                planned_private=result.planned_private,
            )
        )

        self.logger.debug(f"Delete resource response: {str(result)}")

        raise_for_diagnostics(result.diagnostics, "Failed to delete the resource")

        self.resource_state.purge()
