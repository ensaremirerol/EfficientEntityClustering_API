from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from pathlib import Path
from typing import Callable
import filelock
import asyncio


class FileLockerMiddleware(BaseHTTPMiddleware):

    all_locks = []

    def __init__(
            self, app, files_to_lock: list[Path],
            before: Callable = None, after: Callable = None
    ):
        super().__init__(app)
        self.lock_files = [filelock.FileLock(f'{file}.lock')
                           for file in files_to_lock if file.exists()]
        self.before = before
        self.after = after

    async def dispatch(self, request: Request, call_next):
        for file in self.lock_files:
            await asyncio.to_thread(self.lock_file, file)
        if self.before is not None:
            self.before()
        try:
            response = await call_next(request)
        except Exception as e:
            for file in self.lock_files:
                await asyncio.to_thread(self.unlock_file, file)
            raise e
        if self.after is not None:
            self.after()
        for file in self.lock_files:
            await asyncio.to_thread(self.unlock_file, file)
        return response

    def lock_file(self, lock_file: filelock.FileLock):
        lock_file.acquire()
        FileLockerMiddleware.all_locks.append(lock_file)

    def unlock_file(self, lock_file: filelock.FileLock):
        lock_file.release()
        FileLockerMiddleware.all_locks.remove(lock_file)

    @staticmethod
    def unlock_all():
        while len(FileLockerMiddleware.all_locks) > 0:
            FileLockerMiddleware.all_locks.pop().release()
