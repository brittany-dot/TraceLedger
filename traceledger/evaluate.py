"""Compatibility entry point for the frozen experiment runner.

Use `python -m traceledger.evaluate preview|freeze|run ...`.
The v0.1 single-condition runner is superseded; it did not freeze all runtime inputs.
"""
from .experiment import main
if __name__ == '__main__':
    main()
