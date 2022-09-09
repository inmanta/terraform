"""
    Copyright 2022 Inmanta

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

    Module doc
    ==========

    The whole point of this generational_state_fact module is to deal with
    different versions of the state file, possibly stored in the orchestrator,
    due to an upgrade of the module while some resource where already deployed.

    The module provides:
    1.  StateFact classes, to represent the state dictionaries stored in the orchestrator.
        Those are pydantic objects, and provide a class method to reconstruct the object
        from the stored state dict.
    2.  build_state_fact function, it allows to easily reconstruct a state fact object,
        from its state fact dict.
    3.  State converters, those are functions, which will always output the same type of
        state fact, based one whatever state fact generation they received in argument.
        Those are wrapped by a decorator, state_converter, which takes as argument the
        desired output type.

    How to use it:
    --------------

    Build the state fact object from the raw dict:

        ..code-block:: python

            raw_dict: dict = ...
            state_fact = build_state_fact(raw_dict)

    Make sure the state fact object is the latest generation:

        ..code-block:: python

            # Works like this until their is a newer generation than Albatross
            state_fact = convert_to_albatross(state_fact)

    How to extend it:
    -----------------

    1.  Create a new class extending the GenerationalStateFact:

        ..code-block:: python

            class BuboGenerationStateFact(GenerationalStateFact):
                generation: str = "Bubo"
                state: dict
                config_hash: str

                def get_state(self) -> dict:
                    return self.state

    2.  Register the new generation into the state_fact_generations dict:

        ..code-block:: python

            state_fact_generations: typing.Dict[typing.Optional[str], typing.Type[StateFact]] = {
                ...,
                BuboGenerationStateFact.generation: BuboGenerationStateFact,
            }

    3.  Create the state_transfer function to upgrade to your new generation:

        ..code-block:: python

            @state_converter(BuboGenerationStateFact)
            def convert_to_albatross(
                current_state_fact: StateFact,
            ) -> typing.Optional[BuboGenerationStateFact]:
                albatross_state_fact = convert_to_albatross(current_state_fact)
                return BuboGenerationStateFact(
                    state=albatross_state_fact.state,
                    config_hash=albatross_state_fact.config_hash,
                )

"""
import abc
import datetime
import typing

import pydantic

SF = typing.TypeVar("SF", bound="StateFact")
GSF = typing.TypeVar("GSF", bound="GenerationalStateFact")
STATE_DICT_GENERATION_MARKER = "__state_dict_generation"


class StateFact(pydantic.BaseModel):
    @abc.abstractmethod
    def get_state(self) -> dict:
        """
        This method should be implemented for each subclass and returns the dict
        holding the resource state.  This state dict directly comes from the
        terraform handler, it doesn't contain any additional information.
        """

    @abc.abstractclassmethod
    def build_from_state(cls: typing.Type[SF], state: dict) -> SF:
        """
        This method should be implemented for each subclass and returns and
        instance of the subclass, constructed with the provided state dict.
        """


class LegacyStateFact(StateFact):
    """
    The legacy state fact is only composed of the state dict.
    The dict we receive as argument is then the state dict, that we can
    assign to the state attribute.
    """

    state: dict

    def get_state(self) -> dict:
        return self.state

    @classmethod
    def build_from_state(cls, state: dict) -> "LegacyStateFact":
        return cls(state=state)


class GenerationalStateFact(StateFact):
    # Setting an alias for generation attribute.  This attribute is used to recognize
    # a generational state fact amongst others.  We expect that no attribute in a terraform
    # config will ever use this as name.
    generation: str = pydantic.Field(alias=STATE_DICT_GENERATION_MARKER)

    @classmethod
    def build_from_state(cls: typing.Type[GSF], state: dict) -> GSF:
        return cls(**state)


class AlbatrossGenerationStateFact(GenerationalStateFact):
    """
    This is the first iteration on a generational approach for state dicts.
    The generation is named "Albatross" because it is an animal starting with
    letter A.  It is expected for the following generation to respect this
    scheme and pick another animal with the next letter coming in the alphabetic
    order.
    """

    generation: str = "Albatross"
    state: dict
    created_at: datetime.datetime
    updated_at: datetime.datetime
    config_hash: str

    def get_state(self) -> dict:
        return self.state


state_fact_generations: typing.Dict[typing.Optional[str], typing.Type[StateFact]] = {
    None: LegacyStateFact,
    AlbatrossGenerationStateFact.generation: AlbatrossGenerationStateFact,
}
"""
This dict holds all the generations of state dicts which were supported by the module.
It can be navigated to find which class should be used to load the state stored into
a python object.
"""


def build_state_fact(raw_state: dict) -> StateFact:
    """
    This function can be used to reconstruct a state fact object from its
    corresponding raw state dictionary..
    """

    # Get the generation attribute from the raw_state, if it is set
    generation = raw_state.get(STATE_DICT_GENERATION_MARKER)

    # Get the state fact class corresponding to this generation
    state_fact_class = state_fact_generations[generation]

    # Build the state fact and return it
    return state_fact_class.build_from_state(raw_state)


def state_converter(
    target: typing.Type[SF],
) -> typing.Callable[
    [typing.Callable[[StateFact], typing.Optional[SF]]],
    typing.Callable[[StateFact], SF],
]:
    """
    The state_converter function is a decorator to help build efficient and elegant state fact
    object converters.
    """

    def wrap_state_converter(
        state_converter: typing.Callable[[StateFact], typing.Optional[SF]]
    ) -> typing.Callable[[StateFact], SF]:
        """
        This inner function is returned when using the decorator with an argument.  This is the
        actual decorator, which received the function it decorates as argument.
        """

        def state_converter_replacement(current_state_fact: StateFact) -> SF:
            """
            This is the replacement function for the function we decorate.  It does the
            following things when called:
            1. Check whether the input matches the target type, if so, we return the input
            2. Call the converter function we replace and check its output
            2a. The output is None, we failed to do the conversion, and raise an Exception
            2b. The output is not None, it must be of the target type, we return it
            """
            if isinstance(current_state_fact, target):
                # The current state fact is the target one, no need to dig further
                return current_state_fact

            # We call the converter function
            result = state_converter(current_state_fact)
            if result is None:
                # This means the conversion has failed
                raise ValueError(
                    f"Can not convert {type(current_state_fact)} to {type(target)} using {state_converter}"
                )

            # The result is the object we wanted, we simply return it
            return result

        return state_converter_replacement

    return wrap_state_converter


@state_converter(LegacyStateFact)
def convert_to_legacy(
    current_state_fact: StateFact,
) -> typing.Optional[LegacyStateFact]:
    """
    The legacy converter is a bit special.  The only state fact we know how to handle
    if the legacy one, which will be detected by the decorator and returned directly.
    No conversion logic to add here.
    """
    return None


@state_converter(AlbatrossGenerationStateFact)
def convert_to_albatross(
    current_state_fact: StateFact,
) -> typing.Optional[AlbatrossGenerationStateFact]:
    """
    The only source state fact we know how to recover from is the legacy one.  So we
    "convert" the input state fact to the legacy one and then upgrade it.
    """
    legacy_state_fact = convert_to_legacy(current_state_fact)
    return AlbatrossGenerationStateFact(
        state=legacy_state_fact.state,
        created_at=datetime.datetime.now().astimezone(),  # Make our date timezone-aware
        updated_at=datetime.datetime.now().astimezone(),  # Make our date timezone-aware
        config_hash="",
    )
