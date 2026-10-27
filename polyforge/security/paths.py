"""Read-only path policy needed by the first offline capability."""

import stat
from pathlib import Path, PureWindowsPath

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError


def _deny(message: str) -> InputError:
    return InputError(message, kind=ErrorKind.POLICY_DENIED, code="PF-POLICY-PATH")


def _check_link(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise _deny("Symlinks, junctions and reparse points are not allowed")


class WorkspacePolicy:
    """Confine trusted-local writes; this is not an OS isolation boundary."""

    def __init__(self, root: Path) -> None:
        try:
            original = root.absolute()
            _check_link(original)
            self.root = original.resolve()
            if not self.root.is_dir():
                raise InputError("Workspace must be an existing directory")
        except (OSError, ValueError) as exc:
            if isinstance(exc, InputError):
                raise
            raise InputError(f"Invalid workspace path: {exc}") from exc

    def path(self, supplied: str | Path) -> Path:
        """Reject ambiguous Windows spellings and links before resolving a child."""
        try:
            raw = str(supplied)
            if "\x00" in raw:
                raise _deny("NUL is not allowed in paths")
            parts = raw.replace("\\", "/").split("/")
            if ".." in parts:
                raise _deny("Parent traversal is not allowed")
            candidate = Path(raw)
            if not candidate.is_absolute():
                if PureWindowsPath(raw).drive or raw.startswith(("/", "\\")):
                    raise _deny("Drive-relative and network paths are not allowed")
                candidate = self.root / raw.replace("\\", "/")
            # Windows can spell the same directory with an 8.3 name or a long name.
            # Inspect every original component before resolving aliases, so a junction
            # cannot become an apparently safe canonical child of the workspace.
            current = Path(candidate.anchor)
            _check_link(current)
            reserved = {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10)),
            }
            for part in candidate.parts[1:]:
                if (
                    ":" in part
                    or part.endswith((".", " "))
                    or part.split(".")[0].upper() in reserved
                ):
                    raise _deny("Ambiguous Windows path component")
                current /= part
                _check_link(current)
            resolved = candidate.resolve()
            if not resolved.is_relative_to(self.root):
                raise _deny("Resolved path escapes the authorized workspace")
            return resolved
        except (OSError, ValueError) as exc:
            if isinstance(exc, InputError):
                raise
            raise InputError(f"Invalid workspace-relative path: {exc}") from exc

    def mkdir(self, supplied: str | Path) -> Path:
        path = self.path(supplied)
        path.mkdir(parents=True, exist_ok=True)
        return self.path(path)


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
