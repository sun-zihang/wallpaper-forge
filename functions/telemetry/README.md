# telemetry HTTP function

Receives opt-in anonymous aggregate counters from Wallpaper Convert web
(default OFF; see `web/lib/telemetry.js`). Stores sanitized numeric counters
into the CloudBase collection `telemetry_events`.

## Deploy (CloudBase)

1. Prerequisites: a CloudBase env, `tcb login`, and a server API key
   (`manageAppAuth action="createApiKey"` or console equivalent).
2. Create the collection `telemetry_events` in the console first — the
   runtime does not auto-create collections.
3. Deploy as an **HTTP Function** named `telemetry`, runtime `Nodejs18.15`,
   from this directory (`functionRootPath` = `functions/`). Example CLI:
   `tcb fn deploy telemetry --env <envId>` (or console upload).
4. Function env vars (merge, never replace existing ones):
   - `TCB_ENV=<envId>`
   - `CLOUDBASE_APIKEY=<server api key>` (never commit or log it)
5. Public access: default security rules reject anonymous callers — allow
   all callers for this function, then verify `GET /health` twice.
6. Expose `POST /` on the HTTP gateway and note the final URL, e.g.
   `https://<envId>.service.tcloudbase.com/telemetry/`.

## Configure the web client

Set the endpoint in either place (localStorage wins over the built-in):

- `localStorage.wc.telemetryEndpoint = "<function url>"`, or
- `DEFAULT_ENDPOINT` in `web/lib/telemetry.js` (deploy-time edit).

The CSP in `web/index.html` already allows `*.service.tcloudbase.com` and
`*.app.tcloudbase.com`.
