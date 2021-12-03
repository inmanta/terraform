# CheckpointSW/checkpoint
> This has been tested for version 1.4.0

In this document you can find the following examples:
 - [Management network](#management-network)
 - [Management host](#management-host)

To use those code snippet, you will need to set the following environment variables:
 - `CHECKPOINT_HOST`: The host where you can reach the checkpoint server.
 - `CHECKPOINT_USER`: The username to authenticate to the checkpoint server web api.
 - `CHECKPOINT_PASS`: The password to authenticate to the checkpoint server web api.

> :warning: Important note about this provider: **it doesn't apply any of the changes it does in its session**.  If you want to apply the changes done by the checkpoint provider, you need to commit the changes hold in the session used by the provider.  This is made possible because the provider dumps its session sid in a file, in the current working directory of the process of the provider.
> If picking up that file is too complicated, the session changes can also be done by connecting to the smart console.

## Management network
```
provider = terraform::Provider(
    namespace="CheckPointSW",
    type="checkpoint",
    version="1.4.0",
    config={
        "server": std::get_env("CHECKPOINT_HOST"),
        "username": std::get_env("CHECKPOINT_USER"),
        "password": std::get_env("CHECKPOINT_PASS"),
        "context": "web_api"
    },
)

network = terraform::Resource(
    type="checkpoint_management_network",
    name="my network",
    terraform_id=null,
    config={
        "name": "inmanta-gu-test-network",
        "subnet4": "10.100.144.0",
        "mask_length4": 21
    },
    purged=false,
    provider=provider,
)
```

## Management host
```
provider = terraform::Provider(
    namespace="CheckPointSW",
    type="checkpoint",
    version="1.4.0",
    config={
        "server": std::get_env("CHECKPOINT_HOST"),
        "username": std::get_env("CHECKPOINT_USER"),
        "password": std::get_env("CHECKPOINT_PASS"),
        "context": "web_api"
    },
    auto_agent=false,
    agent_config=provider_agent_config,
)

network = terraform::Resource(
    type="checkpoint_management_network",
    name="my network",
    terraform_id=null,
    config={
        "name": "inmanta-gu-test-network",
        "subnet4": "10.100.144.0",
        "mask_length4": 21
    },
    purged=false,
    provider=provider,
)

host = terraform::Resource(
    type="checkpoint_management_host",
    name="my host",
    terraform_id=null,
    config={
        "name": "inmanta-gu-test-host",
        "ipv4_address": "10.100.144.1"
    },
    purged=false,
    provider=provider,
)
```
