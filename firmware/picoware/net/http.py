"""Minimal HTTPS GET client for MicroPython."""

import gc
import usocket as socket


def http_get(host, path, port=443, use_ssl=True, callback=None, buf_size=512):
    """
    HTTP GET request. Returns (body_bytes, content_length) if no callback,
    or (total_written, content_length) if callback streams chunks.
    """
    gc.collect()
    addr = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)[0][-1]
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30)
    try:
        sock.connect(addr)
        if use_ssl:
            import ssl
            gc.collect()
            sock = ssl.wrap_socket(sock, server_hostname=host)

        req = "GET {} HTTP/1.0\r\nHost: {}\r\nConnection: close\r\n\r\n".format(path, host)
        sock.write(req.encode()) if hasattr(sock, 'write') else sock.send(req.encode())

        # read status line
        line = _readline(sock)
        parts = line.split(b' ', 2)
        status = int(parts[1]) if len(parts) >= 2 else 0
        if status != 200:
            raise Exception("HTTP {}".format(status))

        # read headers
        content_length = -1
        while True:
            line = _readline(sock)
            if not line or line == b'\r\n' or line == b'\n':
                break
            if line.lower().startswith(b'content-length:'):
                content_length = int(line.split(b':', 1)[1].strip())

        # read body
        total = 0
        if callback is None:
            buf = bytearray()
            while True:
                chunk = sock.read(buf_size) if hasattr(sock, 'read') else sock.recv(buf_size)
                if not chunk:
                    break
                buf.extend(chunk)
                total += len(chunk)
            return bytes(buf), content_length
        else:
            while True:
                chunk = sock.read(buf_size) if hasattr(sock, 'read') else sock.recv(buf_size)
                if not chunk:
                    break
                callback(chunk)
                total += len(chunk)
                if total % 4096 < buf_size:
                    gc.collect()
            return total, content_length
    finally:
        try:
            sock.close()
        except:
            pass


def _readline(sock):
    buf = bytearray()
    while True:
        b = sock.read(1) if hasattr(sock, 'read') else sock.recv(1)
        if not b:
            break
        buf.extend(b)
        if b == b'\n':
            break
    return bytes(buf)
