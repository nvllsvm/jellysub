import unittest

import aiohttp.test_utils
import aiohttp.web
import jellysub.app
import yarl


class MockJellyfinServer(aiohttp.web.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_routes([
            aiohttp.web.route(
                'POST', '/Users/authenticatebyname', self.authenticate),
        ])

    @staticmethod
    async def authenticate(request):
        body = await request.json()
        if body['Username'] != request.app['username']:
            return aiohttp.web.Response(status=401)
        if body['Pw'] != request.app['password']:
            return aiohttp.web.Response(status=401)
        return aiohttp.web.json_response({'AccessToken': 'ZZZ'})


class AuthTests(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()

        self.username = 'abc'
        self.password = 'xyz'

        self.mock_jellyfin = aiohttp.test_utils.TestServer(
            MockJellyfinServer())

        self.mock_jellyfin.app['username'] = 'abc'
        self.mock_jellyfin.app['password'] = 'xyz'

        await self.mock_jellyfin.start_server()

        self.app = jellysub.app.Application(
            str(yarl.URL.build(
                scheme='http',
                host=self.mock_jellyfin.host,
                port=self.mock_jellyfin.port)))
        self.server = aiohttp.test_utils.TestServer(self.app)
        self.client = aiohttp.test_utils.TestClient(self.server)
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)
        self.addAsyncCleanup(self.app.cleanup)

    async def test_valid_auth(self):
        params = {
            'u': 'abc',
            'p': 'xyz'
        }
        resp = await self.client.request(
            'GET', '/rest/ping.view', params=params)
        self.assertEqual(resp.status, 200)

    async def test_invalid_auth(self):
        correct_params = {
            'u': self.username,
            'p': self.password,
        }

        for key in correct_params:
            params = correct_params.copy()
            params[key] = 'X'
            resp = await self.client.request(
                'GET', '/rest/ping.view', params=params)
            self.assertEqual(resp.status, 401)

    async def test_missing_required_query_param(self):
        required = {
            'u': self.username,
            'p': self.password,
        }
        for key in required:
            params = required.copy()
            params.pop(key)
            resp = await self.client.request(
                'GET', '/rest/ping.view', params=params)
            self.assertEqual(resp.status, 400)
