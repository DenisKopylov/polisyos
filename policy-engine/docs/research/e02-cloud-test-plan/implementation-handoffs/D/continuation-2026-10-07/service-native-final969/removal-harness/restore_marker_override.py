"""Restore the valid supplied-marker override at the actual registry caller."""


def pytest_configure(config):
    from polisyos.scientist.methods.search import controller, frontier

    from removal_observation import install_observation

    canonical = frontier.policy_candidate_hash

    def overridden(candidate, *, metadata_hash=None, explicit_hash=None):
        if metadata_hash:
            return metadata_hash
        if explicit_hash:
            return explicit_hash
        return canonical(candidate)

    frontier.policy_candidate_hash = overridden
    controller.policy_candidate_hash = overridden
    install_observation("restore_marker_override")
