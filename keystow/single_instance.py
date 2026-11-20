"""One dictation process per user; duplicate launches only raise its window.

The lock lives until the Qt loop and workers stop. Older releases without this
protocol must be quit once before upgrading. No running process is killed.
"""
import hashlib
from pathlib import Path
from PySide6.QtCore import QLockFile, QIODevice
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from . import paths


class InstanceGuard:
    def __init__(self, directory=None):
        directory = Path(directory if directory is not None else paths.data_dir())
        self.path = directory / 'dictation-instance.lock'
        self._lock = QLockFile(str(self.path))
        self._lock.setStaleLockTime(0)  # never expire a live long-running owner
        self.owned = False
        self._server = None
        self._sockets = []
        self._name = 'KeyStow-' + hashlib.sha256(str(self.path.resolve()).encode()).hexdigest()[:32]

    def acquire(self):
        self.owned = self._lock.tryLock(0)
        if self.owned:
            return True
        if self._lock.error() == QLockFile.LockFailedError:
            return False
        raise OSError('Cannot protect KeyStow from duplicate startup: ' + str(self.path))

    def listen(self, activate):
        """Only the lock owner may clean up an abandoned local socket endpoint."""
        if not self.owned:
            raise RuntimeError('Instance lock must be held before listening')
        QLocalServer.removeServer(self._name)
        self._server = QLocalServer()
        self._server.setSocketOptions(QLocalServer.UserAccessOption)
        if not self._server.listen(self._name):
            raise OSError('Cannot create KeyStow activation endpoint')
        def connected():
            while self._server.hasPendingConnections():
                socket = self._server.nextPendingConnection()
                self._sockets.append(socket)
                def read(socket=socket):
                    if bytes(socket.readAll()).strip() == b'activate':
                        activate()
                    socket.disconnectFromServer()
                socket.readyRead.connect(read)
                def finished(socket=socket):
                    if socket in self._sockets:
                        self._sockets.remove(socket)
                    socket.deleteLater()
                socket.disconnected.connect(finished)
                if socket.bytesAvailable():
                    read()
        self._server.newConnection.connect(connected)

    def activate_existing(self):
        """Best-effort focus handoff; failure must never start another controller."""
        socket = QLocalSocket()
        socket.connectToServer(self._name, QIODevice.WriteOnly)
        if not socket.waitForConnected(1000):
            return False
        socket.write(b'activate\n')
        sent = socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()
        return sent

    def release(self):
        if self._server is not None:
            self._server.close()
            self._server = None
        if self.owned:
            self._lock.unlock()
            self.owned = False
