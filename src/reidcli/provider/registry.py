"""Provider registry: config-driven registration of providers by name."""
from __future__ import annotations

from reidcli.config.models import Config, ProviderConfig
from reidcli.diagnostics.logger import get_logger
from reidcli.provider.anthropic import AnthropicProvider
from reidcli.provider.base import BaseProvider
from reidcli.provider.stub import StubProvider

log = get_logger("reidcli.provider")


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}

    def register(self, name: str, provider: BaseProvider) -> None:
        self._providers[name] = provider
        log.debug("registered provider: %s", name)

    def get(self, name: str) -> BaseProvider:
        if name not in self._providers:
            raise KeyError(f"provider '{name}' not registered")
        return self._providers[name]

    def names(self) -> list[str]:
        return list(self._providers)


def default_registry(config: Config) -> ProviderRegistry:
    """Build the default registry. Stub is always available; Anthropic auto-registers
    from ANTHROPIC_* env vars when present."""
    reg = ProviderRegistry()
    reg.register("stub", StubProvider())

    anthropic = AnthropicProvider.from_env()
    if anthropic is not None:
        reg.register("anthropic", anthropic)
        # If the config's default_provider is "stub" but we have a real provider,
        # switch to it so the user gets real responses by default.
        if config.default_provider == "stub":
            config.default_provider = "anthropic"
            if anthropic.default_model:
                config.providers["anthropic"] = config.providers.get("anthropic") or ProviderConfig(
                    name="anthropic", default_model=anthropic.default_model
                )
                if not config.providers["anthropic"].default_model:
                    config.providers["anthropic"].default_model = anthropic.default_model
            log.debug("auto-registered anthropic provider from env vars")

    for name in config.providers:
        if name in ("stub", "anthropic"):
            continue
        log.warning("provider '%s' configured but no client implementation yet (TODO)", name)
    return reg
