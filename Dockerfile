FROM python:alpine
COPY . /src
RUN apk add --no-cache -t .build musl-dev gcc \
 && pip install --no-cache-dir /src \
 && apk del .build
ENTRYPOINT ["/usr/local/bin/jellysub"]
