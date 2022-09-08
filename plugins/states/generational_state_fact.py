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
"""
import abc
import datetime
import typing

import pydantic

SF = typing.TypeVar("SF", bound="StateFact")
GSF = typing.TypeVar("GSF", bound="GenerationalStateFact")


class StateFact(pydantic.BaseModel):
    @abc.abstractmethod
    def get_state(self) -> dict:
        """
        This method should be implemented for each subclass and return the dict
        holding the resource state.  This state dict directly comes from the
        terraform handler, it doesn't contain any additional information.
        """

    @abc.abstractclassmethod
    def build_from_state(cls: typing.Type[SF], state: dict) -> SF:
        """"""


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
    generation: str

    class Config:
        alias_generator = (
            lambda attribute_name: attribute_name
            if attribute_name != "generation"
            else "_generation"
        )

    @classmethod
    def build_from_state(cls: typing.Type[GSF], state: dict) -> GSF:
        return cls(**state)


class AlbatrossGenerationStateFact(StateFact):
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
