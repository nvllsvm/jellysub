import asyncio
import collections
import json
import string
from xml.etree.ElementTree import Element, tostring

import aiohttp.web


from . import jellyfin


@aiohttp.web.middleware
async def request_data_middleware(request, handler):
    data = {}
    for key, value in request.url.query.items():
        data[key] = value
    post_body = await request.post()
    for key, value in post_body.items():
        data[key] = value
    request['data'] = data
    return await handler(request)


@aiohttp.web.middleware
async def auth_middleware(request, handler):
    try:
        username = request['data']['u']
        password = request['data']['p']
    except KeyError:
        return aiohttp.web.Response(status=400)

    if password.startswith('enc:'):
        password = bytearray.fromhex(password.split(':')[1]).decode()

    try:
        request.user = await request.app['jellyfin'].get_user(
            username, password)
    except KeyError:
        return aiohttp.web.Response(status=401)
    return await handler(request)


@aiohttp.web.middleware
async def content_format_middleware(request, handler):
    response_format = request['data'].get('f', 'xml')
    if response_format not in ('json', 'xml'):
        return aiohttp.web.Response(status=400)

    response = await handler(request)

    content = response.pop('content', None)
    if content is not None:
        content.setdefault('status', 'ok')
        content.setdefault('version', '1.9.0')
        content = {'subsonic-response': content}

        if response_format == 'xml':
            response.body = tostring(_to_xml(content))
            response.content_type = 'application/xml'
        elif response_format == 'json':
            response.body = json.dumps(content)
            response.content_type = 'application/json'
    return response


def _to_xml(data, key=None):
    if key is None:
        if not isinstance(data, dict) or len(data) != 1:
            raise ValueError
        key = list(data.keys())[0]
        data = data[key]

    root = Element(key)
    for key, value in data.items():
        if isinstance(value, dict):
            root.append(_to_xml(value, key))
        elif isinstance(value, str):
            root.set(key, value)
        elif isinstance(value, (float, int, bool)):
            root.set(key, str(value))
        elif isinstance(value, list):
            root.extend([_to_xml(v, key) for v in value])
        elif value is None:
            root.set(key, '')
        else:
            raise ValueError
    return root


async def ping(request):
    response = aiohttp.web.Response()
    response['content'] = {}
    return response


async def artists(request):
    data = await request.app['jellyfin'].get_album_artists(request.user)

    results = collections.defaultdict(list)
    for item in data['Items']:
        first = item['Name'].lower()
        group = first if first in string.ascii_lowercase else '#'

        results[group].append(item)

    indexes = []
    for prefix, artists in results.items():
        artists = [
            {
                'albumCount': 1,  # TODO: determine real album count
                'id': artist['Id'],
                'name': artist['Name'],
            }
            for artist in artists
        ]
        artists = sorted(
            artists, key=lambda s: (s['name'], s['id']))

        indexes.append({
            'name': prefix,
            'artist': artists
        })
    indexes = sorted(indexes, key=lambda s: s['name'])

    response = aiohttp.web.Response()
    response['content'] = {
        'artists': {
            'ignoredArticles': '',
            'index': indexes
        },
    }
    return response


async def genres(request):
    data = await request.app['jellyfin'].get_genres(request.user)

    genres = [
        {
            'value': item['Name'],

            # TODO: look these up
            'albumCount': 1,
            'songCount': 1,
        }
        for item in data['Items']
    ]

    genres = sorted(genres, key=lambda s: s['value'])

    response = aiohttp.web.Response()
    response['content'] = {
        'genres': {
            'genre': genres
        }
    }
    return response


async def artist(request):
    artist_id = request['data']['id']
    artist_data, album_data = await asyncio.gather(
        request.app['jellyfin'].get_artist(request.user, artist_id),
        request.app['jellyfin'].get_albums(request.user, artist_id)
    )

    # TODO can AlbumArtist and Name be null?
    albums = [
        {
            'artist': item['AlbumArtist'],
            'artistId': artist_id,
            'coverArt': item['Id'],
            'id': item['Id'],
            'name': item['Name'],
            'duration': 0,
            'songCount': 0,
            'year': item.get('ProductionYear'),
        }
        for item in album_data['Items']
    ]
    albums = sorted(albums, key=lambda s: (s['year'] or 0, s['name'], s['id']))

    response = aiohttp.web.Response()
    response['content'] = {
        'artist': {
            'album': albums,
            'albumCount': len(albums),
            'id': artist_id,
            'name': artist_data['Name'],
        },
    }
    return response


