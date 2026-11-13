"""Domain-specific exception hierarchy for fail-closed CLI diagnostics."""

from __future__ import annotations

from pathlib import Path


class AgentsError(Exception):
    """Base error carrying operation context so failures diagnose in one pass."""

    def __init__(
        self,
        operation: str,
        target: str | Path | None,
        reason: str,
    ) -> None:
        self.operation = operation
        self.target = str(target) if target is not None else ""
        self.reason = reason
        location = f" ({self.target})" if self.target else ""
        super().__init__(f"{operation}{location}: {reason}")


class CatalogValidationError(AgentsError):
    """Raised when repository catalog assets violate schema or structure."""


class RenderError(AgentsError):
    """Raised when rendering role markdown or loading model mappings fails."""


class DestinationConflictError(AgentsError):
    """Raised before writing if a destination overlaps repo or unmanaged files."""


class DeploymentError(AgentsError):
    """Raised when filesystem installation or removal fails."""
