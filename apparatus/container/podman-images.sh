# Image evidence shared by step2 and the driver suites. hstep records the
# command, its output and its exit before a caller can use the selected image.
podman_host() {
    hstep version podman --version || return 1
    grep -q '^podman version 5\.' "$OUT/host/version.stdout" || return 1
    hstep podman-info podman info --format json || return 1
    jq -e '.host.security.rootless and .host.cgroupVersion == "v2"' "$OUT/host/podman-info.stdout" >/dev/null
}

image_index() {
    role=$1
    registry_ref=$2
    index_name=index-$role
    [ "$role" != python ] || index_name=python-inspect
    hstep "$index_name" skopeo inspect --raw "docker://$registry_ref" || return 1
    index_file=$OUT/host/$index_name.stdout
    printf '%s  %s\n' "${registry_ref##*@sha256:}" "$index_file" | sha256sum --check --status || return 1
    for arch in $PLATFORMS; do
        digest=$(jq -er --arg arch "$arch" '
            [.manifests[] | select(.platform.os == "linux" and .platform.architecture == $arch) | .digest]
            | select(length == 1) | .[0] | select(test("^sha256:[a-f0-9]{64}$"))
        ' "$index_file") || return 1
        image="${registry_ref%@*}@$digest"
        # Keep the public image root traversable by the UID used after setup.
        (umask 022; hstep "pull-$role-$arch" podman pull --platform "linux/$arch" "$image") || return 1
        hstep "$role-podman-$arch" podman image inspect "$image" || return 1
        jq -e --arg arch "$arch" --arg digest "$digest" '
            length == 1 and .[0].Architecture == $arch and .[0].Os == "linux" and .[0].Digest == $digest
        ' "$OUT/host/$role-podman-$arch.stdout" >/dev/null || return 1
        printf '%s\n' "$image" > "$OUT/host/$role-$arch.ref" || return 1
    done
}

toolchain_identity() {
    arch=$1
    hstep "toolchain-inspect-$arch" podman image inspect "$TAG-$arch" || return 1
    id=$(jq -er --arg arch "$arch" '
        select(length == 1) | .[0] | select(.Architecture == $arch and .Os == "linux")
        | .Id | sub("^sha256:"; "") | select(test("^[a-f0-9]{64}$"))
    ' "$OUT/host/toolchain-inspect-$arch.stdout") || return 1
    printf '%s\n' "$id" > "$OUT/host/toolchain-$arch.id"
}