async def artist_info2(request):
    artist_id = request['data']['id']
    data = await request.app['jellyfin'].get_artist(request.user, artist_id)

    response = aiohttp.web.Response()
    response['content'] = {
        'artistInfo2': {
            'biography': data.get('Overview', ''),
        },
    }
    return response


async def album(request):
    album_id = request['data']['id']
    data = await request.app['jellyfin'].get_album(request.user, album_id)

    songs = []
    for item in data['Items']:
        path = item['MediaSources'][0]['Path']
        suffix = path.split('.')[-1] if '.' in path else ''
        song = {
            'id': item['Id'],
            'artist': ' & '.join(item['Artists']),
            'album': item['Album'],
            'title': item['Name'],
            'coverArt': item['AlbumId'],
            'duration': int(item['RunTimeTicks'] / 10000000),
            'track': item['IndexNumber'],
            'path': path,
            'suffix': suffix,
        }
        songs.append(song)
    songs = sorted(songs, key=lambda s: (s['track'], s['title'], s['id']))

    response = aiohttp.web.Response()
    response['content'] = {
        'album': {
            'song': songs,
            'songCount': len(songs),
            'id': album_id
        },
    }
    return response


async def albumList(request):
    offset = int(request['data'].get('offset', 0))
    size = int(request['data'].get('size', 10))

    data = await request.app['jellyfin'].get_albums(request.user)

    albums = []
    for (i, item) in enumerate(data['Items']):
        if i < offset:
            continue
        if (i - offset) == size:
            break

        album_data = await request.app['jellyfin'].get_album(request.user, item['Id'])

        albums.append({
            'id': item['Id'],
            'parent': 1,
            'title': item['Name'],
            'artist': item['AlbumArtists'][0]['Name'],
            'isDir': True,
            'coverArt': item['Id'],
        })

    response = aiohttp.web.Response()
    response['content'] = {
        'albumList': {
            'album': albums
        },
    }
    return response

async def albumList2(request):
    offset = int(request['data'].get('offset', 0))
    size = int(request['data'].get('size', 10))

    data = await request.app['jellyfin'].get_albums(request.user)

    albums = []
    for (i, item) in enumerate(data['Items']):
        if i < offset:
            continue
        if (i - offset) == size:
            break

        album_data = await request.app['jellyfin'].get_album(request.user, item['Id'])

        albums.append({
            'id': item['Id'],
            'name': item['Name'],
            'coverArt': item['Id'],
            'songCount': len(album_data['Items']),
            'artist': item['AlbumArtists'][0]['Name'],
            'artistId': item['AlbumArtists'][0]['Id'],
            'duration': int(item['RunTimeTicks'] / 10000000)
        })

    response = aiohttp.web.Response()
    response['content'] = {
        'albumList2': {
            'album': albums
        },
    }
    return response


async def cover_art(request):
    album_id = request['data']['id']
    data = await request.app['jellyfin'].get_album_cover(album_id)

    return aiohttp.web.Response(body=data)


async def stream(request):
    song_id = request['data']['id']
    data = await request.app['jellyfin'].download_song(request.user, song_id)

    return aiohttp.web.Response(body=data)


class Application(aiohttp.web.Application):

    def __init__(self, upstream):
        super().__init__(
            middlewares=[
                request_data_middleware,
                content_format_middleware,
                auth_middleware
            ])

        self['jellyfin'] = jellyfin.JellyfinClient(upstream)

        self.add_routes([
            aiohttp.web.route('*', '/rest/ping.view', ping),
            aiohttp.web.route('*', '/rest/getArtists.view', artists),
            aiohttp.web.route('*', '/rest/getArtist.view', artist),
            aiohttp.web.route('*', '/rest/getAlbum.view', album),
            aiohttp.web.route('*', '/rest/getAlbumList.view', albumList),
            aiohttp.web.route('*', '/rest/getAlbumList2.view', albumList2),
            aiohttp.web.route('*', '/rest/stream.view', stream),
            aiohttp.web.route('*', '/rest/getCoverArt.view', cover_art),
            aiohttp.web.route('*', '/rest/getArtistInfo2.view', artist_info2),
            aiohttp.web.route('*', '/rest/getGenres.view', genres),
        ])
        self.on_startup.append(self.on_start)

    async def on_start(self, *_):
        await self['jellyfin'].open()

    async def cleanup(self):
        await super().cleanup()
        await self['jellyfin'].close()
