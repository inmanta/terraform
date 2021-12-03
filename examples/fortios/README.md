# fortinetdev/fortios
> This has been tested for version 1.11.0

In this document you can find the following examples:
 - [System interface](#system-interface)
 - [Firewall address](#firewall-address)
 - [Firewall service custom](#firewall-service-custom)
 - [Firewall policy](#firewall-policy)
 - [Wireless controller vap](#wireless-controller-vap)
 - [Managed switch](#managed-switch)

To use those model snippet, you will need to set the following environment variables:
 - `FORTIOS_ADDRESS`: And address at which the fortios api can be reached.
 - `FORTIOS_TOKEN`: A token that can be used to access the fortios api.

## System interface
```
import terraform

provider = terraform::Provider(
    namespace="fortinetdev",
    type="fortios",
    version="1.11.0",
    config={
        "hostname": std::get_env("FORTIOS_ADDRESS"),
        "token": std::get_env("FORTIOS_TOKEN"),
        "insecure": true
    },
)

interface = terraform::Resource(
    type="fortios_system_interface",
    name="my interface",
    config={
        "ip": "10.100.144.1 255.255.255.0",
        "name": "gu-int1",
        "type": "vlan",
        "vdom": "root",
        "mode": "static",
        "interface": "wan2",
        "vlanid": 144,
        "description": "This is a test description"
    },
    purged=false,
    provider=provider,
)
```

## Firewall address
```
import terraform

provider = terraform::Provider(
    namespace="fortinetdev",
    type="fortios",
    version="1.11.0",
    config={
        "hostname": std::get_env("FORTIOS_ADDRESS"),
        "token": std::get_env("FORTIOS_TOKEN"),
        "insecure": true
    },
)

address = terraform::Resource(
    type="fortios_firewall_address",
    name="my firewall address",
    config={
        "name": "gu-fa1",
        "subnet": "192.168.1.64 255.255.255.192",
        "type": "subnet"
    },
    purged=false,
    provider=provider,
)
```

## Firewall service custom
```
import terraform

provider = terraform::Provider(
    namespace="fortinetdev",
    type="fortios",
    version="1.11.0",
    config={
        "hostname": std::get_env("FORTIOS_ADDRESS"),
        "token": std::get_env("FORTIOS_TOKEN"),
        "insecure": true
    },
)

service = terraform::Resource(
    type="fortios_firewallservice_custom",
    name="my firewall service",
    config={
        "name": "gu-fsc1",
        "protocol": "TCP",
        "tcp_portrange": "456-465",
        "visibility": "enable"
    },
    purged=false,
    provider=provider,
)
```

## Firewall policy
```
import terraform

purge_model = false  # Set this to true to remove deployed resources

provider = terraform::Provider(
    namespace="fortinetdev",
    type="fortios",
    version="1.11.0",
    config={
        "hostname": std::get_env("FORTIOS_ADDRESS"),
        "token": std::get_env("FORTIOS_TOKEN"),
        "insecure": true
    },
)

address_src = terraform::Resource(
    type="fortios_firewall_address",
    name="my firewall address",
    config={
        "name": "gu-fa1",
        "subnet": "192.168.1.1 255.255.255.192",
        "type": "subnet"
    },
    purged=purge_model,
    provider=provider,
    requires=purge_model ? [policy] : [],
    provides=purge_model ? [] : [policy],
)

address_dst = terraform::Resource(
    type="fortios_firewall_address",
    name="my other firewall address",
    config={
        "name": "gu-fa2",
        "subnet": "192.168.2.1 255.255.255.192",
        "type": "subnet"
    },
    purged=purge_model,
    provider=provider,
    requires=purge_model ? [policy] : [],
    provides=purge_model ? [] : [policy],
)

interface_src = terraform::Resource(
    type="fortios_system_interface",
    name="my interface",
    config={
        "ip": "10.100.144.1 255.255.255.0",
        "name": "gu-int1",
        "type": "vlan",
        "vdom": "root",
        "mode": "static",
        "interface": "wan2",
        "vlanid": 144,
        "description": "This is a test description"
    },
    purged=purge_model,
    provider=provider,
    requires=purge_model ? [policy] : [],
    provides=purge_model ? [] : [policy],
)

interface_dst = terraform::Resource(
    type="fortios_system_interface",
    name="my other interface",
    config={
        "ip": "10.100.145.1 255.255.255.0",
        "name": "gu-int2",
        "type": "vlan",
        "vdom": "root",
        "mode": "static",
        "interface": "wan2",
        "vlanid": 145,
        "description": "This is a test description"
    },
    purged=purge_model,
    provider=provider,
    requires=purge_model ? [policy] : [],
    provides=purge_model ? [] : [policy],
)

service_1 = terraform::Resource(
    type="fortios_firewallservice_custom",
    name="my firewall service",
    config={
        "name": "gu-fsc1",
        "protocol": "TCP",
        "tcp_portrange": "456-465",
        "visibility": "enable"
    },
    purged=purge_model,
    provider=provider,
    requires=purge_model ? [policy] : [],
    provides=purge_model ? [] : [policy],
)

service_2 = terraform::Resource(
    type="fortios_firewallservice_custom",
    name="my other firewall service",
    config={
        "name": "gu-fsc2",
        "protocol": "TCP",
        "tcp_portrange": "567-576",
        "visibility": "enable"
    },
    purged=purge_model,
    provider=provider,
    requires=purge_model ? [policy] : [],
    provides=purge_model ? [] : [policy],
)

policy = terraform::Resource(
    type="fortios_firewall_policy",
    name="my firewall policy",
    config={
        "name": "gu-fp1",
        "action": "accept",
        "dstintf": [
            {
                "name": "gu-int2"
            }
        ],
        "dstaddr": [
            {
                "name": "gu-fa2"
            }
        ],
        "srcintf": [
            {
                "name": "gu-int1"
            }
        ],
        "srcaddr": [
            {
                "name": "gu-fa1"
            }
        ],
        "service": [
            {
                "name": "gu-fsc1"
            }
        ]
    },
    purged=purge_model,
    provider=provider,
    requires=purge_model ? [] : [address_src, address_dst, interface_src, interface_dst, service_1, service_2],
    provides=purge_model ? [address_src, address_dst, interface_src, interface_dst, service_1, service_2] : [],
)
```

## Wireless controller vap
```
import terraform

purge_model = false  # Set this to true to remove deployed resources

provider = terraform::Provider(
    namespace="fortinetdev",
    type="fortios",
    version="1.11.0",
    config={
        "hostname": std::get_env("FORTIOS_ADDRESS"),
        "token": std::get_env("FORTIOS_TOKEN"),
        "insecure": true
    },
)

vap = terraform::Resource(
    type="fortios_wirelesscontroller_vap",
    name="my vap",
    config={
        "ip": "10.100.144.1 255.255.255.0",
        "name": "gu-vap1",
        "ssid": "gu vap1",
        "broadcast_ssid": "disable",
        "security": "wap2-only-personal",
        "encrypt": "AES",
        "passphrase": "2aE9fBEBbE",
        "quarantine": "disable",
        "schedule": "\"always\""
    },
    purged=purge_model,
    provider=provider,
    requires=purge_model ? [interface] : [],
    provides=purge_model ? [] : [interface],
)

interface = terraform::Resource(
    type="fortios_system_interface",
    name="my interface",
    config={
        "ip": "10.100.144.2 255.255.255.0",
        "name": "gu-int1",
        "type": "vlan",
        "vdom": "root",
        "mode": "static",
        "interface": "gu-vap1",
        "vlanid": 144,
        "description": "This is a test description"
    },
    purged=purge_model,
    provider=provider,
    requires=purge_model ? [] : [vap],
    provides=purge_model ? [vap] : [],
)
```

## Managed switch
```
import terraform

provider = terraform::Provider(
    namespace="fortinetdev",
    type="fortios",
    version="1.11.0",
    config={
        "hostname": std::get_env("FORTIOS_ADDRESS"),
        "token": std::get_env("FORTIOS_TOKEN"),
        "insecure": true
    },
)

switch_id = std::get_env("FORTIOS_SWITCH_ID")

interface = terraform::Resource(
    type="fortios_system_interface",
    name="my interface",
    terraform_id=null,
    config={
        "ip": "10.100.144.1 255.255.255.0",
        "name": "gu-int1",
        "type": "vlan",
        "vdom": "root",
        "mode": "static",
        "interface": "fortilink",
        "vlanid": 144,
        "description": "This is a test description"
    },
    purged=false,
    provider=provider,
    provides=[switch],
)

switch = terraform::Resource(
    type="fortios_switchcontroller_managedswitch",
    name="my switch",
    terraform_id=switch_id,
    config={
        "switch_id": switch_id,
        "fsw_wan1_admin": "enable",
        "fsw_wan1_peer": "fortilink",
        "type": "physical",
        "ports": [
            {
                "switch_id": switch_id,
                "speed_mask": 207,
                "port_name": "port5",
                "vlan": "gu-int1",
                "export_to": "root",
                "type": "physical",
                "mac_addr": "e0:23:ff:de:f5:9e",
                "allowed_vlans": [
                    {
                        "vlan_name": "quarantine"
                    }
                ],
                "untagged_vlans": [
                    {
                        "vlan_name": "quarantine"
                    }
                ]
            },
            {
                "switch_id": switch_id,
                "speed_mask": 207,
                "port_name": "port6",
                "vlan": "default",
                "export_to": "root",
                "type": "physical",
                "mac_addr": "e0:23:ff:de:f5:9f",
                "allowed_vlans": [
                    {
                        "vlan_name": "quarantine"
                    }
                ],
                "untagged_vlans": [
                    {
                        "vlan_name": "quarantine"
                    }
                ]
            }
        ]
    },
    purged=false,
    provider=provider,
    requires=[interface],
)
```
