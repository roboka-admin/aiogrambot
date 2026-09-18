import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from services.ai.adapters.http import post_json
from services.ai.provider import AIAuthError, AIProviderError, AIQuotaError


async def _handler(request: web.Request) -> web.Response:
    status = int(request.match_info["status"])
    if status == 200:
        return web.json_response({"ok": True, "echo": await request.json()})
    return web.Response(status=status, text="  some   error body  ")


@pytest.fixture
async def server():
    app = web.Application()
    app.router.add_post("/{status}", _handler)
    async with TestServer(app) as test_server:
        yield test_server


@pytest.mark.asyncio
async def test_post_json_returns_body(server):
    data = await post_json(str(server.make_url("/200")), headers={}, payload={"a": 1})
    assert data == {"ok": True, "echo": {"a": 1}}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "error"),
    [(429, AIQuotaError), (401, AIAuthError), (403, AIAuthError), (500, AIProviderError)],
)
async def test_post_json_maps_http_errors(server, status, error):
    with pytest.raises(error) as exc_info:
        await post_json(str(server.make_url(f"/{status}")), headers={}, payload={})
    assert "some error body" in str(exc_info.value)


@pytest.mark.asyncio
async def test_post_json_wraps_connection_errors():
    with pytest.raises(AIProviderError):
        await post_json("http://127.0.0.1:9/x", headers={}, payload={})
