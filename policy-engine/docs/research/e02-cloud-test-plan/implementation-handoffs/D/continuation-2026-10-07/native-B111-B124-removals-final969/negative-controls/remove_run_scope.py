"""Omit only run identity after the real native admission/member reads."""

import hashlib
import inspect
import json


def pytest_configure(config):
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.scientist.methods.search.service import NativeSearchService

    actual_members = NativeSearchService._deduplication_members
    actual_tell = NativeSearchService.tell

    def configuration_only(self, context, **kwargs):
        scope, members, encode = actual_members(self, context, **kwargs)
        scope = hashlib.sha256(
            json.dumps(
                self._configuration(context), sort_keys=True, allow_nan=False
            ).encode()
        ).hexdigest()
        return scope, members, encode

    def observed_tell(self, candidate_id, evaluation):
        result = actual_tell(self, candidate_id, evaluation)
        snapshot = FileSystemCAS(self._store.root).get_verified_snapshot(
            self.checkpoint_ref
        )
        spec = inspect.getclosurevars(self.controller._stage_b).nonlocals["spec"]
        print(  # noqa: T201
            "REMOVAL_PERSISTED_OBSERVATION:"
            + json.dumps(
                {
                    "probe": "remove_run_scope",
                    "checkpoint_ref": self.checkpoint_ref.model_dump(mode="json"),
                    "checkpoint_sha256": hashlib.sha256(snapshot.data).hexdigest(),
                    "fresh_canonical_checkpoint": json.loads(snapshot.data),
                    "physical_calls": spec.benchmark_evaluator.calls,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return result

    NativeSearchService._deduplication_members = configuration_only
    NativeSearchService.tell = observed_tell
