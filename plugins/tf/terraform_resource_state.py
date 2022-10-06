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
from typing import Optional


class TerraformResourceState:
    """
    This class stores the minimal information required to interact with the terraform
    provider reliably.  This simple implementation keeps everything in memory, so it is
    not resilient.  Other implementations can store and load the data from file or to
    the orchestrator so that we don't loose trace of our resource between runs of the
    program.
    The class can be extended to create a compatibility layer with any persistent storage
    solution.
    """

    def __init__(
        self,
        type_name: str,
        resource_id: str,
        *,
        private: Optional[bytes] = None,
        state: Optional[dict] = None,
    ) -> None:
        """
        :attr type_name: The name that the provider give to this resource
        :attr resource_id: The unique identifier used internally to designate this resource
        :attr private: An initial private value for this resource
        :attr state: An initial state for this resource
        """
        self._type_name = type_name
        self._resource_id = resource_id

        self._private: Optional[bytes] = None
        if private is not None:
            self.private = private  # type: ignore

        self._state: Optional[dict] = None
        if state is not None:
            self.state = state  # type: ignore

    @property
    def type_name(self) -> str:
        """
        This is the name that the provider give to this resource
        """
        return self._type_name

    @property
    def resource_id(self) -> str:
        """
        The unique identifier of the resource this object is holding the state of
        """
        return self._resource_id

    @property
    def private(self) -> Optional[bytes]:
        """
        The private is any bytes value that the provider might give us, for giving it back on the next
        interaction with it.
        """
        return self._private

    @property
    def state(self) -> Optional[dict]:
        """
        The state is a dictionary containing the current state of the resource.
        """
        return self._state

    @private.setter  # type: ignore
    def private(self, value: bytes) -> None:
        """
        Set a new private value for the resource.
        """
        self._private = value

    @state.setter  # type: ignore
    def state(self, value: dict) -> None:
        """
        Set a new state for the resource.
        """
        self._state = value

    def purge(self) -> None:
        """
        If the resource is purged, we should also purge all traces of it, so we clean up
        the private and state value stored.
        """
        self._private = None
        self._state = None

    def raise_if_not_complete(self) -> None:
        if self.private is None:
            raise Exception("The private value of the resource is not set")

        if self.state is None:
            raise Exception("The state of the resource is not set")
