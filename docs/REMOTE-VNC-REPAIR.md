# Remote framebuffer repair (2026-10-19)

Baseline: `develop/1.0.0`, commit `ebf28fac3b8ef82fa61f233028875053ec0b5331`
(`v1.0.0-beta.6`). The N1800 installation has no `.git` directory; its beta
markers and the SHA-256 hashes of the web/bridge files matched this baseline.

## Confirmed cause

The X11 framebuffer contains real image content at 1024 x 768. An isolated,
password-authenticated, loopback-only x11vnc connection returned a complete
3,145,728-byte RAW framebuffer, and Tight encoding returned valid JPEG tiles
among its palette/fill tiles. Both were inspected without exporting screen
contents or credentials.

Debian's noVNC 1.3.0 `Display.imageRect()` loads JPEG rectangles with an Image
whose source is a `data:` URL. The previous `img-src 'self'` CSP blocked those
images. noVNC's ordered render queue then waited for image decoding and stopped
displaying subsequent framebuffer updates, despite a successful RFB handshake.

The browser fixture `tests/browser_vnc_fixture.py` reproduced this with synthetic
pixels and the installed noVNC modules under the real response policy:

- Baseline: `FAIL: image decoder blocked; framebuffer queue stalled`.
- Correction: `PASS: JPEG and following framebuffer update rendered`.

## Changes

- Allow `data:` image decoding only in successful, authenticated `/remote` HTML
  responses (including query strings). Other responses retain the previous image
  policy. Script policy, HTTPS, exact WSS origin, authentication, CSRF, exclusive
  leases and loopback-only password-protected VNC remain enforced.
- Replace the previous `-once` backend on authorized reconnect, and terminate
  it immediately on explicit stop rather than waiting for the lease watcher.
- Preserve partial WebSocket headers, masks and payloads across socket timeouts
  while the owner remains authorized. The previous outer retry discarded bytes
  already consumed. Reject reserved bits and malformed control frames; accept
  valid pong frames.

The existing hidden-screen flow and 4:3 layout were retained: the browser
regression reproduced the failure without a hidden element, proving that image
decoding was independently sufficient to cause it.

The 400 response from `/remote/live/ping` is separately reproducible after lease
expiry. The current browser intentionally stops renewing while hidden; after
25 seconds the lease expires. Reconnect obtains a fresh lease and backend.

## Verification and acceptance

Regression tests cover full 1024 x 768 RAW and subsequent update bytes across
proxy chunk boundaries, pointer/key messages, slow partial frames, lease expiry,
resource release, authenticated image policy and reconnect/stop ordering.
Development CI now also runs the remote lease/recovery and frontend suites.

The synthetic browser check uses Chromium via the in-app browser. Microsoft
Edge and the actual scanner's visible updates, mouse, touch and keyboard remain
part of user acceptance. This document does not claim those tests have passed.
No beta release is authorized until the required hardware acceptance succeeds.

## First-start HTTPS error

The user confirmed a visible live image after reloading, but Edge initially
showed `ERR_TOO_MANY_RETRIES` at `/remote/live/start`. The web service had not
restarted or crashed. A second, independently reproduced server defect was
found: the listening SSLSocket performed TLS handshakes synchronously inside
`accept()`. One speculative TCP connection that had not sent ClientHello blocked
every following HTTPS connection. Closing that idle socket immediately restored
HTTP 200 responses. The new regression failed with a TLS handshake timeout on
the previous implementation and passed after the correction.

TLS handshakes are now deferred to the individual request threads, and accepted
connections have a ten-second I/O timeout to bound abandoned preconnections.
Certificate validation, TLS minimum version, origin and authentication checks
are unchanged. Edge first-start acceptance, continued picture updates and input
acceptance are still pending; no beta has been released.
