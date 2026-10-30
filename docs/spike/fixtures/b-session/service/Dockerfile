FROM ubuntu:24.04
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 \
 && rm -rf /var/lib/apt/lists/*
COPY server.py /srv/server.py
EXPOSE 9101
CMD ["python3", "-u", "/srv/server.py"]
