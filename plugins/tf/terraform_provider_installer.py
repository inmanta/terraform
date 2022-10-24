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
import hashlib
import platform
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Tuple

import requests

from inmanta_plugins.terraform.tf.exceptions import (
    InstallerException,
    InstallerNotReadyException,
)

BASE_URL = "https://registry.terraform.io/v1/providers"


class ProviderInstaller:
    def __init__(
        self, namespace: str, type: str, version: Optional[str] = None
    ) -> None:
        self.namespace = namespace
        self.type = type
        self.version = version
        self._download_url: Optional[str] = None
        self._shasum: Optional[str] = None
        self._download_path: Optional[str] = None
        self._filename: Optional[str] = None

    @property
    def download_url(self) -> str:
        if self._download_url is None:
            raise ValueError("Download url has not been set")

        return self._download_url

    @property
    def download_path(self) -> str:
        if self._download_path is None:
            raise ValueError("Download path has not been set")

        return self._download_path

    @property
    def filename(self) -> str:
        if self._filename is None:
            raise ValueError("Filename has not been set")

        return self._filename

    @property
    def shasum(self) -> str:
        if self._shasum is None:
            raise ValueError("Shasum has not been set")

        return self._shasum

    def resolve(self):
        """
        Check if a matching provider can be found for the namespace, type and version specified in the
        constructor.  If no version was specified then, the latest one is picked automatically.
        """
        system = platform.system().lower()
        arch = platform.machine()
        if arch == "x86_64":
            arch = "amd64"

        # Get provider available versions
        response = requests.get(f"{BASE_URL}/{self.namespace}/{self.type}", timeout=3)
        response.raise_for_status()
        data = response.json()
        versions = data.get("versions")
        if self.version is None:
            self.version = data.get("version")
        elif self.version not in versions:
            raise InstallerException(
                f"Provided version '{self.version}' is not available for this provider"
            )

        # Get provider specific version info
        response = requests.get(
            f"{BASE_URL}/{self.namespace}/{self.type}/{self.version}/download/{system}/{arch}",
            timeout=3,
        )
        response.raise_for_status()
        data = response.json()
        self._download_url = data.get("download_url")
        self._filename = data.get("filename")
        self._shasum = data.get("shasum", None)

    def download(self, download_path: Optional[str] = None) -> str:
        """
        Download an archive containing the provider binary.  If the download path is specified, it will download it
        there, otherwise it will download it in a temporary file.  If the object knows the checksum of the archive
        (it can discover it during the 'resolve()' call), it will raise an error if the file checksum is a mismatch.

        This methods returns the path to the downloaded archive.

        :param download_path: The optional path where to download the archive.  This should be the full path, not the
            parent directory.
        :return: The path to the downloaded archive
        """
        if self._download_url is None:
            raise InstallerNotReadyException(
                "Can not download provider, not download url provided, did you call 'resolve()' already?"
            )

        # If no download path is provided, we create a temp file
        if download_path is None:
            _, download_path = tempfile.mkstemp()

        download_location = Path(download_path)
        download_location.parent.mkdir(parents=True, exist_ok=True)

        # If we already have a file there, and we have a shasum, we check if the file is
        # already the one we want to download
        if download_location.is_file() and self._shasum is not None:
            with open(download_path, "rb") as f:
                sha256_hash = hashlib.sha256()
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)

                if self.shasum == sha256_hash.hexdigest():
                    self._download_path = download_path
                    return self.download_path

        # The download file should be a file, not a directory
        if download_location.is_dir():
            raise InstallerException("The provided download path is a directory")

        # Download the file and stream the output to a file, while computing the shasum of it
        with requests.get(self.download_url, stream=True, timeout=3) as r:
            r.raise_for_status()
            sha256_hash = hashlib.sha256()
            with open(str(download_location), "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    sha256_hash.update(chunk)
                    f.write(chunk)

        # At this point, if the checksum is wrong, we got a wrong file
        checksum = sha256_hash.hexdigest()
        if self._shasum is not None and checksum != self.shasum:
            raise InstallerException(
                f"Downloaded file has a bad hash: {checksum} (expected {self.shasum})"
            )

        self._download_path = download_path

        return self.download_path

    def install_dry_run(self, install_location: str) -> Tuple[str, str]:
        """
        Perform a dry run of the binary installation.  This methods returns a tuple containing:
         - The location (full file path) where the binary would be extracted
         - The name of the binary inside the archive

        :param install_location: The directory in which the binary should be installed
        :return: The path to the extracted binary, The name of the binary inside the archive
        """
        if self._download_path is None:
            raise InstallerNotReadyException(
                "Can not install provider, not download path provided, did you call 'download()' already?"
            )

        if not Path(self.download_path).is_file():
            raise InstallerNotReadyException(
                f"Can not install provider, no file has been found at the download path location: {self.download_path}"
            )

        install_dir = Path(install_location)
        if not install_dir.is_dir():
            raise InstallerNotReadyException(
                f"Can not install provider, the provided install location is not an existing directory: {install_location}"
            )

        # The downloaded file has to be a zip, containing the binary named under specific conventions.
        # The recognition of the binary amongst all the files is done the same way terraform does it:
        # https://github.com/hashicorp/terraform/blob/main/internal/providercache/cached_provider.go#L103
        with zipfile.ZipFile(self.download_path, "r") as zip:
            binary_file = None
            binary_name = None
            want_prefix = f"terraform-provider-{self.type}"
            for info in zip.infolist():
                if info.is_dir():
                    continue

                if not info.filename.startswith(want_prefix):
                    continue

                remainder = info.filename[len(want_prefix) :]
                if len(remainder) > 0 and remainder[0] not in ["_", "."]:
                    continue

                binary_name = info.filename
                binary_file = install_dir / binary_name

            if binary_name is None:
                raise InstallerException(
                    f"Could not find any executable file starting with {want_prefix}"
                )

        return str(binary_file), binary_name

    def install(self, install_location: str, force: bool = False) -> str:
        """
        Install the previously downloaded binary to the specified location.  If there is already a file
        with the name of the binary in that location, the method raises an exception, unless force is set
        to True.  In that case, the file will be replaced with the one contained in the archive.

        This methods returns the full path of the installed binary.

        :param install_location: The directory in which the binary should be installed
        :param force: Whether to force a reinstall of the binary if it already exists (default: False)
        :return: The path to the extracted binary
        """
        binary_file, binary_name = self.install_dry_run(install_location)
        binary_file_path = Path(binary_file)
        if binary_file_path.exists() and not force:
            raise InstallerException(
                f"Installing this binary would overwrite the following file: {binary_file}"
            )

        with zipfile.ZipFile(self.download_path, "r") as zip:
            zip.extract(binary_name, install_location)

        binary_file_path.chmod(0o774)

        return binary_file
