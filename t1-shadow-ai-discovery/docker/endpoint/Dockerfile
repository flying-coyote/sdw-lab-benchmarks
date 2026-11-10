# Simulated developer endpoint for T1-shadow-ai-discovery (lab fixture).
FROM python:3.12-slim
ARG OSQUERY_DEB=osquery_5.24.0-1.linux_amd64.deb
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates procps \
    && rm -rf /var/lib/apt/lists/*
COPY ${OSQUERY_DEB} /tmp/osquery.deb
RUN dpkg -i /tmp/osquery.deb && rm /tmp/osquery.deb && osqueryi --version
# uid 1000 matches the host user that owns the bind-mounted home, so files created inside stay readable on the host
RUN useradd -m -u 1000 -s /bin/bash dev
ENV HOME=/home/dev
WORKDIR /home/dev
CMD ["sleep", "infinity"]
