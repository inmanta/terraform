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
from typing import List

import pytest
from netaddr.ip import IPNetwork
from providers.fortios.helpers.fortios_client import FortiosClient
from providers.fortios.helpers.fortios_provider import FortiosProvider

LOGGER = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def fortios_configuration(lab_config_session: dict) -> dict:
    return lab_config_session["fortios"]["configuration"]


@pytest.fixture(scope="package")
def token(fortios_configuration: dict) -> str:
    return os.getenv(fortios_configuration["token_env_var"])


@pytest.fixture(scope="package")
def hostname(fortios_configuration: dict) -> str:
    return fortios_configuration["hostname"]


@pytest.fixture(scope="package")
def provider(hostname: str, token: str) -> FortiosProvider:
    return FortiosProvider(hostname, token)


@pytest.fixture(scope="session")
def fortios_values(lab_config_session: dict) -> dict:
    return lab_config_session["fortios"]["values"]


@pytest.fixture(scope="package")
def prefix(fortios_values: dict) -> str:
    return fortios_values["prefix"]


@pytest.fixture(scope="package")
def ip_range(fortios_values: dict) -> IPNetwork:
    return IPNetwork(fortios_values["ip_range"])


@pytest.fixture(scope="package")
def vlan_range(fortios_values: dict) -> List[int]:
    vlan_range = fortios_values["vlan_range"]
    return list(range(vlan_range["from"], vlan_range["to"]))


@pytest.fixture(scope="package")
def physical_interface(fortios_values: dict) -> str:
    return fortios_values["physical_interface"]


@pytest.fixture(scope="package")
def physical_switch(fortios_values: dict) -> dict:
    return fortios_values["physical_switch"]


@pytest.fixture(scope="package")
def physical_switch_id(physical_switch: dict) -> str:
    return os.getenv(physical_switch["id_env_var"])


@pytest.fixture(scope="package")
def global_client(
    hostname: str,
    token: str,
    prefix: str,
    physical_switch: dict,
    physical_switch_id: str,
) -> FortiosClient:
    fortios_client = FortiosClient(hostname, token, prefix)

    fortios_client.reset_switch_controller_managed_ports(
        switch_id=physical_switch_id,
        clean_port_name="port2",  # By convention
        port_names=[port["name"] for port in physical_switch["ports"]],
    )
    fortios_client.clean_all()

    yield fortios_client


@pytest.fixture(scope="function")
def fortios_client(
    global_client: FortiosClient,
    physical_switch: dict,
    physical_switch_id: str,
) -> FortiosClient:
    yield global_client

    global_client.reset_switch_controller_managed_ports(
        switch_id=physical_switch_id,
        clean_port_name="port2",  # By convention
        port_names=[port["name"] for port in physical_switch["ports"]],
    )
    global_client.clean_all()
