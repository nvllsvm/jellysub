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

Command line arguments may be used instead of environment variables. For example,
the below will start the Jellysub server on port **8000** and
communicate with the Jellyfin server at **https://yourjellyfinserver.com**

```
jellysub --port 8000 --upstream https://yourjellyfinserver.com
```

See `jellysub --help` for more information.
