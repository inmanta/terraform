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
import datetime
import json
import logging
import os
import subprocess
import threading
from typing import IO, Any, List, Optional

import grpc
import inmanta_plugins.terraform.tfplugin5.tfplugin5_pb2 as tfplugin5_pb2  # type: ignore
import inmanta_plugins.terraform.tfplugin5.tfplugin5_pb2_grpc as tfplugin5_pb2_grpc  # type: ignore
import msgpack
from inmanta_plugins.terraform.helpers.utils import fill_partial_state
from inmanta_plugins.terraform.tf.data import Diagnostic
from inmanta_plugins.terraform.tf.exceptions import (
    PluginException,
    PluginInitException,
    PluginNotReadyException,
    PluginResponseException,
)
from inmanta_plugins.terraform.tf.terraform_resource_state import TerraformResourceState

MAGIC_NAME = "TF_PLUGIN_MAGIC_COOKIE"
MAGIC_VALUE = "d602bf8f470bc67ca7faa0386276bbdd4330efaf76d1a219cb4d6991ca9872b2"
CORE_PROTOCOL_VERSION = 1
SUPPORTED_VERSIONS = (4, 5)
TERRAFORM_VERSION = "0.14.10"


def format_log_line(line: str, prefixes: List[str], show_time: bool = True) -> str:
    prefix = "[" + "][".join(prefixes) + "]"
    if show_time:
        prefix = f"[{str(datetime.datetime.now())}] {prefix}"

    return f"{prefix}: {line.strip()}\n"


def parse_response(input: Optional[Any]) -> Optional[Any]:
    if input is None:
        return None

    def decode_if_bytes(x):
        return x.decode("utf-8") if isinstance(x, bytes) else x

    if isinstance(input, bytes):
        return input.decode("utf-8")

    if isinstance(input, list):
        return [parse_response(item) for item in input]

    if isinstance(input, dict):
        return {
            decode_if_bytes(key): parse_response(value) for key, value in input.items()
        }

    if isinstance(input, set):
        raise Exception("A response from msgpack shouldn't contain any set")

    return input


def raise_for_diagnostics(diagnostics: List[Any], message: str):
    """
    Diagnostics are the holders of errors that occurred during an action done by
    the provider.  If we get any, something failed, we should raise an error.
    """
    if diagnostics:
        raise PluginResponseException(
            message,
            [Diagnostic.parse(raw_diagnostic) for raw_diagnostic in diagnostics],
        )


