import httpx
import pytest

from collectors.base import CompanyTarget
from core.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        firecrawl_api_key="fc-test-key",
        serpapi_api_key="serp-test-key",
        sec_edgar_user_agent="IRA-tests test@example.com",
    )


@pytest.fixture
def settings_no_keys() -> Settings:
    return Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.fixture
async def http_client():
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def target() -> CompanyTarget:
    return CompanyTarget(name="Acme Robotics", website="https://acme-robotics.example")
