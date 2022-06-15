import importlib.metadata
import re
import uuid

import aiohttp.web
import yarl

try:
    _VERSION = importlib.metadata.version(__package__)
except importlib.metadata.PackageNotFoundError:
    _VERSION = 'unknown'


class JellyfinClient:
    _CLIENT = 'jellysub'
    _DEVICE = 'jellysub'
    _DEVICE_ID = uuid.uuid4().hex
    _VERSION = _VERSION

    def __init__(self, url):
        self._url = yarl.URL(url)
        self._users = {}
        self._auth_header = {
            'Client': self._CLIENT,
            'Device': self._DEVICE,
            'DeviceId': self._DEVICE_ID,
            'Version': self._VERSION,
        }

    async def open(self):
        self._client = aiohttp.ClientSession()

    async def close(self):
        await self._client.close()

    async def get_user(self, username, password):
        key = (username, password)
        if key not in self._users:
            user = await self._authenticate(username, password)
            if user:
                self._users[key] = user
        return self._users[key]

    async def get_album_artists(self, user):
        url = self._url / 'Artists/AlbumArtists'
        auth = dict(self._auth_header, Token=user['AccessToken'])
        kwargs = {
            'headers': {
                'X-Emby-Authorization': self._build_authorization_header(auth),
            },
            'params': {
                'Recursive': 'true',
                'StartIndex': '0',
                'Limit': '10000',
            }
        }
        async with self._client.get(url, **kwargs) as resp:
            return await resp.json()

    async def get_genres(self, user):
        url = self._url / 'Genres'
        auth = dict(self._auth_header, Token=user['AccessToken'])
        kwargs = {
            'headers': {
                'X-Emby-Authorization': self._build_authorization_header(auth),
            },
            'params': {
                'Recursive': 'true',
                'StartIndex': '0',
                'Limit': '10000',
            }
        }
        async with self._client.get(url, **kwargs) as resp:
            return await resp.json()

    async def get_artist(self, user, artist_id):
        url = self._url / 'Users' / user['User']['Id'] / 'Items' / artist_id
        auth = dict(self._auth_header, Token=user['AccessToken'])
        kwargs = {
            'headers': {
                'X-Emby-Authorization': self._build_authorization_header(auth),
            },
        }
        async with self._client.get(url, **kwargs) as resp:
            return await resp.json()

    async def get_albums(self, user, artist_id=None):
        url = self._url / 'Users' / user['User']['Id'] / 'Items'
        auth = dict(self._auth_header, Token=user['AccessToken'])

        params = {
            'IncludeItemTypes': 'MusicAlbum',
            'Limit': '1000',
            'Recursive': 'true',
            'StartIndex': '0',
        }

        if artist_id is not None:
            params['AlbumArtistIds'] = artist_id

        kwargs = {
            'headers': {
                'X-Emby-Authorization': self._build_authorization_header(auth),
            },
            'params': params
        }
        async with self._client.get(url, **kwargs) as resp:
            return await resp.json()

    async def get_album(self, user, album_id):
        url = self._url / 'Users' / user['User']['Id'] / 'Items'

        auth = dict(self._auth_header, Token=user['AccessToken'])
        kwargs = {
            'headers': {
                'X-Emby-Authorization': self._build_authorization_header(auth),
            },
            'params': {
                'ParentId': album_id,
                'Fields': 'MediaSources',
            }
        }
        async with self._client.get(url, **kwargs) as resp:
            return await resp.json()

    async def download_song(self, user, song_id):
        url = self._url / 'Items' / song_id / 'Download'

        kwargs = {
            'params': {
                'api_key': user['AccessToken']
            }
        }
        async with self._client.get(url, **kwargs) as resp:
            return await resp.read()

    async def get_album_cover(self, album_id):
        url = self._url / 'Items' / album_id / 'Images/Primary/0'

        kwargs = {
            'params': {
                'quality': '90'
            }
        }
        async with self._client.get(url, **kwargs) as resp:
            if resp.status != 200:
                raise ValueError
            return await resp.read()

    async def _authenticate(self, username, password):
        kwargs = {
            'allow_redirects': False,
            'headers': {
                'X-Emby-Authorization': self._build_authorization_header(
                    self._auth_header),
            },
            'json': {
                'Username': username,
                'Pw': password,
            },
        }
        url = self._url / 'Users/authenticatebyname'
        async with self._client.post(url, **kwargs) as resp:
            if resp.status == 200:
                return await resp.json()

    @staticmethod
    def _parse_authorization_header(header):
        # these are always required
        result = {
            'Device': None,
            'DeviceId': None,
            'Version': None,
        }
        # this is only required when accessing authorized resource
        result['Token'] = None

        # required during initial auth
        result['Client'] = None

        AUTH_REGEX = re.compile(r'\s(\w+)="(\S*)"')

        for x in AUTH_REGEX.finditer(header):
            key, value = x.groups()
            if key not in result or result[key] is not None:
                raise ValueError(header)
            result[key] = value

        if not all([v
                    for k, v in result.items()
                    if k not in ('Client', 'Token')]):
            raise ValueError(header)
        return result

    @staticmethod
    def _build_authorization_header(data):
        return 'MediaBrowser {}'.format(
            ', '.join(f'{key}="{value}"' for key, value in data.items()))
