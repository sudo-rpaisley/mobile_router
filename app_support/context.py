"""Shared dependency-context binding for extracted modules.

The legacy application still exposes mutable dependencies through ``app.py``.
Extracted modules use these helpers to refresh their module namespace at call
time, preserving test monkey-patching until dependency injection is completed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
from functools import wraps
from typing import Any, TypeVar


View = TypeVar("View", bound=Callable[..., Any])
ContextProvider = Callable[[], Mapping[str, Any]]
ProviderGetter = Callable[[], ContextProvider | None]


def context_refresher(
    namespace: MutableMapping[str, Any],
    provider_getter: ProviderGetter,
) -> Callable[[View], View]:
    """Return a decorator that refreshes ``namespace`` before each call."""

    def refresh(view: View) -> View:
        @wraps(view)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            provider = provider_getter()
            if provider is not None:
                namespace.update(provider())
            return view(*args, **kwargs)

        return wrapped  # type: ignore[return-value]

    return refresh


def bind_context(
    namespace: MutableMapping[str, Any],
    provider: ContextProvider,
) -> Callable[[View], View]:
    """Populate a module namespace immediately and return its refresher."""

    namespace.update(provider())
    return context_refresher(namespace, lambda: provider)
