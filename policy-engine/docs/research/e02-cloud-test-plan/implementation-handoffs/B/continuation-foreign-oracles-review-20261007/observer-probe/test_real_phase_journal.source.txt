import os, signal, pytest
def test_first():
    assert 7 * 6 == 42
def test_explicit_death():
    os.kill(os.getpid(), signal.SIGKILL)
