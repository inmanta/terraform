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
from typing import Dict, Optional

from inmanta_plugins.terraform.helpers.attribute_reference import AttributeReference
from inmanta_plugins.terraform.helpers.const import TERRAFORM_RESOURCE_STATE_PARAMETER
from inmanta_plugins.terraform.helpers.param_client import ParamClient

import inmanta.resources
from inmanta.config import Config
from inmanta.execute.proxy import SequenceProxy
from inmanta.execute.util import Unknown
from inmanta.export import unknown_parameters
from inmanta.plugins import Context, PluginException, plugin

# This dict contains all resource parameter already queried for this compile run.
# This avoids getting them multiple times if multiple entities use them.
resource_states: Dict[str, Dict] = dict()


def inmanta_reset_state() -> None:
    # Resetting the resource states dict between compiles
    global resource_states
    resource_states = dict()


def resource_attribute_reference(
    resource: "terraform::Resource",
    attribute_path: "any",
) -> AttributeReference:
    resource_id = inmanta.resources.to_id(resource)
    if resource_id is None:
        raise PluginException("Couldn't resolve the id for the provided resource")

    environment = Config.get("config", "environment", None)
    if environment is None:
        raise PluginException(
            "The environment for this model should be configured at this point"
        )

    if not isinstance(attribute_path, SequenceProxy):
        raise PluginException(
            f"The plugin path should be a list but type is {type(attribute_path)}"
        )

    for attribute in attribute_path:
        if isinstance(attribute, str):
            continue

        if isinstance(attribute, int):
            continue

        raise PluginException(
            f"Element in attribute path has an invalid type: {type(attribute)}"
        )

    return AttributeReference(
        environment=environment,
        resource_id=resource_id,
        attribute_path=list(attribute_path),
    )


@plugin
def get_resource_attribute(
    context: Context,
    resource: "terraform::Resource",
    attribute_path: "any",
) -> "any":
    """
    Get a resource attribute from the saved parameters (facts).
    :param resource: The resource we which to get an attribute from.
    :param attribute_path: The path, in the resource state dict, to the desired value.
    """
    global resource_states

    attribute_reference = resource_attribute_reference(resource, attribute_path)

    # Trying to get resource value from cache to avoid unnecessary api calls
    cached_state = resource_states.get(attribute_reference.resource_id)
    if cached_state is not None:
        # Cache hit, we get the attribute value and return it
        try:
            return attribute_reference.extract_from_state(cached_state)
        except ValueError as e:
            raise PluginException(str(e))

    # Cache miss, we continue
    param_client = ParamClient(
        environment=attribute_reference.environment,
        client=context.get_client(),
        run_sync=lambda func: context.run_sync(func),
        param_id=TERRAFORM_RESOURCE_STATE_PARAMETER,
        resource_id=attribute_reference.resource_id,
    )

    resource_state: Optional[str] = param_client.get()
    if resource_state is None:
        unknown_parameters.append(
            {
                "resource": attribute_reference.resource_id,
                "parameter": TERRAFORM_RESOURCE_STATE_PARAMETER,
                "source": "fact",
            }
        )
        return Unknown(source=resource)

    resource_state: dict = json.loads(resource_state)
    resource_states.setdefault(attribute_reference.resource_id, resource_state)

    try:
        return attribute_reference.extract_from_state(resource_state)
    except ValueError as e:
        raise PluginException(str(e))


@plugin
def get_resource_attribute_ref(
    resource: "terraform::Resource",
    attribute_path: "any",
) -> "dict":
    """
    Get a resource attribute reference.  The difference with get_resource_attribute is that
    the value is not resolved at compile time but during the handler execution.
    This means that:
        1. The value can not be manipulated in the model.
        2. We save some time during the compile as we don't need to make api calls.
        3. We avoid multiple recompile due to unknown values.
        4. If the targeted value changes, but none of the other attributes of this
            resource, we will need a full deploy to have our value up to date.
    :param resource: The resource we which to get an attribute from.
    :param attribute_path: The path, in the resource state dict, to the desired value.
    """
    return resource_attribute_reference(resource, attribute_path).to_dict()
