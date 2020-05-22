import collections
import logging
import re
import uuid
import string
from xml.etree.ElementTree import Element, SubElement, tostring

import aiohttp.web
import configargparse
import yarl


class View(aiohttp.web.View):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.jellyfin = self.request.app['jellyfin']


class PingView(View):

    async def get(self):
        data = {
            'status': 'ok',
            'version': '1.9.0',
            'type': 'jellysub',
        }

        top = Element('subsonic-response')
        for key, value in data.items():
            top.set(key, value)

        return aiohttp.web.Response(
            body=tostring(top),
            headers={'Content-Type': 'application/xml'},
            status=200)


class ArtistsView(View):

    async def get(self):
        query = self.request.url.query
        username = query['u']
        password = query['p']

        user = await self.jellyfin.get_user(username, password)
        data = await self.jellyfin.get_album_artists(user)

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


class ArtistView(View):

    async def get(self):
        query = self.request.url.query
        username = query['u']
        password = query['p']
        artist_id = query['id']

        user = await self.jellyfin.get_user(username, password)
        data = await self.jellyfin.get_albums(user, artist_id)

        top = Element('subsonic-response')
        artist = SubElement(top, 'artist')
        album_count = 0
        for item in data['Items']:
            album = Element('album')
            album.set('id', item['Id'])
            album.set('coverArt', item['ImageTags']['Primary'])
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


class AlbumView(View):
    async def get(self):
        query = self.request.url.query
        username = query['u']
        password = query['p']
        album_id = query['id']

        user = await self.jellyfin.get_user(username, password)
        data = await self.jellyfin.get_album(user, album_id)

        top = Element('subsonic-response')
        album = SubElement(top, 'album')
        song_count = 0
        for item in data['Items']:
            song = Element('song')
            song.set('id', item['Id'])
            song.set('artist', ' & '.join(item['Artists']))
            song.set('album', item['Album'])
            song.set('name', item['Name'])

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


class StreamView(View):
    async def get(self):
        query = self.request.url.query

        username = query['u']
        password = query['p']
        song_id = query['id']

        user = await self.jellyfin.get_user(username, password)
        data = await self.jellyfin.download_song(user, song_id)

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
        if username not in self._users:
            self._users[username] = await self._authenticate(
                username, password)
        return self._users[username]

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

#    StartIndex=0&Limit=10000&ParentId=7e64e319657a9516ec78490da03edccb&userId=f698fa3272bd4c0d93111207f45a9cb1
    async def _authenticate(self, username, password):
        kwargs = {
            'allow_redirects': False,
            'headers': {
                'X-Emby-Authorization': self._build_authorization_header(self._auth_header),
            },
            'json': {
                'Username': username,
                'Pw': password,
            },
        }
        url = self._url / 'Users/authenticatebyname'
        async with self._client.post(url, **kwargs) as resp:
            content = await resp.json()
            return content

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

        if not all([v for k, v in result.items() if k not in ('Client', 'Token')]):
            raise ValueError(header)
        return result

    @staticmethod
    def _build_authorization_header(data):
        return 'MediaBrowser {}'.format(', '.join(f'{key}="{value}"' for key, value in data.items()))


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

    app = aiohttp.web.Application()
    app['jellyfin'] = JellyfinClient(upstream)
    app.on_cleanup.append(close_session)

    app.add_routes([
        aiohttp.web.route('*', '/rest/ping.view', PingView),
        aiohttp.web.route('*', '/rest/getArtists.view', ArtistsView),
        aiohttp.web.route('*', '/rest/getArtist.view', ArtistView),
        aiohttp.web.route('*', '/rest/getAlbum.view', AlbumView),
        aiohttp.web.route('*', '/rest/stream.view', StreamView),
    ])
    return app


if __name__ == '__main__':
    main()
