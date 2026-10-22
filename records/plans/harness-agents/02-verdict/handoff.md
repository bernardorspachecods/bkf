## Verification

- `python3 -m unittest discover -s tests` — passed (37 tests).
- `bkf skills` — passed; catalog valid, 0 issues.
- Failure demonstration: in a throwaway copy, I removed the nested-heading section break. `test_nested_heading_ends_checked_section` failed because it counted text after `### Nested`.

## Left ready

The `verdict read|checked` CLI and `read_verdict` / `checked_ok` functions are ready. Missing checked files return exit 1; the parity test compares success versus failure for that case.

## Outside focus

No known differences from the brief.