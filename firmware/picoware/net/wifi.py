class WiFi:
    __slots__ = ('_wlan', '_connected')

    def __init__(self):
        self._wlan = None
        self._connected = False

    def _ensure_wlan(self):
        if self._wlan is None:
            import network
            self._wlan = network.WLAN(network.STA_IF)
            self._wlan.active(True)

    def scan(self):
        self._ensure_wlan()
        try:
            results = self._wlan.scan()
            networks = []
            seen = set()
            for r in results:
                ssid = r[0].decode("utf-8") if isinstance(r[0], bytes) else r[0]
                if ssid and ssid not in seen:
                    seen.add(ssid)
                    rssi = r[3] if len(r) > 3 else 0
                    networks.append({"ssid": ssid, "rssi": rssi})
            networks.sort(key=lambda n: n["rssi"], reverse=True)
            return networks
        except Exception as e:
            print("WiFi scan error:", e)
            return []

    def connect(self, ssid, password, timeout_ms=15000):
        self._ensure_wlan()
        try:
            self._wlan.connect(ssid, password)
            from utime import ticks_ms, ticks_diff
            start = ticks_ms()
            while not self._wlan.isconnected():
                if ticks_diff(ticks_ms(), start) > timeout_ms:
                    self._connected = False
                    return False
            self._connected = True
            return True
        except Exception as e:
            print("WiFi connect error:", e)
            self._connected = False
            return False

    def disconnect(self):
        if self._wlan:
            try:
                self._wlan.disconnect()
            except:
                pass
        self._connected = False

    @property
    def is_connected(self):
        if self._wlan:
            try:
                return self._wlan.isconnected()
            except:
                pass
        return False

    @property
    def ip(self):
        if self._wlan and self._wlan.isconnected():
            try:
                return self._wlan.ifconfig()[0]
            except:
                pass
        return None

    def deinit(self):
        if self._wlan:
            try:
                self._wlan.active(False)
            except:
                pass
            self._wlan = None
        self._connected = False
