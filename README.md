# DeepHPI

DeepHPI is a multi-page React and Tailwind v4 webserver frontend paired with a lightweight local
Python API. The predictor runtime now lives inside this project under `runtime/DeepSeqHPI`, so the
webserver, model checkpoints, and feature code stay together in one place.

## Run DeepHPI

Frontend:

```bash
cd /Users/naveen/Sites/deepH/deepHPI
npm run dev
```

API:

```bash
cd /Users/naveen/Sites/deepH/deepHPI
npm run server
```

Production build:

```bash
cd /Users/naveen/Sites/deepH/deepHPI
npm run build
python3 server/app.py
```

## Docker

Build the image:

```bash
docker build -t deephpi:latest .
```

Run the webserver on port `3010`:

```bash
docker run --rm -p 3010:3010 deephpi:latest
```

To serve DeepHPI from a subpath such as `/deepHPI/`, build and run with a matching base path:

```bash
docker build --build-arg DEEPHPI_BASE_PATH=/deepHPI/ -t deephpi:latest .
docker run -d --restart unless-stopped --name deephpi \
  -p 3010:3010 \
  -e DEEPHPI_BASE_PATH=/deepHPI \
  -e DEEPHPI_APP_URL=https://your-host.example/deepHPI \
  deephpi:latest
```

Example Apache proxy configuration:

```apache
ProxyPass /deepHPI/ http://10.1.1.31:3010/deepHPI/
ProxyPassReverse /deepHPI/ http://10.1.1.31:3010/deepHPI/
```

The container:

- builds the React frontend during image creation
- serves the built app from the Python backend on port `3010`
- installs the Conda runtime from `environment.yml`
- includes a local `sendmail`-compatible binary via `msmtp-mta`
- includes an internal startup script that prepares `sendmail` relay config when mail relay env vars are provided

DeepHPI uses the local `sendmail` path first and sends mail with:

- `From: no-reply-deepHPI@bioinfo.usu.edu`

To make outbound mail work from the container, configure the container or host mail system once so
that `/usr/sbin/sendmail` can relay mail for that sender.

If you prefer, DeepHPI can still fall back to direct SMTP when `sendmail` is not configured.

Example with a mounted `msmtp` config:

```bash
docker run --rm -p 3010:3010 \
  -e DEEPHPI_APP_URL=http://localhost:3010 \
  -e DEEPHPI_MAIL_FROM=no-reply-deepHPI@bioinfo.usu.edu \
  -v /full/path/msmtprc:/home/mambauser/.msmtprc:ro \
  deephpi:latest
```

Example using only `docker run` env vars:

```bash
docker run -d --restart unless-stopped --name deephpi -p 3010:3010 \
  -e DEEPHPI_APP_URL=http://localhost:3010 \
  -e DEEPHPI_MAIL_FROM=no-reply-deepHPI@bioinfo.usu.edu \
  -e DEEPHPI_MAIL_RELAY_HOST=smtp.your-relay.edu \
  -e DEEPHPI_MAIL_RELAY_PORT=587 \
  -e DEEPHPI_MAIL_RELAY_USER=your-relay-user \
  -e DEEPHPI_MAIL_RELAY_PASS=your-relay-password \
  deephpi:latest
```

If you run only:

```bash
docker run -d --restart unless-stopped --name deephpi -p 3010:3010 deephpi:latest
```

the container will start normally, but it will print a clear warning that email notifications are
disabled until a sendmail relay is configured.

## Email notifications

DeepHPI can send submission, completion, and failure notifications through the local `sendmail`
binary. Configure the host or container mail system once, then users only need to provide their
notification email in the web interface.

By default, notification mail is sent with:

- `From: no-reply-deepHPI@bioinfo.usu.edu`

You can override that sender if needed:

```bash
export DEEPHPI_MAIL_FROM="no-reply-deepHPI@bioinfo.usu.edu"
```

If you want to use direct SMTP instead, configure these environment variables before starting
`server/app.py`:

```bash
export DEEPHPI_APP_URL="http://127.0.0.1:5173"
export DEEPHPI_MAIL_FROM="no-reply-deepHPI@bioinfo.usu.edu"
export DEEPHPI_SMTP_HOST="smtp.yourserver.edu"
export DEEPHPI_SMTP_PORT="587"
export DEEPHPI_SMTP_USER="deephpi@yourserver.edu"
export DEEPHPI_SMTP_PASS="your-password-or-app-password"
export DEEPHPI_SMTP_TLS="true"
export DEEPHPI_SMTP_SSL="false"
```

Notes:

- `DEEPHPI_APP_URL` is used to build the result link included in emails.
- DeepHPI tries the local `sendmail` binary first, then falls back to SMTP if configured.
- You can override the local mailer path with:

```bash
export DEEPHPI_SENDMAIL_BIN="/usr/sbin/sendmail"
```

- Use `DEEPHPI_SMTP_TLS=true` for STARTTLS on port `587`.
- Use `DEEPHPI_SMTP_SSL=true` and `DEEPHPI_SMTP_TLS=false` for implicit SSL, typically on port `465`.
- If `bioinfo.usu.edu` does not authorize `no-reply-deepHPI@bioinfo.usu.edu`, messages may be
  rejected or routed to spam.
- For reliable delivery, the sending domain should be backed by valid SPF, DKIM, and DMARC records
  or by a trusted institutional relay that is allowed to send on behalf of `bioinfo.usu.edu`.
- If neither `sendmail` nor SMTP is configured, the notification email field is stored with the job
  but no mail is sent.

## Runtime layout

- `src/`: routed DeepHPI pages and UI components
- `server/app.py`: local DeepHPI API and static server
- `server/jobs/`: submitted job workspaces and generated report files
- `runtime/DeepSeqHPI/`: copied predictor runtime, active model weights, and `iFeature`
- `public/assets/`: DeepHPI branding and figure assets
- `public/covid/`: Human-COVID-PPI bundled data

## Repository size

This repository is intended to store the DeepHPI source code only.

The following large predictor assets are excluded from Git and should be restored separately:

- `DiamondDB/swissprot_dec2019.dmnd`
- `annotations/swissprot.tab`
- `runtime/DeepSeqHPI/*.pth`

To run the full predictor, place the required model files, Diamond database, and SwissProt annotation
table back into their expected locations before starting the server.

After cloning a source-code-only copy of the repository, create the runtime asset folders if they
are not already present:

```bash
mkdir -p DiamondDB annotations runtime/DeepSeqHPI
```

Then place these files back into the project:

- `DiamondDB/swissprot_dec2019.dmnd`
- `annotations/swissprot.tab`
- `runtime/DeepSeqHPI/*.pth`

Notes:

- `server/jobs/` is created automatically by the backend when jobs are submitted.
- `DiamondDB/`, `annotations/`, and the model checkpoint files are not recreated automatically and
  must be restored manually.
- If these runtime assets are missing, DeepHPI exits at startup with a clear message listing the
  missing files and their expected locations.
