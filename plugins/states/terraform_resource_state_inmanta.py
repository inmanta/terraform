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
import base64
import json
from pathlib import Path
from typing import Optional

from inmanta_plugins.terraform.helpers.param_client import ParamClient
from inmanta_plugins.terraform.tf.terraform_resource_state import TerraformResourceState


class TerraformResourceStateInmanta(TerraformResourceState):
    """
    This terraform resource state object allows the resource to have a resilient state
    storage, so that it does not get lost between program execution.  It is meant to be
    used with an Inmanta orchestrator.  It stores the private value into a local file
    and the state in the parameters of the orchestrator.
    """

    def __init__(
        self,
        type_name: str,
        *,
        private_file_path: str,
        param_client: ParamClient,
        private: Optional[bytes] = None,
        state: Optional[dict] = None,
    ) -> None:
        """
        :attr type_name: The name that the provider give to this resource
        :attr private_file_path: A path to a file (existing or not) that can be used
            to store the private value of the resource.
        :attr param_client: A client that can be used to store the resource state in
            the orchestrator parameters.
        :attr private: An initial private value for this resource
        :attr state: An initial state for this resource
        """
        super().__init__(
            type_name=type_name,
            resource_id=param_client.resource_id,
            private=private,
            state=state,
        )
        self._private_file_path = Path(private_file_path)
        self._param_client = param_client

    @property
    def private(self) -> Optional[bytes]:
        """
        The private is any bytes value that the provider might give us, for giving it back on the next
        interaction with it.
        We store this in a local file, and cache it in a variable, only reading the file if the variable
        if None.  This means that the value seen by this object can only be altered by this object.
        """
        if self._private is None and self._private_file_path.exists():
            self._private = base64.b64decode(self._private_file_path.read_bytes())

        return self._private

    @property
    def state(self) -> Optional[dict]:
        """
        The state is a dictionary containing the current state of the resource.  It is stored in a parameter
        on the server.  When this property is called, we only request the parameter from the server if the
        cached value is None.  This means that the value seen by this object can only be altered by this object.
        """
        if self._state is None:
            param_value = self._param_client.get()
            if param_value is not None:
                self._state = json.loads(param_value)

        return self._state

    @private.setter
    def private(self, value: bytes) -> None:
        """
        Every time a new value for the private is set, we save it in the private file.  And update the cached value.
        """
        self._private_file_path.parent.mkdir(parents=True, exist_ok=True)
        self._private_file_path.write_bytes(base64.b64encode(value))

        self._private = value

    @state.setter
    def state(self, value: dict) -> None:
        """
        Every time a new value for the state is set, we save it in the parameter corresponding to it. And update
        the cached value.
        """
        self._param_client.set(json.dumps(value))

        self._state = value

    def purge(self) -> None:
        """
        If the resource is purged, we should also purge all traces of it, that means:
         - remove the private file
         - delete the parameter containing the state
        """
        super().purge()
        self._param_client.delete()
        if self._private_file_path.exists():
            self._private_file_path.unlink()
