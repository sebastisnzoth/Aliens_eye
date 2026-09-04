import pytest
from aiohttp.test_utils import TestClient, TestServer

from aliens_eye.webapp import create_app


@pytest.mark.asyncio
async def test_health_endpoint():
    server = TestServer(create_app())
    client = TestClient(server)
    await client.start_server()
    try:
        response = await client.get('/health')
        assert response.status == 200
        payload = await response.json()
        assert payload['ok'] is True
        assert payload['service'] == 'aliens-eye-web'
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_scan_rejects_invalid_username():
    server = TestServer(create_app())
    client = TestClient(server)
    await client.start_server()
    try:
        response = await client.post('/api/scan', json={'username': 'bad username!'})
        assert response.status == 400
        payload = await response.json()
        assert 'error' in payload
    finally:
        await client.close()
