FROM ubuntu:24.04
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 \
 && rm -rf /var/lib/apt/lists/*
COPY app.py /srv/app.py
EXPOSE 8080
CMD ["python3", "-u", "/srv/app.py"]
