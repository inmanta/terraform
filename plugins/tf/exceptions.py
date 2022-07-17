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


from typing import List

from inmanta_plugins.terraform.tf.data import Diagnostic


class PluginException(Exception):
    def __init__(self, message: str) -> None:
        """
        This error is raised from the plugin client.
        """
        super().__init__(message)


class ResourceLookupException(PluginException, LookupError):
    def __init__(self, message: str, resource_type: str, id: str) -> None:
        """
        This is exception is raised if the plugin client fails to find a resource
        in the import method.
        """
        super().__init__(f"Failed to import {resource_type} with id {id}: {message}")
        self.message = message
        self.resource_type = resource_type
        self.id = id


class PluginResponseException(PluginException):
    def __init__(self, message: str, diagnostics: List[Diagnostic]) -> None:
        """
        This error is raised whenever we receive a response from the plugin which
        contains diagnostics.
        """
        details = "\n+\t".join([str(diagnostic) for diagnostic in diagnostics])
        super().__init__(f"{message}: {details}")
        self._diagnostics = diagnostics

    def diagnostics(self) -> List[Diagnostic]:
        return self._diagnostics


class PluginInitException(PluginException):
    def __init__(self, message: str) -> None:
        """
        This error is raised during the configuration of the plugin client if
        something goes wrong.
        """
        super().__init__(f"Failed to initialize the plugin: {message}")


class PluginNotReadyException(PluginException):
    def __init__(self, message: str) -> None:
        """
        This error is raised if some of the client methods are called while the client
        hasn't been initialized yet.
        """
        super().__init__(
            f"Client is not ready, did you call 'open()' already? {message}"
        )


class InstallerException(Exception):
    def __init__(self, message: str) -> None:
        """
        This error is raised from the plugin installer.
        """
        super().__init__(message)


class InstallerNotReadyException(InstallerException):
    def __init__(self, message: str) -> None:
        """
        This error is raised from the plugin installer whenever some step of the installation
        has been skiped or some resources are not ready/configured correctly.
        """
        super().__init__(message)
