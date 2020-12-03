FROM python:alpine
WORKDIR /app
COPY . .
RUN apk add --no-cache -t .build musl-dev gcc \
 && pip install --no-cache-dir -e . \
 && apk del .build
ENTRYPOINT ["/usr/local/bin/jellysub"]
