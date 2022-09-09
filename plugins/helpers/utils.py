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
import hashlib
import json
import typing
from typing import Any, Callable, Dict

from inmanta.agent.handler import SkipResource
from inmanta.protocol.endpoints import Client
from inmanta_plugins.terraform.helpers.attribute_reference import AttributeReference
from inmanta_plugins.terraform.helpers.const import (
    INMANTA_MAGIC_KEY,
    TERRAFORM_RESOURCE_STATE_PARAMETER,
)
from inmanta_plugins.terraform.helpers.param_client import RUN_SYNC, ParamClient
from inmanta_plugins.terraform.states import generational_state_fact


def parse_resource_state(current_state: dict, block: Any) -> dict:
    """
    The purpose of this method is to filter out any of the generated attributes and None values
    that the response from a read request to the provider might contain.  In order to know if
    an attribute is generated (or computed), we need to go though the schema at the same time.
    """
    parsed_state = dict()
    key: str

    # First we iterate over the attributes of this block
    for attribute in block.attributes:
        if attribute.computed:
            # If the value is genrated by the handler, we don't want it in our state
            # as it can't possibly come from our model
            continue

        key = attribute.name
        current = current_state.get(key)

        if current is None:
            # If the current value is None we don't include it in the state
            continue

        parsed_state[key] = current

    # Then we iterate over the nested blocks of this block
    for nested_block in block.block_types:
        key = nested_block.type_name
        current = current_state.get(key)

        if current is None:
            continue

        # The different type of nesting are single, list, set and map
        # https://www.terraform.io/docs/cli/commands/providers/schema.html#block-representation
        if nested_block.nesting == 1:
            # SINGLE
            parsed_state[key] = parse_resource_state(current, nested_block.block)
        elif nested_block.nesting == 2:
            # LIST
            parsed_state[key] = [
                parse_resource_state(current_item, nested_block.block)
                for current_item in current
            ]
        elif nested_block.nesting == 3:
            # SET -> not serializable, crashes when the changes dict is flushed, use list
            parsed_state[key] = [
                parse_resource_state(current_item, nested_block.block)
                for current_item in current
            ]
        elif nested_block.nesting == 4:
            # MAP
            parsed_state[key] = {
                current_key: parse_resource_state(current_value, nested_block.block)
                for current_key, current_value in current.items()
            }

    return parsed_state


def fill_partial_state(state: dict, schema_block: Any) -> dict:
    """
    This methods takes as input a state from a resource config and a schema block.  It will
    fill all values specified in the schema block but missing from the state and default them
    to None.

    A new dict containing all original values from the state and the default None values is then returned.

    :param state: The state with some values set.
    :param schema_block: The schema of a block corresponding to this state.
    """
    if not isinstance(state, dict):
        raise Exception(
            f"Unexpected input type: a dict should be provided but got {type(state)}"
        )

    # This part handles all the attributes of the block
    base_conf: Dict[str, object] = {x.name: None for x in schema_block.attributes}
    base_conf.update(state)

    # This part handles all the nested blocks
    for nested_block_type in schema_block.block_types:
        key = nested_block_type.type_name
        state_value = state.get(key)

        # If the state doesn't contain this nested block type, we don't need to
        # fill any of the nested blocks
        if state_value is None:
            base_conf[key] = None
            continue

        # The different type of nesting are single, list, set, map and group
        # https://github.com/hashicorp/terraform/blob/main/docs/plugin-protocol/tfplugin5.2.proto#L103-L110
        # https://github.com/hashicorp/terraform/blob/main/docs/plugin-protocol/object-wire-format.md#schemanestedblock-mapping-rules-for-messagepack
        if nested_block_type.nesting in [1, 5]:
            if not isinstance(state_value, dict):
                raise Exception(
                    f"Unexpected input type: a dict should be provided but got {type(state_value)}"
                )

            # SINGLE or GROUP
            base_conf[key] = fill_partial_state(state_value, nested_block_type.block)
        elif nested_block_type.nesting in [2, 3]:
            if not isinstance(state_value, list):
                raise Exception(
                    f"Unexpected input type: a list should be provided but got {type(state_value)}"
                )

            # LIST or SET
            base_conf[key] = [
                fill_partial_state(current_item, nested_block_type.block)
                for current_item in state_value
            ]
        elif nested_block_type.nesting == 4:
            if not isinstance(state_value, dict):
                raise Exception(
                    f"Unexpected input type: a dict should be provided but got {type(state_value)}"
                )

            # MAP
            base_conf[key] = {
                current_key: fill_partial_state(current_value, nested_block_type.block)
                for current_key, current_value in state_value.items()
            }

        else:
            raise Exception(f"Unexpected schema value: {nested_block_type.nesting}")

    return base_conf


def build_resource_state(
    desired_state: Any,
    client: Client,
    run_sync: RUN_SYNC,
) -> Any:
    """
    This function explores a state dictionnary looking for attribute references.
    It returns a copy of the input state dict, with all instances of the attribute
    reference replaced with their actual value.

    :param desired_state: The input state dict.
    :param client: A client with enough permissions to get parameters from the server.
    :param run_sync: A function allowing to execute client calls synchronously.
    """
    if isinstance(desired_state, list):
        return [build_resource_state(item, client, run_sync) for item in desired_state]

    if isinstance(desired_state, dict):
        if INMANTA_MAGIC_KEY in desired_state.keys():
            attribute_reference = AttributeReference.from_dict(desired_state)
            param_client = ParamClient(
                environment=attribute_reference.environment,
                client=client,
                run_sync=run_sync,
                param_id=TERRAFORM_RESOURCE_STATE_PARAMETER,
                resource_id=attribute_reference.resource_id,
            )

            foreign_state_raw = param_client.get()
            if foreign_state_raw is None:
                raise SkipResource(
                    "Can not get an attribute from an unknown resource.  "
                    f"State of {attribute_reference.resource_id} can not be found."
                )

            state_fact = generational_state_fact.build_state_fact(
                json.loads(foreign_state_raw)
            )
            return attribute_reference.extract_from_state(state_fact.get_state())

        return {
            key: build_resource_state(item, client, run_sync)
            for key, item in desired_state.items()
        }

    return desired_state


def dict_hash(
    input: dict, default_encoder: typing.Optional[Callable[[object], object]] = None
) -> str:
    """
    Take a dict as argument and compute a hash for that dict.
    """
    s = json.dumps(input, sort_keys=True, default=default_encoder)
    hash_obj = hashlib.md5(s.encode("utf-8"))
    return hash_obj.hexdigest()
