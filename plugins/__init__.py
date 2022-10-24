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
import warnings
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import inmanta.resources
from inmanta.ast import OptionalValueException
from inmanta.config import Config
from inmanta.execute.proxy import DictProxy, DynamicProxy, SequenceProxy
from inmanta.execute.util import Unknown
from inmanta.export import unknown_parameters
from inmanta.plugins import Context, PluginException, plugin
from inmanta.util import api_boundary_json_encoder
from inmanta_plugins.terraform.helpers import utils
from inmanta_plugins.terraform.helpers.attribute_reference import AttributeReference
from inmanta_plugins.terraform.helpers.const import TERRAFORM_RESOURCE_STATE_PARAMETER
from inmanta_plugins.terraform.helpers.param_client import ParamClient
from inmanta_plugins.terraform.states import generational_state_fact

LOGGER = logging.getLogger(__name__)


# This dict contains all resource state parameter already queried for this compile run.
# This avoids getting them multiple times if multiple entities use them.
resource_states: dict[str, dict] = dict()


class UnknownStateException(RuntimeError):
    """
    This exception is raised whenever we try to get a state dict from the orchestrator
    parameters, but it can't be found.  This should always be handled plugins, it should
    not be exposed to the model.
    """

    def __init__(self, unknown: Unknown) -> None:
        self.unknown = unknown


def inmanta_reset_state() -> None:
    # Resetting the resource states and configs dict between compiles
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

    for attribute in attribute_path:  # type: ignore
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
        attribute_path=list(attribute_path),  # type: ignore
    )


def get_last_resource_parameter(
    context: Context, resource: DynamicProxy, param_id: str, cache_dict: dict[str, dict]
) -> dict:
    """
    Helper method to get the dict params from server or cache (if it is there).

    :returns: The state dict found in parameters
    :raises: UnknownStateException if the state dict is not found in parameters
    """
    resource_id = inmanta.resources.to_id(resource)
    if resource_id is None:
        raise PluginException(
            f"Can not resolve the id for entity {resource}.  Is it a resource?"
        )

    cached_parameter_dict = cache_dict.get(resource_id)
    if cached_parameter_dict is not None:
        return cached_parameter_dict

    environment = Config.get("config", "environment", None)
    if environment is None:
        raise PluginException(
            "The environment for this model should be configured at this point"
        )

    # Cache miss, we continue
    param_client = ParamClient(
        environment=environment,
        client=context.get_client(),
        run_sync=lambda func: context.run_sync(func),  # type: ignore
        param_id=param_id,
        resource_id=resource_id,
    )

    resource_config_raw: Optional[str] = param_client.get()
    if resource_config_raw is None:
        unknown_parameters.append(
            {
                "resource": resource_id,
                "parameter": param_id,
                "source": "fact",
            }
        )
        LOGGER.debug(
            f"Can not find a state for resource {inmanta.resources.to_id(resource)} in environment {environment}"
        )
        raise UnknownStateException(Unknown(source=resource))

    resource_parameter_dict = json.loads(resource_config_raw)
    cache_dict.setdefault(resource_id, resource_parameter_dict)

    return resource_parameter_dict


def get_last_resource_state(
    context: Context,
    resource: DynamicProxy,  # type: ignore
) -> generational_state_fact.StateFact:
    """
    Get the last version of the state of a resource.  This is the version which
    got deployed in the latest deployment of the resource.
    """
    global resource_states

    param = get_last_resource_parameter(
        context=context,
        resource=resource,
        param_id=TERRAFORM_RESOURCE_STATE_PARAMETER,
        cache_dict=resource_states,
    )

    # Build the state fact object
    return generational_state_fact.build_state_fact(param)


