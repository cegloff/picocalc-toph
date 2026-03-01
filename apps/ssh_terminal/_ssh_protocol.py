"""
SSH-2 Protocol Client for PicoCalcOS
Adapted from Picoware SSH Terminal by JBlanked
Pure protocol — no UI dependencies
"""

from micropython import const
import usocket as socket
import select
import struct
import hashlib
import uos as os
from gc import collect

# SSH Message Types
SSH_MSG_DISCONNECT = const(1)
SSH_MSG_IGNORE = const(2)
SSH_MSG_UNIMPLEMENTED = const(3)
SSH_MSG_DEBUG = const(4)
SSH_MSG_SERVICE_REQUEST = const(5)
SSH_MSG_SERVICE_ACCEPT = const(6)
SSH_MSG_KEXINIT = const(20)
SSH_MSG_NEWKEYS = const(21)
SSH_MSG_KEXDH_INIT = const(30)
SSH_MSG_KEXDH_REPLY = const(31)
SSH_MSG_KEX_DH_GEX_INIT = const(32)
SSH_MSG_KEX_DH_GEX_REPLY = const(33)
SSH_MSG_KEX_DH_GEX_REQUEST = const(34)
SSH_MSG_USERAUTH_REQUEST = const(50)
SSH_MSG_USERAUTH_FAILURE = const(51)
SSH_MSG_USERAUTH_SUCCESS = const(52)
SSH_MSG_USERAUTH_BANNER = const(53)
SSH_MSG_GLOBAL_REQUEST = const(80)
SSH_MSG_REQUEST_FAILURE = const(82)
SSH_MSG_CHANNEL_OPEN = const(90)
SSH_MSG_CHANNEL_OPEN_CONFIRMATION = const(91)
SSH_MSG_CHANNEL_OPEN_FAILURE = const(92)
SSH_MSG_CHANNEL_WINDOW_ADJUST = const(93)
SSH_MSG_CHANNEL_DATA = const(94)
SSH_MSG_CHANNEL_EXTENDED_DATA = const(95)
SSH_MSG_CHANNEL_EOF = const(96)
SSH_MSG_CHANNEL_CLOSE = const(97)
SSH_MSG_CHANNEL_REQUEST = const(98)
SSH_MSG_CHANNEL_SUCCESS = const(99)
SSH_MSG_CHANNEL_FAILURE = const(100)

# DH Group 14 prime (RFC 3526) - 2048-bit MODP Group
_DH_G = const(2)
_DH_P = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D6"
    "70C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE"
    "39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9D"
    "E2BCBF6955817183995497CEA956AE515D2261898FA05101"
    "5728E5A8AACAA68FFFFFFFFFFFFFFFF",
    16,
)

# X25519 constants (RFC 7748)
_X25519_P = (1 << 255) - 19
_X25519_A24 = const(121665)


# --- SSH Protocol Helpers ---


def _ssh_string(data):
    if isinstance(data, str):
        data = data.encode()
    return struct.pack(">I", len(data)) + data


def _ssh_mpint(n):
    if n == 0:
        return struct.pack(">I", 0)
    hex_s = "%x" % n
    if len(hex_s) & 1:
        hex_s = "0" + hex_s
    b = bytes(int(hex_s[i : i + 2], 16) for i in range(0, len(hex_s), 2))
    if b[0] & 0x80:
        b = b"\x00" + b
    return struct.pack(">I", len(b)) + b


def _parse_uint32(data, offset):
    return (
        (data[offset] << 24)
        | (data[offset + 1] << 16)
        | (data[offset + 2] << 8)
        | data[offset + 3],
        offset + 4,
    )


def _parse_string(data, offset):
    length, offset = _parse_uint32(data, offset)
    return bytes(data[offset : offset + length]), offset + length


def _parse_mpint(data, offset):
    length, offset = _parse_uint32(data, offset)
    val = 0
    for i in range(length):
        val = (val << 8) | data[offset + i]
    if length > 0 and data[offset] & 0x80:
        val -= 1 << (length * 8)
    return val, offset + length


def _parse_name_list(data, offset):
    raw, offset = _parse_string(data, offset)
    if raw:
        return raw.decode().split(","), offset
    return [], offset


# --- HMAC ---


def _hmac_compute(key, msg, hash_cls, block_size):
    if len(key) > block_size:
        h = hash_cls()
        h.update(key)
        key = h.digest()
    if len(key) < block_size:
        key = key + b"\x00" * (block_size - len(key))
    o_pad = bytes(b ^ 0x5C for b in key)
    i_pad = bytes(b ^ 0x36 for b in key)
    hi = hash_cls()
    hi.update(i_pad)
    hi.update(msg)
    inner = hi.digest()
    ho = hash_cls()
    ho.update(o_pad)
    ho.update(inner)
    return ho.digest()


