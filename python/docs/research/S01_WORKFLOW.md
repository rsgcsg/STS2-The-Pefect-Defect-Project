# S01 operator workflow

S01 is the first engineering cycle: a pinned frozen Qwen plus a Linear ranking head.
The public entry point is `uv run --locked python -m spireagent.research_cli` from `python/`.
Use the locked ML/L2 extras. Mutating preparation/training commands require clean exact source.
This interface reuses the existing ArtifactStore and Worker. It does not start cloud compute.

## Prepare once, reuse exact IDs

1. Choose an explicit `purpose=training` dataset through DatasetCuration. The source evidence,
   quality snapshot, Gold reservations and dataset ID remain authoritative. A historical
   dataset with no explicit purpose must first be published as a new curated version.
2. Run `prepare --dataset ID --operations /existing/operations.sqlite --train-limit 50
   --dev-limit 16 --isolation run`, with global `--store LOCATION`. This is an owner operation
   beside the authoritative Hub database, not a newly created or copied operations database.
   It checks current held-out restrictions and records training use before publishing inputs.
   Use `--profile lite|standard|full` to freeze the existing serializer profile; the default
   is standard. This changes the selected information, so it is recorded in the model identity
   and is not an equivalent runtime optimization. All inputs are length-checked before encoding.
3. Keep the returned allocation and model-view IDs. Run isolation groups known duplicates
   across runs; decision isolation is an explicit engineering diagnostic that may share runs.
   This allocation is train/dev, not a final test or Gold evaluation. The fixed member payload
   records occurrence, source archive digest, transition, run and role. Changed rules create
   another protocol ID. Old artifacts do not change after a later quality annotation.
4. Transfer the verified artifact closure to the chosen execution store using the existing
   `copy_artifact` owner operation. Register managed training use before remote/local transfer.
   A downloaded export alone is not a current Gold/use authorization. Never create an empty
   local use ledger to make a previously downloaded dataset appear eligible.

## Encode, train, resume, evaluate

`encode --view ID --snapshot /pinned/qwen/snapshot --backend mps` creates one immutable
feature set; `cpu` is the other explicit portable choice. Both are FP32 engineering identities,
not the old CUDA scientific qualification. Inputs are never silently truncated. Exact token
lengths/candidate count must be profiled before extrapolating large-run cost.

`train --features ID --steps 100 --stop-after 10` publishes a durable checkpoint and exits.
Rerun in a new process with the same arguments except `--resume CHECKPOINT_ID` and no
`--stop-after`. Data, source, lock and configuration must match. An already completed run
returns its verified existing result. `--replicate` gives an intentional separate run identity;
it is not an implicit retry policy.

The existing Worker publishes the model, dev ranking metrics, uniform-legal and action-only
baselines. Evaluation reports retain exact denominator, sample/run weighting and slices.
This single small run proves engineering connectivity, not model quality. Test and Gold are
not used to choose parameters or debug S01. Keep engineering sample counts and the later
10k pilot protocol distinct.

Within one CLI command, the first model-view load performs full semantic reprojection.
Later preparation/worker/evaluation calls reuse that immutable typed view, after re-reading
and hashing its complete artifact closure. This bounded process-local session retains one
view, never a permission or Gold decision, and ends with the command. Corrupt or missing
source bytes still fail on a hit. The output reports semantic loads and checked reuses;
cross-process resumes revalidate from scratch. This avoids repeating expensive decoding at
every internal layer without creating another persistent data database.

## Export and score without training data

`export --model ID --destination /private/s01-model` writes only `model.json` and
`head.safetensors`. The former binds graph, pooling, model manifest, Qwen/tokenizer,
serializer and runtime identity; no raw source payload is copied into this directory.
It refuses to overwrite an existing model directory.

`score --model-directory /private/s01-model --snapshot /pinned/qwen/snapshot --backend mps
--input /private/input.json` needs no artifact store or training dataset. Input is exactly
`{"state": SemanticState, "actions": [SemanticAction, ...]}` as defined by the existing typed
research contract. Labels, successors and training rows are not part of this inference API.
It returns all finite candidate scores keyed by the caller's unique action keys; it does not
execute a game action or establish legality. Measure fresh encoding, not just cached-head time.

## Trace, archive, and UI

`inspect --artifact ID` returns the immutable parents and parameters. Follow model → run /
training input → feature set → model view → allocation → dataset → original source. Member
occurrence and transition IDs locate the exact row; the source archive digest locates its
original bytes. The Hub's exact source–decision index supports the existing quality page.
Legacy indexes are migrated by the background profiling worker; pending is not an empty set.

`ConsoleIndex.artifact` projects published objects for the existing console. The research
page lists fixed protocols, inputs, features, runs, checkpoints and reports, and supports
personal archive/restore through `ArtifactVisibility`. Archived data remains addressable;
re-indexing does not unarchive it, and other members keep their own lists. A run needs an
indexed completed result before archival; hiding never cancels a task. Existing dataset and
preview archival stays in DecisionJobs. Raw-package retention/deletion is still a separate
owner policy. No archive action removes lineage, historical evidence or Gold/use records.

Only deploy the changed Hub/Workbench UI through the owning rollout procedure. A successful
CLI run does not claim that production is already running this source. First-stage receipts
record actual tested source, dataset, model, target device, elapsed time, memory and failures.
