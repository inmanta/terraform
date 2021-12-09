# tf_grpc_plugin

This package is automatically generated and allows a python program to easily communicate with a running terraform provider via a grpc connection.

It contains the following python packages:
 - `tfplugin5`

The input file is [tfplugin5.proto](tfplugin5.proto).  This file comes directly from terraform project on github: [https://github.com/hashicorp/terraform/blob/main/docs/plugin-protocol/tfplugin5.2.proto](https://github.com/hashicorp/terraform/blob/main/docs/plugin-protocol/tfplugin5.2.proto).

The python code can be generated like so:
```bash
python -m grpc_tools.protoc -I proto --python_out=src/ --grpc_python_out=src/ proto/**/*.proto
```

## Versioning
This packages uses semantic versioning, but major and minor versions are directly linked to the terraform project.
 - The *major* version, indicates the highest proto version available in the package.
 - The *minor* version, indicates the latest update of the highest version available in the package.
 - The *patch* version, is independent from terraform, can be used internally to fix a package with build failures.

Here is the content of each version (to be updated on each *major* or *minor* release):

| **Version** | **Packages** |
| --- | --- |
| `5.2.0` | `tfplugin5` (version `5.2`) |
