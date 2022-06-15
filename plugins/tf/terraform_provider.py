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
import subprocess
import threading
from pathlib import Path
from types import TracebackType
from typing import IO, Any, List, Optional, Type

import grpc  # type: ignore
import inmanta_tfplugin.tfplugin5_pb2 as tfplugin5_pb2  # type: ignore
import inmanta_tfplugin.tfplugin5_pb2_grpc as tfplugin5_pb2_grpc  # type: ignore

from inmanta_plugins.terraform.helpers.utils import fill_partial_state

"""
The two import statements above SHOULD NOT BE REMOVED without proper consideration.
Because of a design choice of the protobuf library, we can not simply copy the generated code
in this module's plugins (as the inmanta agent will rename them):

    https://github.com/protocolbuffers/protobuf/issues/9535

Also note that this limitation can not be discovered by simply running this module's test suite
as pytest-inmanta doesn't run a real agent.
Changing those imports and having a successfull test run IS NOT ENOUGH to assume the module
will work.
"""

import msgpack  # type: ignore

from inmanta_plugins.terraform.tf.data import Diagnostic
from inmanta_plugins.terraform.tf.exceptions import (
    PluginInitException,
    PluginNotReadyException,
    PluginResponseException,
)

MAGIC_NAME = "TF_PLUGIN_MAGIC_COOKIE"
MAGIC_VALUE = "d602bf8f470bc67ca7faa0386276bbdd4330efaf76d1a219cb4d6991ca9872b2"
CORE_PROTOCOL_VERSION = 1
SUPPORTED_VERSIONS = (4, 5)
TERRAFORM_VERSION = "0.14.10"


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


class TerraformProvider:
    def __init__(
        self,
        provider_path: str,
        log_file_path: str,
    ) -> None:
        self._provider_path: str = provider_path
        self._log_file_path: str = log_file_path
        self._proc: Optional[subprocess.Popen] = None
        self._stub: Optional[tfplugin5_pb2_grpc.ProviderStub] = None
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._schema = None
        self._name = Path(provider_path).name
        self._configured = False

        # This logger will go into the agent's logs
        self.logger = logging.getLogger(self._name)

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
                "Invalid protocol version for plugin %d. Only %s supported."
                % (proto_version, SUPPORTED_VERSIONS)
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

    def configure(self, provider_config: dict) -> None:
        """
        Configure the provider with the given config.
        """
        base_config = fill_partial_state(provider_config, self.provider_schema.block)

        result = self.stub.Configure(
            tfplugin5_pb2.Configure.Request(
                terraform_version=TERRAFORM_VERSION,
                config=tfplugin5_pb2.DynamicValue(msgpack=msgpack.packb(base_config)),
            )
        )

        raise_for_diagnostics(result.diagnostics, "Failed to configure the plugin")
        self._configured = True

    def open(self) -> None:
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

        stdout = self._proc.stdout
        assert stdout is not None

        stderr = self._proc.stderr
        assert stderr is not None

        line = stdout.readline().decode().strip()
        proto_addr = self._parse_proto(line)

        self._stdout_thread = threading.Thread(
            target=self._io_logger,
            args=(
                stdout,
                self.logger.name + "-stdout",
            ),
        )
        self._stdout_thread.start()

        self._stderr_thread = threading.Thread(
            target=self._io_logger,
            args=(
                stderr,
                self.logger.name + "-stderr",
            ),
        )
        self._stderr_thread.start()

        channel = grpc.insecure_channel(proto_addr)
        self._stub = tfplugin5_pb2_grpc.ProviderStub(channel)

        self.logger.debug("Provider is ready to accept requests")

    def close(self) -> None:
        """
        This method has to be called once for each provider, once we are done with it.
        It will close the opened stub, kill the provider process, and wait for the
        I/O threads to join.

        After this method is called, open needs to be called again if we want to use the provider.
        """
        self._configured = False

        if self._stub is not None:
            self._stub.Stop(tfplugin5_pb2.Stop.Request())
            self._stub = None

        if self._proc is not None:
            self._proc.kill()
            self._proc.wait(5)
            self._proc = None

        if self._stdout_thread is not None:
            self._stdout_thread.join(5)

        if self._stderr_thread is not None:
            self._stderr_thread.join(5)

        self.logger.debug("Provider has been stopped")

    @property
    def schema(self) -> Any:
        if self._proc is None or self._stub is None:
            raise PluginNotReadyException(
                "Can not get resource schema, provider is not ready"
            )

        if not self._schema:
            self._schema = self.stub.GetSchema(
                tfplugin5_pb2.GetProviderSchema.Request()
            )

        return self._schema

    @property
    def provider_schema(self) -> Any:
        return self.schema.provider

    @property
    def ready(self) -> bool:
        return self._proc is not None and self._stub is not None and self._configured

    @property
    def stub(self) -> tfplugin5_pb2_grpc.ProviderStub:
        if self._stub is None:
            raise PluginNotReadyException(
                "The provider hasn't been properly started yet"
            )

        return self._stub

    def __enter__(self) -> "TerraformProvider":
        """
        Enter the context and get the provider object, with the guarantee it
        has been initialized.  The provider is not yet configured at this stage.
        """
        self.open()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type],
        exc_value: Optional[Exception],
        exc_traceback: Optional[TracebackType],
    ) -> None:
        """
        Exit the context, with the guarantee that the provider is stopped.
        """
        self.close()
