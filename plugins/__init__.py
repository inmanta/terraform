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
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import inmanta.resources
from inmanta.ast import OptionalValueException
from inmanta.config import Config
from inmanta.execute.proxy import DynamicProxy, SequenceProxy
from inmanta.execute.util import Unknown
from inmanta.export import unknown_parameters
from inmanta.plugins import Context, PluginException, plugin
from inmanta_plugins.terraform.helpers.attribute_reference import AttributeReference
from inmanta_plugins.terraform.helpers.const import TERRAFORM_RESOURCE_STATE_PARAMETER
from inmanta_plugins.terraform.helpers.param_client import ParamClient

LOGGER = logging.getLogger(__name__)


# This dict contains all resource parameter already queried for this compile run.
# This avoids getting them multiple times if multiple entities use them.
resource_states: Dict[str, Dict] = dict()


def inmanta_reset_state() -> None:
    # Resetting the resource states dict between compiles
    global resource_states
    resource_states = dict()


def resource_attribute_reference(
    resource: DynamicProxy,  # type: ignore
    attribute_path: SequenceProxy,  # type: ignore
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
    resource: "terraform::Resource",  # type: ignore
    attribute_path: "any",  # type: ignore
) -> "any":  # type: ignore
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
        run_sync=lambda func: context.run_sync(func),  # type: ignore
        param_id=TERRAFORM_RESOURCE_STATE_PARAMETER,
        resource_id=attribute_reference.resource_id,
    )

    resource_state_raw: Optional[str] = param_client.get()
    if resource_state_raw is None:
        unknown_parameters.append(
            {
                "resource": attribute_reference.resource_id,
                "parameter": TERRAFORM_RESOURCE_STATE_PARAMETER,
                "source": "fact",
            }
        )
        return Unknown(source=resource)

    resource_state = json.loads(resource_state_raw)
    resource_states.setdefault(attribute_reference.resource_id, resource_state)

    try:
        return attribute_reference.extract_from_state(resource_state)
    except ValueError as e:
        raise PluginException(str(e))


@plugin
def get_resource_attribute_ref(
    resource: "terraform::Resource",  # type: ignore
    attribute_path: "any",  # type: ignore
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


@plugin
def serialize_config(config_block: "terraform::config::Block") -> "dict":  # type: ignore
    """
    Serialize a config block into a dictionnary.
    """
    for child in config_block.children:
        # access all required attributes to let the compiler know we need them
        child.name
        child._config

    # Build the base dict, containing all the attribute of this block
    d = {k: v for k, v in config_block.attributes.items()}

    sets: Dict[str, List[Any]] = defaultdict(list)
    lists: Dict[str, Dict[str, Any]] = defaultdict(dict)
    dicts: Dict[str, Dict[str, Any]] = defaultdict(dict)

    # For each children, we pick up the config and attach it to this dict.
    # Depending on the nesting_mode of the child, the way we attach the config will vary.
    for child in config_block.children:
        if child.nesting_mode == "single":
            if child.name in d:
                raise PluginException(
                    f"Key {child.name} is already used in the config: {d}"
                )

            d[child.name] = child._config

        elif child.nesting_mode == "set":
            sets[child.name].append(child._config)

        elif child.nesting_mode == "list":
            if child.key is None:
                raise PluginException("Nesting type dict requires the key to be set")

            if child.key in lists[child.name]:
                raise PluginException(
                    f"Can not set key-value pair {child.key}={child._config} as key is already "
                    f"used in {lists[child.name]}"
                )

            lists[child.name][child.key] = child._config

        elif child.nesting_mode == "dict":
            if child.key is None:
                raise PluginException("Nesting type dict requires the key to be set")

            if child.key in dicts[child.name]:
                raise PluginException(
                    f"Can not set key-value pair {child.key}={child._config} as key is already "
                    f"used in {dicts[child.name]}"
                )

            dicts[child.name][child.key] = child._config

        else:
            raise PluginException(f"Uknown nesting type: {child.nesting_mode}")

    # Check for all the dicts we will join that the keys sets don't intersect
    dict_sets: List[Tuple[str, dict]] = [
        ("single", d),
        ("sets", sets),
        ("lists", lists),
        ("dicts", dicts),
    ]
    for dict_set_name_a, dict_set_a in dict_sets:
        for dict_set_name_b, dict_set_b in dict_sets:
            if dict_set_name_a >= dict_set_name_b:
                # We don't want to compare a set against itself
                # We don't want to compare sets twice either
                continue

            intersection = set(dict_set_a.keys()) & set(dict_set_b.keys())
            if intersection:
                raise PluginException(
                    f"The keys {intersection} are present in two part of the config with "
                    f"unmatching types: {dict_set_name_a}={dict_set_a} "
                    f"and {dict_set_name_b}={dict_set_b}"
                )

    # Add all the unordered lists (sets) to the config
    for key, s in sets.items():
        d[key] = s

    # Add all the ordered lists to the config
    for key, l in lists.items():
        sorted_l = sorted(((k, v) for k, v in l.items()), key=lambda x: x[0])
        d[key] = [x[1] for x in sorted_l]

    # Add all the dicts to the config
    for key, dd in dicts.items():
        d[key] = dd

    return d


@plugin
def deprecated_config_block(config_block: "terraform::config::Block") -> None:  # type: ignore
    """
    Log a warning for the usage of a deprecated config block
    """
    config_path = []
    block = config_block
    while block is not None:
        config_path.append(block.name)

        try:
            block = block.parent
        except OptionalValueException:
            block = None

    config_path_str = ".".join(reversed(config_path))

    LOGGER.warning(
        f"The usage of config '{config_path_str}' at {config_block._get_instance().location} is deprecated"
    )
