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
from enum import IntEnum
from typing import Any, List, Optional


class DiagnosticSeverity(IntEnum):

    INVALID = 0
    ERROR = 1
    WARNING = 2

    def __str__(self) -> str:
        return self.name

    def parse(value: int) -> "DiagnosticSeverity":
        values = [
            DiagnosticSeverity.INVALID,
            DiagnosticSeverity.ERROR,
            DiagnosticSeverity.WARNING,
        ]
        if value >= len(values) or value < 0 or not isinstance(value, int):
            raise ValueError(
                f"The diagnostic severity can only be an integer between 0 and {len(values)}"
            )

        return values[value]


class AttributePathStep:
    def __init__(
        self,
        attribute_name: str,
        element_key_string: str,
        element_key_int: int,
    ) -> None:
        self.attribute_name = attribute_name
        self.element_key_string = element_key_string
        self.element_key_int = element_key_int

    def __str__(self) -> str:
        return self.attribute_name

    def parse(raw_step: Any) -> "AttributePathStep":
        return AttributePathStep(
            raw_step.attribute_name,
            raw_step.element_key_string,
            raw_step.element_key_int,
        )


class AttributePath:
    def __init__(self, steps: List[AttributePathStep]) -> None:
        self.steps = steps

    def __str__(self) -> str:
        return ".".join(str(step) for step in self.steps)

    def parse(raw_attribute_path: Any) -> "AttributePath":
        return AttributePath(
            [AttributePathStep.parse(raw_step) for raw_step in raw_attribute_path.steps]
        )


class Diagnostic:
    def __init__(
        self,
        severity: DiagnosticSeverity,
        summary: str,
        detail: str,
        attribute_path: Optional[AttributePath],
    ) -> None:
        self.severity = severity
        self.summary = summary
        self.detail = detail
        self.attribute_path = attribute_path

    def __str__(self) -> str:
        suffix = f" at {self.attribute_path}" if self.attribute_path is not None else ""
        return f"{str(self.severity)}: {self.summary}{suffix}"

    def parse(raw_diagnostic: Any) -> "Diagnostic":

        attribute_path = (
            AttributePath.parse(raw_diagnostic.attribute_path)
            if hasattr(raw_diagnostic, "attribute_path")
            and raw_diagnostic.attribute_path is not None
            else None
        )
        return Diagnostic(
            DiagnosticSeverity.parse(raw_diagnostic.severity),
            raw_diagnostic.summary,
            raw_diagnostic.detail,
            attribute_path,
        )
