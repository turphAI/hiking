"""ops — hiking's _ops producer. Mechanism comes from turphOps ops_core.

One copy of the shared core, imported (design-journal 035, docs/specs/
shared-core.md). This bootstrap is the only thing every producer carries:
it finds the turphOps checkout and fails loudly if it isn't there. Appended,
not prepended, so nothing in turphOps can shadow this app's own modules.
"""
import os
import sys
from pathlib import Path

try:
    import ops_core  # noqa: F401
except ImportError:
    _root = Path(os.environ.get("TURPHOPS_ROOT", str(Path.home() / "Projects" / "turphOps"))).expanduser()
    sys.path.append(str(_root))
    try:
        import ops_core  # noqa: F401
    except ImportError:
        raise ImportError(f"ops_core not found at {_root}: check out turphOS/turphOps there, "
                          "or set TURPHOPS_ROOT for this job") from None
