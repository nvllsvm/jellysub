FROM python
WORKDIR /app
COPY . .
RUN pip install -e .
CMD jellysub
