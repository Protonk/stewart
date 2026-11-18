# Local HTTP and CONNECT captures

On 2026-11-18 at 14:40:32 UTC, a local Ruby client recorded WEBrick 1.9.1
responses on Darwin 25.6.0 arm64 with Ruby 2.6.10p210. Each connection used a
fresh Unix socketpair. WEBrick's HTTPServer read the request and wrote the
response. The client retained the bytes it received through EOF, except that
successful CONNECT replies end at the blank line preceding the tunnel.

The [checksums](SHA256SUMS) cover the selected bytes and the
[acquisition record](observation.json), which identifies the library sources,
input digests, timestamps and upstream-open counts. The complete original
observations and WEBrick log are in `.tmp/readiness-wire-01/capture-01/`.
Its parent holds the acquisition script.
A checkout needs only the selected files to replay the comparisons.

## HTTP framing

WEBrick received the same [GET request](http-request.bin) with `Connection: close` in all four
exchanges. Its application supplied the bytes of the existing
[M3 ordinary-ending response body](../messages/m3-ordinary-ending.json).
The local observation covers the resulting HTTP wire framing. The body has
[separate provenance](../README.md#m3-ordinary-ending-and-citation-recovery).

| Capture | Observed wire bytes | Body framing |
| --- | ---: | --- |
| [Length](http-length.bin) | 1,732 | HTTP 200, content length 1,555 |
| [Chunked](http-chunked.bin) | 1,756 | HTTP 200, chunks of 53 and 1,502 bytes followed by the terminating zero chunk |
| [Close](http-close.bin) | 1,710 | HTTP 200, body through EOF with neither a length nor a transfer coding |
| [Unavailable](http-unavailable.bin) | 1,749 | HTTP 503, same length and body as the 200 length response |

The string-body handler allowed WEBrick to calculate the length. The streaming
handler wrote the same two slices with chunking enabled and disabled. The
application set status 503 for the differing case. The driver uses this 503
to check the retry decision. Its body is the
same successful Messages response supplied to the three 200s. It supplies no
observation of a live provider's 503 body.

## CONNECT and tunnel

The [CONNECT request](connect-accepted-request.bin) is the unedited request
captured in the Linux lookback run. Both architectures produced the same 63
bytes at
`.scratch/acceptance-lookback-03/driver-{arm64,amd64}/evidence/cases/c1.tls-proxy/test/provider-provider/proxy/0001-connect.bin`.
The local client replayed the arm64 original to WEBrick's HTTPProxyServer.
The capture script supplied a connected socketpair endpoint when the proxy
opened the exact authority `provider.test:443`. The proxy itself parsed,
authorized, selected the HTTP response, and relayed the tunnel. This observes
local stream behavior with a supplied upstream. DNS, TCP connect and TLS are
outside that observation.

| Input or policy | Reply | Independent observation |
| --- | --- | --- |
| Original request | [200 head](connect-accepted.bin), 142 bytes | One upstream open. Origin received the [25 upstream bytes](origin-accepted-received.bin) and client received the [26 downstream bytes](client-accepted-received.bin) before EOF. |
| Same request, WEBrick proxy Basic authentication required | [407 response](connect-refused.bin), 612 bytes | Client received the challenge and complete 348-byte HTML body through EOF. The upstream connector was never called. |
| Only the header's first letter changed to [uppercase](connect-header-case-request.bin) | Same 142 bytes | One upstream open. The same two binary markers crossed the tunnel in their respective directions. |

Each successful proxy head contains both `Content-Length: 0` and
`Connection: close`. The marker transfers demonstrate that the tunnel opened.
No credential was supplied to the proxy.

The [release driver](../../cases_wire.py) self-test compares all HTTP frame
types with the fake encoder and replays both CONNECT outcomes and the
header-case change through the fake proxy. It also removes one final byte
from separate copies of the length and chunked 200s as incomplete-frame controls.
The `c1.captured-wire` case uses the recorded proxy head with end-to-end TLS
and compares the exact response captures and attempt decisions across both
framing sequences. It separately replays the 407 and checks that all four
connection attempts failed before a provider request was written.
