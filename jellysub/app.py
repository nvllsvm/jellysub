import collections
import json
import string
from xml.etree.ElementTree import Element, SubElement, tostring

import aiohttp.web

from . import jellyfin


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


class Application(aiohttp.web.Application):

    def __init__(self, upstream):
        super().__init__(middlewares=[auth_middleware])

        self['jellyfin'] = jellyfin.JellyfinClient(upstream)

        self.add_routes([
            aiohttp.web.route('*', '/rest/ping.view', ping),
            aiohttp.web.route('*', '/rest/getArtists.view', artists),
            aiohttp.web.route('*', '/rest/getArtist.view', artist),
            aiohttp.web.route('*', '/rest/getAlbum.view', album),
            aiohttp.web.route('*', '/rest/stream.view', stream),
            aiohttp.web.route('*', '/rest/getCoverArt.view', cover_art),
        ])

    async def cleanup(self):
        await super().cleanup()
        await self['jellyfin'].close()
