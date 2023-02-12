import signal
from typing import Callable, Optional
import logging


class SIGINTHandler():
    def __init__(self, handler: Optional[Callable] = None):
        self.handler = handler or self.handler

    def __enter__(self):
        signal.signal(signal.SIGINT, self.handler)

    def __exit__(self, type, value, traceback):
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    def handler(self, signum, frame):
        logging.warning('Saving data...')
        logging.warning('SIGINT Ignored!')
