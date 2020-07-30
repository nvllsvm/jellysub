# jellysub
An HTTP service which allows Subsonic clients to use Jellyfin

Known compatible clients:
- [Audinaut](https://github.com/nvllsvm/audinaut) (except playlist support)


## Installation
Available in the following distribution channels:
- [Docker](https://hub.docker.com/r/nvllsvm/jellysub)
- [PyPi (Python)](https://pypi.org/project/jellysub/)

## Example usage

The below will start the Jellysub server on port **8000** and
communicate with the Jellyfin server at **https://yourjellyfinserver.com**

```
jellysub --port 8000 --upstream https://yourjellyfinserver.com
```