def _hmac_sha256(key, msg):
    return _hmac_compute(key, msg, hashlib.sha256, 64)


def _hmac_sha1(key, msg):
    return _hmac_compute(key, msg, hashlib.sha1, 64)


# --- X25519 (RFC 7748) ---


def _x25519(k_bytes, u_bytes):
    p = _X25519_P
    a24 = _X25519_A24

    k_list = bytearray(k_bytes)
    k_list[0] &= 248
    k_list[31] &= 127
    k_list[31] |= 64
    scalar = int.from_bytes(bytes(k_list), "little")
    del k_list
    collect()

    u = int.from_bytes(u_bytes, "little") & ((1 << 255) - 1)

    x_2, z_2 = 1, 0
    x_3, z_3 = u, 1
    swap = 0

    for t in range(254, -1, -1):
        k_t = (scalar >> t) & 1
        swap ^= k_t
        if swap:
            x_2, x_3 = x_3, x_2
            z_2, z_3 = z_3, z_2
        swap = k_t

        A = (x_2 + z_2) % p
        AA = (A * A) % p
        B = (x_2 - z_2) % p
        BB = (B * B) % p
        E = (AA - BB) % p
        C = (x_3 + z_3) % p
        D = (x_3 - z_3) % p
        DA = (D * A) % p
        CB = (C * B) % p
        sum_dc = (DA + CB) % p
        diff_dc = (DA - CB) % p
        x_3 = (sum_dc * sum_dc) % p
        z_3 = (u * ((diff_dc * diff_dc) % p)) % p
        x_2 = (AA * BB) % p
        z_2 = (E * ((AA + (a24 * E) % p) % p)) % p

        if t % 32 == 0:
            collect()

    if swap:
        x_2, x_3 = x_3, x_2
        z_2, z_3 = z_3, z_2

    result = (x_2 * pow(z_2, p - 2, p)) % p
    del x_2, z_2, x_3, z_3, scalar, u
    collect()

    return result.to_bytes(32, "little")


_X25519_BASE = b"\x09" + b"\x00" * 31


# --- AES-CTR Cipher ---


class _AES_CTR:
    def __init__(self, key, iv):
        try:
            from cryptolib import aes
        except ImportError:
            from ucryptolib import aes
        self._native = False
        try:
            self._aes = aes(key, 6, iv[:16])
            self._native = True
        except Exception:
            self._ecb = aes(key, 1)
            self._ctr = bytearray(iv[:16])
            self._buf = bytearray(16)
            self._pos = 16

    def _inc_counter(self):
        for i in range(15, -1, -1):
            self._ctr[i] = (self._ctr[i] + 1) & 0xFF
            if self._ctr[i]:
                break

    def process(self, data):
        if self._native:
            return self._aes.encrypt(data)
        out = bytearray(len(data))
        for i in range(len(data)):
            if self._pos >= 16:
                ks = self._ecb.encrypt(bytes(self._ctr))
                for j in range(16):
                    self._buf[j] = ks[j]
                self._inc_counter()
                self._pos = 0
            out[i] = data[i] ^ self._buf[self._pos]
            self._pos += 1
        return bytes(out)


# --- SSH-2 Client ---


