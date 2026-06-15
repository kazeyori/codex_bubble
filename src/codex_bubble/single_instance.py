from ctypes import GetLastError, windll


ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    def __init__(self, name):
        self.name = name
        self.handle = None

    def acquire(self):
        self.handle = windll.kernel32.CreateMutexW(None, False, self.name)
        if not self.handle:
            return False
        return GetLastError() != ERROR_ALREADY_EXISTS

    def release(self):
        if self.handle:
            windll.kernel32.CloseHandle(self.handle)
            self.handle = None
