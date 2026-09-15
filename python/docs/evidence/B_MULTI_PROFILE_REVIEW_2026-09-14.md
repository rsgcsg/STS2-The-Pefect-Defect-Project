# Same-computer member review

## Actual account gate

The operator completed a new invited member's first connection, logout and reconnection
using a separate Workbench configuration on the same Mac. Production readback at STPD
`a5593758e368d9f1a6374b536774f798ed3df96f` confirmed schema 4, two active account identities
and two device registrations. The new member retains role `member`, enrollment permission
and device quota 3. Reconnection reused its original device/token and did not transfer ownership.

The audit contains the ordered `identity_connection_approved`, `personal_session_logged_out`,
`identity_connection_approved` events and the new current personal session. The original two
verified uploads, content IDs and receipt hashes were unchanged. Jobs remained zero and
compute budget remained zero. The private redacted readback receipt has SHA-256
`705de04f93f572a4bb35f19056796f0ae8db687d70ec809878e05b54df1cec01`.
It contains no bearer credentials; raw account records are not committed.

## Owning defects and changes

- Browsers scope cookies by host/path, not port. Two loopback Workbenches used the same
  cookie name; opening the second caused the first to return `browser_session_required`.
  Cookie names now derive from the resolved private state directory, while their secret
  values rotate per running instance. Host/Origin/CSRF checks remain in force. A real pair
  of local HTTP servers and one cookie jar cover coexistence, rejected cross-context
  mutations, restart rotation and rejection of the old unscoped cookie.
- An old Runtime client could send Stop to a new process reusing its port, then notice the
  wrong run ID only after the effect. Platform Runtime HTTP/2 checks an explicit expected
  process run ID before mutation, and `/v2/*` prevents old HTTP/1 servers from silently
  ignoring the new precondition. STPD binds every command to its captured startup identity.
  This ID identifies a Policy Runtime process, not a native STS2 run.
- A recovered client has no local Popen handle. Unknown Stop used to be persisted as stopped,
  and a failed recovery observation could discard the recovery gate on the next restart.
  Confirmation now requires an exact stopped response or observed exit of the owned process;
  uncertainty and the startup identity survive failed recovery and repeated restarts.

The cross-repository candidate is Platform
`c6e5151e62a5daabfe3863591a8fe2297f92ece1`, Runtime `0.1.0-rc.3`, source
`cdcb324b2115cb25dc9fb253a7e8f36b5c5307e9`. The reviewed archive SHA-256 is
`48bf27ad931667a6c0bcb34dffc15a80de536c72e8ca4d3fde6fa973fdafa651`.
The STPD registry binds the archive, installed content and dependency closure. Resolve the
current PR head and its actual local/hosted/installed receipts before release promotion.

## Operational meaning and next gate

A device is one durable Workbench registration, not a physical hardware fingerprint.
Two independent configurations on one Mac may belong to different accounts. A registration
has one owner; logout does not transfer it or its data. Keep account/device files private,
never copy credentials between profiles, and bind only one campaign to the active native
recording root. For different people sharing hardware, separate OS users provide file isolation;
two project logins within one OS user are not a security sandbox.

The new member has no collection activity yet. Publish an exact compatible template, then
the Human declares origin, upload permission and project sharing for that new activity.
Preparation must read that real enrollment before binding the native recorder. The next
bounded session verifies Close, local outbox, Hub receipt and R2 bytes. This account test
does not authorize consent on the member's behalf, qualify new native bytes, admit a Dataset,
run a GPU or establish model quality. Preserve predecessor evidence and rollback pairs.
