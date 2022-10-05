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

    How to use it:
    --------------

    Build the state fact object from the raw dict:

        ..code-block:: python

            raw_dict: dict = ...
            state_fact = build_state_fact(raw_dict)

    Make sure the state fact object is the latest generation:

        ..code-block:: python

            # Works like this until their is a newer generation than Albatross
            state_fact = AlbatrossGenerationStateFact.convert(state_fact)

    How to extend it:
    -----------------

    1.  Create a new class extending the GenerationalStateFact:

        ..code-block:: python

            class BuboGenerationStateFact(GenerationalStateFact):
                state: dict
                config_hash: str

                @classmethod
                def generation(cls) -> str:
                    return "Bubo"

                @classmethod
                def _convert(cls, state: StateFact) -> typing.Optional["BuboGenerationStateFact"]:
                    albatross_state_fact = AlbatrossGenerationStateFact.convert(state)
                    return BuboGenerationStateFact(
                        state=albatross_state_fact.state,
                        config_hash=albatross_state_fact.config_hash,
                    )


    2.  Register the new generation into the state_fact_generations dict:

        ..code-block:: python

            state_fact_generations: typing.Dict[typing.Optional[str], typing.Type[StateFact]] = {
                ...,
                BuboGenerationStateFact.generation(): BuboGenerationStateFact,
            }

"""
import abc
import datetime
import typing

import pydantic
import pydantic.typing

STATE_DICT_GENERATION_MARKER = "__state_dict_generation"


class StateFact(pydantic.BaseModel):
    @abc.abstractmethod
    def get_state(self) -> dict:
        """
        This method should be implemented for each subclass and returns the dict
        holding the resource state.  This state dict directly comes from the
        terraform handler, it doesn't contain any additional information.
        """

    @classmethod
    @abc.abstractmethod
    def build_from_state(cls: typing.Type["SF"], state: dict) -> "SF":
        """
        This method should be implemented for each subclass and returns and
        instance of the subclass, constructed with the provided state dict.
        """

    @classmethod
    @abc.abstractmethod
    def _convert(cls: typing.Type["SF"], state: "StateFact") -> typing.Optional["SF"]:
        """
        Convert any input state received in argument to this class type of state.
        If the conversion is not possible, it should return None or raise a ValueError.
        """

    @classmethod
    def convert(cls: typing.Type["SF"], state: "StateFact") -> "SF":
        if isinstance(state, cls):
            # The current state fact is the targeted one, no need to dig further
            return state

        # We call the converter function
        result = cls._convert(state)
        if result is None:
            # This means the conversion has failed
            raise ValueError(f"Can not convert {type(state)} to {cls}.")

        # The result is the object we wanted, we simply return it
        return result


SF = typing.TypeVar("SF", bound=StateFact)


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
    def build_from_state(cls: typing.Type["SF"], state: dict) -> "SF":
        return cls(state=state)

    @classmethod
    def _convert(cls: typing.Type["SF"], state: "StateFact") -> typing.Optional["SF"]:
        """
        The legacy state fact should not be the desired type for any conversion
        """
        return None


class GenerationalStateFact(StateFact):
    @classmethod
    @abc.abstractmethod
    def generation(cls) -> str:
        """
        Should be implemented by the subclass, and return the generation identifier
        """

    def _iter(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> "pydantic.typing.TupleGenerator":
        """
        We overwrite the _iter method simply to add our generation marker to the
        generated dict or json payload.
        """
        for x in super()._iter(*args, **kwargs):
            yield x

        yield STATE_DICT_GENERATION_MARKER, self.generation()

    @classmethod
    def build_from_state(cls: typing.Type["GSF"], state: dict) -> "GSF":
        state_generation = state[STATE_DICT_GENERATION_MARKER]
        if not state_generation == cls.generation():
            # Actively check that the state dict is of the correct generation
            raise ValueError(
                f"Unexpected generation value: {state_generation} != {cls.generation()}"
            )

        return cls(**state)


GSF = typing.TypeVar("GSF", bound=GenerationalStateFact)


class AlbatrossGenerationStateFact(GenerationalStateFact):
    """
    This is the first iteration on a generational approach for state dicts.
    The generation is named "Albatross" because it is an animal starting with
    letter A.  It is expected for the following generation to respect this
    scheme and pick another animal with the next letter coming in the alphabetic
    order.
    """

    state: dict
    created_at: datetime.datetime
    updated_at: datetime.datetime
    config_hash: str

    def get_state(self) -> dict:
        return self.state

    @classmethod
    def generation(cls) -> str:
        return "Albatross"

    @classmethod
    def _convert(
        cls, state: StateFact
    ) -> typing.Optional["AlbatrossGenerationStateFact"]:
        """
        The only source state fact we know how to recover from is the legacy one.  So we
        "convert" the input state fact to the legacy one and then upgrade it.

        The config hash we set here is empty, this is because:
        1. We can not derive the config hash from the state dict, it should be done by hashing
            the desired config dict that was sent to the provider when we received this state
            dict back.  This comes from a previous model version so there is no way we can
            get it now.
        2. The config hash is a safety guarantee that tells whoever accesses the state, that if
            the hash of their desired config matches this one, the state that comes along with
            the hash can safely be used.  Without a hash we can not offer this guarantee, so the
            hash we "fake" having is one that will never be valid.

        In pratice, this means that when a state that required conversion is accessed in the model
        by through the terraform.safe_resource_state plugin, it will always be unknown, even if the
        resource the state is originating from is already deployed.  The unknown will only be resolved
        after the next deployment of the resource, once the handler code has been updated to use the
        new state version.
        """
        legacy_state_fact = LegacyStateFact.convert(state)
        return AlbatrossGenerationStateFact(
            state=legacy_state_fact.state,
            created_at=datetime.datetime.now().astimezone(),  # Make our date timezone-aware
            updated_at=datetime.datetime.now().astimezone(),  # Make our date timezone-aware
            config_hash="",
        )


state_fact_generations: typing.Dict[typing.Optional[str], typing.Type[StateFact]] = {
    None: LegacyStateFact,
    AlbatrossGenerationStateFact.generation(): AlbatrossGenerationStateFact,
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
