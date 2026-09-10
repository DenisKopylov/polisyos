# Foundry validation

This package owns validation of Foundry inputs and candidate outputs. Existing
numeric constraints remain in `constraints_engine.py`; legal subject recognition
belongs to `legal_correspondence.py` and is exposed through the lazy Foundry facade.

Legal recognition compares entity membership in a versioned subject namespace,
including content identity and effective interval. Independent annotation inputs
are persisted separately, bound to current entity content and joined into a CAS
spine before proposals are evaluated. The producer does not select subjects from
the proposed relation. The runtime intervention owner supplies current L6/L3
projections and consumes recognition before numerical or unit evaluation.

| Plane | Current result |
| --- | --- |
| Source-relative recognition | `passed`, `rejected`, or `ambiguous`; the comparator recomputes the addressed relation. |
| Current entity projection | Caller-supplied to Foundry; the runtime bridge derives it from the current L6/L3 owners. |
| Legal authority | `not_established`; every result remains `blocked` for governed use. |

`synthetic` is explicit and typed, and true ancestry cannot be erased by a false
child marker. The entire resolved JSON ancestry is inspected, including nested
records, and source separation compares both artifact and producer identity sets.
Those checks establish separation of the declared inputs, not external authority.
Real-data source records are readable without changing the grammar.
Their `source_authority_ref` is a typed integration slot, not an implemented legal
authority verifier. Changing a marker or supplying an unresolved authority ref
does not grant authority. Synthetic annotation meanings are constructed controls,
not claims about actual statutory meaning; the missing real source is `CORR-B1`.

The source/result contracts, persistence functions and comparison share this owner.
The result retains its submitted source descriptor separately from its resolved
reference. Persistence reruns the recognizer against that input and request,
and refuses any result that differs, including caller-edited comparison passes.
Consumers must use `current_authority_status` for authority, never recognition's
`status`. The current API is a candidate recognition interface; it is not a court,
identity authority, legal ontology, or independent semantic verifier.
