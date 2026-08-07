# Deferred Items — Phase 02-discovery

Items discovered during execution that are OUT OF SCOPE for the current plan
(not caused by this plan's changes). Left untouched per the scope boundary.

| Date | Item | Details |
| ---- | ---- | ------- |
| 2026-08-05 | `tests/test_database.py` not black-formatted | Unchanged since T02 commit `1513257` (feat(02): discovery schema); `black --check` reports "would reformat" while all T03/T04/T05-touched files are clean. Fix opportunistically in a later plan touching that file. |