@plugin
def get_resource_attribute(
    context: Context,
    resource: "terraform::Resource",  # type: ignore
    attribute_path: "any",  # type: ignore
) -> "any":  # type: ignore
    """
    Get a resource attribute from the saved parameters (facts).

    Disclaimer: Whatever comes out of this method might not be very safe to use,
        as it might be out of sync with the current state of the model.
        i.e. If you access here the id of a file, which is modified in the same
            model, the id you will receive will be the one of the previous file
            not the one deployed in this model.
        It is safer to use safe_resource_state plugin.

    :param resource: The resource we which to get an attribute from.
    :param attribute_path: The path, in the resource state dict, to the desired value.
    """
    try:
        resource_state_wrapper = get_last_resource_state(
            context=context,
            resource=resource,
        )
    except UnknownStateException as e:
        return e.unknown

    resource_state = resource_state_wrapper.get_state()
    attribute_reference = resource_attribute_reference(resource, attribute_path)
    return attribute_reference.extract_from_state(resource_state)


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

    lists: Dict[str, Dict[str, Any]] = defaultdict(dict)
    dicts: Dict[str, Dict[str, Any]] = defaultdict(dict)

    # For each children, we pick up the config and attach it to this dict.
    # Depending on the nesting_mode of the child, the way we attach the config will vary.
    for child in config_block.children:
        if child.name is None:
            raise PluginException("A child config block can not have a null name")

        if child.nesting_mode == "single":
            if child.name in d:
                raise PluginException(
                    f"Key {child.name} is already used in the config: {d}"
                )

            d[child.name] = child._config

        elif child.nesting_mode in ["set", "list"]:
            # We will consider each set as a list, sorted with the generated key
            # This allows us to generate the config consistently
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
            raise PluginException(f"Unknown nesting type: {child.nesting_mode}")

    # Check for all the dicts we will join that the keys sets don't intersect
    dict_sets: List[Tuple[str, dict]] = [
        ("single", d),
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

    # Add all the ordered lists to the config
    for key, l in lists.items():
        sorted_l = sorted(((k, v) for k, v in l.items()), key=lambda x: x[0])
        d[key] = [x[1] for x in sorted_l]

    # Add all the dicts to the config
    for key, dd in dicts.items():
        d[key] = dd

    return d


@plugin
def safe_resource_state(
    context: Context,
    resource: "terraform::Resource",  # type: ignore
) -> "dict":
    """
    Get the state dict of a resource and check whether the current config of
    the resource has changed since the state was published.  If this is the
    case, raise an Unknown value, as the state is out of sync and is dangerous
    to use.
    """
    try:
        previous_state_wrapper = get_last_resource_state(context, resource)
    except UnknownStateException as e:
        return e.unknown  # type: ignore

    current_config_hash = utils.dict_hash(
        resource.config, default_encoder=api_boundary_json_encoder
    )
    if (
        generational_state_fact.AlbatrossGenerationStateFact.convert(
            previous_state_wrapper
        ).config_hash
        != current_config_hash
    ):
        # The config and the state we have in cache are out of sync, it is
        # unsafe to use, so we return an Unknown
        LOGGER.debug(
            f"Config hash for {inmanta.resources.to_id(resource)} (={current_config_hash}) doesn't match the current state"
        )
        return Unknown(source=resource)  # type: ignore

    # We can safely get the state
    return previous_state_wrapper.get_state()


@plugin
def extract_state(parent_state: "dict", config: "terraform::config::Block") -> "dict":  # type: ignore
    """
    Extract the state corresponding to the provided config block from the parent state.
    This method should only be used with a state originating from the safe_resource_state
    plugin.

    :param state: The parent state dict, it should include our config at key config.name
    :param config: The config block we want to find the matching config for.
    """
    if config.name is None:
        raise PluginException("Can not extract the config for the root config block")

    state_container = parent_state[config.name]

    if config.nesting_mode == "single":
        # Single embedded block, we can simply pick the the block in the state
        return state_container  # type: ignore

    if config.nesting_mode == "dict":
        # Block embedded in a dict, we need to take the block at key config.key
        # in the dict
        if not isinstance(state_container, DictProxy):
            raise PluginException(
                f"The state dict has an unexpected value at key {config.name}: "
                f"{state_container} ({type(state_container)}).  State dict is "
                f"{parent_state} ({type(parent_state)})"
            )

        return state_container[config.key]  # type: ignore

    if config.nesting_mode == "list":
        # Block embedded in a list, the list should be sorted using the key, and
        # we should take the element in the state_container list at the same position
        # as our config block in the global config
        if not isinstance(state_container, SequenceProxy):
            raise PluginException(
                f"The state dict has an unexpected value at key {config.name}: "
                f"{state_container} ({type(state_container)}).  State dict is "
                f"{parent_state} ({type(parent_state)})"
            )

        # This is the key of our config
        config_key = config.key

        parent_config = config.parent
        sibling_configs = parent_config.children

        # These are all the config keys, sorted (the state should be sorted the same way)
        config_keys = sorted(c.key for c in sibling_configs if c.name == config.name)

        # Sanity check, the state_container should have the same length as our configs
        if not len(state_container) == len(config_keys):
            raise PluginException(
                "The length of the state list doesn't match the number of config blocks there is.  "
                f"state={state_container}, config_keys={config_keys}"
            )

        config_position = config_keys.index(config_key)
        return state_container[config_position]  # type: ignore

    if config.nesting_mode == "set":
        # Block embedded in a set, the matching state might be anywhere.  To find it,
        # we rely on the fact that the config dict is a subset of the state dict.  We
        # check for each element in the list, which one wouldn't we changed it we
        # updated it with our config, that one should be our state.
        if not isinstance(state_container, SequenceProxy):
            raise PluginException(
                f"The state dict has an unexpected value at key {config.name}: "
                f"{state_container} ({type(state_container)}).  State dict is "
                f"{parent_state} ({type(parent_state)})"
            )

        # This is our attributes dict, minus all the default (null) values
        # We don't consider values which are not attributes
        clean_config = {k: v for k, v in config.attributes.items() if v is not None}

        matching_states: list[DictProxy] = []
        for candidate_state in state_container:  # type: ignore
            state = {k: v for k, v in candidate_state.items()}
            for key, value in clean_config.items():
                state[key] = value

            if state == candidate_state:
                matching_states.append(candidate_state)

        if len(matching_states) != 1:
            warnings.warn(
                Warning(
                    f"Failed to find a unique matching state in the list {state_container} for config "
                    f"{clean_config}.  Got a total of {len(matching_states)} in {matching_states}"
                )
            )
            return Unknown(object())  # type: ignore

        return matching_states[0]  # type: ignore

    raise PluginException(f"Unknown nesting mode: {config.nesting_mode}")


@plugin
def deprecated_config_block(config_block: "terraform::config::Block") -> None:  # type: ignore
    """
    Log a warning for the usage of a deprecated config block
    """
    config_path = []
    block = config_block
    while block is not None:
        config_path.append(block.name or "")

        try:
            block = block.parent
        except OptionalValueException:
            block = None

    config_path_str = ".".join(reversed(config_path))

    warnings.warn(
        DeprecationWarning(
            f"The usage of config '{config_path_str}' at {config_block._get_instance().location} is deprecated"
        )
    )


@plugin
def dict_hash(input: "dict") -> "string":  # type: ignore
    return utils.dict_hash(input, api_boundary_json_encoder)


@plugin
def sorted_list(input_list: "list") -> "list":
    return sorted(input_list)
