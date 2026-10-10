# Generator scratch path and retention boundary

Exact slice base: `4699fdf8419dd2c89609f68a3edf5f3bfb7c851a`. Candidate remains the attached `codex/e02-unified-local-20261009` WIP until root commits the source boundary. This note is an author receipt, not G acceptance.

P40: NEW_CLASS path resolution. With a relative TMPDIR from the repository root, the original script returned exit 0 but its reported scratch directory did not contain either generated raw client. The generator wrote them under a second relative path after changing to policy-engine. This is the divergent case: successful exit did not prove the retained bytes existed at the reported location. Both raw outputs are preserved in the ignored evidence area; `LOCAL/raw/client-relative-tmpdir/preserved-relocation.json` records the original wrong location, current paths and matching hashes.

The script resolves the created scratch directory to an absolute path before changing directory. Opt-in `POLISYOS_RETAIN_GENERATOR_SCRATCH=1` retains local generator outputs for inspection; default cleanup behavior remains unchanged. No schema, client behavior, or API export changes are introduced by this script repair.

The same real generation command with the same relative TMPDIR then returned exit 0: the reported absolute directory contained both raw clients, and all three canonical generated outputs exactly matched the current tracked output family. Full command, stdout, stderr and red/green property readbacks are under `LOCAL/raw/client-relative-tmpdir/`. This is an actual generation and byte comparison, not a marker assertion. Independent source review is in `LOCAL/reviews/lifecycle-selected-intake-independent.md`.

Exact source and output hashes:

```json
{
  "packages/runtime-api-client/scripts/generate-runtime-api-client.sh": "3bd20e2c421ec6e703ce0b48c5a0a9ca5ced8e73a9464e33e1706136fbc5cc53",
  "packages/runtime-api-client/README.md": "bd10d2bc06e9665fed5ec386a2fe46d1fd53bf21c1b7fc969bb62f596e2c5108",
  "raw/client-relative-tmpdir/green.stderr": "652a6e9a61e4c3c81141d74183779afe5869e2ac121cf7bad88c4e0fef213206",
  "raw/client-relative-tmpdir/green-property-readback.json": "22f504791df2478ebd031de2b853a46da87ecd94189a0af18d7ee7662d604323",
  "raw/client-relative-tmpdir/red-property-readback.json": "31a85e3c58ee2be8024d7d03c656ee4fbd899e97c0be50b69a1adafc748abf18",
  "raw/client-relative-tmpdir/green-command.json": "2be8372d6d743a1fb33d72ab5592e7234a382b683be43fd4d49ce602d81d6993",
  "raw/client-relative-tmpdir/green.stdout": "88332a542a3ff7972a673d2ed8e6b982d9679fe0896228ce4b7efda41a7347e2",
  "raw/client-relative-tmpdir/red.stderr": "2fe1f0a06038c056b01a6711c018d1cd33e9f2f98978d9669f7c20c1879d6de7",
  "raw/client-relative-tmpdir/red.stdout": "726ae46788295d69d02324b5ca406579fe24c056f5597ad53c97d057ba859d5f",
  "raw/client-relative-tmpdir/red-command.json": "2be8372d6d743a1fb33d72ab5592e7234a382b683be43fd4d49ce602d81d6993"
}
```
