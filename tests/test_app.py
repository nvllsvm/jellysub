import unittest

import aiohttp.test_utils
import jellysub.__main__

import tests


class PingHandlerTests(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()

        self.app = await jellysub.__main__.get_app(
            str(tests.bootstrap()['mockserver_url']))
        self.server = aiohttp.test_utils.TestServer(self.app)
        self.client = aiohttp.test_utils.TestClient(self.server)
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)
        self.addAsyncCleanup(self.app.cleanup)

    async def test_missing_required_query_param(self):
        required = {
            'u': 'abc',
            'p': 'xyz'
        }
        for key in required:
            params = required.copy()
            params.pop(key)
            resp = await self.client.request(
                'GET', '/ping.view', params=params)
            self.assertEqual(resp.status, 400)
