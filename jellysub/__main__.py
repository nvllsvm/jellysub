import logging

import aiohttp.web
import configargparse
import yarl

from . import app


def main():
    parser = configargparse.ArgumentParser()
    parser.add_argument(
        '--port', type=int, default=4040,
        env_var='JELLYSUB_HTTP_PORT',
        help='port to serve on (default: %(default)s)')
    parser.add_argument(
        '--upstream', type=yarl.URL, metavar='URL',
        env_var='JELLYSUB_UPSTREAM_URL', required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    aiohttp.web.run_app(
        app.Application(args.upstream),
        port=args.port)


if __name__ == '__main__':
    main()
