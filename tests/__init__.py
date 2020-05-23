#!/usr/bin/env python3
import functools
import os
import pathlib
import subprocess

import aiohttp
import yarl

_TEST_DIR = pathlib.Path(__file__).parent


os.environ['COMPOSE_FILE'] = str(_TEST_DIR.joinpath('docker-compose.yml'))


@functools.lru_cache()
def bootstrap():
    subprocess.run(
        ['docker-compose', 'pull'],
        check=True)

    subprocess.run(
        ['docker-compose', 'down', '--timeout=0',
         '--volumes', '--remove-orphans'],
        check=True)

    subprocess.run(
        ['docker-compose', 'up', '-d'],
        check=True)

    return {
        'mockserver_url': yarl.URL(_docker_compose_port('mockserver', 1080))
    }


def _docker_compose_port(service, port):
    proc = subprocess.run(
        ['docker-compose', 'port', service, str(port)],
        stdout=subprocess.PIPE,
        check=True)
    return proc.stdout.decode()


async def mockserver_expectation(**kwargs):
    response = await aiohttp.put(
        bootstrap()['mockserver_url'] / 'mockserver/expectation',
        json=kwargs)


async def mockserver_reset():
    response = await aiohttp.put(
        bootstrap()['mockserver_url'] / 'mockserver/reset')
