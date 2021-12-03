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
import datetime
import json
import logging
from abc import abstractmethod
from textwrap import dedent, indent
from typing import Callable, Iterable, List, Optional
from uuid import UUID

from helpers.terraform_provider import TerraformProvider

from inmanta.data import model
from inmanta.protocol.common import Result
from inmanta.protocol.endpoints import Client

QUERY_LIMIT = 25

LOGGER = logging.getLogger(__name__)


def is_offset_aware(date: datetime.datetime) -> bool:
    return date.tzinfo is not None and date.tzinfo.utcoffset(date) is not None


class TerraformResource:
    def __init__(
        self,
        type: str,
        name: str,
        provider: TerraformProvider,
        terraform_id: Optional[str] = None,
        send_event: bool = False,
    ) -> None:
        self.type = type
        self.name = name
        self.provider = provider
        self.terraform_id = terraform_id
        self.send_event = send_event

    @property
    @abstractmethod
    def config(self) -> dict:
        pass

    @property
    def resource_type(self) -> str:
        return "terraform::Resource"

    @property
    def attribute(self) -> str:
        return "resource_type"

    @property
    def attribute_value(self) -> str:
        return self.type

    @property
    def agent(self) -> str:
        return self.provider.agent

    def model_instance(
        self,
        var_name: str,
        purged: bool = False,
        requires: Optional[List[str]] = None,
        provides: Optional[List[str]] = None,
    ) -> str:
        provider_reference = self.provider.model_reference()
        provider_reference = indent(provider_reference, "                ").strip()
        config = json.dumps(self.config, indent=4)
        config = indent(config, "                ").strip()
        requires = requires or []
        provides = provides or []
        terraform_id = '"' + self.terraform_id + '"' if self.terraform_id else "null"
        model = f"""
            {var_name} = terraform::Resource(
                type="{self.type}",
                name="{self.name}",
                terraform_id={terraform_id},
                config={config},
                purged={str(purged).lower()},
                send_event={str(self.send_event).lower()},
                provider={provider_reference},
                requires={'[' + ', '.join(requires) + ']'},
                provides={'[' + ', '.join(provides) + ']'},
            )
        """
        return dedent(model.strip("\n"))

    async def get_actions(
        self,
        client: Client,
        environment: UUID,
        oldest_first: bool = False,
        action_filter: Callable[[model.ResourceAction], bool] = None,
        after: Optional[datetime.datetime] = None,
        before: Optional[datetime.datetime] = None,
    ) -> Iterable[model.ResourceAction]:
        before = before or datetime.datetime.now().astimezone()
        after = after or datetime.datetime.fromtimestamp(0).astimezone()

        while before > after:
            kwargs = dict(
                tid=environment,
                limit=QUERY_LIMIT,
                resource_type=self.resource_type,
                agent=self.agent,
                attribute=self.attribute,
                attribute_value=self.attribute_value,
            )

            # Filtering None values from dict
            kwargs = dict(filter(lambda item: item[1] is not None, kwargs.items()))

            if not oldest_first:
                kwargs["last_timestamp"] = before
            else:
                kwargs["first_timestamp"] = after

            response: Result = await client.get_resource_actions(**kwargs)
            if response.code != 200:
                raise RuntimeError(
                    f"Unexpected response code when getting resource actions: received {response.code} "
                    f"(expected 200): {response.result}"
                )

            actions: List[model.ResourceAction] = [
                model.ResourceAction(**action)
                for action in response.result.get("data", [])
            ]

            if oldest_first:
                actions.reverse()

            for action in actions:
                if not is_offset_aware(action.started):
                    # Depending on the version of the core, the returned date might not be offset-aware
                    # if it is not, the date is a utc one.  We then make it aware of its timezone.
                    LOGGER.debug("Converting action date to be offset aware")
                    action.started = action.started.replace(
                        tzinfo=datetime.timezone.utc
                    )

                if not oldest_first and action.started < after:
                    # We get fixed size pages so this might happen when we reach the end
                    break

                if oldest_first and action.started > before:
                    # We get fixed size pages so this might happen when we reach the end
                    break

                if action_filter is None or action_filter(action):
                    yield action

            if len(actions) == 0:
                before = after
            elif not oldest_first:
                before = actions[-1].started
            else:
                after = actions[-1].started

    async def get_last_action(
        self,
        client: Client,
        environment: UUID,
        action_filter: Callable[[model.ResourceAction], bool] = None,
        after: Optional[datetime.datetime] = None,
        before: Optional[datetime.datetime] = None,
    ) -> Optional[model.ResourceAction]:
        async for action in self.get_actions(
            client=client,
            environment=environment,
            oldest_first=False,
            action_filter=action_filter,
            after=after,
            before=before,
        ):
            return action

        return None

    async def get_first_action(
        self,
        client: Client,
        environment: UUID,
        action_filter: Callable[[model.ResourceAction], bool] = None,
        after: Optional[datetime.datetime] = None,
        before: Optional[datetime.datetime] = None,
    ) -> Optional[model.ResourceAction]:
        async for action in self.get_actions(
            client=client,
            environment=environment,
            oldest_first=True,
            action_filter=action_filter,
            after=after,
            before=before,
        ):
            return action

        return None
