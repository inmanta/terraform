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
from copy import deepcopy
from typing import List

import requests

LOGGER = logging.getLogger(__name__)


class FortiosClient:
    def __init__(self, hostname: str, token: str, prefix: str) -> None:
        self._hostname = hostname
        self.base_url = f"https://{self._hostname}/api/v2/cmdb/"
        self._client = requests.session()
        self._client.params = dict(
            access_token=token,
            filter=[f"name=@{prefix}"],
        )
        self._client.verify = False
        self._response_filter = lambda named_dict: named_dict["name"].startswith(prefix)

    @property
    def session(self) -> requests.Session:
        return self._client

    def _get_named_objects(self, route_segment: str) -> List[dict]:
        response = self.session.get(self.base_url + route_segment)
        response.raise_for_status()

        data = response.json()
        return list(filter(self._response_filter, data["results"]))

    def _clean_named_objects(self, route_segment: str) -> None:
        for named_object in self._get_named_objects(route_segment):
            LOGGER.debug(f"Cleaning {route_segment}/{named_object['name']}")
            response = self.session.delete(
                self.base_url + route_segment + "/" + named_object["name"]
            )
            response.raise_for_status()

    def _clean_object(self, route_segment: str, id: str) -> None:
        LOGGER.debug(f"Cleaning {route_segment}/{id}")
        response = self.session.delete(self.base_url + route_segment + "/" + id)
        response.raise_for_status()

    def get_firewall_addresses(self) -> List[dict]:
        return self._get_named_objects("firewall/address")

    def clean_firewall_addresses(self) -> None:
        return self._clean_named_objects("firewall/address")

    def get_firewall_policies(self) -> List[dict]:
        return self._get_named_objects("firewall/policy")

    def clean_firewall_policies(self) -> None:
        for policy in self._get_named_objects("firewall/policy"):
            self._clean_object("firewall/policy", str(policy["policyid"]))

    def get_firewall_services(self) -> List[dict]:
        return self._get_named_objects("firewall.service/custom")

    def clean_firewall_services(self) -> None:
        return self._clean_named_objects("firewall.service/custom")

    def get_system_interfaces(self) -> List[dict]:
        return self._get_named_objects("system/interface")

    def clean_system_interfaces(self) -> None:
        return self._clean_named_objects("system/interface")

    def get_wireless_controller_vap(self) -> List[dict]:
        return self._get_named_objects("wireless-controller/vap")

    def clean_wireless_controller_vap(self) -> None:
        return self._clean_named_objects("wireless-controller/vap")

    def get_switch_controller_managed_switch(self, switch_id: str) -> dict:
        response = requests.get(
            self.base_url + "switch-controller/managed-switch/" + switch_id,
            params=dict(access_token=self.session.params["access_token"]),
            verify=False,
        )
        response.raise_for_status()

        return response.json()["results"][0]

    def reset_switch_controller_managed_ports(
        self, switch_id: str, clean_port_name: str, port_names: List[str]
    ) -> None:
        """
        We cannot simply reset a port config, so we will actually copy the config from un untouched port
        and apply it to port we wish to cleanup.

        :param switch_id: The id of the switch we are going to reset some port onto
        :param clean_port_name: The name of one of the switch port, that we are going to copy the config
            from, and apply it to to port we are cleaning out
        :param port_names: The name of the ports we wish to clean up
        """
        switch_config = self.get_switch_controller_managed_switch(switch_id)
        switch_ports = {port["port-name"]: port for port in switch_config["ports"]}

        # This port will serve as a basis for our reset
        clean_port: dict = switch_ports[clean_port_name]

        cleaned_ports = []
        for port in switch_ports.values():
            if port["port-name"] not in port_names:
                continue

            cleaned_port = deepcopy(clean_port)
            cleaned_port.update(
                {
                    "port-name": port["port-name"],
                    "mac-addr": port["mac-addr"],
                    "q_origin_key": port["q_origin_key"],
                }
            )
            cleaned_ports.append(cleaned_port)

        switch_config["ports"] = cleaned_ports

        response = self.session.put(
            self.base_url + "switch-controller/managed-switch/" + switch_id,
            json=switch_config,
        )
        response.raise_for_status()

    def clean_all(self) -> None:
        self.clean_firewall_policies()
        self.clean_firewall_addresses()  # Should be cleaned after policies
        self.clean_firewall_services()  # Should be cleaned after policies
        self.clean_system_interfaces()
        self.clean_wireless_controller_vap()  # Should be cleaned after interfaces
