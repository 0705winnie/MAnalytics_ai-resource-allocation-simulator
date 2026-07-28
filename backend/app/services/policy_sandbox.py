"""
Sandboxed execution of a student's `admission_policy` function.

The student submits Python source as a string from the Page 2 editor. We
compile and exec it against a restricted namespace (no `import`, no
filesystem/network/env access) and hand back a bound callable that the
simulation engine can call once per arriving request.

This mirrors the "whitelisted sandbox" approach used elsewhere in this
project's history for student-submitted routing code: fine for classroom use,
not adversarial-grade. If this is ever exposed to the public internet, swap
it for subprocess/container isolation.
"""

from __future__ import annotations

import builtins as _builtins
from typing import Any, Callable, Dict

_SAFE_BUILTIN_NAMES = (
    "abs", "all", "any", "bool", "dict", "enumerate", "float", "int",
    "len", "list", "max", "min", "range", "round", "sorted", "str",
    "sum", "tuple", "zip", "True", "False", "None",
)

_SAFE_BUILTINS: Dict[str, Any] = {
    name: getattr(_builtins, name) for name in _SAFE_BUILTIN_NAMES if hasattr(_builtins, name)
}

_ENTRY_POINT = "admission_policy"


class PolicyError(Exception):
    """Raised when the student's code fails to compile or define the entry point."""


class PolicyRuntimeError(Exception):
    """Raised when a single call into the student's policy raises or misbehaves."""


def compile_policy(code: str) -> Callable[[dict, dict, dict, dict], int]:
    """
    Compile the student's source and return a callable with signature
    `admission_policy(request, state, history, params) -> int`.

    Raises PolicyError if the code doesn't compile or doesn't define
    `admission_policy`.
    """
    namespace: Dict[str, Any] = {"__builtins__": dict(_SAFE_BUILTINS)}

    try:
        compiled = compile(code, "<student_policy>", "exec")
        exec(compiled, namespace)
    except Exception as e:
        raise PolicyError(f"Policy code failed to compile: {e}") from e

    policy_fn = namespace.get(_ENTRY_POINT)
    if not callable(policy_fn):
        raise PolicyError(
            f"Policy code must define a callable `{_ENTRY_POINT}(request, state, history, params)`."
        )

    return policy_fn


def call_policy(
    policy_fn: Callable[[dict, dict, dict, dict], int],
    request: dict,
    state: dict,
    history: dict,
    params: dict,
) -> int:
    """
    Invoke the policy for a single request. Returns the cluster id the
    student's code chose. Raises PolicyRuntimeError on any exception or
    non-int return — callers should treat that as an auto-reject.
    """
    try:
        result = policy_fn(request, state, history, params)
    except Exception as e:
        raise PolicyRuntimeError(f"Policy raised an exception: {e}") from e

    if not isinstance(result, int) or isinstance(result, bool):
        raise PolicyRuntimeError(
            f"Policy must return an int cluster id or 0 to reject, got {type(result).__name__}."
        )

    return result
