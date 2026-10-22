## Verification

- Harness tests: 43 passed.
- Injection, plan and review gate, and council, research, and review board checks passed.
- Deletion and grep checks passed.
- `bkf skills` failed: restoring `SKILL.md` leaves a reference to the deleted `lib-inject.sh` and leaves six harness files unlinked.
- The throwaway failure demonstration remains unchecked, as the brief directs.

## Left ready

`SKILL.md` is restored to its prior text. The only test edit is restoring the comment’s `lib-inject.sh` reference.

## Caveat

The scope correction conflicts with the `bkf skills` gate. Fixing that failure requires changing `SKILL.md`, which the review flagged as out of scope.