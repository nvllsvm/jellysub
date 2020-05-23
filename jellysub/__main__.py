import collections
import json
import logging
import re
import uuid
import string
from xml.etree.ElementTree import Element, SubElement, tostring

import aiohttp.web
import configargparse
import yarl


@aiohttp.web.middleware
async def auth_middleware(request, handler):
    query = request.url.query
    try:
        username = query['u']
        password = query['p']
    except KeyError:
        return aiohttp.web.Response(status=400)

    try:
        request.user = await request.app['jellyfin'].get_user(
            username, password)
    except KeyError:
        return aiohttp.web.Response(status=401)
    return await handler(request)


async def ping(request):
    data = {
        'subsonic-response': {
            'status': 'ok',
            'version': '1.9.0',
            'type': 'jellysub',
        }
    }

    if request.query.get('f') == 'json':
        content_type = 'application/json'
        body = json.dumps(data)
    else:
        content_type = 'application/xml'

        key = 'subsonic-response'
        top = Element(key)
        for key, value in data[key].items():
            top.set(key, value)

        body = tostring(top)

    return aiohttp.web.Response(
        body=body,
        headers={'Content-Type': content_type},
        status=200)


async def artists(request):
    data = await request.app['jellyfin'].get_album_artists(request.user)

    results = collections.defaultdict(list)
    for item in data['Items']:
        first = item['Name'].lower()
        group = first if first in string.ascii_lowercase else '#'

        results[group].append(item)

    top = Element('subsonic-response')
    artists = SubElement(top, 'artists')
    artists.set('ignoredArticles', '')

    for prefix, values in results.items():
        index = SubElement(artists, 'index')
        index.set('name', prefix)

        for artist in values:
            ele = Element('artist')
            ele.set('id', artist['Id'])
            ele.set('name', artist['Name'])
            ele.set('albumCount', str(1))
            index.append(ele)

    return aiohttp.web.Response(
        body=tostring(top),
        headers={'Content-Type': 'application/xml'},
        status=200)


async def artist(request):
    artist_id = request.url.query['id']
    data = await request.app['jellyfin'].get_albums(request.user, artist_id)

    top = Element('subsonic-response')
    artist = SubElement(top, 'artist')
    album_count = 0
    for item in data['Items']:
        album = Element('album')
        album.set('id', item['Id'])
        album.set('coverArt', item['Id'])
        album.set('artistId', artist_id)
        album.set('artist', ' & '.join(item['Artists'])),
        album.set('name', item['Name'])
        album.set('year', str(item['ProductionYear']))
        artist.append(album)
        album_count += 1

    artist.set('albumCount', str(album_count))

    return aiohttp.web.Response(
        body=tostring(top),
        headers={'Content-Type': 'application/xml'},
        status=200)


async def album(request):
    album_id = request.url.query['id']
    data = await request.app['jellyfin'].get_album(request.user, album_id)

    top = Element('subsonic-response')
    album = SubElement(top, 'album')
    song_count = 0
    for item in data['Items']:
        song = Element('song')
        song.set('id', item['Id'])
        song.set('artist', ' & '.join(item['Artists']))
        song.set('album', item['Album'])
        song.set('name', item['Name'])
        song.set('coverArt', item['Album'])

        song.set('duration', str(int(item['RunTimeTicks'] / 10000000)))
        song.set('track', str(item['IndexNumber']))

        # TODO: determine actual suffix
        # this is necessary for songs to be detected in Audinaut's
        # broken-ass offline mode
        song.set('suffix', 'mp3')

        album.append(song)
        song_count += 1

    album.set('songCount', str(song_count))

    return aiohttp.web.Response(
        body=tostring(top),
        headers={'Content-Type': 'application/xml'},
        status=200)


async def cover_art(request):
    album_id = request.url.query['id']
    data = await request.app['jellyfin'].get_album_cover(album_id)

    return aiohttp.web.Response(
        body=data,
        status=200)


async def stream(request):
    song_id = request.url.query['id']
    data = await request.app['jellyfin'].download_song(request.user, song_id)

    return aiohttp.web.Response(
        body=data,
        status=200)


class JellyfinClient:
    _CLIENT = 'jellysub'
    _DEVICE = 'jellysub'
    _DEVICE_ID = uuid.uuid4().hex
    _VERSION = '0.0.0'

    def __init__(self, url):
        self._client = aiohttp.ClientSession()
        self._url = yarl.URL(url)
        self._users = {}
        self._auth_header = {
            'Client': self._CLIENT,
            'Device': self._DEVICE,
            'DeviceId': self._DEVICE_ID,
            'Version': self._VERSION,
        }

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
        auth = dict(self._auth_header, token=user['AccessToken'])
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

    async def get_albums(self, user, artist_id):
        url = self._url / 'Users' / user['User']['Id'] / 'Items'
        auth = dict(self._auth_header, token=user['AccessToken'])
        kwargs = {
            'headers': {
                'X-Emby-Authorization': self._build_authorization_header(auth),
            },
            'params': {
                'AlbumArtistIds': artist_id,
                'IncludeItemTypes': 'MusicAlbum',
                'Limit': '1000',
                'Recursive': 'true',
                'StartIndex': '0',
            }
        }
        async with self._client.get(url, **kwargs) as resp:
            return await resp.json()

    async def get_album(self, user, album_id):
        url = self._url / 'Users' / user['User']['Id'] / 'Items'

        auth = dict(self._auth_header, token=user['AccessToken'])
        kwargs = {
            'headers': {
                'X-Emby-Authorization': self._build_authorization_header(auth),
            },
            'params': {
                'ParentId': album_id,
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


def main():
    parser = configargparse.ArgumentParser()
    parser.add_argument(
        '--port', type=int, default=4040,
        env_var='JELLYSUB_HTTP_PORT')
    parser.add_argument(
        '--upstream', type=yarl.URL,
        env_var='JELLYSUB_UPSTREAM_URL', required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    aiohttp.web.run_app(
        get_app(args.upstream),
        port=args.port)


async def get_app(upstream):
    async def close_session(app):
        await app['jellyfin'].close()

    app = aiohttp.web.Application(
        middlewares=[auth_middleware])
    app['jellyfin'] = JellyfinClient(upstream)
    app.on_cleanup.append(close_session)

    app.add_routes([
        aiohttp.web.route('*', '/rest/ping.view', ping),
        aiohttp.web.route('*', '/rest/getArtists.view', artists),
        aiohttp.web.route('*', '/rest/getArtist.view', artist),
        aiohttp.web.route('*', '/rest/getAlbum.view', album),
        aiohttp.web.route('*', '/rest/stream.view', stream),
        aiohttp.web.route('*', '/rest/getCoverArt.view', cover_art),
    ])
    return app


if __name__ == '__main__':
    main()
