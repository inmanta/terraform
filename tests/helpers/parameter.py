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
import os
from abc import abstractclassmethod
from typing import Generic, Optional, TypeVar

from _pytest.config import Config

ParameterType = TypeVar("ParameterType", bound=object)


class ParameterNotSetException(ValueError):
    pass


class TestParameter(Generic[ParameterType]):
    """
    This class represents a parameter that can be passed to the tests, either via a pytest
    argument, or via an environment variable.
    """

    def __init__(
        self,
        argument: str,
        environment_variable: str,
        usage: str,
        default: Optional[ParameterType] = None,
    ) -> None:
        """
        :param argument: This is the argument that can be passed to the pytest command.
        :param environment_variable: This is the name of the environment variable in which
            the value can be stored.
        :param usage: This is a small description of what the parameter value will be used for.
        :param default: This is the default value to provide if the parameter is resolved but
            hasn't been set.
        """
        self.argument = argument
        self.environment_variable = environment_variable
        self.usage = usage
        self.default = default

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
        of the received value.  It is up to the class extending this one to convert
        it to whatever value it wants.
        """

    def resolve(self, config: Config) -> ParameterType:
        """
        Resolve the test parameter.
        First, we try to get it from the provided options.
        Second, we try to get it from environment variables.
        Then, if there is a default, we use it.
        Finally, if none of the above worked, we raise a ParameterNotSetException.
        """
        option = config.getoption(self.argument, default=self.default)
        if option is not None and option is not self.default:
            # A value is set, and it is not the default one
            return self.validate(str(option))

        env_var = os.getenv(self.environment_variable)
        if env_var is not None:
            # A value is set
            return self.validate(env_var)

        if self.default is not None:
            return self.default

        raise ParameterNotSetException(
            f"Couldn't resolve a test parameter.  "
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

    def __init__(
        self, argument: str, environment_variable: str, usage: str, default=False
    ) -> None:
        super().__init__(argument, environment_variable, usage, default)

    @property
    def action(self) -> str:
        if self.default is True:
            return "store_false"

        return "store_true"

    @classmethod
    def validate(cls, raw_value: str) -> bool:
        parsed = raw_value.lower().strip()
        if parsed == "false":
            return False

        if parsed == "true":
            return True

        raise ValueError("Boolean env var should be set to either 'true' or 'false'")
