"""Minimal HTTPS GET/POST client for MicroPython."""

import gc
import usocket as socket


def http_get(host, path, port=443, use_ssl=True, callback=None, buf_size=512, headers=None):
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

        req = "GET {} HTTP/1.0\r\nHost: {}\r\n".format(path, host)
        if headers:
            for k, v in headers.items():
                req += "{}: {}\r\n".format(k, v)
        req += "Connection: close\r\n\r\n"
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


def http_post(host, path, body=None, headers=None, port=443, use_ssl=True,
              stream=False, buf_size=512):
    """
    HTTP POST request.
    If stream=False: returns (body_bytes, status_code).
    If stream=True: returns (socket, status_code) — caller reads body and closes.
    """
    gc.collect()
    addr = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)[0][-1]
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30)
    close = True
    try:
        sock.connect(addr)
        if use_ssl:
            import ssl
            gc.collect()
            sock = ssl.wrap_socket(sock, server_hostname=host)

        if body is not None and isinstance(body, str):
            body = body.encode()

        req = "POST {} HTTP/1.0\r\nHost: {}\r\n".format(path, host)
        if headers:
            for k, v in headers.items():
                req += "{}: {}\r\n".format(k, v)
        if body is not None:
            req += "Content-Length: {}\r\n".format(len(body))
        req += "Connection: close\r\n\r\n"

        _send(sock, req.encode())
        if body is not None:
            _send(sock, body)

        line = _readline(sock)
        parts = line.split(b' ', 2)
        status = int(parts[1]) if len(parts) >= 2 else 0

        while True:
            line = _readline(sock)
            if not line or line == b'\r\n' or line == b'\n':
                break

        if stream:
            close = False
            return sock, status

        buf = bytearray()
        while True:
            chunk = sock.read(buf_size) if hasattr(sock, 'read') else sock.recv(buf_size)
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf), status
    finally:
        if close:
            try:
                sock.close()
            except:
                pass


def http_readline(sock):
    """Read one line from socket. For SSE parsing."""
    return _readline(sock)


def _send(sock, data):
    sock.write(data) if hasattr(sock, 'write') else sock.send(data)


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
