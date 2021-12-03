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


class TerraformResourceState:
    def __init__(
        self,
        private_file_path: str,
        param_client: ParamClient,
        type_name: str,
        private: Optional[bytes] = None,
        state: Optional[dict] = None,
    ) -> None:
        self._private_file_path = private_file_path
        self._param_client = param_client
        self._type_name = type_name
        self._private = private
        self._state = state

    @property
    def private_file_path(self) -> str:
        """
        This is the path to the file where the private value is saved
        """
        return self._private_file_path

    @property
    def type_name(self) -> str:
        """
        This is the name that the provider give to this resource
        """
        return self._type_name

    @property
    def resource_id(self) -> str:
        return self._param_client.resource_id

    @property
    def private(self) -> Optional[bytes]:
        """
        The private is any bytes value that the provider might give us, for giving it back on the next
        interaction with it.
        We store this in a local file, and cache it in a variable, only reading the file if the variable
        if None.  This means that the value seen by this object can only be altered by this object.
        """
        if self._private is None:
            p = Path(self.private_file_path)
            if p.exists():
                with open(str(p), "r") as f:
                    # Encoding the bytes in base64 to make the file human readable
                    self._private = base64.b64decode(f.readline())
                    f.close()

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
        with open(self.private_file_path, "w") as f:
            f.write(base64.b64encode(value).decode("ascii"))
            f.close()

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
        self._private = None
        self._state = None
        self._param_client.delete()
        p = Path(self.private_file_path)
        if p.exists():
            p.unlink()

    def raise_if_not_complete(self) -> None:
        if self.private is None:
            raise Exception("The private value of the resource is not set")

        if self.state is None:
            raise Exception("The state of the resource is not set")
