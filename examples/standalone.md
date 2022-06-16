# Standalone usage of the library

All Inmanta module V2 are python packages, containing the module plugins logic (amongst other things).  This logic is then easily reachable and usable by any one.  This module is no exception, if you install the `inmanta-module-terraform` python package, you can use all of the terraform provider logic as a terraform provider client sdk.

Here is a basic example of such usage of the package.

```python
import os
import logging
from pathlib import Path
from uuid import UUID

from inmanta_plugins.terraform.tf.terraform_provider import TerraformProvider
from inmanta_plugins.terraform.tf.terraform_provider_installer import ProviderInstaller
from inmanta_plugins.terraform.tf.terraform_resource_client import TerraformResourceClient
from inmanta_plugins.terraform.tf.terraform_resource_state import TerraformResourceState

LOGGER = logging.getLogger(__name__)

cwd = Path(os.getcwd())

provider_installer = ProviderInstaller(
    namespace=provider.namespace,
    type=provider.type,
    version=provider.version,
)
provider_installer.resolve()
provider_installer.download(str(cwd / "download.zip"))
provider_path = provider_installer.install(str(cwd))

resource_state = TerraformResourceState(
    type_name="local_file",
    resource_id="file",
)

generate_file_path = cwd / "file.txt"

with TerraformProvider(
    provider_path=provider_path,
    log_file_path=str(cwd / "provider.log"),
) as p:
    LOGGER.debug(p.schema)
    assert not p.ready
    p.configure({})
    assert p.ready

    client = TerraformResourceClient(
        provider=p,
        resource_state=resource_state,
        logger=LOGGER,
    )
    LOGGER.debug(client.resource_schema)

    assert not generate_file_path.exists()

    client.create_resource(
        {
            "filename": str(generate_file_path),
            "content": "Hello World",
        }
    )

    assert generate_file_path.exists()
    assert generate_file_path.read_text() == "Hello World"

    client.delete_resource()

    assert not generate_file_path.exists()

assert not p.ready
```
