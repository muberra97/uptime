#!/usr/bin/env python

"""
Provides a cross-platform way to figure out the system uptime.

Should work on damned near any operating system you can realistically expect
to be asked to write Python code for.
If this module is invoked as a stand-alone script, it will print the current
uptime in a human-readable format, or display an error message if it can't,
to standard output.

"""

try:
    # So many broken ctypeses out there.
    import ctypes
    import struct
except ImportError:
    ctypes = None

try:
    import os
except ImportError:
    pass

import sys
import time

try:
    from datetime import datetime
except ImportError:
    datetime = None

try:
    # RISC OS only.
    import swi
except ImportError:
    pass

try:
    # Mac OS, Python <3 only.
    import MacOS
except ImportError:
    pass

try:
    from uptime._posix import _uptime_posix, _uptime_osx
except ImportError:
    _uptime_posix = lambda: None
    _uptime_osx = lambda: None

__all__ = ['uptime', 'boottime']

__boottime = None

def _uptime_linux():
    """Returns uptime in seconds or None, on Linux."""
    # With procfs
    try:
        f = open('/proc/uptime', 'r')
        up = float(f.readline().split()[0])
        f.close()
        return up
    except (IOError, ValueError):
        pass

    # Without procfs (really?)
    try:
        libc = ctypes.CDLL('libc.so')
    except AttributeError:
        return None
    except OSError:
        # Debian and derivatives do the wrong thing because /usr/lib/libc.so
        # is a GNU ld script rather than an ELF object. To get around this, we
        # have to be more specific.
        # We don't want to use ctypes.util.find_library because that creates a
        # new process on Linux. We also don't want to try too hard because at
        # this point we're already pretty sure this isn't Linux.
        try:
            libc = ctypes.CDLL('libc.so.6')
        except OSError:
            return None

    if not hasattr(libc, 'sysinfo'):
        # Not Linux.
        return None

    buf = ctypes.create_string_buffer(128) # 64 suffices on 32-bit, whatever.
    if libc.sysinfo(buf) < 0:
        return None

    up = struct.unpack_from('@l', buf.raw)[0]
    if up < 0:
        up = None
    return up

def _boottime_linux():
    """A way to figure out the boot time directly on Linux."""
    global __boottime
    try:
        f = open('/proc/stat', 'r')
        for line in f:
            if line.startswith('btime'):
                __boottime = int(line.split()[1])

        if datetime is None:
            raise NotImplementedError('datetime module required.')

        return datetime.fromtimestamp(__boottime)
    except (IOError, IndexError):
        return None

def _uptime_bsd():
    """Returns uptime in seconds or None, on BSD (including OS X)."""
    global __boottime
    try:
        libc = ctypes.CDLL('libc.so')
    except AttributeError:
        return None
    except OSError:
        # OS X; can't use ctypes.util.find_library because that creates
        # a new process on Linux, which is undesirable.
        try:
            libc = ctypes.CDLL('libc.dylib')
        except OSError:
            return None

    if not hasattr(libc, 'sysctlbyname'):
        # Not BSD.
        return None

    # Determine how much space we need for the response.
    sz = ctypes.c_uint(0)
    libc.sysctlbyname('kern.boottime', None, ctypes.byref(sz), None, 0)
    if sz.value != struct.calcsize('@LL'):
        # Unexpected, let's give up.
        return None

    # For real now.
    buf = ctypes.create_string_buffer(sz.value)
    libc.sysctlbyname('kern.boottime', buf, ctypes.byref(sz), None, 0)
    sec, usec = struct.unpack('@LL', buf.raw)

    # OS X disagrees what that second value is.
    if usec > 1000000:
        usec = 0.

    __boottime = sec + usec / 1000000.
    up = time.time() - __boottime
    if up < 0:
        up = None
    return up

def _uptime_mac():
    """Returns uptime in seconds or None, on Mac OS."""
    try:
        # Python docs say a clock tick is 1/60th of a second, Mac OS docs say
        # it's ``approximately'' 1/60th. It's incremented by vertical retraces,
        # which the Macintosh Plus docs say happen 60.15 times per second.
        # I don't know if ``approximately'' means it's actually 1/60.15, or
        # 1/60 on some machines and 1/60.15 on others.
        return MacOS.GetTicks() / 60.15
    except NameError:
        return None

def uptime():
    """Returns uptime in seconds if even remotely possible, or None if not."""
    if __boottime is not None:
        return time.time() - __boottime

    return {'linux': _uptime_linux,
            'linux-armv71': _uptime_linux,
            'linux2': _uptime_linux,
            'mac': _uptime_mac}.get(sys.platform, _uptime_bsd)() or \
           _uptime_bsd() or _uptime_linux() or \
           _uptime_posix() or _uptime_mac() or _uptime_osx()
           
def boottime():
    """Returns boot time if remotely possible, or None if not."""
    global __boottime

    if __boottime is None:
        up = uptime()
        if up is None:
            return None
    if __boottime is None:
        _boottime_linux()

    if datetime is None:
        raise RuntimeError('datetime module required.')

    return datetime.fromtimestamp(__boottime or time.time() - up)