class SSHClient:
    _CLIENT_VERSION = "SSH-2.0-PicoCalcOS_1.0"

    _KEX_ALGORITHMS = (
        "curve25519-sha256,"
        "curve25519-sha256@libssh.org,"
        "diffie-hellman-group-exchange-sha256,"
        "diffie-hellman-group14-sha256,"
        "diffie-hellman-group14-sha1"
    )
    _HOST_KEY_ALGORITHMS = (
        "ssh-ed25519,rsa-sha2-256,rsa-sha2-512,"
        "ecdsa-sha2-nistp256,ssh-rsa"
    )
    _CIPHERS = "aes128-ctr,aes256-ctr"
    _MACS = "hmac-sha2-256,hmac-sha1"
    _COMPRESSION = "none"

    def __init__(self):
        self._sock = None
        self._connected = False
        self._authenticated = False
        self._error = None
        self._output = []

        self._server_version = ""
        self._send_seq = 0
        self._recv_seq = 0
        self._session_id = None

        self._encrypted = False
        self._enc_cipher = None
        self._dec_cipher = None
        self._mac_key_c2s = None
        self._mac_key_s2c = None
        self._mac_len = 0
        self._mac_func = None

        self._kex_algorithm = None
        self._cipher_c2s = None
        self._cipher_s2c = None
        self._mac_c2s = None
        self._mac_s2c = None
        self._client_kexinit = None
        self._server_kexinit = None

        self._channel_id = 0
        self._remote_channel = 0
        self._remote_window = 0
        self._remote_max_pkt = 0
        self._channel_eof = False
        self._channel_closed = False
        self._local_consumed = 0

    @property
    def is_connected(self):
        return self._connected and self._authenticated

    @property
    def error(self):
        return self._error

    @property
    def output(self):
        return self._output

    # ---- Transport ----

    def _recv_exact(self, n):
        buf = bytearray()
        while len(buf) < n:
            chunk = self._sock.recv(min(n - len(buf), 4096))
            if not chunk:
                raise Exception("Connection closed")
            buf.extend(chunk)
        return bytes(buf)

    def _send_all(self, data):
        mv = memoryview(data)
        total = 0
        while total < len(data):
            sent = self._sock.send(mv[total:])
            if sent <= 0:
                raise Exception("Send failed")
            total += sent

    def _read_packet(self):
        if self._encrypted:
            raw4 = self._recv_exact(4)
            dec4 = self._dec_cipher.process(raw4)
            pkt_len, _ = _parse_uint32(dec4, 0)
            if pkt_len > 35000:
                raise Exception("Packet too large")
            raw_rest = self._recv_exact(pkt_len)
            dec_rest = self._dec_cipher.process(raw_rest)
            mac_recv = self._recv_exact(self._mac_len)
            seq_b = struct.pack(">I", self._recv_seq)
            mac_calc = self._mac_func(self._mac_key_s2c, seq_b + dec4 + dec_rest)
            if mac_calc[: self._mac_len] != mac_recv:
                raise Exception("MAC verification failed")
            self._recv_seq = (self._recv_seq + 1) & 0xFFFFFFFF
            pad_len = dec_rest[0]
            return bytes(dec_rest[1 : pkt_len - pad_len])
        else:
            raw4 = self._recv_exact(4)
            pkt_len, _ = _parse_uint32(raw4, 0)
            if pkt_len > 35000:
                raise Exception("Packet too large")
            raw_rest = self._recv_exact(pkt_len)
            self._recv_seq = (self._recv_seq + 1) & 0xFFFFFFFF
            pad_len = raw_rest[0]
            return bytes(raw_rest[1 : pkt_len - pad_len])

    def _send_packet(self, payload):
        bs = 16 if self._encrypted else 8
        inner = 1 + len(payload)
        pad_len = bs - ((4 + inner) % bs)
        if pad_len < 4:
            pad_len += bs
        pkt_len = inner + pad_len
        padding = os.urandom(pad_len)
        packet = struct.pack(">IB", pkt_len, pad_len) + payload + padding
        if self._encrypted:
            seq_b = struct.pack(">I", self._send_seq)
            mac = self._mac_func(self._mac_key_c2s, seq_b + packet)
            mac = mac[: self._mac_len]
            enc = self._enc_cipher.process(packet)
            self._send_all(enc + mac)
        else:
            self._send_all(packet)
        self._send_seq = (self._send_seq + 1) & 0xFFFFFFFF

    def _read_ssh_packet(self):
        while True:
            payload = self._read_packet()
            if not payload:
                raise Exception("Empty packet")
            t = payload[0]
            if t == SSH_MSG_DISCONNECT:
                _, off = _parse_uint32(payload, 1)
                desc, _ = _parse_string(payload, off)
                raise Exception("Disconnected: " + desc.decode("utf-8", "ignore"))
            if t in (SSH_MSG_IGNORE, SSH_MSG_DEBUG, SSH_MSG_UNIMPLEMENTED):
                continue
            if t == SSH_MSG_GLOBAL_REQUEST:
                self._send_packet(bytes([SSH_MSG_REQUEST_FAILURE]))
                continue
            return payload

    # ---- Key Exchange ----

    def _build_kexinit(self):
        p = bytearray()
        p.append(SSH_MSG_KEXINIT)
        p.extend(os.urandom(16))
        for alg_list in (
            self._KEX_ALGORITHMS,
            self._HOST_KEY_ALGORITHMS,
            self._CIPHERS, self._CIPHERS,
            self._MACS, self._MACS,
            self._COMPRESSION, self._COMPRESSION,
            "", "",
        ):
            p.extend(_ssh_string(alg_list))
        p.append(0)
        p.extend(b"\x00\x00\x00\x00")
        return bytes(p)

    def _negotiate_kexinit(self, server_payload):
        off = 17
        s_kex, off = _parse_name_list(server_payload, off)
        s_host, off = _parse_name_list(server_payload, off)
        s_enc_c2s, off = _parse_name_list(server_payload, off)
        s_enc_s2c, off = _parse_name_list(server_payload, off)
        s_mac_c2s, off = _parse_name_list(server_payload, off)
        s_mac_s2c, off = _parse_name_list(server_payload, off)

        def pick(client_csv, server_list):
            for a in client_csv.split(","):
                if a in server_list:
                    return a
            return None

        self._kex_algorithm = pick(self._KEX_ALGORITHMS, s_kex)
        if not self._kex_algorithm:
            raise Exception("No common KEX")

        host_alg = pick(self._HOST_KEY_ALGORITHMS, s_host)
        if not host_alg:
            raise Exception("No common host key")

        self._cipher_c2s = pick(self._CIPHERS, s_enc_c2s)
        self._cipher_s2c = pick(self._CIPHERS, s_enc_s2c)
        if not self._cipher_c2s or not self._cipher_s2c:
            raise Exception("No common cipher")

        self._mac_c2s = pick(self._MACS, s_mac_c2s)
        self._mac_s2c = pick(self._MACS, s_mac_s2c)
        if not self._mac_c2s or not self._mac_s2c:
            raise Exception("No common MAC")

    def _do_kex(self):
        alg = self._kex_algorithm
        if alg in ("curve25519-sha256", "curve25519-sha256@libssh.org"):
            return self._do_curve25519_kex()
        elif alg == "diffie-hellman-group-exchange-sha256":
            return self._do_gex_kex()
        elif alg.startswith("diffie-hellman-group14"):
            return self._do_dh_group14_kex()
        else:
            raise Exception("KEX '%s' not implemented" % alg)

    def _do_curve25519_kex(self):
        priv = os.urandom(32)
        Q_C = _x25519(priv, _X25519_BASE)
        self._send_packet(bytes([SSH_MSG_KEXDH_INIT]) + _ssh_string(Q_C))
        reply = self._read_ssh_packet()
        if reply[0] != SSH_MSG_KEXDH_REPLY:
            raise Exception("Expected ECDH_REPLY, got %d" % reply[0])
        off = 1
        K_S, off = _parse_string(reply, off)
        Q_S, off = _parse_string(reply, off)
        sig, off = _parse_string(reply, off)
        if len(Q_S) != 32:
            raise Exception("Invalid server ECDH key")
        raw_K = _x25519(priv, Q_S)
        if raw_K == b"\x00" * 32:
            raise Exception("X25519 zero result")
        K = int.from_bytes(raw_K, "big")
        hash_cls = hashlib.sha256
        h = hash_cls()
        h.update(_ssh_string(self._CLIENT_VERSION))
        h.update(_ssh_string(self._server_version))
        h.update(_ssh_string(self._client_kexinit))
        h.update(_ssh_string(self._server_kexinit))
        h.update(_ssh_string(K_S))
        h.update(_ssh_string(Q_C))
        h.update(_ssh_string(Q_S))
        h.update(_ssh_mpint(K))
        H = h.digest()
        if self._session_id is None:
            self._session_id = H
        del priv, raw_K
        collect()
        return K, H, hash_cls

    def _do_gex_kex(self):
        gex_min, gex_n, gex_max = 2048, 2048, 4096
        req = bytearray()
        req.append(SSH_MSG_KEX_DH_GEX_REQUEST)
        req.extend(struct.pack(">III", gex_min, gex_n, gex_max))
        self._send_packet(bytes(req))
        grp = self._read_ssh_packet()
        if grp[0] != SSH_MSG_KEXDH_REPLY:
            raise Exception("Expected GEX_GROUP, got %d" % grp[0])
        off = 1
        p, off = _parse_mpint(grp, off)
        g, off = _parse_mpint(grp, off)
        if p < (1 << (gex_min - 1)):
            raise Exception("Server DH prime too small")
        x = int.from_bytes(os.urandom(16), "big")
        e = pow(g, x, p)
        self._send_packet(bytes([SSH_MSG_KEX_DH_GEX_INIT]) + _ssh_mpint(e))
        reply = self._read_ssh_packet()
        if reply[0] != SSH_MSG_KEX_DH_GEX_REPLY:
            raise Exception("Expected GEX_REPLY, got %d" % reply[0])
        off = 1
        K_S, off = _parse_string(reply, off)
        f, off = _parse_mpint(reply, off)
        sig, off = _parse_string(reply, off)
        if f < 2 or f >= p - 1:
            raise Exception("Invalid server GEX value")
        K = pow(f, x, p)
        hash_cls = hashlib.sha256
        h = hash_cls()
        h.update(_ssh_string(self._CLIENT_VERSION))
        h.update(_ssh_string(self._server_version))
        h.update(_ssh_string(self._client_kexinit))
        h.update(_ssh_string(self._server_kexinit))
        h.update(_ssh_string(K_S))
        h.update(struct.pack(">III", gex_min, gex_n, gex_max))
        h.update(_ssh_mpint(p))
        h.update(_ssh_mpint(g))
        h.update(_ssh_mpint(e))
        h.update(_ssh_mpint(f))
        h.update(_ssh_mpint(K))
        H = h.digest()
        if self._session_id is None:
            self._session_id = H
        del x, e, f, p, g
        collect()
        return K, H, hash_cls

    def _do_dh_group14_kex(self):
        x = int.from_bytes(os.urandom(16), "big")
        e = pow(_DH_G, x, _DH_P)
        self._send_packet(bytes([SSH_MSG_KEXDH_INIT]) + _ssh_mpint(e))
        reply = self._read_ssh_packet()
        if reply[0] != SSH_MSG_KEXDH_REPLY:
            raise Exception("Expected KEXDH_REPLY, got %d" % reply[0])
        off = 1
        k_s, off = _parse_string(reply, off)
        f, off = _parse_mpint(reply, off)
        sig, off = _parse_string(reply, off)
        if f < 2 or f >= _DH_P - 1:
            raise Exception("Invalid server DH value")
        K = pow(f, x, _DH_P)
        if "sha256" in self._kex_algorithm:
            hash_cls = hashlib.sha256
        else:
            hash_cls = hashlib.sha1
        h = hash_cls()
        h.update(_ssh_string(self._CLIENT_VERSION))
        h.update(_ssh_string(self._server_version))
        h.update(_ssh_string(self._client_kexinit))
        h.update(_ssh_string(self._server_kexinit))
        h.update(_ssh_string(k_s))
        h.update(_ssh_mpint(e))
        h.update(_ssh_mpint(f))
        h.update(_ssh_mpint(K))
        H = h.digest()
        if self._session_id is None:
            self._session_id = H
        del x, e, f
        collect()
        return K, H, hash_cls

    def _derive_keys(self, K, H, hash_cls):
        K_enc = _ssh_mpint(K)

        def derive(letter, needed):
            h = hash_cls()
            h.update(K_enc)
            h.update(H)
            h.update(letter.encode())
            h.update(self._session_id)
            key = h.digest()
            while len(key) < needed:
                h = hash_cls()
                h.update(K_enc)
                h.update(H)
                h.update(key)
                key += h.digest()
            return key[:needed]

        c2s_key_len = 32 if self._cipher_c2s == "aes256-ctr" else 16
        s2c_key_len = 32 if self._cipher_s2c == "aes256-ctr" else 16

        if self._mac_c2s == "hmac-sha2-256":
            mac_key_len = 32
            self._mac_len = 32
            self._mac_func = _hmac_sha256
        else:
            mac_key_len = 20
            self._mac_len = 20
            self._mac_func = _hmac_sha1

        iv_c2s = derive("A", 16)
        iv_s2c = derive("B", 16)
        key_c2s = derive("C", c2s_key_len)
        key_s2c = derive("D", s2c_key_len)
        self._mac_key_c2s = derive("E", mac_key_len)
        self._mac_key_s2c = derive("F", mac_key_len)

        self._enc_cipher = _AES_CTR(key_c2s, iv_c2s)
        self._dec_cipher = _AES_CTR(key_s2c, iv_s2c)

        del K_enc
        collect()

    # ---- Authentication ----

    def _request_service(self, name):
        self._send_packet(bytes([SSH_MSG_SERVICE_REQUEST]) + _ssh_string(name))
        resp = self._read_ssh_packet()
        if resp[0] != SSH_MSG_SERVICE_ACCEPT:
            raise Exception("Service '%s' rejected" % name)

    def _auth_password(self, username, password):
        p = bytearray()
        p.append(SSH_MSG_USERAUTH_REQUEST)
        p.extend(_ssh_string(username))
        p.extend(_ssh_string("ssh-connection"))
        p.extend(_ssh_string("password"))
        p.append(0)
        p.extend(_ssh_string(password))
        self._send_packet(bytes(p))
        while True:
            resp = self._read_ssh_packet()
            t = resp[0]
            if t == SSH_MSG_USERAUTH_SUCCESS:
                return True
            elif t == SSH_MSG_USERAUTH_BANNER:
                continue
            elif t == SSH_MSG_USERAUTH_FAILURE:
                methods, _ = _parse_string(resp, 1)
                raise Exception("Auth failed (%s)" % methods.decode())
            else:
                raise Exception("Auth unexpected msg %d" % t)

    # ---- Channel operations ----

    def _open_session_channel(self):
        self._channel_id = 0
        local_win = 0x200000
        local_max = 0x8000
        p = bytearray()
        p.append(SSH_MSG_CHANNEL_OPEN)
        p.extend(_ssh_string("session"))
        p.extend(struct.pack(">III", self._channel_id, local_win, local_max))
        self._send_packet(bytes(p))
        while True:
            resp = self._read_ssh_packet()
            t = resp[0]
            if t == SSH_MSG_CHANNEL_OPEN_CONFIRMATION:
                off = 1
                _, off = _parse_uint32(resp, off)
                self._remote_channel, off = _parse_uint32(resp, off)
                self._remote_window, off = _parse_uint32(resp, off)
                self._remote_max_pkt, off = _parse_uint32(resp, off)
                self._channel_eof = False
                self._channel_closed = False
                return
            elif t == SSH_MSG_CHANNEL_OPEN_FAILURE:
                _, off = _parse_uint32(resp, 1)
                code, off = _parse_uint32(resp, off)
                desc, _ = _parse_string(resp, off)
                raise Exception("Channel open failed: " + desc.decode("utf-8", "ignore"))
            else:
                continue

    def _send_exec(self, command):
        p = bytearray()
        p.append(SSH_MSG_CHANNEL_REQUEST)
        p.extend(struct.pack(">I", self._remote_channel))
        p.extend(_ssh_string("exec"))
        p.append(1)
        p.extend(_ssh_string(command))
        self._send_packet(bytes(p))

    def _collect_output(self):
        lines = []
        while not self._channel_closed:
            try:
                self._sock.settimeout(15.0)
                resp = self._read_ssh_packet()
            except Exception as e:
                s = str(e)
                if "timed out" in s or "ETIMEDOUT" in s:
                    break
                raise

            t = resp[0]
            if t == SSH_MSG_CHANNEL_SUCCESS:
                continue
            if t == SSH_MSG_CHANNEL_FAILURE:
                lines.append("[Server rejected command]")
                break
            if t == SSH_MSG_CHANNEL_DATA:
                off = 1
                _, off = _parse_uint32(resp, off)
                data, _ = _parse_string(resp, off)
                text = data.decode("utf-8", "ignore")
                for ln in text.split("\n"):
                    lines.append(ln)
                continue
            if t == SSH_MSG_CHANNEL_EXTENDED_DATA:
                off = 1
                _, off = _parse_uint32(resp, off)
                dtype, off = _parse_uint32(resp, off)
                data, _ = _parse_string(resp, off)
                text = data.decode("utf-8", "ignore")
                prefix = "[stderr] " if dtype == 1 else ""
                for ln in text.split("\n"):
                    lines.append(prefix + ln)
                continue
            if t == SSH_MSG_CHANNEL_EOF:
                self._channel_eof = True
                continue
            if t == SSH_MSG_CHANNEL_CLOSE:
                self._channel_closed = True
                cp = bytearray()
                cp.append(SSH_MSG_CHANNEL_CLOSE)
                cp.extend(struct.pack(">I", self._remote_channel))
                self._send_packet(bytes(cp))
                break
            if t == SSH_MSG_CHANNEL_WINDOW_ADJUST:
                off = 1
                _, off = _parse_uint32(resp, off)
                adj, _ = _parse_uint32(resp, off)
                self._remote_window += adj
                continue
            if t == SSH_MSG_CHANNEL_REQUEST:
                off = 1
                _, off = _parse_uint32(resp, off)
                rtype, off = _parse_string(resp, off)
                want = resp[off] if off < len(resp) else 0
                if want:
                    sp = bytearray()
                    sp.append(SSH_MSG_CHANNEL_SUCCESS)
                    sp.extend(struct.pack(">I", self._remote_channel))
                    self._send_packet(bytes(sp))
                continue

        while lines and not lines[-1].strip():
            lines.pop()
        return lines

    # ---- PTY / Shell / Non-blocking I/O ----

    def _wait_channel_reply(self, name):
        while True:
            resp = self._read_ssh_packet()
            t = resp[0]
            if t == SSH_MSG_CHANNEL_SUCCESS:
                return
            if t == SSH_MSG_CHANNEL_FAILURE:
                raise Exception("%s request failed" % name)
            if t == SSH_MSG_CHANNEL_WINDOW_ADJUST:
                off = 1
                _, off = _parse_uint32(resp, off)
                adj, _ = _parse_uint32(resp, off)
                self._remote_window += adj
                continue
            if t == SSH_MSG_CHANNEL_DATA or t == SSH_MSG_CHANNEL_EXTENDED_DATA:
                continue  # discard early data
            if t == SSH_MSG_CHANNEL_REQUEST:
                off = 1
                _, off = _parse_uint32(resp, off)
                rtype, off = _parse_string(resp, off)
                want = resp[off] if off < len(resp) else 0
                if want:
                    sp = bytearray()
                    sp.append(SSH_MSG_CHANNEL_SUCCESS)
                    sp.extend(struct.pack(">I", self._remote_channel))
                    self._send_packet(bytes(sp))
                continue
            if t == SSH_MSG_CHANNEL_EOF:
                self._channel_eof = True
                continue
            if t == SSH_MSG_CHANNEL_CLOSE:
                self._channel_closed = True
                raise Exception("%s: channel closed" % name)

    def request_pty(self, cols, rows, term="xterm"):
        p = bytearray()
        p.append(SSH_MSG_CHANNEL_REQUEST)
        p.extend(struct.pack(">I", self._remote_channel))
        p.extend(_ssh_string("pty-req"))
        p.append(1)  # want reply
        p.extend(_ssh_string(term))
        p.extend(struct.pack(">IIII", cols, rows, cols * 8, rows * 16))
        p.extend(_ssh_string(""))  # terminal modes (empty)
        self._send_packet(bytes(p))
        self._wait_channel_reply("PTY")

    def request_shell(self):
        p = bytearray()
        p.append(SSH_MSG_CHANNEL_REQUEST)
        p.extend(struct.pack(">I", self._remote_channel))
        p.extend(_ssh_string("shell"))
        p.append(1)  # want reply
        self._send_packet(bytes(p))
        self._wait_channel_reply("Shell")

    def open_shell(self, cols, rows):
        self._sock.settimeout(15.0)
        self._open_session_channel()
        self.request_pty(cols, rows)
        self.request_shell()
        self._sock.settimeout(0.1)
        self._local_consumed = 0

    def send_data(self, data):
        if isinstance(data, str):
            data = data.encode()
        while data:
            chunk_len = min(len(data), self._remote_window, self._remote_max_pkt)
            if chunk_len <= 0:
                break
            p = bytearray()
            p.append(SSH_MSG_CHANNEL_DATA)
            p.extend(struct.pack(">I", self._remote_channel))
            p.extend(_ssh_string(data[:chunk_len]))
            self._send_packet(bytes(p))
            self._remote_window -= chunk_len
            data = data[chunk_len:]

    def poll_data(self):
        if not self._connected or self._channel_closed:
            return None
        poller = select.poll()
        poller.register(self._sock, select.POLLIN)
        ready = poller.poll(0)
        poller.unregister(self._sock)
        if not ready:
            return None
        result = bytearray()
        burst = 0
        while burst < 8:
            try:
                self._sock.settimeout(0.5)
                payload = self._read_packet()
            except Exception as e:
                s = str(e)
                if "timed out" in s or "ETIMEDOUT" in s:
                    break
                self._connected = False
                self._channel_closed = True
                break
            if not payload:
                break
            t = payload[0]
            if t in (SSH_MSG_IGNORE, SSH_MSG_DEBUG, SSH_MSG_UNIMPLEMENTED):
                continue
            if t == SSH_MSG_GLOBAL_REQUEST:
                self._send_packet(bytes([SSH_MSG_REQUEST_FAILURE]))
                continue
            if t == SSH_MSG_DISCONNECT:
                self._connected = False
                self._channel_closed = True
                break
            if t == SSH_MSG_CHANNEL_DATA:
                off = 1
                _, off = _parse_uint32(payload, off)
                data, _ = _parse_string(payload, off)
                result.extend(data)
                self._local_consumed += len(data)
                burst += 1
            elif t == SSH_MSG_CHANNEL_EXTENDED_DATA:
                off = 1
                _, off = _parse_uint32(payload, off)
                _, off = _parse_uint32(payload, off)  # data type
                data, _ = _parse_string(payload, off)
                result.extend(data)
                self._local_consumed += len(data)
                burst += 1
            elif t == SSH_MSG_CHANNEL_WINDOW_ADJUST:
                off = 1
                _, off = _parse_uint32(payload, off)
                adj, _ = _parse_uint32(payload, off)
                self._remote_window += adj
            elif t == SSH_MSG_CHANNEL_EOF:
                self._channel_eof = True
            elif t == SSH_MSG_CHANNEL_CLOSE:
                self._channel_closed = True
                cp = bytearray()
                cp.append(SSH_MSG_CHANNEL_CLOSE)
                cp.extend(struct.pack(">I", self._remote_channel))
                try:
                    self._send_packet(bytes(cp))
                except Exception:
                    pass
                break
            elif t == SSH_MSG_CHANNEL_REQUEST:
                off = 1
                _, off = _parse_uint32(payload, off)
                rtype, off = _parse_string(payload, off)
                want = payload[off] if off < len(payload) else 0
                if want:
                    sp = bytearray()
                    sp.append(SSH_MSG_CHANNEL_SUCCESS)
                    sp.extend(struct.pack(">I", self._remote_channel))
                    self._send_packet(bytes(sp))
            # Check if more data available without blocking
            poller = select.poll()
            poller.register(self._sock, select.POLLIN)
            more = poller.poll(0)
            poller.unregister(self._sock)
            if not more:
                break
        # Auto-adjust window
        if self._local_consumed >= 0x8000:
            self.adjust_window(self._local_consumed)
            self._local_consumed = 0
        return bytes(result) if result else None

    def send_window_change(self, cols, rows):
        p = bytearray()
        p.append(SSH_MSG_CHANNEL_REQUEST)
        p.extend(struct.pack(">I", self._remote_channel))
        p.extend(_ssh_string("window-change"))
        p.append(0)  # no reply
        p.extend(struct.pack(">IIII", cols, rows, cols * 8, rows * 16))
        self._send_packet(bytes(p))

    def adjust_window(self, bytes_consumed):
        p = bytearray()
        p.append(SSH_MSG_CHANNEL_WINDOW_ADJUST)
        p.extend(struct.pack(">II", self._remote_channel, bytes_consumed))
        self._send_packet(bytes(p))

    # ---- Public API ----

    def connect(self, host, port, username, password):
        if self._connected:
            self._error = "Already connected"
            return False
        try:
            info = socket.getaddrinfo(host, port)[0]
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(15.0)
            self._sock.connect(info[-1])

            # Version exchange
            buf = b""
            while True:
                c = self._sock.recv(1)
                if not c:
                    raise Exception("Connection closed during version exchange")
                buf += c
                if buf.endswith(b"\n"):
                    line = buf.decode("utf-8", "ignore").strip()
                    if line.startswith("SSH-"):
                        self._server_version = line
                        break
                    buf = b""
                if len(buf) > 255:
                    raise Exception("Version line too long")

            self._sock.send((self._CLIENT_VERSION + "\r\n").encode())

            # Key exchange
            kexinit = self._build_kexinit()
            self._client_kexinit = kexinit
            self._send_packet(kexinit)

            s_kex = self._read_ssh_packet()
            if s_kex[0] != SSH_MSG_KEXINIT:
                raise Exception("Expected KEXINIT, got %d" % s_kex[0])
            self._server_kexinit = s_kex

            self._negotiate_kexinit(s_kex)
            K, H, hash_cls = self._do_kex()
            self._derive_keys(K, H, hash_cls)
            del K
            collect()

            self._send_packet(bytes([SSH_MSG_NEWKEYS]))
            nk = self._read_ssh_packet()
            if nk[0] != SSH_MSG_NEWKEYS:
                raise Exception("Expected NEWKEYS, got %d" % nk[0])

            self._encrypted = True
            self._client_kexinit = None
            self._server_kexinit = None
            collect()

            # Authentication
            self._request_service("ssh-userauth")
            self._auth_password(username, password)

            self._connected = True
            self._authenticated = True
            self._error = None
            return True

        except Exception as e:
            self._error = str(e)
            self._connected = False
            self._authenticated = False
            self._close_socket()
            return False

    def execute_command(self, command):
        if not self._connected or not self._authenticated:
            self._error = "Not connected"
            return False
        try:
            self._sock.settimeout(15.0)
            self._open_session_channel()
            self._send_exec(command)
            lines = self._collect_output()
            self._output.append("$ " + command)
            self._output.extend(lines)
            return True
        except Exception as e:
            self._error = str(e)
            self._output.append("$ " + command)
            self._output.append("[Error: %s]" % str(e))
            return False

    def disconnect(self):
        if self._connected:
            try:
                p = bytearray()
                p.append(SSH_MSG_DISCONNECT)
                p.extend(struct.pack(">I", 11))
                p.extend(_ssh_string("Bye"))
                p.extend(_ssh_string(""))
                self._send_packet(bytes(p))
            except Exception:
                pass

        self._connected = False
        self._authenticated = False
        self._encrypted = False
        self._enc_cipher = None
        self._dec_cipher = None
        self._mac_key_c2s = None
        self._mac_key_s2c = None
        self._session_id = None
        self._send_seq = 0
        self._recv_seq = 0
        self._output.clear()
        self._close_socket()

    def _close_socket(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
