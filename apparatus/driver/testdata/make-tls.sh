#!/bin/sh
# Regenerates the TEST-ONLY TLS fixtures for the driver's fake provider
# (see README.md beside this script). The private keys are published on purpose:
# nothing outside the acceptance driver may ever trust these certificates.
#
#   sh apparatus/driver/testdata/make-tls.sh     # needs OpenSSL 3.4 or later
#
# It replaces the files in tls/; commit the result. Fixed validity dates keep the
# certificates usable whatever the container clock says (2025 to 2125); the
# expired leaf is valid only during 2001.
set -eu
D=$(cd "$(dirname "$0")" && pwd)/tls
mkdir -p "$D"
cd "$D"
NB=20250101000000Z
NA=21250101000000Z

key() { openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$1"; }

ca() { # ca NAME SUBJECT
    key "testonly-$1.key"
    openssl req -new -x509 -sha256 -key "testonly-$1.key" -subj "$2" \
        -not_before "$NB" -not_after "$NA" \
        -addext "basicConstraints=critical,CA:TRUE" \
        -addext "keyUsage=critical,keyCertSign,cRLSign" \
        -addext "subjectKeyIdentifier=hash" \
        -out "testonly-$1.pem"
}

leaf() { # leaf NAME ISSUER SUBJECT SAN NOT_BEFORE NOT_AFTER
    key "testonly-$1.key"
    openssl req -new -sha256 -key "testonly-$1.key" -subj "$3" -out "$1.csr"
    printf '%s\n' \
        "basicConstraints=critical,CA:FALSE" \
        "keyUsage=critical,digitalSignature" \
        "extendedKeyUsage=serverAuth" \
        "subjectAltName=$4" \
        "subjectKeyIdentifier=hash" \
        "authorityKeyIdentifier=keyid" >"$1.ext"
    openssl x509 -req -sha256 -in "$1.csr" -CA "testonly-$2.pem" -CAkey "testonly-$2.key" \
        -set_serial "0x$(openssl rand -hex 16)" -not_before "$5" -not_after "$6" \
        -extfile "$1.ext" -out "testonly-$1.pem"
    rm -f "$1.csr" "$1.ext"
}

ca ca "/CN=Stewart acceptance driver TEST-ONLY CA"
ca other-ca "/CN=Stewart acceptance driver TEST-ONLY untrusted CA"
leaf provider ca "/CN=provider.test" "DNS:provider.test,DNS:localhost,IP:127.0.0.1" "$NB" "$NA"
leaf wrongname ca "/CN=other.test" "DNS:other.test" "$NB" "$NA"
leaf expired ca "/CN=provider.test" "DNS:provider.test,DNS:localhost,IP:127.0.0.1" 20010101000000Z 20011231000000Z
leaf untrusted other-ca "/CN=provider.test" "DNS:provider.test,DNS:localhost,IP:127.0.0.1" "$NB" "$NA"
rm -f testonly-ca.srl testonly-other-ca.srl

openssl verify -CAfile testonly-ca.pem testonly-provider.pem testonly-wrongname.pem
if openssl verify -CAfile testonly-ca.pem testonly-untrusted.pem >/dev/null 2>&1; then
    echo "control failed: the untrusted leaf verifies against the test CA" >&2
    exit 1
fi
openssl version >VERSION
sha256sum testonly-*.pem testonly-*.key 2>/dev/null >SHA256SUMS || shasum -a 256 testonly-*.pem testonly-*.key >SHA256SUMS
