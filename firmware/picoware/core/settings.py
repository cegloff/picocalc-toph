_DEFAULTS = {
    "dark_mode": True,
    "brightness": 128,
    "kb_brightness": 64,
    "wifi_ssid": "",
    "wifi_password": "",
    "auto_connect_wifi": True,
    "font_size": 0,
}

_SETTINGS_PATH = "picoware/settings/system.json"


class Settings:
    __slots__ = ('_storage', '_cache')

    def __init__(self, storage):
        self._storage = storage
        self._cache = dict(_DEFAULTS)
        self._load()

    def _load(self):
        data = self._storage.read_json(_SETTINGS_PATH)
        if data:
            self._cache.update(data)

    def _save(self):
        self._storage.write_json(_SETTINGS_PATH, self._cache)

    def get(self, key, default=None):
        return self._cache.get(key, default)

    def set(self, key, value):
        self._cache[key] = value
        self._save()

    def get_all(self):
        return dict(self._cache)
