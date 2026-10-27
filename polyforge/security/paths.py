"""Read-only path policy needed by the first offline capability."""

from pathlib import Path

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError


def workspace_input(workspace: Path, supplied: Path) -> Path:
    """Resolve a local input without creating directories or following escape links.

    Phase 1 adds worker-level filesystem policies. This function only confines
    input reads; it is not protection against malicious local plugin execution.
    """
    root = workspace.resolve()
    path = supplied if supplied.is_absolute() else root / supplied
    if ".." in supplied.parts:
        raise InputError(
            "Parent traversal is not allowed", kind=ErrorKind.POLICY_DENIED, code="PF-POLICY-PATH"
        )
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise InputError(
            "Input must remain inside the authorized workspace",
            kind=ErrorKind.POLICY_DENIED,
            code="PF-POLICY-PATH",
        )
    if not root.is_dir():
        raise InputError("Workspace must be an existing directory")
    return resolved
