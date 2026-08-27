# Scientist Publishing

`polisyos.scientist.publishing` is the canonical hub for decision-grade export
and publication helpers. The decision-grade compiler implementation lives in
`polisyos.scientist.publishing.publisher`; older publisher module paths are
compatibility shims.

Decision-grade publication accepts a content-bound Claim owner key and resolves
the current Claim Ledger head through the container-owned port. Production
callers cannot inject ledger bytes, a ledger ref, an artifact store, a shaped
head, or pending markers. Public output fails closed for stale, absent,
unverified, or bridge-pending heads; reviewer and machine projections preserve
the complete lifecycle history and its limitations.

`polisyos.scientist.publisher` has been retired; canonical publishing imports
sunset on 2026-12-31.
