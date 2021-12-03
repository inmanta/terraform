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
import json
import logging
import os
from copy import deepcopy
from pathlib import Path

from providers.checkpoint.helpers.checkpoint_client import CheckpointClient

LOGGER = logging.getLogger(__name__)


def sid_path() -> Path:
    """
    The checkpoint provider will "leak" its session id in a file, in the current directory.
    This methods returns a Path objects to this file if it exists.
    """
    p = Path(os.getcwd()) / Path("sid.json")
    if not p.exists():
        raise FileNotFoundError("Couldn't find the sid file")

    return p


def attach_session(checkpoint_client: CheckpointClient) -> CheckpointClient:
    """
    This methods returns a copy of the provided checkpoint client, with its uid and sid
    overwritten with those of the last provider session.
    """
    p = sid_path()

    with open(str(p), "r") as f:
        sid_config = json.load(f)
        sid = sid_config["sid"]
        uid = sid_config["uid"]

    LOGGER.debug(f"Attaching to existing session: {uid}")

    client = deepcopy(checkpoint_client)
    client._session_uid = uid
    client.api_client.sid = sid

    return client


def manual_publish(checkpoint_client: CheckpointClient):
    """
    As of right now, Terraform does not provide native support for publish and
    install-policy, so both of them are handled out-of-band.
    https://registry.terraform.io/providers/CheckPointSW/checkpoint/latest/docs#post-applydestroy-commands
    """
    client = attach_session(checkpoint_client)

    LOGGER.debug("Publishing")
    client.publish()
    client.logout()


def manual_discard(checkpoint_client: CheckpointClient):
    """
    If something went wrong during a deployment, the session created by the provider
    might still hold resources.  Those can't then be cleaned up.  Here, we discard
    this session, if it appears to be one.
    """
    client = attach_session(checkpoint_client)

    LOGGER.debug("Discarding")
    client.discard()
    client.logout()
