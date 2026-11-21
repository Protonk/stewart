"""Rootless guest container setup shared by the C10 and sanity launchers."""
import json
import re


def image_reference(digest):
    if not isinstance(digest, str) or not re.fullmatch('sha256:[0-9a-f]{64}', digest):
        raise ValueError('qualification must name a registry image digest')
    return 'docker.io/library/python@' + digest


def qualified_image(entry):
    platform = entry['platforms']['linux-aarch64']
    if not platform.get('python_manifest'):
        raise ValueError('qualification must identify the Linux arm64 Python manifest')
    return image_reference(platform['python_manifest'])


def check_engine(step, host):
    step('version', ['podman', '--version'])
    if not re.fullmatch(r'podman version 5\.[0-9]+\.[^\s]+\s*', (host / 'version.stdout').read_text()):
        raise ValueError('this launcher requires Podman 5.x')
    step('rootless', ['podman', 'info', '--format', '{{.Host.Security.Rootless}}'])
    if (host / 'rootless.stdout').read_text().strip() != 'true':
        raise ValueError('run Podman under the unprivileged launcher account')


def start(step, host, name, image, staging, binaries, exported, offline):
    step('image', ['podman', 'image', 'inspect', image])
    inspected, = json.loads((host / 'image.stdout').read_bytes())
    if (inspected['Digest'] != image.split('@')[1] or inspected['Architecture'] != 'arm64'
            or inspected['Os'] != 'linux'):
        raise ValueError('locally cached image differs from qualified Linux arm64 manifest')
    volume = name + '-work'
    step('work-volume', ['podman', 'volume', 'create', volume])
    setup = ('umask 077; mkdir -p /work/code && chmod 755 /work /work/code '
             '&& tar -xf /in/source.tar -C /work/code && touch /work/code/.ready && exec sleep infinity')
    argv = ['podman', 'run', '--pull=never', '--name', name, '--detach', '--init', '--user', '0:0',
            '--ulimit', 'core=0:0', '--cpus', '2', '--memory', '512m', '--platform', 'linux/arm64',
            '--network', 'none' if offline else 'pasta', '--volume', volume + ':/work:nocopy',
            '--mount', f'type=bind,source={staging},target=/in,readonly',
            '--mount', f'type=bind,source={binaries},target=/bin-in,readonly',
            '--mount', f'type=bind,source={exported},target=/out', image, 'sh', '-c', setup]
    (host / 'container.name').write_text(name + '\n')
    step('container-start', argv)
    step('running-image', ['podman', 'inspect', '--format', '{{.Image}}', name])
    if (host / 'running-image.stdout').read_text().strip() != inspected['Id']:
        raise ValueError('container started with a different image configuration')
    step('container-ready', ['podman', 'exec', name, 'sh', '-ec',
        'n=0; until test -f /work/code/.ready; do n=$((n+1)); test "$n" -lt 100; sleep 0.1; done; '
        'test "$(findmnt -n -T /work -o FSTYPE)" = ext4; '
        'test "$(cat /sys/fs/cgroup/memory.max)" = 536870912; '
        'read quota period < /sys/fs/cgroup/cpu.max; test "$quota" -eq "$((2 * period))"'])
