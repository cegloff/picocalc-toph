import picoware_sd
from picoware_vfs import mount as _vfs_mount, umount as _vfs_umount


class Storage:
    __slots__ = ('_vfs_mounted',)

    def __init__(self):
        picoware_sd.init()
        self._vfs_mounted = False

    @property
    def active(self):
        return picoware_sd.is_initialized()

    @property
    def vfs_mounted(self):
        return self._vfs_mounted

    def mount_vfs(self, mount_point="/sd"):
        if self._vfs_mounted:
            return True
        try:
            if _vfs_mount(mount_point):
                self._vfs_mounted = True
                return True
        except Exception as e:
            print("VFS mount error:", e)
        return False

    def unmount_vfs(self, mount_point="/sd"):
        if not self._vfs_mounted:
            return True
        try:
            _vfs_umount(mount_point)
            self._vfs_mounted = False
            return True
        except Exception as e:
            print("VFS unmount error:", e)
            return False

    def read(self, path, mode="r"):
        try:
            data = picoware_sd.read(path, 0, 0)
            return data.decode("utf-8") if mode == "r" else data
        except Exception as e:
            print("Read error:", path, e)
            return "" if mode == "r" else b""

    def write(self, path, data, overwrite=True):
        try:
            if isinstance(data, str):
                data = data.encode("utf-8")
            return picoware_sd.write(path, data, overwrite)
        except Exception as e:
            print("Write error:", path, e)
            return False

    def exists(self, path):
        return picoware_sd.exists(path)

    def listdir(self, path="/"):
        try:
            return [item["filename"] for item in picoware_sd.read_directory(path)]
        except Exception as e:
            print("Listdir error:", path, e)
            return []

    def mkdir(self, path):
        try:
            return picoware_sd.create_directory(path)
        except Exception as e:
            print("Mkdir error:", path, e)
            return False

    def remove(self, path):
        try:
            return picoware_sd.remove(path)
        except Exception as e:
            print("Remove error:", path, e)
            return False

    def size(self, path):
        return picoware_sd.get_file_size(path)

    def is_directory(self, path):
        return picoware_sd.is_directory(path)

    def read_json(self, path):
        from json import loads
        data = self.read(path)
        if data:
            try:
                return loads(data)
            except:
                pass
        return {}

    def write_json(self, path, obj):
        from json import dumps
        return self.write(path, dumps(obj))
