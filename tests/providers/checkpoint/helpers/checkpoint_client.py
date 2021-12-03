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
import logging
import time
from typing import Any, Callable, Dict, Iterable, List, Optional

from cpapi import APIClient, APIClientArgs
from cpapi.api_exceptions import TimeoutException
from netaddr import IPAddress, IPNetwork
from providers.checkpoint.helpers.checkpoint_credentials import CheckpointCredentials

LOGGER = logging.getLogger(__name__)


class CheckpointClient:
    SESSION_SUFFIX = "systemtenant-session"
    HANDLER_SESSION_NAME = "inmanta-checkpoint-client-session"
    OBJECT_BATCH_SIZE = 50
    API_CALL_TIMEOUT = 60
    SESSION_TIMEOUT = 3600
    RETRY_COUNT = 2
    RETRY_DELAY = 3

    def __init__(
        self,
        credentials: CheckpointCredentials,
        context: str,
        prefix: str,
        ip_range: IPNetwork,
        retry_count: int = RETRY_COUNT,
        retry_delay: int = RETRY_DELAY,
    ):
        client_args = APIClientArgs(server=credentials.host, unsafe_auto_accept=True)
        self._credentials = credentials
        self._context = context
        self._prefix = prefix
        self._ip_range = ip_range
        self._client = APIClient(client_args)
        self._session_uid = None
        self._retry_count = retry_count
        self._retry_delay = retry_delay

    @property
    def context(self) -> str:
        return self._context

    @property
    def credentials(self) -> CheckpointCredentials:
        return self._credentials

    @property
    def api_client(self) -> APIClient:
        return self._client

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def ip_range(self) -> IPNetwork:
        return self._ip_range

    @property
    def session_name(self) -> str:
        return f"{self.prefix}-{self.SESSION_SUFFIX}"

    def login(self):
        login_response = self.api_client.login(
            self.credentials.username,
            self.credentials.password,
            payload={
                "session-name": self.session_name,
                "session-timeout": self.SESSION_TIMEOUT,
            },
        )

        if not login_response.success:
            raise RuntimeError(f"Login failed: {login_response.error_message}")

        self._session_uid = login_response.data["uid"]

    def logout(self):
        if self.api_client.sid and self._session_uid:
            response = self.api_client.api_call(
                "show-session",
                payload={"uid": self._session_uid},
                timeout=self.API_CALL_TIMEOUT,
            )
            if not response.success:
                raise RuntimeError(
                    f"Error when looking for own session: {response.error_message}"
                )
            if response.data["state"] == "open":
                LOGGER.info(
                    f"Cleaning own session: {self._session_uid}, discarding all remaining changes"
                )
                response = self.api_client.api_call(
                    "discard",
                    payload={"uid": self._session_uid},
                    timeout=self.API_CALL_TIMEOUT,
                )
                if not response.success:
                    raise RuntimeError(
                        f"Error when discarding own session: {response.error_message}"
                    )
            else:
                LOGGER.info(
                    f"No need to discard current session, session state is {response.data['state']}"
                )
            LOGGER.info("Logging out")
            self.api_client.api_call("logout")

        self._session_uid = None

    def relog(self):
        self.logout()
        self.login()

    def publish(self):
        response = self.api_client.api_call("publish")
        if not response.success:
            raise RuntimeError(f"Publish failed: {response.error_message}")
        self.relog()

    def discard(self):
        response = self.api_client.api_call("discard")
        if not response.success:
            raise RuntimeError(f"Discard failed: {response.error_message}")

    def cleanup(self):
        LOGGER.info("Proceeding to full checkpoint cleanup")

        did_something = self.cleanup_sessions()
        did_something = self.cleanup_hosts() or did_something
        did_something = self.cleanup_networks() or did_something
        if did_something:
            self.publish()

    # Cleaning objects #

    def cleanup_hosts(self) -> bool:
        return self._retry(
            self._cleanup,
            "host",
            self.show_hosts(),
            ["name"],
        )

    def cleanup_networks(self) -> bool:
        return self._retry(
            self._cleanup,
            "network",
            self.show_networks(),
            ["name"],
        )

    def _cleanup(
        self,
        api_endpoint: str,
        object_list: Iterable[Dict[str, Any]],
        object_id_fields: List[str],
    ) -> bool:
        if object_list:
            for element in object_list:
                element_id = {
                    id_field: element[id_field] for id_field in object_id_fields
                }
                LOGGER.info(f"Removing {api_endpoint}: {element_id}.")
                result = self.api_client.api_call(
                    f"delete-{api_endpoint}",
                    element_id,
                )
                if not result.success and result.status_code != 404:
                    raise RuntimeError(
                        f"Error on {api_endpoint} cleanup: {result.error_message}"
                    )
            return True
        else:
            LOGGER.info(f"No {api_endpoint}s to cleanup.")
            return False

    # Cleanup sessions #

    def cleanup_sessions(self) -> bool:
        did_something = False
        for session in self.show_sessions():
            if (
                "name" in session
                and session["name"] in {self.session_name, self.HANDLER_SESSION_NAME}
                and session["uid"] != self._session_uid
            ):
                result = self.api_client.api_call(
                    "show-session",
                    payload={"uid": session["uid"]},
                    timeout=self.API_CALL_TIMEOUT,
                )
                if not result.success:
                    LOGGER.warning(
                        f"The session with uid {session['uid']} doesn't exist anymore"
                    )
                    continue

                session = result.data

                time_since_last_modify = (
                    time.time()
                    - session["meta-info"]["last-modify-time"]["posix"] / 1000
                )
                if (time_since_last_modify > self.SESSION_TIMEOUT) or (
                    session["in-work"] is False and "last-logout-time" in session
                ):
                    LOGGER.info(f"Cleaning session {session['uid']}")
                    response = self.api_client.api_call(
                        "discard",
                        payload={"uid": session["uid"]},
                        timeout=self.API_CALL_TIMEOUT,
                    )
                    if not response.success:
                        raise RuntimeError(
                            f"Error when discarding session: {response.error_message}"
                        )
                    did_something = True
                else:
                    LOGGER.info(
                        f"Skipping session cleanup for {session['uid']}, it was used to recently "
                        f"({int(time_since_last_modify)} seconds ago)"
                    )
        return did_something

    # Getting sessions #

    def show_sessions(self) -> List:
        return [session for session in self._get_instances("show-sessions")]

    # Getting objects #

    def show_hosts(self) -> List:
        hosts = []
        for host in self._get_instances("show-hosts"):
            address = IPAddress(host["ipv4-address"])
            if address in self.ip_range:
                hosts.append(host)

        return hosts

    def show_host(self, name: str) -> Optional[Any]:
        result = self.api_client.api_call("show-host", payload={"name": name})
        if not result.success:
            return None
        return result.data

    def show_networks(self) -> List:
        return [
            network
            for network in self._get_instances("show-networks")
            if network["name"].startswith(self.prefix)
        ]

    def show_network(self, name: str) -> Optional[Any]:
        result = self.api_client.api_call("show-network", payload={"name": name})
        if not result.success:
            LOGGER.debug(result)
            return None
        return result.data

    def _retry(
        self,
        func: Callable,
        *args,
        **kwargs,
    ):
        attempt = 1
        while True:
            try:
                return func(*args, **kwargs)
            except TimeoutException as e:
                LOGGER.error(f"TimeoutException on {attempt} attempt:\n{e}")
            if attempt > self._retry_count:
                raise RuntimeError(
                    f"Maximum number of retries {self._retry_count} exceeded."
                )
            LOGGER.info(f"Retrying in {self._retry_delay} seconds...")
            time.sleep(self._retry_delay)
            attempt += 1

    def _get_instances(self, show_api_endpoint: str) -> Iterable:
        offset = 0
        while True:
            result = self.api_client.api_call(
                show_api_endpoint,
                {
                    "limit": self.OBJECT_BATCH_SIZE,
                    "offset": offset,
                    "details-level": "full",
                },
            )

            if not result.success:
                raise RuntimeError(
                    f"Error while processing groups: {result.error_message}"
                )

            for instance in result.data["objects"]:
                yield instance

            if offset + self.OBJECT_BATCH_SIZE < result.data["total"]:
                offset += self.OBJECT_BATCH_SIZE
            else:
                break
