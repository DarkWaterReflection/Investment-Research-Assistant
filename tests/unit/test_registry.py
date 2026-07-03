import httpx
import pytest

import collectors  # noqa: F401  (populate registry)
from collectors.registry import build_enabled, register, registered_names


def test_builtin_collectors_are_registered():
    assert {"firecrawl", "sec_edgar", "serpapi"} <= set(registered_names())


def test_duplicate_registration_rejected():
    with pytest.raises(ValueError, match="already registered"):
        register("sec_edgar")(lambda client, settings: None)


async def test_keyless_settings_enable_only_credential_free_collectors(settings_no_keys):
    async with httpx.AsyncClient() as client:
        enabled = build_enabled(client, settings_no_keys)
    assert [c.name for c in enabled] == ["sec_edgar"]


async def test_all_collectors_enabled_with_keys(settings):
    async with httpx.AsyncClient() as client:
        enabled = build_enabled(client, settings)
    assert [c.name for c in enabled] == ["firecrawl", "sec_edgar", "serpapi"]


async def test_only_filter_restricts_selection(settings):
    async with httpx.AsyncClient() as client:
        enabled = build_enabled(client, settings, only={"serpapi"})
    assert [c.name for c in enabled] == ["serpapi"]
