"""Disable only lookup: actual fingerprint, callers and custody stay active."""


def pytest_configure(config):
    from polisyos.scientist.methods.autotune.dedup import TrialDeduplicator

    from removal_observation import install_observation

    def unseen(self, candidate, loop_id=""):
        return False

    TrialDeduplicator.is_duplicate = unseen
    install_observation("remove_trial_lookup")
