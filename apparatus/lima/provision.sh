#!/bin/sh
# Run as root during guest provisioning, including subsequent boots.
set -eu
export DEBIAN_FRONTEND=noninteractive
set -- \
    podman catatonit uidmap passt slirp4netns dbus-user-session \
    git openssh-client python3 keyutils gnupg gpgv curl ca-certificates \
    build-essential rustup dosfstools e2fsprogs locales procps skopeo jq ripgrep gh gnome-keyring libsecret-tools
for package do
    if [ "$(dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null || true)" != installed ]; then
        apt-get update
        apt-get install -y --no-install-recommends "$@"
        break
    fi
done


for account in stewart-dev stewart-launch; do
    if ! id "$account" >/dev/null 2>&1; then
        useradd --create-home --user-group --shell /bin/bash "$account"
    fi
    for ranges in /etc/subuid /etc/subgid; do
        awk -F: -v user="$account" '$1 == user && $3 >= 65536 { found = 1 } END { exit !found }' "$ranges"
    done
done
getent group stewart-queue >/dev/null || groupadd --system stewart-queue
usermod -a -G stewart-queue stewart-dev
usermod -a -G stewart-queue stewart-launch
install -d -m 0755 /var/lib/stewart
install -d -m 2750 -o stewart-launch -g stewart-queue /var/lib/stewart/queue
for directory in requests packets; do
    runuser -u stewart-launch -- install -d -m 3770 -g stewart-queue "/var/lib/stewart/queue/$directory"
done
runuser -u stewart-launch -- install -d -m 2750 -g stewart-queue /var/lib/stewart/queue/results
for directory in claims sessions submissions; do
    runuser -u stewart-launch -- install -d -m 0700 "/var/lib/stewart/queue/$directory"
done
install -d -m 0755 /etc/systemd/system/user@.service.d
cat > /etc/systemd/system/user@.service.d/stewart-delegate.conf <<'UNIT'
[Service]
Delegate=cpu cpuset io memory pids
UNIT
systemctl daemon-reload
for account in stewart-dev stewart-launch; do
    loginctl enable-linger "$account"
done
printf '%s\n' 'kernel.keys.persistent_keyring_expiry = 2592000' > /etc/sysctl.d/60-stewart-keyring.conf
sysctl -p /etc/sysctl.d/60-stewart-keyring.conf

# The public login key is provisioned in an administrator-owned directory.
admin_home=$(getent passwd stewart-admin | cut -d: -f6)
install -d -m 0755 /etc/ssh/stewart
install -m 0644 "$admin_home/.ssh/authorized_keys" /etc/ssh/stewart/development.pub
cat > /etc/ssh/sshd_config.d/60-stewart-development.conf <<'SSH'
Match User stewart-dev
    AuthorizedKeysFile /etc/ssh/stewart/development.pub
Match all
SSH
sshd -t
systemctl reload ssh
install -d -m 0700 -o stewart-dev -g stewart-dev /var/lib/stewart/dev-tmp

# The fixture can represent both boundary filenames. Its parent restricts
# access, while the mount admits both the developer and remapped driver UID.
install -d -m 0710 -o root -g stewart-dev /var/lib/stewart/fixtures
fixture=/var/lib/stewart/fixtures
if [ ! -e "$fixture/names.img" ]; then
    truncate -s 64M "$fixture/names.img.new"
    mkfs.vfat "$fixture/names.img.new"
    mv "$fixture/names.img.new" "$fixture/names.img"
fi
mkdir -p "$fixture/names"
entry="$fixture/names.img $fixture/names vfat loop,utf8=1,umask=000,nodev,nosuid,noexec 0 0"
grep -Fxq "$entry" /etc/fstab || printf '%s\n' "$entry" >> /etc/fstab
mountpoint -q "$fixture/names" || mount "$fixture/names"
# Integration tests exercise name aliases on a casefold-enabled ext4 directory.
if [ ! -e "$fixture/fold.img" ]; then
    truncate -s 128M "$fixture/fold.img.new"
    mkfs.ext4 -q -O casefold -E encoding=utf8 "$fixture/fold.img.new"
    mv "$fixture/fold.img.new" "$fixture/fold.img"
fi
mkdir -p "$fixture/fold"
entry="$fixture/fold.img $fixture/fold ext4 loop,nodev,nosuid 0 0"
grep -Fxq "$entry" /etc/fstab || printf '%s\n' "$entry" >> /etc/fstab
mountpoint -q "$fixture/fold" || mount "$fixture/fold"
mkdir -p "$fixture/fold/work"
chattr +F "$fixture/fold/work"
chown stewart-dev:stewart-dev "$fixture/fold/work"
chmod 0700 "$fixture/fold/work"
sed -i 's/^# *en_US.UTF-8 UTF-8$/en_US.UTF-8 UTF-8/' /etc/locale.gen
locale-gen
if ! runuser -u stewart-dev -- env HOME=/home/stewart-dev rustup run 1.99.0 rustc --version >/dev/null 2>&1; then
    runuser -u stewart-dev -- env HOME=/home/stewart-dev rustup toolchain install 1.99.0 --profile minimal
fi
runuser -u stewart-dev -- env HOME=/home/stewart-dev rustup default 1.99.0
