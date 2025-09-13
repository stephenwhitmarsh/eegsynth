import sys
import time

from .historysignal import _setup, _start, _loop_once, _loop_forever, _stop

class _executable:
    # start this module as a stand-alone executable
    def __init__(self, args=None):
        if args!=None:
            # override the command line arguments
            sys.argv = [sys.argv[0]] + args

        # the setup MUST pass without errors
        _setup()

        while True:
            # keep running until KeyboardInterrupt
            try:
                _start()
                _loop_forever()
            except RuntimeError:
                # restart after one second
                time.sleep(1)
            except KeyboardInterrupt:
                raise SystemExit

    def __del__(self):
        _stop()
