# jellysub
A shim to use Subsonic clients with Jellyfin

Jellysub is an HTTP service which sits between Subsonic-compatible clients and a
Jellyfin server.

## Compatibility
Clients tested with Jellysub:

| Client                                          | Notes                                |
|-------------------------------------------------|--------------------------------------|
| [Audinaut](https://github.com/nvllsvm/audinaut) | fully functional excluding playlists |


## Installation
Available in the following distribution channels:
- [Docker](https://hub.docker.com/r/nvllsvm/jellysub)
- [PyPi (Python)](https://pypi.org/project/jellysub/)

## Running
The following environment variables may be used to configure Jellysub.

| Name                    | Description                                           |
|-------------------------|-------------------------------------------------------|
| `JELLYSUB_HTTP_PORT`    | Port to listen for HTTP requests on. (Default `4040`) |
| `JELLYSUB_UPSTREAM_URL` | URL of the Jellyfin server. Required.                 |

Command line arguments may also be used. See `jellysub --help` for more information.

### Examples
Both examples below start a Jellysub server on port **4040** and communicating
with the Jellyfin server at **https://yourjellyfinserver.com**.

#### Docker
```
docker run \
    -e JELLYSUB_UPSTREAM_URL=https://yourjellyfinserver.com \
    -p 4040:4040 \
    nvllsvm/jellysub
```

#### Command Line
```
jellysub --upstream https://yourjellyfinserver.com
```
