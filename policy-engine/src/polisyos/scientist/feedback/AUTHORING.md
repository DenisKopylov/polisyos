# Feedback Authoring

- Put public service behavior in `core.py`.
- Put private extraction/coercion helpers in `utils.py` only when they support
  feedback behavior directly.
- Keep artifact schema names stable unless a migration plan explicitly changes
  persisted payload compatibility.
- New first-party imports must use `polisyos.scientist.feedback.*`, never
  `polisyos.scientist.feedback.utils`.
- Add focused tests under `tests/unit/scientist/feedback` for new behavior and
  shim tests under `tests/unit/scientist/evidence` only when the compatibility
  surface changes.