class TerraformResourceClient:
    def __init__(
        self,
        provider_path: str,
        log_file_path: str,
        resource_state: TerraformResourceState,
    ) -> None:
        self._provider_path: str = provider_path
        self._log_file_path: str = log_file_path
        self._proc: subprocess.Popen = None
        self._stub: tfplugin5_pb2_grpc.ProviderStub = None
        self._stdout_thread: threading.Thread = None
        self._stderr_thread: threading.Thread = None
        self._schema = None
        self._resource_state = resource_state

        # This logger will go into the agent's logs
        self.logger = logging.getLogger(resource_state.resource_id + "-terres-client")

    def _io_logger(self, stream: IO[bytes], logger_name: str) -> None:
        # This logger will go into the agent's logs and into a file
        # this file is picked up by the handler in the post method.  It then adds it to
        # the handler ctx logger and remove the file.
        logger = logging.getLogger(logger_name)
        fh = logging.FileHandler(self._log_file_path, mode="a")
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)

        while self._proc:
            line = stream.readline().decode().strip()
            if not line:
                continue

            logger.info(line)

        logger.removeHandler(fh)

    def _parse_proto(self, line: str) -> str:
        parts = line.split("|")
        if len(parts) < 4:
            raise PluginInitException(f"Invalid protocol response of plugin: '{line}'")

        core_version = int(parts[0])
        if core_version != CORE_PROTOCOL_VERSION:
            raise PluginInitException(
                f"Invalid core protocol version: '{core_version}' (expected {CORE_PROTOCOL_VERSION})"
            )

        proto_version = int(parts[1])
        if proto_version not in SUPPORTED_VERSIONS:
            raise PluginInitException(
                "Invalid protocol version for plugin %d. Only %s supported.",
                proto_version,
                SUPPORTED_VERSIONS,
            )

        proto_type = parts[2]
        if proto_type != "unix":
            raise PluginInitException(
                f"Only unix sockets are supported, but got '{proto_type}'"
            )

        proto = parts[4]
        if proto != "grpc":
            raise PluginInitException(
                f"Only GRPC protocol is supported, but got '{proto}'"
            )

        return f"{proto_type}://{parts[3]}"

    def _configure(self, provider_config: dict) -> None:
        base_config = fill_partial_state(provider_config, self.provider_schema.block)

        result = self._stub.Configure(
            tfplugin5_pb2.Configure.Request(
                terraform_version=TERRAFORM_VERSION,
                config=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb(base_config)),
            )
        )

        raise_for_diagnostics(result.diagnostics, "Failed to configure the plugin")

    def open(self, provider_config: dict) -> None:
        """
        This methods has to be called once for each provider
        It will create a new process and execute the provider binary in it.
        We then create a stub, to communicate via grpc with the provider.
        End finally we apply to the running provider the provided configuration.

        :param provider_config: The config to apply to the provider.  Missing values will
            be set to None automatically.
        """
        if self._proc:
            return

        env = dict(os.environ)
        env.update(
            {
                MAGIC_NAME: MAGIC_VALUE,
                "PLUGIN_MIN_PORT": "40000",
                "PLUGIN_MAX_PORT": "41000",
                "PLUGIN_PROTOCOL_VERSIONS": ",".join(
                    [str(v) for v in SUPPORTED_VERSIONS]
                ),
                "TF_LOG": "TRACE",
                "TF_LOG_LEVEL": "DEBUG",
            },
        )
        self._proc = subprocess.Popen(
            self._provider_path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.logger.debug(f"Started plugin with pid {self._proc.pid}")

        line = self._proc.stdout.readline().decode().strip()
        proto_addr = self._parse_proto(line)

        self._stdout_thread = threading.Thread(
            target=self._io_logger,
            args=(
                self._proc.stdout,
                self.resource_state.resource_id + "-terprov-stdout",
            ),
        )
        self._stdout_thread.start()

        self._stderr_thread = threading.Thread(
            target=self._io_logger,
            args=(
                self._proc.stderr,
                self.resource_state.resource_id + "-terprov-stderr",
            ),
        )
        self._stderr_thread.start()

        channel = grpc.insecure_channel(proto_addr)
        self._stub = tfplugin5_pb2_grpc.ProviderStub(channel)

        self._configure(provider_config)

        self.logger.debug("Provider is ready to accept requests")

    def close(self) -> None:
        """
        This method has to be called once for each provider, once we are done with it.
        It will close the opened stub, kill the provider process, and wait for the
        I/O threads to join.

        After this method is called, open needs to be called again if we want to use the provider.
        """
        if self._stub:
            self._stub.Stop(tfplugin5_pb2.Stop.Request())
            self._stub = None

        if self._proc:
            self._proc.kill()
            self._proc.wait(5)
            self._proc = None

        if self._stdout_thread:
            self._stdout_thread.join(5)

        if self._stderr_thread:
            self._stderr_thread.join(5)

        self.logger.debug("Provider has been stopped")

    @property
    def schema(self) -> Any:
        if not self.ready:
            raise PluginNotReadyException("Can not get resource schema")

        if not self._schema:
            self._schema = self._stub.GetSchema(
                tfplugin5_pb2.GetProviderSchema.Request()
            )

        return self._schema

    @property
    def provider_schema(self) -> Any:
        return self.schema.provider

    @property
    def resource_schema(self) -> Any:
        return self.schema.resource_schemas.get(self.resource_state.type_name)

    @property
    def ready(self) -> bool:
        return self._proc is not None and self._stub is not None

    @property
    def resource_state(self) -> TerraformResourceState:
        return self._resource_state

    def import_resource(self, id: str) -> Optional[dict]:
        if (
            self.resource_state.state is not None
            and self.resource_state.state.get("id") != id
        ):
            raise PluginException(
                "Can not import a resource which already has a state and has "
                f"a different id: {self.resource_state.state.get('id')} != {id}"
            )

        result = self._stub.ImportResourceState(
            tfplugin5_pb2.ImportResourceState.Request(
                type_name=self.resource_state.type_name,
                id=id,
            )
        )

        self.logger.debug(f"Import resource response: {str(result)}")

        raise_for_diagnostics(result.diagnostics, "Failed to import the resource")

        imported = list(result.imported_resources)

        if len(imported) != 1:
            raise PluginException(
                "The resource import failed, wrong amount of resources returned: "
                f"got {len(imported)} (expected 1)"
            )

        self.resource_state.state = parse_response(
            msgpack.unpackb(imported[0].state.msgpack)
        )
        self.resource_state.private = imported[0].private

        return self.resource_state.state

    def read_resource(self) -> Optional[dict]:
        if self.resource_state.state is None:
            return None

        self.resource_state.raise_if_not_complete()

        result = self._stub.ReadResource(
            tfplugin5_pb2.ReadResource.Request(
                type_name=self.resource_state.type_name,
                current_state=tfplugin5_pb2.DynamicValue(
                    msgpack=msgpack.packb(self.resource_state.state)
                ),
                private=self.resource_state.private,
            )
        )

        self.logger.debug(f"Read resource response: {str(result)}")

        raise_for_diagnostics(result.diagnostics, "Failed to read the resource")

        self.resource_state.state = parse_response(
            msgpack.unpackb(result.new_state.msgpack)
        )
        self.resource_state.private = result.private

        self.logger.info(
            f"Read resource with state: {json.dumps(self.resource_state.state, indent=2)}"
        )

        return self.resource_state.state

    def create_resource(self, desired: dict) -> Optional[dict]:
        base_conf = fill_partial_state(desired, self.resource_schema.block)

        # Plan
        result = self._stub.PlanResourceChange(
            tfplugin5_pb2.PlanResourceChange.Request(
                type_name=self.resource_state.type_name,
                prior_state=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb(None)),
                proposed_new_state=tfplugin5_pb2.DynamicValue(
                    msgpack=msgpack.packb(base_conf)
                ),
                config=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb(base_conf)),
                prior_private=None,
            )
        )

        self.logger.debug(f"Plan create resource response: {str(result)}")

        raise_for_diagnostics(
            result.diagnostics, "Failed to plan creation of the resource"
        )

        # Apply
        result = self._stub.ApplyResourceChange(
            tfplugin5_pb2.ApplyResourceChange.Request(
                type_name=self.resource_state.type_name,
                prior_state=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb(None)),
                planned_state=result.planned_state,
                config=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb(base_conf)),
                planned_private=result.planned_private,
            )
        )

        self.logger.debug(f"Create resource response: {str(result)}")

        self.resource_state.private = result.private
        self.resource_state.state = parse_response(
            msgpack.unpackb(result.new_state.msgpack)
        )

        raise_for_diagnostics(result.diagnostics, "Failed to create the resource")

        return self.resource_state.state

    def update_resource(self, desired: dict) -> Optional[dict]:
        """
        Perform an update (or a replace if required) of the specified resource.
        The following document's comments were a great help in the process of wiring this
        all up.
        https://github.com/hashicorp/terraform/blob/main/providers/provider.go
        """
        self.resource_state.raise_if_not_complete()

        desired_conf = fill_partial_state(desired, self.resource_schema.block)

        prior_state = msgpack.packb(self.resource_state.state)

        # Plan
        result = self._stub.PlanResourceChange(
            tfplugin5_pb2.PlanResourceChange.Request(
                type_name=self.resource_state.type_name,
                prior_state=tfplugin5_pb2.DynamicValue(msgpack=prior_state),
                proposed_new_state=tfplugin5_pb2.DynamicValue(
                    msgpack=msgpack.packb(desired_conf)
                ),
                config=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb(desired_conf)),
                prior_private=self.resource_state.private,
            )
        )

        self.logger.debug(f"Plan update resource response: {str(result)}")

        raise_for_diagnostics(
            result.diagnostics, "Failed to plan update of the resource"
        )

        # Checking if the plan detected any changes to apply, this condition will only
        # be true if we failed some things in our diff computation.  This can happen
        # as the diff is currently computed with the attributes of the entities and the
        # state deployed, and the attributes of the entities might not contain some values
        # which have default assignments in the provider.
        if result.planned_state.msgpack == prior_state:
            self.logger.warning(
                "The client had to skip an update because there was no difference between the desired and current state."
            )
            return self.resource_state.state

        if result.requires_replace:
            self.delete_resource()
            return self.create_resource(desired)

        # Apply
        result = self._stub.ApplyResourceChange(
            tfplugin5_pb2.ApplyResourceChange.Request(
                type_name=self.resource_state.type_name,
                prior_state=tfplugin5_pb2.DynamicValue(
                    msgpack=msgpack.packb(self.resource_state.state)
                ),
                planned_state=result.planned_state,
                config=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb(desired_conf)),
                planned_private=result.planned_private,
            )
        )

        self.logger.debug(f"Update resource response: {str(result)}")

        self.resource_state.state = parse_response(
            msgpack.unpackb(result.new_state.msgpack)
        )
        self.resource_state.private = result.private

        raise_for_diagnostics(result.diagnostics, "Failed to update the resource")

        return self.resource_state.state

    def delete_resource(self) -> None:
        self.resource_state.raise_if_not_complete()

        # Plan
        result = self._stub.PlanResourceChange(
            tfplugin5_pb2.PlanResourceChange.Request(
                type_name=self.resource_state.type_name,
                prior_state=tfplugin5_pb2.DynamicValue(
                    msgpack=msgpack.packb(self.resource_state.state)
                ),
                proposed_new_state=tfplugin5_pb2.DynamicValue(
                    msgpack=msgpack.packb(None)
                ),
                config=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb({})),
                prior_private=self.resource_state.private,
            )
        )

        self.logger.debug(f"Plan delete resource response: {str(result)}")

        raise_for_diagnostics(
            result.diagnostics, "Failed to plan deleting of the resource"
        )

        # Apply
        result = self._stub.ApplyResourceChange(
            tfplugin5_pb2.ApplyResourceChange.Request(
                type_name=self.resource_state.type_name,
                prior_state=tfplugin5_pb2.DynamicValue(
                    msgpack=msgpack.packb(self.resource_state.state)
                ),
                planned_state=result.planned_state,
                config=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb({})),
                planned_private=result.planned_private,
            )
        )

        self.logger.debug(f"Delete resource response: {str(result)}")

        raise_for_diagnostics(result.diagnostics, "Failed to delete the resource")

        self.resource_state.purge()
