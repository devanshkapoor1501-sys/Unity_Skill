# Cleanup initial independent review

Scope: in-progress backend after initial22testGREEN, before repairs. Reviewer
was a separate actual native Codex code-reviewer. No user data cleaned.

Confirmed issues: cross-run registered evidence could be selected; UnityProject/
Library subtrees inside private tmp were not excluded; errors on lock exit could
lose already-deleted paths; malformed list-valued process reason/ownership could
escape as TypeError. Existing hardlinked lockfiles lacked a single-link guard;
initial runtime hardlink probe was sandbox-blocked. Findings were sent to the
backend owner for behavior-level RED/GREEN regressions. Final review must verify
the corrected source; this initial record is not a current-source failure claim.
