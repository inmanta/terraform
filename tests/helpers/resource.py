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
import logging
import typing
from typing import Callable, List, Optional
from uuid import UUID

from inmanta.data import model
from inmanta.protocol.common import Result
from inmanta.protocol.endpoints import Client
from inmanta.resources import Id

QUERY_LIMIT = 25

LOGGER = logging.getLogger(__name__)


def is_offset_aware(date: datetime.datetime) -> bool:
    return date.tzinfo is not None and date.tzinfo.utcoffset(date) is not None


class Resource:
    def __init__(self, id: Id) -> None:
        self.id = id

    @property
    def resource_type(self) -> str:
        return self.id.entity_type

    @property
    def attribute(self) -> str:
        return self.id.attribute

    @property
    def attribute_value(self) -> str:
        return self.id.attribute_value

    @property
    def agent(self) -> str:
        return self.id.agent_name

    async def get_actions(
        self,
        client: Client,
        environment: UUID,
        oldest_first: bool = False,
        action_filter: Optional[Callable[[model.ResourceAction], bool]] = None,
        after: Optional[datetime.datetime] = None,
        before: Optional[datetime.datetime] = None,
    ) -> typing.Iterator[model.ResourceAction]:
        """
        Get all the resource actions of the specified resource.  Those resource actions
        will be before :param before: and after :param after:.  If :param oldest_first: is True,
        the actions are visited starting from the oldest ones, otherwise it is the opposite.

        :param client: A client that can be used to query actions
        :param environment: The environment from which the actions should be queried
        :param oldest_first: True to get the oldest visit the oldest actions first, False for the newest ones first
        :param action_filter: A callable that will see all queried action and filter them
        :param after: A datetime, timezone-aware, which should be the starting point of our research (or end).
        :param before: A datetime, timezone-aware, which should be the end of our research (or start).
        """
        # All created datetimes are offset-aware and in utc
        # We expect any value passed in the parameter to be as well
        before = before or datetime.datetime.max.replace(tzinfo=datetime.timezone.utc)
        if not is_offset_aware(before):
            raise ValueError(
                f"The provided value should be timezone-aware but isn't: before={before}"
            )

        after = after or datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc)
        if not is_offset_aware(after):
            raise ValueError(
                f"The provided value should be timezone-aware but isn't: after={after}"
            )

        while before > after:
            kwargs = dict(
                tid=environment,
                limit=QUERY_LIMIT,
                resource_type=self.resource_type,
                agent=self.agent,
            )

            # Filtering None values from dict
            kwargs = dict(filter(lambda item: item[1] is not None, kwargs.items()))

            if not oldest_first:
                # We force the date we send to be offset-naive, to stay compatible with ISO3
                # It will also be compatible with ISO4+ as the datetime is UTC
                kwargs["last_timestamp"] = before.astimezone(
                    tz=datetime.timezone.utc
                ).replace(tzinfo=None)
            else:
                # We force the date we send to be offset-naive, to stay compatible with ISO3
                # It will also be compatible with ISO4+ as the datetime is UTC
                kwargs["first_timestamp"] = after.astimezone(
                    tz=datetime.timezone.utc
                ).replace(tzinfo=None)

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

            if not actions:
                # We reached the end, the server doesn't have any more action to give us
                break

            for action in sorted(
                actions, key=lambda action: action.started, reverse=not oldest_first
            ):
                if not is_offset_aware(action.started):
                    # Depending on the version of the core, the returned date might not be offset-aware
                    # if it is not, the date is a utc one.  We then make it aware of its timezone.
                    action.started = action.started.replace(
                        tzinfo=datetime.timezone.utc
                    )

                if not oldest_first:
                    before = action.started
                else:
                    after = action.started

                if before <= after:
                    # We need to check this here as well or me might accept an action that
                    # is out of the bounds
                    break

                # Build the id with version of this resource
                versioned_id = self.id.copy(version=action.version)
                if (
                    versioned_id.resource_version_str()
                    not in action.resource_version_ids
                ):
                    # Our resource is not part of this action
                    continue

                if action_filter is None or action_filter(action):
                    yield action

    async def get_last_action(
        self,
        client: Client,
        environment: UUID,
        action_filter: Optional[Callable[[model.ResourceAction], bool]] = None,
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
        action_filter: Optional[Callable[[model.ResourceAction], bool]] = None,
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
