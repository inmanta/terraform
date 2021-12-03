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
import os

import pytest
from netaddr import IPNetwork
from providers.checkpoint.common import manual_discard
from providers.checkpoint.helpers.checkpoint_client import CheckpointClient
from providers.checkpoint.helpers.checkpoint_credentials import CheckpointCredentials
from providers.checkpoint.helpers.checkpoint_provider import CheckpointProvider

LOGGER = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def credentials(lab_config_session: dict) -> CheckpointCredentials:
    checkpoint_conf = lab_config_session["checkpoint"]["configuration"]
    return CheckpointCredentials(
        host=checkpoint_conf["host"],
        username=os.getenv(checkpoint_conf["username_env_var"]),
        password=os.getenv(checkpoint_conf["password_env_var"]),
    )


@pytest.fixture(scope="package")
def provider(credentials: CheckpointCredentials) -> CheckpointProvider:
    return CheckpointProvider(credentials)


@pytest.fixture(scope="package")
def prefix(lab_config_session: dict) -> str:
    return lab_config_session["checkpoint"]["values"]["prefix"]


@pytest.fixture(scope="package")
def ip_range(lab_config_session: dict) -> IPNetwork:
    return IPNetwork(lab_config_session["checkpoint"]["values"]["ip_range"])


@pytest.fixture(scope="package")
def global_client(
    lab_config_session: dict,
    prefix: str,
    ip_range: IPNetwork,
    credentials: CheckpointCredentials,
) -> CheckpointClient:
    checkpoint_client = CheckpointClient(
        credentials=credentials,
        context=lab_config_session["checkpoint"]["configuration"]["context"],
        prefix=prefix,
        ip_range=ip_range,
    )

    checkpoint_client.login()
    try:
        checkpoint_client.cleanup_sessions()
        checkpoint_client.cleanup()
    finally:
        checkpoint_client.logout()

    yield checkpoint_client


@pytest.fixture(scope="function")
def checkpoint_client(global_client: CheckpointClient) -> CheckpointClient:

    yield global_client

    try:
        # In case there is still a connection setup by the provider, we clean it up
        manual_discard(global_client)
    except FileNotFoundError:
        # There was no session to discard
        pass
    except RuntimeError as e:
        # Their was an error during the discarding of the session
        LOGGER.warning(
            "Could not discard last provider session (this is only an issue if "
            "the previous test failed, as the session might hold some resources)"
        )
        LOGGER.warning(str(e))

    global_client.login()
    try:
        global_client.cleanup_sessions()
        global_client.cleanup()
    finally:
        global_client.logout()
