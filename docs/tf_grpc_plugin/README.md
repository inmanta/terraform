# tf_grpc_plugin

This folder contains the [protobuf file](proto/inmanta_plugins/terraform/tfplugin5/tfplugin5.proto) specifying the interactions with the Terraform providers binaries.  This file comes directly from terraform project on github: [https://github.com/hashicorp/terraform/blob/main/docs/plugin-protocol/tfplugin5.2.proto](https://github.com/hashicorp/terraform/blob/main/docs/plugin-protocol/tfplugin5.2.proto).

Is has been used to generate the package `inmanta_plugins.terraform.tfplugin5` in this module's plugins.  If for any reason, it has to be generated again, a make command has been added in this module's top level Makefile: `make tfplugin5`.
