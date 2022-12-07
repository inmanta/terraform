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
from typing import Any, Callable, Coroutine, Optional, TypeVar

from inmanta.const import ParameterSource
from inmanta.protocol import Client
from inmanta.protocol.common import Result

T = TypeVar("T")
RUN_SYNC = Callable[[Callable[[], Coroutine[Any, Any, T]]], T]


class ParamClientResultException(Exception):
    def __init__(self, message: str, result: Result) -> None:
        error = None
        if isinstance(result.result, dict):
            error = result.result.get("message")

        super().__init__(f"{message}: {result.code}, {error}")


class ParamClient:
    def __init__(
        self,
        environment: str,
        client: Client,
        run_sync: RUN_SYNC,
        param_id: str,
        resource_id: str,
    ) -> None:
        """
        A ParamClient is bound to its parameter.  Once the param_id and resource_id have been set
        in the constructor, they can not be changed anymore.  The get, set and delete operations
        allow to easily interact with this parameter.

        :param environment: The environment UUID in which the parameter is (to be) stored
        :param client: A Client with access to the param api
        :param run_sync: Any method which allows to run an asynchronous api call, synchronously.
            The runsync method from the handler is expected here.
        :param param_id: The parameter id, as stored on the server
        :param resource_id: The resource id, for the parameter stored on the server.
        """
        self._environment = environment
        self._client = client
        self._run_sync = run_sync
        self._param_id = param_id
        self._resource_id = resource_id

    @property
    def param_id(self) -> str:
        return self._param_id

    @property
    def resource_id(self) -> str:
        return self._resource_id

    def set(self, value: str) -> None:
        async def set_param() -> None:
            result = await self._client.set_param(
                tid=self._environment,
                id=self._param_id,
                source=ParameterSource.fact,
                value=value,
                resource_id=self._resource_id,
                recompile=True,
            )
            if result.code == 200:
                return

            raise ParamClientResultException(
                "Bad response while trying to set parameter", result
            )

        self._run_sync(set_param)

    def get(self) -> Optional[str]:
        async def get_param() -> Optional[str]:
            result = await self._client.get_param(
                tid=self._environment,
                id=self._param_id,
                resource_id=self._resource_id,
            )
            if result.code == 200:
                assert result.result is not None
                return result.result["parameter"]["value"]

            if result.code == 404:
                return None

            if result.code == 503:
                # In our specific case, we might get a 503 if the parameter is not set yet
                # https://github.com/inmanta/inmanta-core/blob/5bfe60683f7e21657794eaf222f43e4c53540bb5/src/inmanta/server/agentmanager.py#L799
                return None

            raise ParamClientResultException(
                "Bad response while trying to get parameter", result
            )

        return self._run_sync(get_param)

    def delete(self) -> None:
        async def delete_param() -> None:
            result = await self._client.delete_param(
                tid=self._environment,
                id=self._param_id,
                resource_id=self._resource_id,
            )
            if result.code == 200 or result.code == 404:
                return

            raise ParamClientResultException(
                "Bad response while trying to delete parameter", result
            )

        self._run_sync(delete_param)
