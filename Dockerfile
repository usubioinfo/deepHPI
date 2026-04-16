FROM node:20-bookworm-slim AS frontend-build

WORKDIR /app

ARG DEEPHPI_BASE_PATH=/
ENV DEEPHPI_BASE_PATH=${DEEPHPI_BASE_PATH}

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build


FROM mambaorg/micromamba:2.0.5 AS runtime

USER root

RUN apt-get update \
  && apt-get install -y --no-install-recommends msmtp-mta ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml
RUN micromamba install -y -n base -f /tmp/environment.yml \
  && micromamba clean --all --yes

COPY --chown=$MAMBA_USER:$MAMBA_USER docker /app/docker

COPY --from=frontend-build --chown=$MAMBA_USER:$MAMBA_USER /app/dist /app/dist
COPY --from=frontend-build --chown=$MAMBA_USER:$MAMBA_USER /app/public /app/public
COPY --from=frontend-build --chown=$MAMBA_USER:$MAMBA_USER /app/server /app/server
COPY --from=frontend-build --chown=$MAMBA_USER:$MAMBA_USER /app/runtime /app/runtime
COPY --from=frontend-build --chown=$MAMBA_USER:$MAMBA_USER /app/DiamondDB /app/DiamondDB
COPY --from=frontend-build --chown=$MAMBA_USER:$MAMBA_USER /app/annotations /app/annotations
COPY --from=frontend-build --chown=$MAMBA_USER:$MAMBA_USER /app/README.md /app/README.md

USER $MAMBA_USER

ENV DEEPHPI_HOST=0.0.0.0 \
    DEEPHPI_PORT=3010 \
    DEEPHPI_PORT_MAX=3010 \
    DEEPHPI_RUNTIME_ROOT=/app/runtime \
    DEEPHPI_DIAMOND_DB=/app/DiamondDB/swissprot_dec2019.dmnd \
    DEEPHPI_SWISSPROT_TAB=/app/annotations/swissprot.tab \
    DEEPHPI_MAIL_FROM=no-reply-deepHPI@bioinfo.usu.edu \
    DEEPHPI_SENDMAIL_BIN=/usr/sbin/sendmail \
    DEEPHPI_APP_URL=http://localhost:3010

EXPOSE 3010

ENTRYPOINT ["/bin/sh", "/app/docker/entrypoint.sh"]
CMD []
