#!/bin/sh
set -eu

MAIL_FROM="${DEEPHPI_MAIL_FROM:-no-reply-deepHPI@bioinfo.usu.edu}"
MSMTPRC_PATH="${DEEPHPI_MSMTPRC_PATH:-/home/mambauser/.msmtprc}"
RELAY_HOST="${DEEPHPI_MAIL_RELAY_HOST:-}"
RELAY_PORT="${DEEPHPI_MAIL_RELAY_PORT:-587}"
RELAY_USER="${DEEPHPI_MAIL_RELAY_USER:-}"
RELAY_PASS="${DEEPHPI_MAIL_RELAY_PASS:-}"
RELAY_TLS="${DEEPHPI_MAIL_RELAY_TLS:-true}"

mkdir -p "$(dirname "$MSMTPRC_PATH")"

if [ -s "$MSMTPRC_PATH" ]; then
  echo "DeepHPI: using existing sendmail relay config at $MSMTPRC_PATH"
elif [ -n "$RELAY_HOST" ]; then
  {
    echo "defaults"
    if [ -n "$RELAY_USER" ]; then
      echo "auth on"
      echo "user $RELAY_USER"
      echo "password $RELAY_PASS"
    else
      echo "auth off"
    fi
    if [ "$RELAY_TLS" = "false" ] || [ "$RELAY_TLS" = "0" ] || [ "$RELAY_TLS" = "no" ]; then
      echo "tls off"
    else
      echo "tls on"
      echo "tls_trust_file /etc/ssl/certs/ca-certificates.crt"
    fi
    echo "logfile /tmp/msmtp.log"
    echo
    echo "account default"
    echo "host $RELAY_HOST"
    echo "port $RELAY_PORT"
    echo "from $MAIL_FROM"
  } > "$MSMTPRC_PATH"
  chmod 600 "$MSMTPRC_PATH"
  echo "DeepHPI: generated sendmail relay config at $MSMTPRC_PATH"
else
  echo "DeepHPI: no sendmail relay config found."
  echo "DeepHPI: email notifications are disabled until one of these is provided:"
  echo "  1. Mount an msmtp config at $MSMTPRC_PATH"
  echo "  2. Set DEEPHPI_MAIL_RELAY_HOST and related relay env vars"
  echo "DeepHPI: current sender is $MAIL_FROM"
fi

if [ "$#" -eq 0 ]; then
  exec micromamba run -n base python server/app.py
fi

exec "$@"
