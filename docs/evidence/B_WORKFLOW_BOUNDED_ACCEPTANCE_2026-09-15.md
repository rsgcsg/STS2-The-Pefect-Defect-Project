# B workflow bounded engineering acceptance — 2026-09-15

## Decision and scope

The owner explicitly authorized engineering integration without another uninterrupted
native-start-to-terminal Human run. This removes that additional release condition; it does
not turn an unobserved lifecycle into PASS. This release is the developer collection/account/
delivery workflow, not exhaustive Full-Run, training admission or model qualification.
Historical failed evidence is unchanged. No known new correctness failure is deferred by this
acceptance: the prior event handoff defect was repaired and exercised in the new recording.

## Exact observed candidate

- Platform source: `3da01ecbd3b4da3c2651868f7de1ce6cad54510f`.
- STPD source: `675309814691e5331dd8f4ba7874c2e8107d9fd6`.
- STPD lock SHA256: `7f760f8be6f7f9f7ac150f5d02f81f9b0190775753cc3215f14630153eec3dca`.
- Mod SHA256: `1a8072e02d2c0721bab9f33794302c49181853befdb931881407217af780a001`.
- Mod MVID: `0d5931ad-a7bb-405c-a7d0-200ed18b7443`.
- Fixed tool: `80d37fd70f7eb51353870bdbc6032c85084e1e5f7384a56c41341b7058d68481`.
- Hub OCI: `ghcr.io/rsgcsg/stpd-worker@sha256:18c5d8bbbf0388d4551e6b780db3852497f3ab02e72b6e4bd6d8d08402f8ca1d`.
- Source CI: Platform `34907450004`; STPD `34908083343`; all required lanes passed.

These identify the actually tested source/artifacts, not a future merge commit. Normal merge
preserves source ancestry; merged-head CI must still pass. Documentation-only acceptance does
not relabel the deployed image. Keep the exact previous install/image/config for rollback;
never reset or discard recording queues to roll back software.

## Human recording and delivery

The new recording observed an existing run through natural defeat: 546 accepted decisions,
545 proved/canonical, one explicit native cancellation, zero real failures and zero unresolved.
All 119 nested canonical children have canonical parents and matching causal roots. All eight
event Proceed handoffs used `NEventRoom.Proceed->NMapScreen.Open.return` and proved before the
next Human acceptance (0.925087–10.801410 seconds earlier).

The 77 invalidations were diagnostics: 47 ReadyToBeginEnemyTurnAction and 30
MoveToMapCoordAction. Compatibility audit: 161 valid / zero invalid. Native semantic diagnostic:
333 accepted, 332 successful, one cancelled, zero unknown. Those are distinct populations.
All 1,792 original session files were byte-identical before and after audit.

Automatic packaging and upload reached verified Hub receipt, authenticated member collection
read succeeded, and current-root preparation remained bound after Close. The detailed audit
and receipt are retained privately; no raw Human data or personal identifiers are published.
This audit did not independently download the new archive from R2; the preceding recording's
independent R2/member-download verification retains its own scope.

## Non-claims and maintenance

Native starts/ends were 0/1, with an explicit observed-in-progress witness. This is not a
continuous native-start-to-terminal Full Run. The literal immediate Event Proceed → Close
recipe was not repeated. Full-Run completeness, research dataset admission, exhaustive
surface/rapid-input coverage, model quality and GPU execution are not release claims.

Keep canonical decisions, failures, cancellation and diagnostics distinguishable. A failed
decision does not justify deleting the entire source; neither does a successful upload admit
that source for training. Inspect collection quality and detailed owner reasons separately
from delivery incidents. Preserve evidence, fix the owning cause with a regression, issue new
artifacts and run the affected bounded canary. Do not fabricate successors or rewrite failures.
