"""Dependency binding helpers for extracted application modules.

Legacy modules may still refresh their namespace at call time. New migrations
should prefer :func:`dependency_proxy`, which exposes only named application
dependencies and never mutates the receiving module's globals.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, MutableMapping
from functools import wraps
from typing import Any, TypeVar


View = TypeVar("View", bound=Callable[..., Any])
ContextProvider = Callable[[], Mapping[str, Any]]
ProviderGetter = Callable[[], ContextProvider | None]


class DependencyProxy:
    """Resolve an explicit set of dependencies from a dynamic provider."""

    def __init__(
        self,
        provider: ContextProvider,
        allowed_names: Collection[str],
        label: str = 'application',
    ) -> None:
        self._provider = provider
        self._allowed_names = frozenset(allowed_names)
        self._label = label

    def __getattr__(self, name: str) -> Any:
        if name not in self._allowed_names:
            raise AttributeError(name)
        context = self._provider()
        try:
            return context[name]
        except KeyError as exc:
            raise RuntimeError(
                f'{self._label} dependency {name!r} is not configured'
            ) from exc


def dependency_proxy(
    provider: ContextProvider,
    allowed_names: Collection[str],
    label: str = 'application',
) -> DependencyProxy:
    """Return a non-mutating resolver for explicitly named dependencies."""
    return DependencyProxy(provider, allowed_names, label)


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
