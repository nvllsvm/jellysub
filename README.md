# jellysub
An HTTP service which allows Subsonic clients to use Jellyfin

## Installation
```
pip install jellysub
```

## Usage
```
usage: jellysub [-h] [--port PORT] --upstream UPSTREAM

If an arg is specified in more than one place, then commandline values
override environment variables which override defaults.

optional arguments:
  -h, --help           show this help message and exit
  --port PORT          [env var: JELLYSUB_HTTP_PORT]
  --upstream UPSTREAM  [env var: JELLYSUB_UPSTREAM_URL]
```

## Testing
**Requires Python 3.8**
```
python -m unittest
```
