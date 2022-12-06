# terraform Module

This modules is an interface between any terraform provider and inmanta.  It allows to quickly have a basic support of any technology that terraform supports in an inmanta model, managed by an inmanta orchestrator.

## Terraform features
Terraform has some features that do not translate directly to existing inmanta features (the opposite is true too).  For those, some workarounds needed to be found.  Here bellow are presented the main terraform features, and a short description of how we deal with those.

### Provider picking
> :heavy_check_mark: (*supported*)

You can pick whatever version of any provider available in the terraform registry, you only need to provide three values:
 - `namespace`: a section in the terraform registry, in which the provider is present.  More information [here](https://www.terraform.io/docs/internals/module-registry-protocol.html#namespace)
 - `type`: the name of the provider, in the previously mentioned namespace.  :warning: This might be different from its display name.
 - `version` (optional, defaults to `"latest"`)  The version of the provider to use, if none is selected, the latest one is picked up.  We advise to pin the version, to avoid any surprise if a new version of the provider is released.

The provider is presented as an entity: `terraform::Provider`.  Additionally to the previously mentioned values, the provider takes a `config` attribute.  This attribute is a dict containing as key, the entries in the provider arguments and as value, whatever value we want to set it to.

> :bulb: In the case of nested blocks, the typing of the block has to be respected.  Unfortunately, this type is not documented in the terraform registry.  To know the nesting type you will need to check the provider schema.  You can do this either by executing the provider binary and getting the schema, or looking at the source of the provider (probably the easiest solution).

*Example:*
The following inmanta model:
```
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
```
is equivalent to:
```
variable "FORTIOS_ADDRESS" {
    type = string
}

variable "FORTIOS_TOKEN" {
    type = string
}

terraform {
  required_providers {
    fortios = {
      source = "fortinetdev/fortios"
      version = "1.11.0"
    }
  }
}

provider "fortios" {
  hostname = var.FORTIOS_ADDRESS
  token = var.FORTIOS_TOKEN
  insecure = true
}
```

### Standalone resource
> :heavy_check_mark: (*supported*)

The main feature of this module is of course the resource support.  Any resource from any provider can be created, updated, deleted using inmanta model with the entity `terraform::Resource`.
This entity needs to be provided with a unique identifier (`name`), its type in the provider documentation (`type`) and a `config` dict.  Similarly as for the provider, the dict contains any parameters that this resource can take.  Nested blocks have the same behavior too.
In addition to these attributes, the resource also needs to be specified the provider that should be used to deploy it.  This is done via the `provider` relation.

> :bulb: The entity can also take an optional `terraform_id` attribute, we will come back to this one [later](#resource-import).

*Example:*
The following inmanta model:
```
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
is equivalent to:
```
resource "fortios_system_interface" "my interface" {
    ip = "10.100.144.1 255.255.255.0"
    name = "gu-int1"
    type = "vlan"
    vdom = "root"
    mode = "static"
    interface = "wan2"
    vlanid = 144
    description = "This is a test description"
}
```

### Reference to resource attribute
> :heavy_check_mark: (*supported*)

As in inmanta language, terraform allows to reference a resource attribute value, and assign it to another resource attribute for example.  What is interesting about it is that is works for generated attributes too.  (Generated attributes are attributes that you don't populate in your model but that will be filled by the provider.)
Inmanta doesn't have this notion of generated attribute, so some workarounds had to be taken to support this.
This feature is supported with two different implementations, which all have advantages and tradeoffs compare to the other.  It is up to you to decide which one should be use for your use case.  Both can be used in the same model without any interference issue.
 1. `terraform::get_resource_attribute(resource, ["id"])`: returns the value directly, it can then be manipulated, formatted, etc.
    1. Advantages:
       1. The value can be manipulated.
       2. The value can be used anywhere in the model, not only for terraform resources configs.
    2. Disadvantages:
       1. As the value is resolved at compile time, the value we get always comes from the last deployment, not the one to come (obviously).
 2. `terraform::get_resource_attribute_ref(resource, ["id"])`: returns a reference to the value, it can not be manipulated, only assigned in another resource config dict.
    1. Advantages:
       1. It doesn't require multiple compile to resolve the value.
       2. The value resolved (on resource deployment) will always be in sync with the current deployment.  (As long as the requires/provides relations are set properly).
    2. Disadvantages:
       1. The value can not be manipulated in the model.
       2. This can not be used for anything else than a resource config as the reference will only be understood by the terraform resource handler.

**Behavioral notes:**
| Situation | First solution, direct access | Second solution, reference access |
| --- | --- | --- |
| The value is unknown at compile time. | If the value is unknown at compile time, the deployment will be skipped for the resource using it.  Once the value is known, a second compile is triggered and the resource will be deployed. | If the value is unknown at compile time, but can be resolved by the handler, the resource will be deployed. |
| The value is unknown at deployment time. | Same as above. | The deployment will be skipped.  It will try again on every new deployment. |

*Example:*
```
file = terraform::Resource(
    type="local_file",
    name="my file",
    config={
        "filename": "/tmp/test-file.txt",
        "content": "my original content",
    },
    send_event=true,  # Without this, any update of the content wouldn't trigger an update for the reference mechanism
    purged=false,
    provider=provider,
)

# This entity will only be known after the first compile and deployed after the second
file_id = terraform::get_resource_attribute(file, ["id"])
terraform::Resource(
    type="local_file",
    name="my id file",
    config={
        "filename": "/tmp/test-file-id.txt",
        "content": "File id is: {{ file_id }}",
    },
    purged=false,
    provider=provider,
)

# This entity will be deployed directly
terraform::Resource(
    type="local_file",
    name="my id file ref",
    config={
        "filename": "/tmp/test-file-id-ref.txt",
        "content": terraform::get_resource_attribute_ref(file, ["id"]),
    },
    purged=false,
    provider=provider,
    requires=file,  # This is important
)
```

### Resource import
> :heavy_check_mark: (*supported*)

Terraform allows to import existing resources that are not currently managed into the model so that they become managed.  We can do this too by making use of the `terraform_id` attribute.
When it is set, and if the resource doesn't have a state yet (isn't managed yet), we will first try to import it.  If the import fails, the resource deployment will fail too.

*Example:*
```
switch_id = std::get_env("FORTIOS_SWITCH_ID")
switch = terraform::Resource(
    type="fortios_switchcontroller_managedswitch",
    name="my switch",
    terraform_id=switch_id,
    config={
        "switch_id": switch_id,
        "fsw_wan1_admin": "enable",
        "fsw_wan1_peer": "fortilink",
        "type": "physical",
    },
    purged=false,
    provider=provider,
)
```

### Data sources
> :x: (*not supported at the moment*)

Support for data sources will be brought to the module by https://code.inmanta.com/solutions/modules/terraform/-/issues/16.

## Examples

Some example of usage of this module can be found in [examples](examples/README.md).

## Running tests

1. Setup a virtual env

```bash
mkvirtualenv inmanta-test -p python3
pip install -r requirements.dev.txt
pip install -r requirements.txt

mkdir /tmp/env
export INMANTA_TEST_ENV=/tmp/env
export INMANTA_MODULE_REPO=git@github.com:inmanta/
```

2. Run tests

The tests need some environment variables to be set in order to run properly:
```bash
export TERRAFORM_GITHUB_TOKEN=""  # A personal github token, with read/write/delete access to your organization (can be your own user) repositories.
export TERRAFORM_GITLAB_TOKEN=""  # A personal gitlab token, with read/write/delete access to your group (can be your own user) projects.
export TERRAFORM_CHECKPOINT_USER=""  # A username to authenticate to the checkpoint instance
export TERRAFORM_CHECKPOINT_PASS=""  # A password to authenticate to the checkpoint instance
export TERRAFORM_FORTIOS_TOKEN=""  # A token to authenticate to fortios
export TERRAFORM_FORTIOS_SWITCH_ID=""  # The id of the switch you will use in your tests
```
> :warning: Once you have created your own lab file, you can change the name of those environment variables, they might not exactly correspond to what is shown above.

To speed up multiple test executions, you can set a caching directory so that all the provider binaries don't need to be downloaded every time.  This is done using the `--terraform-cache-dir <path-to-folder>` argument.

Finally, the test will need some input, coming from a lab file (in [`tests/labs`](tests/labs/)).  You can base yourself on one of the existing one to create your own.  Then add the `--terraform-lab <file-name-minus-.yaml>` argument.
Alternatively, the lab can be picked through the `INMANTA_TERRAFORM_LAB` environment variable.

You can then run the test like so:
```bash
source env.sh
pytest tests --terraform-lab guillaume --terraform-cache-dir /tmp/your-cache-dir
```

3. Test options

The test are configurable through several means, one of them is pytest options.  You can use them to set the lab to use, a cache folder to use or to select which tests to run.
By default, all tests will run.  If you need/want to skip some, you have to unselect them, specifying the provider they are soliciting.  The options that can be used for this are the following:
```console
$ pytest --help
...
Terraform module testing options:
  --terraform-cache-dir=TERRAFORM_CACHE_DIR
                        Set fixed cache directory (overrides INMANTA_TERRAFORM_CACHE_DIR)
  --terraform-lab=TERRAFORM_LAB
                        Name of the lab to use (overrides INMANTA_TERRAFORM_LAB)
  --terraform-skip-provider-checkpoint
                        Skip tests using the checkpoint provider (overrides INMANTA_TERRAFORM_SKIP_PROVIDER_CHECKPOINT, defaults to False)
  --terraform-skip-provider-fortios
                        Skip tests using the fortios provider (overrides INMANTA_TERRAFORM_SKIP_PROVIDER_FORTIOS, defaults to False)
  --terraform-skip-provider-github
                        Skip tests using the github provider (overrides INMANTA_TERRAFORM_SKIP_PROVIDER_GITHUB, defaults to False)
  --terraform-skip-provider-gitlab
                        Skip tests using the gitlab provider (overrides INMANTA_TERRAFORM_SKIP_PROVIDER_GITLAB, defaults to False)
  --terraform-skip-provider-local
                        Skip tests using the local provider (overrides INMANTA_TERRAFORM_SKIP_PROVIDER_LOCAL, defaults to False)
...
```
All the options can also be set using environment variables, as mentioned in the above documentation.  For *flag* options (options whose value is either `true`, if it is set, or `false` if it is not set), the value will be converted to lower case and striped, it will be then evaluated like this:
 - `value == "true"`: The flag value is True
 - `value == "false"`: The flag value is False
 - Anything else: Raise a ValueError

4. Provider specific tests

Most tests in this module are specific to a unique provider.  If you don't have an environment setup to use this provider, you can simply skip the test by not specifying the corresponding pytest option.  Those tests are selected based on a marker, there is one for each provider:
```console
$ pytest --markers
@pytest.mark.terraform_provider_checkpoint: mark test to run only with option --terraform-provider-checkpoint

@pytest.mark.terraform_provider_fortios: mark test to run only with option --terraform-provider-fortios

@pytest.mark.terraform_provider_github: mark test to run only with option --terraform-provider-github

@pytest.mark.terraform_provider_gitlab: mark test to run only with option --terraform-provider-gitlab

@pytest.mark.terraform_provider_local: mark test to run only with option --terraform-provider-local
```

## License

This module is available as opensource under ASL2 and commercially under the Inmanta EULA, with the following disclaimer:

This module is an Inmanta internal tool, with no other purpose than assisting in the construction of specific other modules.
This module provides no functionality of its own, has no implied warranties and has no fitness for any particular purpose.
It requires specific training to use safely.

No support is provided on this module except through Inmanta supported and licensed modules that use its functionality
