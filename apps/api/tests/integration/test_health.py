import httpx
import pytest

from clipforge.api.app import app


@pytest.mark.asyncio
async def test_healthz_endpoint():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readyz_endpoint():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/readyz")
        assert response.status_code in [200, 503]
        data = response.json()
        assert "checks" in data or "detail" in data
