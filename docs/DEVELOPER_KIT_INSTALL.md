# Initial installation of a developer kit

This is an operator-assisted macOS installation using the existing Platform lifecycle.
The kit is not a standalone installer. The operator retains a clean, exact Platform checkout;
the member uses STPD and the fixed tool for everyday recording. Do not build native source
as part of installing a published binary kit. Windows/Linux portable CI is not proof that
this native installation procedure works there. Consult the release's supported game/OS tuple.

## Verify and stage the approved bytes

1. Verify the ZIP SHA256 against its independently approved release receipt before extraction.
   Read `combination.json`, the release's exact refs, game identity, qualification and rollback.
   Obtain clean STPD and Platform checkouts at those refs, in durable directories.
2. Install Git, Python 3.11/uv, Node 20+ and the fixed tool's declared .NET runtime.
   The member owns a local game installation; game files are never distributed in the kit.
3. Fully close the game and stop the existing workbench. Preserve its configuration, complete
   old tool, raw recordings and outbox. This installation does not migrate a queue.
4. In the clean Platform checkout run `npm ci`. Compare the tracked
   `apps/game-mod/mod_manifest.json` to the kit's `mod/STS2_PLATFORM.json`; stop on differences.
   Stage only these ignored outputs, creating their parent directories if necessary:

| Kit file | Destination within the retained Platform checkout |
|---|---|
| `mod/STS2_PLATFORM.dll` | `apps/game-mod/bin/Release/net9.0/STS2_PLATFORM.dll` |
| `collection-tool/game-mod/build-provenance.json` | `apps/game-mod/bin/Release/net9.0/build-provenance.json` |
| `collection-tool/sts2-human-annotator.dll` | `components/annotator/src/STS2HumanAnnotator.Tool/bin/Release/net9.0/sts2-human-annotator.dll` |
| `collection-tool/sts2-human-annotator.deps.json` | same destination directory, same name |
| `collection-tool/sts2-human-annotator.runtimeconfig.json` | same destination directory, same name |
| `collection-tool/STS2HumanAnnotator.Core.dll` | same destination directory, same name |

Require `git status --porcelain` to remain empty. Set `STS2_GAME_DIR` to the actual Steam game
directory containing `SlayTheSpire2.app`, not the app itself. Do not set recording-root or
status-path overrides. Use the packaged tool's `identity` command to verify the Mod and the
installed game's `sts2.dll` SHA256/MVID against build provenance. Check the game release and
the pinned GodotSharp/Harmony bytes too. A version label alone is not the qualification tuple.
The owner lifecycle validates source/artifact provenance; this independent game-byte comparison
is also required. A mismatch requires compatibility qualification, not a forced install.

## Deploy and cold-load through the existing owner

From that exact Platform checkout, run these commands separately and retain their receipts:

```bash
npm run game-mod:doctor
npm run game-mod:deploy
npm run game-mod:doctor
npm run game-mod:launch
npm run game-mod:verify-loaded
```

The first doctor must show the intended directory and no running game. Deploy backs up
managed files/configuration and verifies installed identity. Launch selects no gameplay.
Verify-loaded must confirm the exact current process, loaded Modset, components and execution
admission. Do not run a build command here: it would replace the supplied release artifact.

On first macOS installation, a Human may need to enable Mods and exactly `STS2_PLATFORM` in
the native game interface, then fully close and repeat launch/verify-loaded. The lifecycle
does not edit macOS Mod-enable settings. Do not invent a settings file or remove unrelated Mods.
Initial Recorder status storage may point inside the retained Platform checkout; do not delete
or relocate that checkout after installation. Later STPD binding preserves this status path.

## Continue collection and retain recovery

Follow [the everyday workflow](B_PIPELINE_HANDOFF.md): register the whole fixed tool while the
workbench is stopped, reopen the same private profile, confirm daily consent, prepare, bind
with the game closed, cold-load, check the current root and explicitly activate uploads.
The member's first real Close-to-receipt check is separate from installation evidence.

For rollback, stop delivery and close the game. From the same retained Platform checkout and
game directory run `npm run game-mod:rollback`. It uses the recorded installed provenance and
backup; it does not accept an arbitrary backup path. Preserve old/new receipts. Cold-load the
restored compatible pair with its owning checkout and verify it. A first install may roll back
to no Platform installation. Native macOS Mod-enable choices are outside the file rollback.

Do not rewrite old queues, historical failures, consent or loaded identities to force an
upgrade. Use the [maintenance procedure](B_PIPELINE_HANDOFF.md#daily-work-upgrades-and-incidents).
