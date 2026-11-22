"""Bound a single Stewart placement, then exec the writer with its owned key pipe."""
import os
import resource
import signal
import sys


def main():
    ready, proceed, size = map(int, sys.argv[1:4])
    resource.setrlimit(resource.RLIMIT_FSIZE, (size, size))
    signal.signal(signal.SIGXFSZ, signal.SIG_DFL)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, [signal.SIGXFSZ])
    os.write(ready, b'1')
    os.close(ready)
    if os.read(proceed, 1) != b'1':
        raise SystemExit(1)
    os.close(proceed)
    os.execv(sys.argv[4], sys.argv[4:])


if __name__ == '__main__':
    main()
