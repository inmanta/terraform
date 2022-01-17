"""
    :copyright: 2021 Inmanta
    :contact: code@inmanta.com
    :license: Inmanta EULA
"""

from abc import abstractclassmethod
import os
from typing import Any, Generic, List, Optional, TypeVar

from _pytest.config import Config
from _pytest.config.argparsing import Parser
from pydantic import BaseModel


all_parameters: List["TestParameter"] = []
"""
This list will holds all test parameters, as they will add themself here on creation
"""


def pytest_addoption(parser: Parser) -> None:
    """
    Setting up all test parameters in one go
    """
    group = parser.getgroup(
        "terraform", description="Terraform module testing options"
    )
    for param in all_parameters:
        group.addoption(
            param.argument,
            action=param.action,
            help=param.help,
            dest=param.key,
        )


ParameterType = TypeVar("ParameterType", object)


class TestParameter(Generic[ParameterType], BaseModel):
    """
    This class represents a parameter that can be passed to the tests, either via a pytest
    argument, or via an environment variable.
    """

    argument: str
    """
    This is the argument that can be passed to the pytest command.
    """

    environment_variable: str
    """
    This is the name of the environment variable in which the value can be stored.
    """

    usage: str
    """
    This is a small description of what the parameter value will be used for.
    """

    key: str
    """
    This is a unique value, used to identify the parameter.
    """

    default: Optional[ParameterType] = None
    """
    This is the default value to provide if the parameter is resolved but hasn't been set.
    """

    def __init__(__pydantic_self__, **data: Any) -> None:
        super().__init__(**data)

        # Registering this test parameter, this will then be automatically added to pytest options
        all_parameters.append(__pydantic_self__)

    @property
    def help(self) -> str:
        """
        Build up a help message, based on the usage, default value and environment variable name.
        """
        additional_messages = [f"overrides {self.environment_variable}"]
        if self.default is not None:
            additional_messages.append(f"defaults to {self.default}")

        return self.usage + f" ({', '.join(additional_messages)})"

    @property
    def action(self) -> str:
        """
        The argparse action for this option
        https://docs.python.org/3/library/argparse.html
        """
        return "store"

    @classmethod
    @abstractclassmethod
    def validate(cls, raw_value: str) -> ParameterType:
        """
        This method is called when any value is received from parameters or
        env variables.  It is given in the raw_value argument a string conversion
        of tge received value.  It is up to the class extending this one to convert
        it to whatever value it wants.
        """

    def resolve(self, config: Config) -> ParameterType:
        """
        Resolve the test parameter.
        First, we try to get it from the provided options.
        Second, we try to get it from environment variables.
        Then, if there is a default, we use it.
        Finally, if none of the above worked, we raise an Exception.
        """
        option = config.getoption(self.key, default=None)
        if option is not None:
            return self.validate(str(option))

        env_var = os.getenv(self.environment_variable)
        if env_var is not None:
            return self.validate(env_var)

        if self.default is not None:
            return self.default

        raise Exception(
            f"Couldn't resolve a test parameter: {self.key}.  "
            f"You can set it using {self.argument} argument or "
            f"{self.environment_variable} environment variable."
        )


class StringTestParameter(TestParameter[str]):
    """
    A test parameter that should contain a string value
    """

    @classmethod
    def validate(cls, raw_value: str) -> str:
        return raw_value


class IntegerTestParameter(TestParameter[int]):
    """
    A test parameter that should contain an integer value
    """

    @classmethod
    def validate(cls, raw_value: str) -> int:
        return int(raw_value)


class BooleanTestParameter(TestParameter[bool]):
    """
    A test parameter that should contain a boolean value
    """

    default = False
    """
    If the value is not set, the value is False
    """

    @property
    def action(self) -> str:
        return "store_true"

    @classmethod
    def validate(cls, raw_value: str) -> bool:
        return raw_value.lower() != "false"
