using System.Text.Json;
using System.Text.Json.Nodes;
using STS2HumanAnnotator.Core;
using Xunit;

namespace STS2HumanAnnotator.Core.Tests;

public sealed class CurrentEvidenceTests
{
    [Fact]
    public void ExplicitContinuousEmptySessionIsValidButMissingPromisedProjectionIsNot()
    {
        string root = Temp("empty-continuous");
        try
        {
            var profile = Profile();
            var manifest = Manifest(profile) with { ContinuousSchemaVersion = 1, DispositionSchemaVersion = 1 };
            string session;
            using (var store = RecordingSessionStore.Create(root, manifest, profile))
            { session = store.DirectoryPath; AppendJournal(store, manifest); }
            var audit = RecordingSessionAuditor.Audit(session);
            Assert.True(audit.Status == "pass", JsonSerializer.Serialize(audit.Errors));
            File.AppendAllText(Path.Combine(session, "run-journal.jsonl"), JsonSerializer.Serialize(new RunJournalEvent(
                2, CurrentRecordingContract.RunJournalSchema, "promised", manifest.SessionId, "run-0001",
                manifest.TimelineId, 3, DateTimeOffset.UnixEpoch, "canonical_transition_recorded", "missing", null, null),
                EvidenceJson.Options) + "\n");
            Assert.Equal("fail", RecordingSessionAuditor.Audit(session).Status);
        }
        finally { Delete(root); }
    }

    [Fact]
    public void InterruptedRecoveryPreservesOriginalBytesAndAddsOnlyUnknownClosure()
    {
        string root = Temp("interrupted-source"), recovered = Temp("interrupted-copy");
        try
        {
            var profile = Profile();
            var manifest = Manifest(profile) with { CloseSchemaVersion = 1, RecoverySchemaVersion = 1,
                DispositionSchemaVersion = 1 };
            string session;
            using (var store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                var frame = CurrentRecord(RecordValidationTests.ValidRecord(),
                    (PersistReads(store, "snapshot-a"), PersistReads(store, "snapshot-b"))).Pre;
                var action = new SemanticActionReference("pending-action", 1, "record-ref", "run-0001",
                    "PlayCardAction", 1, frame.SnapshotId);
                store.AppendSemanticEvidenceEvents(new[] {
                    SemanticEvidenceEvent(manifest, 1, SemanticBoundaryTraceKinds.ActionAccepted, action)
                        with { HumanObservationRef = store.PersistSemanticFrame(frame) }
                });
                var busy = JsonSerializer.SerializeToElement(InterruptedRecordingRecovery.RecoverOne(root, recovered));
                Assert.Equal("idle", busy.GetProperty("status").GetString());
                Assert.Equal(1, busy.GetProperty("busy").GetInt32());
            }
            // Model process loss after durable stream writes but before the final seal.
            File.Delete(Path.Combine(session, "session-close-receipt.json"));
            var original = Directory.GetFiles(session, "*", SearchOption.AllDirectories)
                .ToDictionary(p => p, EvidenceIdentity.Sha256File);
            var result = JsonSerializer.SerializeToElement(InterruptedRecordingRecovery.RecoverOne(root, recovered));
            Assert.Equal("recovered", result.GetProperty("status").GetString());
            foreach (var (path, hash) in original) Assert.Equal(hash, EvidenceIdentity.Sha256File(path));
            string copy = Assert.Single(Directory.GetDirectories(recovered));
            var audit = RecordingSessionAuditor.Audit(copy);
            Assert.True(audit.Status == "pass", JsonSerializer.Serialize(audit.Errors));
            var trace = File.ReadAllLines(Path.Combine(copy, "semantic-boundary-trace.jsonl"))
                .Select(line => JsonSerializer.Deserialize<SemanticEvidenceEvent>(line, EvidenceJson.Options)!).ToArray();
            Assert.Equal(2, trace.Length);
            Assert.Equal("transition_unknown", trace[1].Kind);
            Assert.Null(trace[1].SuccessorRef);
            var again = JsonSerializer.SerializeToElement(InterruptedRecordingRecovery.RecoverOne(root, recovered));
            Assert.Equal("idle", again.GetProperty("status").GetString());
            File.AppendAllText(Path.Combine(copy, "capture-profile.json"), " ");
            Assert.Contains("recording_recovery_invalid", RecordingSessionAuditor.Audit(copy).Errors.Keys);
        }
        finally { Delete(root); Delete(recovered); }
    }

    [Fact]
    public void InterruptedRecoveryRetainsTornStreamAsIncident()
    {
        string root = Temp("torn-source"), recovered = Temp("torn-copy");
        try
        {
            var profile = Profile();
            var manifest = Manifest(profile) with { CloseSchemaVersion = 1, RecoverySchemaVersion = 1 };
            string session;
            using (var store = RecordingSessionStore.Create(root, manifest, profile))
            { session = store.DirectoryPath; AppendJournal(store, manifest); }
            File.Delete(Path.Combine(session, "session-close-receipt.json"));
            string trace = Path.Combine(session, "semantic-boundary-trace.jsonl");
            File.AppendAllText(trace, "{\"schema\":");
            string before = EvidenceIdentity.Sha256File(trace);
            var result = JsonSerializer.SerializeToElement(InterruptedRecordingRecovery.RecoverOne(root, recovered));
            Assert.Equal("incident", result.GetProperty("status").GetString());
            Assert.Equal(before, EvidenceIdentity.Sha256File(trace));
            Assert.Empty(Directory.GetDirectories(recovered, "recovered-*"));
        }
        finally { Delete(root); Delete(recovered); }
    }

    [Fact]
    public void CloseWriteFailureLeavesAccountingUnavailableWithoutACompletedReceipt()
    {
        string root = Temp("close-receipt-failure");
        RecordingSessionStore? store = null;
        string? obstruction = null;
        try
        {
            var profile = Profile();
            var manifest = Manifest(profile) with { CloseSchemaVersion = 1 };
            store = RecordingSessionStore.Create(root, manifest, profile);
            obstruction = Path.Combine(store.DirectoryPath, "performance-profile.json");
            Directory.CreateDirectory(obstruction); // actual I/O failure before terminal receipt
            Exception? closeError = Record.Exception(() => store.Dispose());
            // Windows reports a directory collision as access denied; POSIX
            // reports an I/O error. Both must preserve the same failed close.
            Assert.True(closeError is IOException or UnauthorizedAccessException,
                closeError?.ToString() ?? "Expected the real filesystem obstruction to fail close.");
            var status = store.GetSnapshot();
            Assert.False(status.Closed);
            Assert.Equal("failed", status.AppendHealth);
            Assert.Null(status.Counters.Decisions!.RealFailures);
            Assert.False(File.Exists(Path.Combine(store.DirectoryPath, "session-close-receipt.json")));
        }
        finally
        {
            if (obstruction != null && Directory.Exists(obstruction)) Directory.Delete(obstruction);
            store?.Dispose(); // explicit test cleanup after removing the fault; never a native retry
            Delete(root);
        }
    }

    [Fact]
    public void DurableDispositionCountersExcludeCancellationAndDiagnosticsAndDeduplicateExactFailure()
    {
        string root = Temp("disposition-counters");
        try
        {
            var profile = Profile();
            var manifest = Manifest(profile);
            using var store = RecordingSessionStore.Create(root, manifest, profile);
            var action = new SemanticActionReference("action-ref", 1, "record-ref", "run-0001", "PlayCardAction", 1, "snapshot-a");
            store.AppendSemanticEvidenceEvents(new[] {
                SemanticEvidenceEvent(manifest, 1, SemanticBoundaryTraceKinds.ActionAccepted, action),
                SemanticEvidenceEvent(manifest, 2, SemanticBoundaryTraceKinds.ActionCancelledBeforeStart, action),
                SemanticEvidenceEvent(manifest, 3, SemanticBoundaryTraceKinds.ActionAccepted, action with { ActionWitnessId = "unknown-action" }),
                SemanticEvidenceEvent(manifest, 4, SemanticBoundaryTraceKinds.TransitionUnknown, action with { ActionWitnessId = "unknown-action" })
            });
            var diagnostic = new InvalidationRecord(CurrentRecordingContract.SchemaVersion, CurrentRecordingContract.InvalidationSchema,
                "diagnostic", manifest.SessionId, "run-0001", DateTimeOffset.UnixEpoch, "human_action_native_type_mismatch", "internal",
                null, "MoveToMapCoordAction", "failed_closed") { Disposition = "diagnostic" };
            store.AppendInvalidation(diagnostic);
            var occurrence = new HumanActionOccurrenceEvidence("missing-choice", "SelectCard", "nested_selector.decision", "select",
                "card", new Dictionary<string, string>(), "owner", null, null, null, "SelectCard", "failed_closed");
            var failure = diagnostic with { InvalidationId = "missing", Disposition = "failed_closed", HumanOccurrence = occurrence,
                DecisionFailure = new("missing-choice", "capture", "nested_selector.decision") };
            store.AppendInvalidation(failure);
            store.AppendInvalidation(failure with { InvalidationId = "same-exact-occurrence" });
            store.AppendInvalidation(diagnostic with { InvalidationId = "unknown-projection", Disposition = "failed_closed",
                DecisionFailure = new("unknown-action", "persistence", "ordinary_combat.play_card") });
            var counts = store.GetSnapshot().Counters.Decisions!;
            Assert.Equal(1, counts.Cancelled);
            Assert.Equal(1, counts.Unresolved);
            Assert.Equal(0, counts.Pending);
            Assert.Equal(1, counts.CaptureFailures);
            Assert.Equal(2, counts.RealFailures);
            Assert.Equal(1, store.GetSnapshot().FailedActionFamilies!["nested_selector.decision"]);
            Assert.Throws<InvalidDataException>(() => store.AppendInvalidation(failure with { Disposition = "diagnostic" }));
            Assert.Equal(2, store.GetSnapshot().Counters.Decisions!.RealFailures);
            Assert.Throws<InvalidDataException>(() => store.AppendInvalidation(diagnostic with { Disposition = "invented" }));
            Assert.Throws<InvalidDataException>(() => store.AppendInvalidation(diagnostic with { Disposition = "failed_closed" }));
            store.MarkDecisionAccountingUnavailable();
            Assert.Null(store.GetSnapshot().Counters.Decisions!.RealFailures);
        }
        finally { Delete(root); }
    }

    [Fact]
    public void FullRunCoverageMapIsCompleteAndClosesExactNestedLineage()
    {
        IReadOnlyList<FullRunCoverageEntry> entries = FullRunCoverageContract.Entries;

        Assert.Empty(FullRunCoverageContract.Validate());
        Assert.Equal(
            entries.Count,
            entries.Select(entry => entry.Family).Distinct(StringComparer.Ordinal).Count());

        HumanCaptureProfile profile = HumanCaptureProfiles.FullRunReadRich;
        foreach (string family in profile.SupportedActionFamilies)
        {
            FullRunCoverageEntry entry = Assert.Single(
                entries,
                value => string.Equals(value.Family, family, StringComparison.Ordinal));
            Assert.Equal(FullRunCoverageClassifications.InScopeImplemented, entry.Classification);
        }

        Assert.Equal(
            FullRunCoverageClassifications.InScopeImplemented,
            Assert.Single(entries, value => value.Family == "boss_relic.select").Classification);
        Assert.Equal(
            FullRunCoverageClassifications.InScopeImplemented,
            Assert.Single(entries, value => value.Family == "boss_relic.skip").Classification);
        Assert.Contains(entries, value =>
            value.Family == "act_change.ready"
            && value.AcceptedSeam.Contains("SetLocalPlayerReady", StringComparison.Ordinal)
            && value.LifecycleCommit.Contains("ExecuteAction", StringComparison.Ordinal)
            && value.NextAuthoritativeBoundary.Contains("ActEntered", StringComparison.Ordinal));

        foreach (FullRunCoverageEntry entry in entries.Where(value =>
                     value.Family.Contains("nested_selector", StringComparison.Ordinal)))
        {
            Assert.Equal(FullRunCoverageClassifications.InScopeImplemented, entry.Classification);
            Assert.Contains("exact", entry.AcceptedSeam, StringComparison.OrdinalIgnoreCase);
        }
    }

    [Fact]
    public void FullRunCoverageDeclaresEveryMandatoryFamilyAndIsQualificationReady()
    {
        IReadOnlyList<FullRunCoverageEntry> entries = FullRunCoverageContract.Entries;
        HashSet<string> declared = entries
            .Select(entry => entry.Family)
            .ToHashSet(StringComparer.Ordinal);

        Assert.All(
            FullRunCoverageContract.MandatoryFamilies,
            family => Assert.Contains(family, declared));

        FullRunCoverageValidation validation =
            FullRunCoverageContract.ValidateForQualification();
        Assert.True(validation.QualificationReady);
        Assert.Empty(validation.BlockedInScopeFamilies);
        Assert.Empty(validation.Errors);

        string[] implementedFamilies =
        {
            "generic_simple_card_selector",
            "generic_deck_card_selector",
            "generic_combat_pile_selector",
            "generic_card_bundle_selector",
            "shop_inventory.card_removal_nested_selector",
            "event_option.nested_selector",
            "rest_site.nested_selector",
            "reward_card_removal.nested_selector",
            "reward_nested.replacement_selection"
        };
        foreach (string family in implementedFamilies)
        {
            FullRunCoverageEntry entry = Assert.Single(
                entries,
                value => value.Family == family);
            Assert.Equal(FullRunCoverageClassifications.InScopeImplemented, entry.Classification);
        }
        Assert.Equal(
            FullRunCoverageClassifications.NotAPlayerDecisionWithNativeJustification,
            Assert.Single(entries, value => value.Family == "target_picker.cancel").Classification);
    }

    [Fact]
    public void FullRunCoverageValidationRejectsOmittedMandatoryFamily()
    {
        IReadOnlyList<FullRunCoverageEntry> entries = FullRunCoverageContract.Entries
            .Where(entry => entry.Family != "target_picker.cancel")
            .ToArray();

        FullRunCoverageValidation validation =
            FullRunCoverageContract.ValidateForQualification(entries);
        Assert.False(validation.IsValid);
        Assert.False(validation.QualificationReady);
        Assert.Contains("target_picker.cancel", validation.MissingMandatoryFamilies);
        Assert.Contains("mandatory_family_missing:target_picker.cancel", validation.Errors);
    }

    [Fact]
    public void AnyEnumeratedBlockedSurfaceBlocksQualificationEvenWhenNonMandatory()
    {
        FullRunCoverageEntry nonMandatoryBlocked = new(
            "census_only_surface",
            FullRunCoverageClassifications.Blocked,
            "BLOCKED: exact native input census pending",
            "BLOCKED: exact native owner pending",
            "BLOCKED: exact semantic provider pending",
            "BLOCKED: accepted seam pending",
            "BLOCKED: lifecycle seam pending",
            "BLOCKED: next boundary pending",
            "BLOCKED: bounded census has not proven the carrier.");
        FullRunCoverageValidation validation =
            FullRunCoverageContract.ValidateForQualification(
                FullRunCoverageContract.Entries
                    .Concat(new[] { nonMandatoryBlocked })
                    .ToArray());

        Assert.False(validation.QualificationReady);
        Assert.Contains("census_only_surface", validation.BlockedInScopeFamilies);
        Assert.Contains("in_scope_blocked:census_only_surface", validation.Errors);
    }

    [Theory]
    [InlineData("ordinary_combat", "play", "ordinary_combat.play_card")]
    [InlineData("ordinary_combat", "end_turn", "ordinary_combat.end_turn")]
    [InlineData("ordinary_combat", "use", "ordinary_combat.use_potion")]
    [InlineData("native_generated_card_choice", "select", "native_generated_card_choice.select")]
    public void ActionFamilyNormalizationIsSharedByAdmissionAndStatus(
        string decisionFamily,
        string verb,
        string expected)
    {
        Assert.Equal(
            expected,
            HumanCaptureProfileValidator.ResolveActionFamily(decisionFamily, verb));
    }

    [Fact]
    public void FullRunProfileDeclaresRoomFamiliesWithoutChangingReadPolicy()
    {
        HumanCaptureProfile profile = HumanCaptureProfiles.FullRunReadRich;

        Assert.Equal("human-full-run-read-rich-v4", profile.ProfileId);
        Assert.Contains("combat_hand_selector.select", profile.SupportedActionFamilies);
        Assert.Contains("combat_hand_selector.deselect", profile.SupportedActionFamilies);
        Assert.Contains("combat_hand_selector.confirm", profile.SupportedActionFamilies);
        Assert.Contains("event_option.choose", profile.SupportedActionFamilies);
        Assert.Contains("event_option.proceed", profile.SupportedActionFamilies);
        Assert.Contains("shop_room.open", profile.SupportedActionFamilies);
        Assert.Contains("shop_room.proceed", profile.SupportedActionFamilies);
        Assert.Contains("shop_inventory.purchase", profile.SupportedActionFamilies);
        Assert.Contains("shop_inventory.card_removal", profile.SupportedActionFamilies);
        Assert.Contains("shop_inventory.close", profile.SupportedActionFamilies);
        Assert.Contains("rest_site.choose", profile.SupportedActionFamilies);
        Assert.Contains("rest_site.proceed", profile.SupportedActionFamilies);
        Assert.Contains(profile.Reads, read =>
            read.InteractionKind == "shop_inventory" && read.Kind == "shop_catalog");
        Assert.Contains(profile.NonClaims, claim =>
            claim.Contains("non_combat_successor", StringComparison.Ordinal));
    }

    [Fact]
    public void ReadRichDecisionValidatesWithoutChangingV1()
    {
        HistoricalDecisionRecord v1 = RecordValidationTests.ValidRecord();
        CurrentDecisionRecord current = CurrentRecord(v1, Reads(v1));

        Assert.True(HistoricalDecisionRecordValidator.Validate(v1).Valid);
        RecordValidationResult result = CurrentDecisionRecordValidator.Validate(current);
        Assert.True(result.Valid, string.Join(',', result.Errors));

        CurrentDecisionRecord unified = current with
        {
            Environment = current.Environment with { ModsetStatus = "exact_platform_modset" }
        };
        RecordValidationResult unifiedResult = CurrentDecisionRecordValidator.Validate(unified);
        Assert.True(unifiedResult.Valid, string.Join(',', unifiedResult.Errors));
    }

    [Fact]
    public void ReadBindingAndFailureStatusFailClosed()
    {
        CurrentDecisionRecord record = CurrentRecord(
            RecordValidationTests.ValidRecord(),
            Reads(RecordValidationTests.ValidRecord()));
        ReadEvidence drifted = record.Pre.Reads[0] with { SnapshotId = "snapshot-elsewhere" };
        RecordValidationResult binding = CurrentDecisionRecordValidator.Validate(record with
        {
            Pre = record.Pre with { Reads = new[] { drifted, record.Pre.Reads[1] } }
        });
        Assert.Contains("pre_read_binding_mismatch", binding.Errors);

        ReadEvidence ambiguousFailure = record.Pre.Reads[0] with
        {
            Status = "failed",
            ErrorCode = null,
            PayloadRef = null,
            PayloadSha256 = null
        };
        RecordValidationResult failure = CurrentDecisionRecordValidator.Validate(record with
        {
            Pre = record.Pre with { Reads = new[] { ambiguousFailure, record.Pre.Reads[1] } }
        });
        Assert.Contains("pre_read_failure_invalid", failure.Errors);
    }

    [Fact]
    public void CaptureProfileRequiresMaterializedReadsAndAdmittedFamily()
    {
        CurrentDecisionRecord record = CurrentRecord(
            RecordValidationTests.ValidRecord(),
            Reads(RecordValidationTests.ValidRecord()));
        CurrentDecisionRecord missing = record with
        {
            Pre = record.Pre with { Reads = record.Pre.Reads.Take(1).ToArray() }
        };
        RecordValidationResult reads = HumanCaptureProfileValidator.ValidateRecord(Profile(), missing);
        Assert.Contains("pre_required_read_missing_combat_piles", reads.Errors);

        RecordValidationResult family = HumanCaptureProfileValidator.ValidateRecord(
            Profile(),
            record with { DecisionFamily = "unknown_selector" });
        Assert.Contains("record_action_family_outside_profile", family.Errors);
    }

    [Fact]
    public void CurrentStoreDeduplicatesBlobsAndAuditDetectsTampering()
    {
        string root = Temp("current-store");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            string session;
            using (var store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                HistoricalDecisionRecord v1 = RecordValidationTests.ValidRecord();
                IReadOnlyList<ReadEvidence> pre = PersistReads(store, v1.Pre.SnapshotId);
                IReadOnlyList<ReadEvidence> successor = PersistReads(store, v1.Successor.SnapshotId);
                Assert.Equal(pre[0].PayloadSha256, pre[1].PayloadSha256);
                store.AppendDecision(CurrentRecord(v1, (pre, successor)));
            }
            RecordingAuditResult pass = RecordingSessionAuditor.Audit(session);
            Assert.Equal("pass", pass.Status);
            Assert.Equal(1, pass.ValidRecords);
            string blob = Directory.GetFiles(
                Path.Combine(session, "blobs"), "*.json", SearchOption.AllDirectories).Single();
            File.AppendAllText(blob, "tamper");
            RecordingAuditResult fail = RecordingSessionAuditor.Audit(session);
            Assert.Equal("fail", fail.Status);
            Assert.Contains("read_blob_missing_or_changed", fail.Errors);
        }
        finally
        {
            Delete(root);
        }
    }

    [Fact]
    public void CurrentStoreRejectsHistoricalInvalidationSchema()
    {
        string root = Temp("current-invalidation-schema");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            using var store = RecordingSessionStore.Create(root, manifest, profile);

            Assert.Throws<InvalidDataException>(() => store.AppendInvalidation(
                new InvalidationRecord(
                    HistoricalRecordingContract.SchemaVersion,
                    HistoricalRecordingContract.InvalidationSchema,
                    "invalidation-legacy",
                    manifest.SessionId,
                    "run-0001",
                    DateTimeOffset.UnixEpoch,
                    "historical",
                    "archival-only",
                    null,
                    null,
                    "historical")));
        }
        finally
        {
            Delete(root);
        }
    }

    [Fact]
    public void GeneratedChoiceFailedClosedOccurrenceRoundTripsAndIsAudited()
    {
        string root = Temp("generated-choice-occurrence");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            string session;
            using (var store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                HistoricalDecisionRecord source = RecordValidationTests.ValidRecord();
                store.AppendDecision(CurrentRecord(source, (
                    PersistReads(store, source.Pre.SnapshotId),
                    PersistReads(store, source.Successor.SnapshotId))));
                store.AppendInvalidation(new InvalidationRecord(
                    CurrentRecordingContract.SchemaVersion,
                    CurrentRecordingContract.InvalidationSchema,
                    "invalidation-generated-choice",
                    manifest.SessionId,
                    source.RunId,
                    DateTimeOffset.UnixEpoch,
                    "semantic_causal_overlap",
                    "The parent continuation was not available for canonical child proof.",
                    source.Pre.SnapshotId,
                    "NChooseACardSelectionScreen.SelectHolder",
                    "decision_and_lifecycle_only")
                {
                    HumanOccurrence = new HumanActionOccurrenceEvidence(
                        "occurrence-generated-choice",
                        "NChooseACardSelectionScreen.SelectHolder",
                        "generated_card_choice",
                        "select",
                        "card:exact",
                        new Dictionary<string, string>
                        {
                            ["selected_card_holder"] = "card_holder:exact"
                        },
                        "choice_owner:exact",
                        "game_action:parent",
                        "GenericHookGameAction",
                        "gatheringplayerchoice",
                        "NChooseACardSelectionScreen.SelectHolder",
                        "failed_closed")
                });
            }

            InvalidationRecord persisted = JsonSerializer.Deserialize<InvalidationRecord>(
                File.ReadLines(Path.Combine(session, "invalidations.jsonl")).Single(),
                EvidenceJson.Options)!;
            Assert.Equal("card:exact", persisted.HumanOccurrence!.NativeSubjectWitnessId);
            Assert.Equal("game_action:parent", persisted.HumanOccurrence.PausedParentActionWitnessId);
            Assert.Equal("pass", RecordingSessionAuditor.Audit(session).Status);

            string original = File.ReadLines(Path.Combine(session, "invalidations.jsonl")).Single();
            JsonObject missing = JsonNode.Parse(original)!.AsObject();
            missing.Remove("human_occurrence");
            File.WriteAllText(
                Path.Combine(session, "invalidations.jsonl"),
                missing.ToJsonString(EvidenceJson.Options) + "\n");
            RecordingAuditResult audit = RecordingSessionAuditor.Audit(session);
            Assert.Equal("fail", audit.Status);
            Assert.True(audit.Errors.ContainsKey("generated_choice_human_occurrence_missing"));

            JsonObject incomplete = JsonNode.Parse(original)!.AsObject();
            incomplete["human_occurrence"]!["native_subject_witness_id"] = null;
            incomplete["human_occurrence"]!["native_operands"]!["selected_card_holder"] = null;
            File.WriteAllText(
                Path.Combine(session, "invalidations.jsonl"),
                incomplete.ToJsonString(EvidenceJson.Options) + "\n");
            RecordingAuditResult incompleteAudit = RecordingSessionAuditor.Audit(session);
            Assert.Equal("fail", incompleteAudit.Status);
            Assert.True(incompleteAudit.Errors.ContainsKey("generated_choice_subject_missing"));
            Assert.True(incompleteAudit.Errors.ContainsKey("generated_choice_selected_holder_missing"));
        }
        finally
        {
            Delete(root);
        }
    }

    [Fact]
    public void HistoricalNativeLedgerSidecarIsIgnoredByCurrentAuditAndBundle()
    {
        string root = Temp("current-archival-ledger");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            string session;
            using (var store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                HistoricalDecisionRecord source = RecordValidationTests.ValidRecord();
                store.AppendDecision(CurrentRecord(source, (
                    PersistReads(store, source.Pre.SnapshotId),
                    PersistReads(store, source.Successor.SnapshotId))));
            }

            // A historical sidecar is not a current authority and is ignored
            // by current audit and bundle materialization.
            File.WriteAllText(
                Path.Combine(session, "native-action-ledger.jsonl"),
                "not-current-ledger\n");
            RecordingAuditResult pass = RecordingSessionAuditor.Audit(session);
            Assert.Equal("pass", pass.Status);
            string output = Path.Combine(root, "bundle");
            SessionBundlePacker.PackCompatibility(
                session,
                "human-001",
                "human-read-rich-2026-08",
                output,
                new string('c', 40),
                true);
            Assert.False(File.Exists(Path.Combine(
                output,
                "raw",
                "native-action-ledger.jsonl")));
        }
        finally
        {
            Delete(root);
        }
    }

    [Fact]
    public void CurrentAuditDoesNotRequireHistoricalLedgerAccounting()
    {
        string root = Temp("current-semantic-accounting");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            string session;
            using (var store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                HistoricalDecisionRecord v1 = RecordValidationTests.ValidRecord();
                CurrentDecisionRecord current = CurrentRecord(v1, (
                    PersistReads(store, v1.Pre.SnapshotId),
                    PersistReads(store, v1.Successor.SnapshotId)));
                store.AppendDecision(current);

                var directAction = new SemanticActionReference(
                    "direct-action-accounted",
                    2,
                    "direct-record",
                    "run-0001",
                    "NPlayerHand.OnSelectModeConfirmButtonPressed",
                    null,
                    current.Pre.SnapshotId)
                {
                    NativeMechanism = "direct_ui_commit"
                };
                store.AppendSemanticBoundaryEvent(SemanticEvent(
                    manifest,
                    1,
                    SemanticBoundaryTraceKinds.ActionAccepted,
                    directAction,
                    current.Pre));
                store.AppendSemanticBoundaryEvent(SemanticEvent(
                    manifest,
                    2,
                    SemanticBoundaryTraceKinds.ActionCancelledBeforeStart,
                    directAction));
            }

            RecordingAuditResult audit = RecordingSessionAuditor.Audit(session);

            Assert.True(audit.Status == "pass", JsonSerializer.Serialize(audit.Errors));
            Assert.DoesNotContain(
                audit.Errors.Keys,
                key => key.Contains("native_action", StringComparison.Ordinal));
        }
        finally
        {
            Delete(root);
        }
    }

    [Fact]
    public void CurrentAuditAcceptsDiagnosticDiscriminatorWithoutUsingItAsAuthority()
    {
        string root = Temp("current-semantic-discriminator");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            string session;
            using (var store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                HistoricalDecisionRecord v1 = RecordValidationTests.ValidRecord();
        CurrentDecisionRecord current = CurrentRecord(v1, (
                    PersistReads(store, v1.Pre.SnapshotId),
                    PersistReads(store, v1.Successor.SnapshotId)));
        store.AppendDecision(current);

                store.AppendNativeSemanticDiscriminatorEvent(DiscriminatorEvent(
                    manifest,
                    1,
                    "accepted",
                    "diagnostic-only-action"));
                store.AppendNativeSemanticDiscriminatorEvent(DiscriminatorEvent(
                    manifest,
                    2,
                    "before_execution",
                    "diagnostic-only-action") with
                {
                    SemanticStateDigest = "semantic-state",
                    SemanticState = JsonNode.Parse("{\"energy\":3}"),
                    SemanticActionKeys = new[] { "play|card" },
                    ObservedActionKey = "play|card",
                    SemanticMembership = "exact_once",
                    SemanticMatchCount = 1
                });
                store.AppendNativeSemanticDiscriminatorEvent(DiscriminatorEvent(
                    manifest,
                    3,
                    "started",
                    "diagnostic-only-action"));
                store.AppendNativeSemanticDiscriminatorEvent(DiscriminatorEvent(
                    manifest,
                    4,
                    "finished",
                    "diagnostic-only-action"));
            }

            RecordingAuditResult audit = RecordingSessionAuditor.Audit(session);

            Assert.True(
                audit.Status == "pass",
                JsonSerializer.Serialize(audit.Errors));
            Assert.DoesNotContain(
                "native_semantic_discriminator_accepted_without_canonical_accounting",
                audit.Errors.Keys);
        }
        finally
        {
            Delete(root);
        }
    }

    [Fact]
    public void ModernSemanticRootDoesNotRequireLegacyNativeLedgerProjection()
    {
        string root = Temp("modern-semantic-accounting");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            string session;
            using (var store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                HistoricalDecisionRecord v1 = RecordValidationTests.ValidRecord();
        CurrentDecisionRecord current = CurrentRecord(v1, (
                    PersistReads(store, v1.Pre.SnapshotId),
                    PersistReads(store, v1.Successor.SnapshotId)));
        store.AppendDecision(current);
        CurrentDecisionFrame frame = current.Pre;
                var action = new SemanticActionReference(
                    "semantic-only-root",
                    1,
                    "semantic-only-record",
                    "run-0001",
                    "VoteForMapCoordAction",
                    1,
                    frame.SnapshotId);
                store.AppendSemanticBoundaryEvent(SemanticEvent(
                    manifest,
                    1,
                    SemanticBoundaryTraceKinds.ActionAccepted,
                    action,
                    frame));
                store.AppendSemanticBoundaryEvent(SemanticEvent(
                    manifest,
                    2,
                    SemanticBoundaryTraceKinds.ActionCancelledBeforeStart,
                    action));
                store.AppendNativeSemanticDiscriminatorEvent(DiscriminatorEvent(
                    manifest,
                    1,
                    "accepted",
                    action.ActionWitnessId));
                store.AppendNativeSemanticDiscriminatorEvent(DiscriminatorEvent(
                    manifest,
                    2,
                    "before_execution",
                    action.ActionWitnessId) with
                {
                    SemanticStateDigest = "semantic-state",
                    SemanticState = JsonNode.Parse("{\"map\":true}"),
                    SemanticActionKeys = new[] { "activate|map" },
                    ObservedActionKey = "activate|map",
                    SemanticMembership = "exact_once",
                    SemanticMatchCount = 1
                });
                store.AppendNativeSemanticDiscriminatorEvent(DiscriminatorEvent(
                    manifest,
                    3,
                    "started",
                    action.ActionWitnessId));
                store.AppendNativeSemanticDiscriminatorEvent(DiscriminatorEvent(
                    manifest,
                    4,
                    "finished",
                    action.ActionWitnessId));
            }

            RecordingAuditResult audit = RecordingSessionAuditor.Audit(session);

            Assert.True(audit.Status == "pass", JsonSerializer.Serialize(audit.Errors));
            Assert.DoesNotContain(
                "native_semantic_discriminator_accepted_without_canonical_accounting",
                audit.Errors.Keys);
        }
        finally
        {
            Delete(root);
        }
    }

    [Fact]
    public void CanonicalRootCommitSuccessorPersistsAndAuditsEndToEnd()
    {
        string root = Temp("canonical-causal-path");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            string session;
            string discriminatorPath;
            using (var store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                HistoricalDecisionRecord v1 = RecordValidationTests.ValidRecord();
                CurrentDecisionRecord current = CurrentRecord(v1, (
                    PersistReads(store, v1.Pre.SnapshotId),
                    PersistReads(store, v1.Successor.SnapshotId)));
                store.AppendDecision(current);
                CurrentDecisionFrame successor = current.Pre with
                {
                    SnapshotId = current.Successor.SnapshotId,
                    InteractionId = current.Successor.InteractionId,
                    InteractionKind = current.Successor.InteractionKind,
                    Snapshot = current.Successor.Snapshot,
                    Reads = current.Successor.Reads
                };

                var action = new SemanticActionReference(
                    "map-root",
                    1,
                    "map-record",
                    "run-0001",
                    "VoteForMapCoordAction",
                    1,
                    current.Pre.SnapshotId)
                {
                    RequiresNativePostCommit = true
                };
                var tracker = new SemanticBoundaryTracker();
                var drafts = new List<SemanticBoundaryTraceDraft>();
                drafts.AddRange(tracker.Accept(action, current.Pre));
                drafts.AddRange(tracker.ObserveBeforeActionExecution(
                    action.ActionWitnessId,
                    new SemanticBoundaryObservation(
                        SemanticBoundaryWitnessKinds.BeforeHumanActionExecution,
                        DateTimeOffset.UnixEpoch,
                        current.Pre.SnapshotId,
                        "interactive",
                        "complete",
                        current.Pre.InteractionId,
                        current.Pre.InteractionKind,
                        current.Pre,
                        action.ActionWitnessId)));
                drafts.AddRange(tracker.Started(action.ActionWitnessId));
                drafts.AddRange(tracker.Finished(action.ActionWitnessId));
                drafts.AddRange(tracker.ObserveNativeCommit(
                    action.ActionWitnessId,
                    new NativeCompletionEvidence(
                        "map-commit",
                        "map_navigation",
                        "GameAction.Finished",
                        action.ActionWitnessId,
                        null,
                        "map-action",
                        "map-coordinate",
                        null,
                        true)));
                drafts.AddRange(tracker.ObserveDecisionBoundary(
                    new SemanticBoundaryObservation(
                        SemanticBoundaryWitnessKinds.NativeDecisionOwnerReady,
                        DateTimeOffset.UnixEpoch.AddSeconds(1),
                        successor.SnapshotId,
                        "interactive",
                        "complete",
                        successor.InteractionId,
                        successor.InteractionKind,
                        successor,
                        null)
                    {
                        NativeDecisionOwnerReady = new NativeDecisionOwnerReadyEvidence(
                            successor.InteractionKind,
                            "combat-state-owner",
                            "MegaCrit.Sts2.Core.Combat.CombatState",
                            "CombatManager.TurnStarted->NEndTurnButton.OnTurnStarted.postfix")
                    }));
                store.AppendSemanticBoundaryEvents(drafts.Select((draft, index) =>
                    SemanticEvent(manifest, index + 1, draft)).ToArray());
                store.AppendNativeSemanticDiscriminatorEvent(DiscriminatorEvent(
                    manifest,
                    1,
                    "accepted",
                    action.ActionWitnessId));
                store.AppendNativeSemanticDiscriminatorEvent(DiscriminatorEvent(
                    manifest,
                    2,
                    "before_execution",
                    action.ActionWitnessId) with
                {
                    SemanticStateDigest = "semantic-state",
                    SemanticState = JsonNode.Parse("{\"map\":true}"),
                    SemanticActionKeys = new[] { "activate|map" },
                    ObservedActionKey = "activate|map",
                    SemanticMembership = "not_applicable",
                    SemanticMatchCount = 0
                });
                store.AppendNativeSemanticDiscriminatorEvent(DiscriminatorEvent(
                    manifest,
                    3,
                    "started",
                    action.ActionWitnessId));
                store.AppendNativeSemanticDiscriminatorEvent(DiscriminatorEvent(
                    manifest,
                    4,
                    "finished",
                    action.ActionWitnessId));
                discriminatorPath = Path.Combine(
                    session,
                    "native-semantic-discriminator.jsonl");
            }

            RecordingAuditResult audit = RecordingSessionAuditor.Audit(session);

            Assert.True(audit.Status == "pass", JsonSerializer.Serialize(audit.Errors));
            NativeSemanticDiscriminatorReport diagnostic =
                NativeSemanticDiscriminatorAnalyzer.Analyze(
                    File.ReadLines(discriminatorPath)
                        .Where(line => !string.IsNullOrWhiteSpace(line))
                        .Select(line => JsonSerializer.Deserialize<NativeSemanticDiscriminatorEvent>(
                            line,
                            EvidenceJson.Options)!)
                        .ToArray());
            Assert.Equal("fail", diagnostic.Status);
            Assert.Contains(diagnostic.Errors, value =>
                value.EndsWith(
                    "successful_action_not_exact_once_in_semantic_catalog",
                    StringComparison.Ordinal));

            File.WriteAllText(
                discriminatorPath,
                File.ReadAllText(discriminatorPath).Replace(
                    NativeSemanticDiscriminatorContract.EventSchema,
                    "tampered-native-semantic-schema",
                    StringComparison.Ordinal));
            RecordingAuditResult malformed = RecordingSessionAuditor.Audit(session);
            Assert.Equal("fail", malformed.Status);
            Assert.Contains(
                "native_semantic_discriminator_analysis_failed",
                malformed.Errors.Keys);
        }
        finally
        {
            Delete(root);
        }
    }

    [Fact]
    public void SemanticBoundaryBatchIsVisibleInOrderAndReadableAfterClose()
    {
        string root = Temp("current-semantic-batch");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            string session;
            using (RecordingSessionStore store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                SemanticActionReference action = new(
                    "action-batch",
                    1,
                    "record-batch",
                    "run-0001",
                    "PlayCardAction",
                    1,
                    "snapshot-a");
                store.AppendSemanticBoundaryEvents(new[]
                {
                    SemanticEvent(manifest, 1, SemanticBoundaryTraceKinds.ActionAccepted, action),
                    SemanticEvent(manifest, 2, SemanticBoundaryTraceKinds.ActionStarted, action)
                });

                Assert.Equal(
                    new[] { 1L, 2L },
                    ReadLiveLines(Path.Combine(session, "semantic-boundary-trace.jsonl"))
                        .Select(line => JsonSerializer.Deserialize<SemanticBoundaryTraceEvent>(
                            line,
                            EvidenceJson.Options)!.Sequence));
            }

            Assert.Equal(
                new[] { 1L, 2L },
                File.ReadLines(Path.Combine(session, "semantic-boundary-trace.jsonl"))
                    .Select(line => JsonSerializer.Deserialize<SemanticBoundaryTraceEvent>(
                        line,
                        EvidenceJson.Options)!.Sequence));
        }
        finally
        {
            Delete(root);
        }
    }

    [Fact]
    public void SemanticBoundaryBatchValidatesBeforeWritingAndRejectsClosedStore()
    {
        string root = Temp("current-semantic-batch-failure");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            using RecordingSessionStore store = RecordingSessionStore.Create(root, manifest, profile);
            SemanticActionReference action = new(
                "action-batch",
                1,
                "record-batch",
                "run-0001",
                "PlayCardAction",
                1,
                "snapshot-a");
            string tracePath = Path.Combine(store.DirectoryPath, "semantic-boundary-trace.jsonl");

            Assert.Throws<InvalidDataException>(() => store.AppendSemanticBoundaryEvents(new[]
            {
                SemanticEvent(manifest, 1, SemanticBoundaryTraceKinds.ActionAccepted, action),
                SemanticEvent(manifest with { TimelineId = "timeline-other" }, 2,
                    SemanticBoundaryTraceKinds.ActionStarted, action)
            }));
            Assert.Empty(ReadLiveLines(tracePath));

            store.Dispose();
            Assert.Throws<ObjectDisposedException>(() => store.AppendSemanticBoundaryEvents(
                new[] { SemanticEvent(manifest, 1, SemanticBoundaryTraceKinds.ActionAccepted, action) }));
        }
        finally
        {
            Delete(root);
        }
    }

    [Fact]
    public void SemanticEvidenceStoresAnExactFrameOnceAndAuditsTampering()
    {
        string root = Temp("current-semantic-evidence");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            string session;
            string framePath;
            using (RecordingSessionStore store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                CurrentDecisionFrame frame = CurrentRecord(
                    RecordValidationTests.ValidRecord(),
                    (PersistReads(store, "snapshot-a"), PersistReads(store, "snapshot-b"))).Pre;
                SemanticFrameReference first = store.PersistSemanticFrame(frame);
                SemanticFrameReference second = store.PersistSemanticFrame(frame);
                Assert.Equal(first, second);
                Assert.Single(Directory.GetFiles(
                    Path.Combine(session, "semantic-frames"),
                    "*.json",
                    SearchOption.AllDirectories));

                var action = new SemanticActionReference(
                    "action-ref",
                    1,
                    "record-ref",
                    "run-0001",
                    "PlayCardAction",
                    1,
                    frame.SnapshotId);
                store.AppendSemanticEvidenceEvents(new[]
                {
                    SemanticEvidenceEvent(manifest, 1, SemanticBoundaryTraceKinds.ActionAccepted, action)
                        with { HumanObservationRef = first },
                    SemanticEvidenceEvent(
                        manifest,
                        2,
                        SemanticBoundaryTraceKinds.ActionCancelledBeforeStart,
                        action)
                });
                SemanticEvidenceEvent persisted = JsonSerializer.Deserialize<SemanticEvidenceEvent>(
                    ReadLiveLines(Path.Combine(session, "semantic-boundary-trace.jsonl")).First(),
                    EvidenceJson.Options)!;
                Assert.Equal(SemanticEvidenceContract.EventSchema, persisted.Schema);
                Assert.Equal(first, persisted.HumanObservationRef);
                framePath = Path.Combine(session, first.ObjectRef);
            }

            RecordingAuditResult beforeTamper = RecordingSessionAuditor.Audit(session);
            Assert.DoesNotContain(
                beforeTamper.Errors.Keys,
                key => key.StartsWith("semantic_", StringComparison.Ordinal));
            File.AppendAllText(framePath, "tampered");
            RecordingAuditResult audit = RecordingSessionAuditor.Audit(session);
            Assert.Equal("fail", audit.Status);
            Assert.True(audit.Errors.ContainsKey("semantic_frame_missing_or_changed"));
        }
        finally
        {
            Delete(root);
        }
    }

    [Fact]
    public void SemanticEvidenceOwnerReadyRoundTripsAndFailsClosedWhenIncomplete()
    {
        string root = Temp("current-semantic-owner-ready-round-trip");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            string session;
            string tracePath;
            using (RecordingSessionStore store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                HistoricalDecisionRecord validRecord = RecordValidationTests.ValidRecord();
                CurrentDecisionRecord record = CurrentRecord(
                    validRecord,
                    (PersistReads(store, validRecord.Pre.SnapshotId),
                        PersistReads(store, validRecord.Successor.SnapshotId)));
                store.AppendDecision(record);
                CurrentDecisionFrame pre = record.Pre with
                {
                    SnapshotId = "snapshot-pre",
                    InteractionId = "map-owner",
                    InteractionKind = "map"
                };
                CurrentDecisionFrame successor = pre with
                {
                    SnapshotId = "snapshot-successor",
                    InteractionId = "combat-owner",
                    InteractionKind = "combat_turn",
                    Snapshot = JsonNode.Parse("{\"energy\":3,\"combat\":true}")!
                };
                SemanticFrameReference preRef = store.PersistSemanticFrame(pre);
                SemanticFrameReference successorRef = store.PersistSemanticFrame(successor);
                var action = new SemanticActionReference(
                    "owner-ready-action",
                    1,
                    "owner-ready-record",
                    "run-0001",
                    "VoteForMapCoordAction",
                    1,
                    pre.SnapshotId)
                {
                    RequiresNativePostCommit = true
                };
                var completion = new NativeCompletionEvidence(
                    "owner-ready-commit",
                    "map_navigation",
                    "GameAction.Finished",
                    action.ActionWitnessId,
                    null,
                    "map-owner",
                    "map-coordinate",
                    null,
                    true);
                var ownerReady = new NativeDecisionOwnerReadyEvidence(
                    "combat_turn",
                    "combat-owner",
                    "MegaCrit.Sts2.Core.Combat.CombatState",
                    "CombatManager.TurnStarted->NEndTurnButton.OnTurnStarted.postfix");
                var boundary = SemanticBoundaryObservationCodec.Encode(
                    new SemanticBoundaryObservation(
                        SemanticBoundaryWitnessKinds.NativeDecisionOwnerReady,
                        DateTimeOffset.UnixEpoch.AddSeconds(1),
                        successor.SnapshotId,
                        "interactive",
                        "complete",
                        successor.InteractionId,
                        successor.InteractionKind,
                        successor,
                        null)
                    {
                        NativeDecisionOwnerReady = ownerReady
                    },
                    store.PersistSemanticFrame);
                var executionBoundary = new SemanticBoundaryObservationReference(
                    SemanticBoundaryWitnessKinds.BeforeHumanActionExecution,
                    DateTimeOffset.UnixEpoch,
                    pre.SnapshotId,
                    "interactive",
                    "complete",
                    pre.InteractionId,
                    pre.InteractionKind,
                    preRef,
                    action.ActionWitnessId);
                store.AppendSemanticEvidenceEvents(new[]
                {
                    SemanticEvidenceEvent(
                        manifest,
                        1,
                        SemanticBoundaryTraceKinds.ActionAccepted,
                        action) with { HumanObservationRef = preRef },
                    SemanticEvidenceEvent(
                        manifest,
                        2,
                        SemanticBoundaryTraceKinds.BoundaryObserved,
                        action) with { Boundary = executionBoundary },
                    SemanticEvidenceEvent(
                        manifest,
                        3,
                        SemanticBoundaryTraceKinds.ActionStarted,
                        action),
                    SemanticEvidenceEvent(
                        manifest,
                        4,
                        SemanticBoundaryTraceKinds.ActionFinished,
                        action),
                    SemanticEvidenceEvent(
                        manifest,
                        5,
                        SemanticBoundaryTraceKinds.NativeCommitObserved,
                        action) with { NativeCompletion = completion },
                    SemanticEvidenceEvent(
                        manifest,
                        6,
                        SemanticBoundaryTraceKinds.TransitionProved,
                        action) with
                    {
                        ProofStatus = "proved_native_commit_then_owner_boundary",
                        Boundary = boundary,
                        ExecutionPreRef = preRef,
                        SuccessorRef = successorRef,
                        NativeCompletion = completion
                    }
                });
                tracePath = Path.Combine(session, "semantic-boundary-trace.jsonl");
            }

            RecordingAuditResult audit = RecordingSessionAuditor.Audit(session);
            Assert.True(audit.Status == "pass", JsonSerializer.Serialize(audit.Errors));
            JsonObject persistedTransition = JsonNode.Parse(
                    File.ReadLines(tracePath).Single(line =>
                        line.Contains("transition_proved", StringComparison.Ordinal)))!
                .AsObject();
            JsonObject persistedBoundary = persistedTransition["boundary"]!.AsObject();
            Assert.Equal(
                "combat_turn",
                persistedBoundary["native_decision_owner_ready"]!["domain"]!.GetValue<string>());
            Assert.Equal(
                "combat-owner",
                persistedBoundary["native_decision_owner_ready"]!["native_owner_witness_id"]!.GetValue<string>());

            string[] original = File.ReadAllLines(tracePath);
            JsonObject missing = JsonNode.Parse(original.Single(line =>
                    line.Contains("transition_proved", StringComparison.Ordinal)))!.AsObject();
            missing["boundary"]!.AsObject().Remove("native_decision_owner_ready");
            File.WriteAllLines(
                tracePath,
                original.Select(line => line.Contains("transition_proved", StringComparison.Ordinal)
                    ? missing.ToJsonString(EvidenceJson.Options)
                    : line));
            RecordingAuditResult missingAudit = RecordingSessionAuditor.Audit(session);
            Assert.Equal("fail", missingAudit.Status);
            Assert.True(missingAudit.Errors.ContainsKey("semantic_native_owner_ready_evidence_invalid"));
            Assert.True(missingAudit.Errors.ContainsKey("semantic_transition_proof_incomplete"));

            JsonObject mismatched = JsonNode.Parse(original.Single(line =>
                    line.Contains("transition_proved", StringComparison.Ordinal)))!.AsObject();
            mismatched["boundary"]!["native_decision_owner_ready"]!["domain"] = "map";
            File.WriteAllLines(
                tracePath,
                original.Select(line => line.Contains("transition_proved", StringComparison.Ordinal)
                    ? mismatched.ToJsonString(EvidenceJson.Options)
                    : line));
            RecordingAuditResult mismatchedAudit = RecordingSessionAuditor.Audit(session);
            Assert.Equal("fail", mismatchedAudit.Status);
            Assert.True(mismatchedAudit.Errors.ContainsKey("semantic_native_owner_ready_evidence_invalid"));
            Assert.True(mismatchedAudit.Errors.ContainsKey("semantic_transition_proof_incomplete"));
        }
        finally
        {
            Delete(root);
        }
    }

    [Theory]
    [InlineData("complete", true)]
    [InlineData("incomplete", false)]
    [InlineData("no_owner_ready", false)]
    public void EventProceedCloseUsesCommittedExactMapBoundaryWithoutAnotherHumanInput(string condition, bool canonical)
    {
        string root = Temp("event-proceed-close");
        try
        {
            HumanCaptureProfile profile = Profile() with
            {
                ProfileId = "event-proceed-test",
                SupportedActionFamilies = new[] { "event_option.proceed" },
                Reads = new[] { new CaptureReadRequirement("pre", "run_deck", true),
                    new CaptureReadRequirement("successor", "run_deck", true) }
            };
            CurrentRecordingManifest manifest = Manifest(profile) with
            { DecisionSchemaVersion = 2, DispositionSchemaVersion = 1, CloseSchemaVersion = 1 };
            string session;
            using (var store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                HistoricalDecisionRecord seed = RecordValidationTests.ValidRecord();
                var input = new RecordedBoundAction("event-proceed", "activate", "event-option",
                    new Dictionary<string, string>(), "Continue");
                CurrentDecisionFrame Frame(string id, string kind, string owner)
                {
                    JsonNode snapshot = seed.Pre.Snapshot.DeepClone();
                    snapshot["snapshot_id"] = id;
                    snapshot["interaction"]!["kind"] = kind;
                    snapshot["interaction"]!["interaction_id"] = owner;
                    snapshot["interaction"]!["content"] = kind == "event_option"
                        ? JsonNode.Parse("{\"context\":{\"event_id\":\"PAEL\"},\"surface\":{\"options\":[{\"entity_id\":\"event-option\",\"is_proceed\":true}]}}")
                        : JsonNode.Parse("{\"context\":{\"act_index\":1},\"surface\":{\"travel_enabled\":true,\"next_options\":[{\"entity_id\":\"map-point\"}]}}");
                    string subject = kind == "event_option" ? input.SubjectReferentId! : "map-point";
                    snapshot["bound_actions"]!["actions"] = new JsonArray(new JsonObject
                    {
                        ["bound_action_id"] = kind == "event_option" ? input.BoundActionId : "travel-map-point", ["verb"] = "activate",
                        ["subject_referent_id"] = subject, ["arguments"] = new JsonArray(),
                        ["label"] = kind == "event_option" ? input.Label : "Choose next room"
                    });
                    snapshot["referents"] = new JsonArray(new JsonObject
                    { ["referent_id"] = subject, ["kind"] = "entity", ["role"] = kind == "event_option" ? "option" : "map_point" });
                    snapshot["bound_actions"]!["materialized_count"] = 1;
                    return new CurrentDecisionFrame(id, owner, kind, $"sts2.player-environment/surface/{kind}-1",
                        EvidenceIdentity.Sha256Json(snapshot["bound_actions"]!), 1, snapshot,
                        PersistReads(store, id).Where(read => read.Kind == "run_deck").ToArray());
                }
                CurrentDecisionFrame pre = Frame("event-pre", "event_option", "event-room");
                CurrentDecisionFrame map = Frame("map-after-proceed", "map_navigation", "map-owner");
                var action = new SemanticActionReference("event-root", 1, "event-record", "run-0001",
                    "NEventRoom.OptionButtonClicked", null, pre.SnapshotId)
                {
                    NativeMechanism = "direct_ui_commit", RequiresNativePostCommit = true,
                    Decision = new DecisionOccurrenceIdentity(2, "event-decision", "event-root", null,
                        "event_option", "event_option.proceed", "root", null),
                    NativeWitness = seed.NativeWitness with
                    { Origin = "native_event_option_ui", NativeActionType = "NEventRoom.OptionButtonClicked", SubjectWitnessId = "native-option", ArgumentWitnessIds = new Dictionary<string, string>() },
                    Mapping = seed.Mapping, BoundAction = input
                };
                var nativeCatalog = new ExecutionSemanticActionSpaceEvidence(
                    ExecutionSemanticActionSpaceContract.SchemaVersion, ExecutionSemanticActionSpaceContract.Schema,
                    action.ActionWitnessId, "before_native_action_admission", "captured", "event_option",
                    new string('a', 64), JsonNode.Parse("{\"event\":\"PAEL\",\"is_proceed\":true}")!, new string('b', 64),
                    new[] { new ExecutionSemanticAction("proceed|event-option|", "proceed_event", "event-option",
                        input.Arguments, "EventOption.IsProceed") }, "proceed|event-option|", "exact_once", 1,
                    new[] { "EventOption.IsProceed" }, Array.Empty<string>(), null)
                { HumanBoundActionId = input.BoundActionId };
                var tracker = new SemanticBoundaryTracker();
                var drafts = new List<SemanticBoundaryTraceDraft>();
                drafts.AddRange(tracker.Accept(action, pre));
                drafts.AddRange(tracker.ObserveBeforeActionExecution(action.ActionWitnessId,
                    new SemanticBoundaryObservation(SemanticBoundaryWitnessKinds.BeforeHumanActionExecution,
                        DateTimeOffset.UnixEpoch, pre.SnapshotId, "interactive", "complete", pre.InteractionId,
                        pre.InteractionKind, pre, action.ActionWitnessId) { ExecutionSemanticActionSpace = nativeCatalog }));
                drafts.AddRange(tracker.Started(action.ActionWitnessId));

                // The exact EventOption registration is the same identity
                // consumed by the native synchronous completion path.
                var completions = new NativePostCommitCompletionLedger();
                Assert.True(completions.Register(new NativePostCommitCompletionRegistration(manifest.SessionId, 1,
                    action.ActionWitnessId, new NativePostCommitCompletionExpectation("event_option", "EventOption.Chosen",
                        NativeOperandWitnessId: "native-option"))));
                Assert.True(completions.BindTask(new NativeTaskObservation(manifest.SessionId, 1, "EventOption.Chosen",
                    "native-sync", NativeOperandWitnessId: "native-option"), action.ActionWitnessId).IsMatched);
                var completionSignal = new NativeTaskCompletion(manifest.SessionId, 1, "event-commit", "native-sync", true);
                NativePostCommitCompletion completed = completions.PreviewTaskCompletion(completionSignal).Completion!;
                var commit = new NativeCompletionEvidence(completed.CompletionId, completed.Family, completed.Kind,
                    completed.ActionWitnessId, completed.TaskWitnessId, null, completed.NativeOperandWitnessId, null, completed.Succeeded);
                drafts.AddRange(tracker.Finished(action.ActionWitnessId));
                drafts.AddRange(tracker.ObserveNativeCommit(action.ActionWitnessId, commit));
                Assert.DoesNotContain(drafts, draft => draft.Kind == SemanticBoundaryTraceKinds.TransitionProved);
                Assert.True(completions.CommitTaskCompletion(completionSignal));
                if (condition != "no_owner_ready")
                    drafts.AddRange(tracker.ObserveDecisionBoundary(new SemanticBoundaryObservation(
                        SemanticBoundaryWitnessKinds.NativeDecisionOwnerReady, DateTimeOffset.UnixEpoch.AddSeconds(1),
                        map.SnapshotId, "interactive", "complete", map.InteractionId, map.InteractionKind, map, null)
                    {
                        NativeDecisionOwnerReady = new NativeDecisionOwnerReadyEvidence("map_navigation", "map-owner",
                            "MegaCrit.Sts2.Core.Nodes.Screens.Map.NMapScreen", "NEventRoom.Proceed->NMapScreen.Open.return"),
                        StateCompleteness = condition == "incomplete" ? "partial" : "complete",
                        StateBlockers = condition == "incomplete" ? new[] { "required_read_evidence_unavailable" } : Array.Empty<string>()
                    }));
                drafts.AddRange(tracker.CloseUnknown(RecordingClosePolicy.TerminalUnknownReason));
                Assert.Single(drafts, draft => draft.Kind == (canonical
                    ? SemanticBoundaryTraceKinds.TransitionProved : SemanticBoundaryTraceKinds.TransitionUnknown));
                Assert.Single(drafts, draft => draft.Kind == SemanticBoundaryTraceKinds.ActionAccepted);
                Assert.DoesNotContain(drafts, draft => draft.Kind == (canonical
                    ? SemanticBoundaryTraceKinds.TransitionUnknown : SemanticBoundaryTraceKinds.TransitionProved));

                long sequence = 0;
                store.AppendSemanticEvidenceEvents(drafts.Select(draft => new SemanticEvidenceEvent(
                    SemanticEvidenceContract.SchemaVersion, SemanticEvidenceContract.EventSchema,
                    $"event-proceed-{++sequence}", manifest.SessionId, manifest.TimelineId, action.RunId, sequence,
                    DateTimeOffset.UnixEpoch.AddMilliseconds(sequence), draft.Kind, draft.Action, draft.ProofStatus,
                    draft.RelatedActionWitnessId, draft.Boundary == null ? null : SemanticBoundaryObservationCodec.Encode(draft.Boundary, store.PersistSemanticFrame),
                    draft.SemanticPre == null ? null : store.PersistSemanticFrame(draft.SemanticPre),
                    draft.SemanticSuccessor == null ? null : store.PersistSemanticFrame(draft.SemanticSuccessor), draft.Detail,
                    draft.NonClaims ?? Array.Empty<string>())
                {
                    HumanObservationRef = draft.HumanObservation == null ? null : store.PersistSemanticFrame(draft.HumanObservation),
                    NativeCompletion = draft.NativeCompletion,
                    ExecutionSemanticActionSpaceRef = draft.ExecutionSemanticActionSpace == null ? null
                        : store.PersistExecutionSemanticActionSpace(draft.ExecutionSemanticActionSpace)
                }).ToArray());
                long journalSequence = 2;
                void Journal(string kind, string? recordId = null) => store.AppendRunEvent(new RunJournalEvent(
                    2, CurrentRecordingContract.RunJournalSchema, $"event-proceed-journal-{++journalSequence}",
                    manifest.SessionId, action.RunId, manifest.TimelineId, journalSequence, DateTimeOffset.UnixEpoch,
                    kind, recordId, map.SnapshotId, "event Proceed fixture"));
                Journal("semantic_human_action_accepted", action.RecordId);
                if (canonical)
                {
                    SemanticBoundaryTraceDraft proved = drafts.Single(draft => draft.Kind == SemanticBoundaryTraceKinds.TransitionProved);
                    CanonicalTransitionEvidence row = SemanticTransitionProjection.CreateCanonical(proved,
                        store.PersistSemanticFrame(proved.SemanticPre!), store.PersistSemanticFrame(proved.SemanticSuccessor!),
                        store.PersistExecutionSemanticActionSpace(proved.ExecutionSemanticActionSpace!), manifest.SessionId, manifest.TimelineId);
                    store.AppendCanonicalTransition(row);
                    Assert.Equal("event_option.proceed", row.Decision!.Family);
                    Journal("canonical_transition_recorded", row.TransitionId);
                    Journal("current_decision_projection_omitted", row.TransitionId);
                }
                Journal("session_closed");
                Assert.Equal(canonical ? 0 : 1, store.GetSnapshot().Counters.Decisions!.RealFailures);
            }
            RecordingAuditResult audit = RecordingSessionAuditor.Audit(session);
            Assert.True(audit.Status == "pass", JsonSerializer.Serialize(audit.Errors));
            Assert.Equal(canonical ? 1 : 0, File.ReadLines(Path.Combine(session, "canonical-transitions.jsonl")).Count());
            Assert.True(File.Exists(Path.Combine(session, "session-close-receipt.json")));
        }
        finally { Delete(root); }
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void TrackerSettlementProjectsDurableDecisionAndCanonicalEvidence(bool gameOver)
    {
        string root = Temp("tracker-settlement-projection");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            string session;
            using (RecordingSessionStore store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                HistoricalDecisionRecord source = RecordValidationTests.ValidRecord();
        CurrentDecisionRecord seed = CurrentRecord(
                    source,
                    (PersistReads(store, source.Pre.SnapshotId),
                        PersistReads(store, source.Successor.SnapshotId)));
                CurrentDecisionFrame humanObservation = seed.Pre;
                CurrentDecisionFrame successor = new(
                    seed.Successor.SnapshotId,
                    seed.Successor.InteractionId,
                    seed.Successor.InteractionKind,
                    seed.Pre.SurfaceSchema,
                    seed.Pre.CatalogDigest,
                    seed.Pre.CatalogCount,
                    seed.Successor.Snapshot,
                    seed.Successor.Reads);
                if (gameOver)
                {
                    JsonNode snapshot = successor.Snapshot.DeepClone();
                    snapshot["interaction"]!["kind"] = "game_over";
                    snapshot["bound_actions"]!["actions"] = new JsonArray(new JsonObject
                    {
                        ["bound_action_id"] = "terminal-continue",
                        ["verb"] = "activate",
                        ["subject_referent_id"] = "game-over-continue",
                        ["arguments"] = new JsonObject(),
                        ["label"] = "Continue"
                    });
                    successor = successor with
                    {
                        InteractionKind = "game_over", Snapshot = snapshot,
                        CatalogDigest = EvidenceIdentity.Sha256Json(snapshot["bound_actions"]!),
                        Reads = successor.Reads.Where(read => read.Kind == "run_deck").ToArray()
                    };
                }
                SemanticActionReference action = new(
                    "tracker-settlement-action",
                    source.Sequence,
                    source.RecordId,
                    source.RunId,
                    source.NativeWitness.NativeActionType,
                    null,
                    humanObservation.SnapshotId)
                {
                    NativeMechanism = "game_action",
                    RequiresNativePostCommit = true,
                    NativeWitness = source.NativeWitness,
                    Mapping = source.Mapping,
                    BoundAction = source.Action
                };
                string semanticKey =
                    $"{source.Action.Verb}|{source.Action.SubjectReferentId ?? "-"}|";
                var actionSpace = new ExecutionSemanticActionSpaceEvidence(
                    ExecutionSemanticActionSpaceContract.SchemaVersion,
                    ExecutionSemanticActionSpaceContract.Schema,
                    action.ActionWitnessId,
                    "before_execution",
                    "captured",
                    "combat_play_phase",
                    new string('a', 64),
                    JsonNode.Parse("{\"turn\":1}")!,
                    new string('b', 64),
                    new[]
                    {
                        new ExecutionSemanticAction(
                            semanticKey,
                            source.Action.Verb,
                            source.Action.SubjectReferentId,
                            source.Action.Arguments,
                            "native_test_validator")
                    },
                    semanticKey,
                    "exact_once",
                    1,
                    new[] { "native_test_validator" },
                    new[] { "not_public_delivery_authority" },
                    null)
                {
                    HumanBoundActionId = source.Action.BoundActionId
                };
                var tracker = new SemanticBoundaryTracker();
                var drafts = new List<SemanticBoundaryTraceDraft>();
                drafts.AddRange(tracker.Accept(action, humanObservation));
                drafts.AddRange(tracker.ObserveBeforeActionExecution(
                    action.ActionWitnessId,
                    new SemanticBoundaryObservation(
                        SemanticBoundaryWitnessKinds.BeforeHumanActionExecution,
                        DateTimeOffset.UnixEpoch,
                        humanObservation.SnapshotId,
                        "settling",
                        "complete",
                        humanObservation.InteractionId,
                        humanObservation.InteractionKind,
                        humanObservation,
                        action.ActionWitnessId)
                    {
                        ExecutionSemanticActionSpace = actionSpace
                    }));
                drafts.AddRange(tracker.Started(action.ActionWitnessId));
                drafts.AddRange(tracker.Finished(action.ActionWitnessId));
                NativeCompletionEvidence completion = new(
                    "tracker-settlement-completion",
                    "ordinary_combat",
                    "native.test.commit",
                    action.ActionWitnessId,
                    "task-tracker-settlement",
                    "owner-tracker-settlement",
                    "operand-tracker-settlement",
                    null,
                    true);
                drafts.AddRange(tracker.ObserveNativeCommit(action.ActionWitnessId, completion));
                IReadOnlyList<SemanticBoundaryTraceDraft> provedDrafts =
                    tracker.ObserveDecisionBoundary(
                        new SemanticBoundaryObservation(
                            SemanticBoundaryWitnessKinds.NativeDecisionOwnerReady,
                            DateTimeOffset.UnixEpoch.AddSeconds(1),
                            successor.SnapshotId,
                            "interactive",
                            "complete",
                            successor.InteractionId,
                            successor.InteractionKind,
                            successor,
                            null)
                        {
                            NativeDecisionOwnerReady = new NativeDecisionOwnerReadyEvidence(
                                successor.InteractionKind,
                                "owner-tracker-settlement",
                                gameOver ? "NGameOverScreen" : "CombatState",
                                gameOver ? "NGameOverScreen.AnimateIn->NGameOverContinueButton.OnEnable.postfix" : "native.test.owner-ready")
                        });
                SemanticBoundaryTraceDraft proved = Assert.Single(provedDrafts);
                drafts.AddRange(provedDrafts);

                Assert.Same(humanObservation, proved.HumanObservation);
                Assert.Same(completion, proved.NativeCompletion);
                Assert.Same(actionSpace, proved.ExecutionSemanticActionSpace);

                var semanticEvents = new List<SemanticEvidenceEvent>(drafts.Count);
                long sequence = 0;
                foreach (SemanticBoundaryTraceDraft draft in drafts)
                {
                    SemanticFrameReference? humanRef = draft.HumanObservation == null
                        ? null
                        : store.PersistSemanticFrame(draft.HumanObservation);
                    SemanticFrameReference? preRef = draft.SemanticPre == null
                        ? null
                        : store.PersistSemanticFrame(draft.SemanticPre);
                    SemanticFrameReference? successorFrameRef = draft.SemanticSuccessor == null
                        ? null
                        : store.PersistSemanticFrame(draft.SemanticSuccessor);
                    ExecutionSemanticActionSpaceReference? actionSpaceRef =
                        draft.ExecutionSemanticActionSpace == null
                            ? null
                            : store.PersistExecutionSemanticActionSpace(
                                draft.ExecutionSemanticActionSpace);
                    semanticEvents.Add(new SemanticEvidenceEvent(
                        SemanticEvidenceContract.SchemaVersion,
                        SemanticEvidenceContract.EventSchema,
                        $"tracker-semantic-event-{++sequence}",
                        manifest.SessionId,
                        manifest.TimelineId,
                        draft.Action.RunId,
                        sequence,
                        DateTimeOffset.UnixEpoch.AddMilliseconds(sequence),
                        draft.Kind,
                        draft.Action,
                        draft.ProofStatus,
                        draft.RelatedActionWitnessId,
                        draft.Boundary == null
                            ? null
                            : SemanticBoundaryObservationCodec.Encode(
                                draft.Boundary,
                                store.PersistSemanticFrame),
                        preRef,
                        successorFrameRef,
                        draft.Detail,
                        draft.NonClaims ?? Array.Empty<string>())
                    {
                        HumanObservationRef = humanRef,
                        NativeCompletion = draft.NativeCompletion,
                        ExecutionSemanticActionSpaceRef = actionSpaceRef
                    });
                }
                store.AppendSemanticEvidenceEvents(semanticEvents);

                CurrentDecisionRecord decision = SemanticTransitionProjection.CreateDecision(
                    proved,
                    source.Environment,
                    manifest.SessionId,
                    manifest.TimelineId,
                    profile.ProfileId);
                // Legacy combat-only compatibility requires combat_piles on
                // both ends. A terminal successor instead uses the canonical
                // stream, as the production projection-omission path does.
                if (!gameOver)
                    store.AppendDecision(decision);
                SemanticFrameReference preStateRef = store.PersistSemanticFrame(proved.SemanticPre!);
                SemanticFrameReference successorRef = store.PersistSemanticFrame(
                    proved.SemanticSuccessor!);
                ExecutionSemanticActionSpaceReference canonicalActionSpaceRef =
                    store.PersistExecutionSemanticActionSpace(
                        proved.ExecutionSemanticActionSpace!);
                store.AppendCanonicalTransition(SemanticTransitionProjection.CreateCanonical(
                    proved,
                    preStateRef,
                    successorRef,
                    canonicalActionSpaceRef,
                    manifest.SessionId,
                    manifest.TimelineId));
                if (gameOver)
                {
                    long journalSequence = 2;
                    foreach (string kind in new[] { "canonical_transition_recorded", "current_decision_projection_omitted" })
                        store.AppendRunEvent(new RunJournalEvent(
                            CurrentRecordingContract.SchemaVersion, CurrentRecordingContract.RunJournalSchema,
                            $"event-{++journalSequence}", manifest.SessionId, source.RunId,
                            manifest.TimelineId, journalSequence, DateTimeOffset.UtcNow, kind,
                            $"canonical-{source.RecordId}", successor.SnapshotId,
                            "successor_required_read_missing_combat_piles"));
                }
            }

            RecordingAuditResult audit = RecordingSessionAuditor.Audit(session);
            Assert.True(audit.Status == "pass", JsonSerializer.Serialize(audit.Errors));
            Assert.Equal(gameOver ? 0 : 1, RecordingSessionAuditor.ReadAdmitted(session).Count);
            Assert.Single(File.ReadLines(Path.Combine(session, "canonical-transitions.jsonl")));
            JsonObject provedEvent = JsonNode.Parse(
                    File.ReadLines(Path.Combine(session, "semantic-boundary-trace.jsonl"))
                        .Single(line => line.Contains("transition_proved", StringComparison.Ordinal)))!
                .AsObject();
            Assert.NotNull(provedEvent["human_observation_ref"]);
            Assert.NotNull(provedEvent["native_completion"]);
            Assert.NotNull(provedEvent["execution_semantic_action_space_ref"]);
        }
        finally
        {
            Delete(root);
        }
    }

    [Theory]
    [InlineData(false, false)]
    [InlineData(true, false)]
    [InlineData(true, true)]
    [InlineData(true, true, true)]
    public void ExecutionSemanticActionSpaceRoundTripsIntoCanonicalAudit(bool omitLegacy, bool nativeInput, bool potion = false)
    {
        string root = Temp("execution-semantic-action-space-round-trip");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            string session;
            string actionSpacePath;
            using (RecordingSessionStore store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                HistoricalDecisionRecord source = RecordValidationTests.ValidRecord();
        CurrentDecisionRecord decision = CurrentRecord(
                    source,
                    (PersistReads(store, source.Pre.SnapshotId),
                        PersistReads(store, source.Successor.SnapshotId)));
                if (!omitLegacy) store.AppendDecision(decision);

                JsonNode executionSnapshot = decision.Pre.Snapshot.DeepClone();
                executionSnapshot["snapshot_id"] = "execution-pre";
                executionSnapshot["status"] = "settling";
                executionSnapshot["bound_actions"]!["actions"] = new JsonArray();
                executionSnapshot["bound_actions"]!["materialized_count"] = 0;
                executionSnapshot["bound_actions"]!["total_count"] = 0;
                var executionPre = new CurrentDecisionFrame(
                    "execution-pre",
                    decision.Pre.InteractionId,
                    decision.Pre.InteractionKind,
                    decision.Pre.SurfaceSchema,
                    EvidenceIdentity.Sha256Json(executionSnapshot["bound_actions"]!),
                    0,
                    executionSnapshot,
                    decision.Pre.Reads);
                var successor = new CurrentDecisionFrame(
                    decision.Successor.SnapshotId,
                    decision.Successor.InteractionId,
                    decision.Successor.InteractionKind,
                    decision.Pre.SurfaceSchema,
                    decision.Pre.CatalogDigest,
                    decision.Pre.CatalogCount,
                    decision.Successor.Snapshot.DeepClone(),
                    decision.Successor.Reads);
                var action = new SemanticActionReference(
                    "execution-semantic-action",
                    decision.Sequence,
                    decision.RecordId,
                    decision.RunId,
                    decision.NativeWitness.NativeActionType,
                    7,
                    decision.Pre.SnapshotId)
                {
                    NativeMechanism = "game_action",
                    NativeWitness = decision.NativeWitness,
                    Mapping = decision.Mapping,
                    BoundAction = decision.Action
                };
                string semanticKey = $"{decision.Action.Verb}|{decision.Action.SubjectReferentId ?? "-"}|";
                var actionSpace = new ExecutionSemanticActionSpaceEvidence(
                    ExecutionSemanticActionSpaceContract.SchemaVersion,
                    ExecutionSemanticActionSpaceContract.Schema,
                    action.ActionWitnessId,
                    "before_execution",
                    "captured",
                    "combat_play_phase",
                    new string('a', 64),
                    JsonNode.Parse("{\"player_phase\":\"Play\"}")!,
                    new string('b', 64),
                    new[]
                    {
                        new ExecutionSemanticAction(
                            semanticKey,
                            decision.Action.Verb,
                            decision.Action.SubjectReferentId,
                            decision.Action.Arguments,
                            "CardModel.CanPlayTargeting")
                    },
                    semanticKey,
                    "exact_once",
                    1,
                    new[] { "CardModel.CanPlayTargeting" },
                    new[] { "not_public_bound_action_delivery_authority" },
                    null)
                {
                    HumanBoundActionId = decision.Action.BoundActionId
                };
                if (potion)
                {
                    // Real failure shape: native potion input has no public action at H,
                    // but an independent execution catalog contains its exact target.
                    const string potionKey = "use|potion-a1|target=player-a1";
                    var arguments = new Dictionary<string, string> { ["target"] = "player-a1" };
                    action = action with { NativeActionType = "UsePotionAction",
                        NativeWitness = action.NativeWitness! with {
                            Origin = "native_potion_use_ui", NativeActionType = "UsePotionAction",
                            SubjectWitnessId = "native-potion", ArgumentWitnessIds = new Dictionary<string, string> { ["target"] = "native-player" } } };
                    actionSpace = actionSpace with {
                        Actions = new[] { new ExecutionSemanticAction(potionKey, "use", "potion-a1", arguments,
                            "current_potion_slot+native_potion_usability_and_target_validation") },
                        ObservedActionKey = potionKey };
                }
                if (nativeInput)
                {
                    ExecutionSemanticAction selected = actionSpace.Actions.Single();
                    action = action with { BoundAction = null,
                        NativeInput = new(selected.Key, selected.Verb, selected.SubjectReferentId,
                            selected.Arguments, decision.Action.Label),
                        Mapping = new("exact_native_input", 1, "scoped_native_input_reference_equality", null) };
                    actionSpace = actionSpace with { HumanBoundActionId = null, HumanNativeActionKey = selected.Key };
                }
                var tracker = new SemanticBoundaryTracker();
                var drafts = new List<SemanticBoundaryTraceDraft>();
                drafts.AddRange(tracker.Accept(action, decision.Pre));
                drafts.AddRange(tracker.ObserveBeforeActionExecution(
                    action.ActionWitnessId,
                    new SemanticBoundaryObservation(
                        SemanticBoundaryWitnessKinds.BeforeHumanActionExecution,
                        DateTimeOffset.UnixEpoch,
                        executionPre.SnapshotId,
                        "settling",
                        "complete",
                        executionPre.InteractionId,
                        executionPre.InteractionKind,
                        executionPre,
                        action.ActionWitnessId)
                    {
                        ExecutionSemanticActionSpace = actionSpace
                    }));
                drafts.AddRange(tracker.Started(action.ActionWitnessId));
                drafts.AddRange(tracker.Finished(action.ActionWitnessId));
                drafts.AddRange(tracker.ObserveDecisionBoundary(
                    new SemanticBoundaryObservation(
                        SemanticBoundaryWitnessKinds.NativeDecisionOwnerReady,
                        DateTimeOffset.UnixEpoch.AddSeconds(1),
                        successor.SnapshotId,
                        "interactive",
                        "complete",
                        successor.InteractionId,
                        successor.InteractionKind,
                        successor,
                        null)
                    {
                        NativeDecisionOwnerReady = new NativeDecisionOwnerReadyEvidence(
                            successor.InteractionKind,
                            "combat-owner",
                            "CombatState",
                            "native-test-owner-ready")
                    }));

                int sequence = 0;
                foreach (SemanticBoundaryTraceDraft draft in drafts)
                {
                    SemanticFrameReference? humanRef = draft.HumanObservation == null
                        ? null
                        : store.PersistSemanticFrame(draft.HumanObservation);
                    SemanticFrameReference? preRef = draft.SemanticPre == null
                        ? null
                        : store.PersistSemanticFrame(draft.SemanticPre);
                    SemanticFrameReference? successorRef = draft.SemanticSuccessor == null
                        ? null
                        : store.PersistSemanticFrame(draft.SemanticSuccessor);
                    ExecutionSemanticActionSpaceReference? actionSpaceRef =
                        draft.ExecutionSemanticActionSpace == null
                            ? null
                            : store.PersistExecutionSemanticActionSpace(
                                draft.ExecutionSemanticActionSpace);
                    store.AppendSemanticEvidenceEvents(new[]
                    {
                        SemanticEvidenceEvent(
                            manifest,
                            ++sequence,
                            draft.Kind,
                            draft.Action) with
                        {
                            ProofStatus = draft.ProofStatus,
                            RelatedActionWitnessId = draft.RelatedActionWitnessId,
                            Boundary = draft.Boundary == null
                                ? null
                                : SemanticBoundaryObservationCodec.Encode(
                                    draft.Boundary,
                                    store.PersistSemanticFrame),
                            HumanObservationRef = humanRef,
                            ExecutionPreRef = preRef,
                            SuccessorRef = successorRef,
                            ExecutionSemanticActionSpaceRef = actionSpaceRef,
                            NativeCompletion = draft.NativeCompletion
                        }
                    });
                }

                SemanticBoundaryTraceDraft proved = drafts.Single(draft =>
                    draft.Kind == SemanticBoundaryTraceKinds.TransitionProved);
                SemanticFrameReference canonicalPre = store.PersistSemanticFrame(
                    proved.SemanticPre!);
                SemanticFrameReference canonicalSuccessor = store.PersistSemanticFrame(
                    proved.SemanticSuccessor!);
                ExecutionSemanticActionSpaceReference canonicalActionSpace =
                    store.PersistExecutionSemanticActionSpace(
                        proved.ExecutionSemanticActionSpace!);
                store.AppendCanonicalTransition(SemanticTransitionProjection.CreateCanonical(
                    proved,
                    canonicalPre,
                    canonicalSuccessor,
                    canonicalActionSpace,
                    manifest.SessionId,
                    manifest.TimelineId));
                if (omitLegacy)
                {
                    long journalSequence = 2;
                    foreach (string kind in new[] { "canonical_transition_recorded", "current_decision_projection_omitted" })
                        store.AppendRunEvent(new RunJournalEvent(
                            CurrentRecordingContract.SchemaVersion,
                            CurrentRecordingContract.RunJournalSchema,
                            $"event-{++journalSequence}", manifest.SessionId,
                            decision.RunId, manifest.TimelineId, journalSequence,
                            DateTimeOffset.UtcNow, kind, $"canonical-{decision.RecordId}",
                            canonicalSuccessor.SnapshotId, "legacy_projection_not_available"));
                }
                actionSpacePath = Path.Combine(session, canonicalActionSpace.ObjectRef);
                store.AppendRunEvent(new RunJournalEvent(
                    2, CurrentRecordingContract.RunJournalSchema, "closed-event", manifest.SessionId,
                    decision.RunId, manifest.TimelineId, 10, DateTimeOffset.UtcNow,
                    "session_closed", null, null, "fixture closed"));
            }

            RecordingAuditResult audit = RecordingSessionAuditor.Audit(session);
            Assert.True(audit.Status == "pass", JsonSerializer.Serialize(audit.Errors));
            string invalidationPath = Path.Combine(session, "invalidations.jsonl");
            string originalInvalidations = File.ReadAllText(invalidationPath);
            var falsePersistence = new InvalidationRecord(2, CurrentRecordingContract.InvalidationSchema,
                "false-persistence", Manifest(Profile()).SessionId, "run-0001", DateTimeOffset.UtcNow,
                "canonical_transition_append_failed", "fixture contradiction", null, "PlayCardAction", "native_human_decision") {
                DecisionFailure = new("execution-semantic-action", "persistence", "ordinary_combat.play_card"),
                Disposition = "failed_closed" };
            File.WriteAllText(invalidationPath, JsonSerializer.Serialize(falsePersistence, EvidenceJson.Options) + "\n");
            Assert.Contains("invalidation_persistence_contradicts_canonical", RecordingSessionAuditor.Audit(session).Errors);
            File.WriteAllText(invalidationPath, originalInvalidations);
            string bundlePath = Path.Combine(root, "canonical-bundle");
            CanonicalSessionBundleResult packed = SessionBundlePacker.Pack(session, "human-001", "canonical-test",
                bundlePath, new string('c', 40), true);
            CanonicalSessionBundleResult retry = SessionBundlePacker.Pack(session, "human-001", "canonical-test",
                bundlePath, new string('c', 40), true);
            Assert.Equal(packed.BundleContentId, retry.BundleContentId);
            Assert.Equal(packed.ChecksumsSha256, retry.ChecksumsSha256);
            JsonNode bundleManifest = JsonNode.Parse(File.ReadAllText(Path.Combine(bundlePath,
                "session-bundle-manifest.json")))!;
            Assert.Equal(CanonicalSessionBundleContract.Schema, bundleManifest["schema"]!.GetValue<string>());
            Assert.Equal(1, bundleManifest["canonical_count"]!.GetValue<int>());
            Assert.Null(bundleManifest["record_count"]);
            Assert.Equal(File.ReadAllBytes(Path.Combine(session, "canonical-transitions.jsonl")),
                File.ReadAllBytes(Path.Combine(bundlePath, "export", "canonical-transitions.jsonl")));
            if (omitLegacy) Assert.Throws<InvalidDataException>(() => SessionBundlePacker.PackCompatibility(
                session, "human-001", "canonical-test", Path.Combine(root, "legacy-bundle"), new string('c', 40), true));
            string exportPath = Path.Combine(root, "canonical-export.jsonl");
            Assert.Equal(1, SessionBundlePacker.ExportCanonical(session, exportPath));
            if (!nativeInput)
            {
                // A current exporter reads schema 2 without upgrading its
                // immutable row to the current writer's schema 3.
                string canonicalPath = Path.Combine(session, "canonical-transitions.jsonl");
                string originalCanonical = File.ReadAllText(canonicalPath);
                JsonNode predecessor = JsonNode.Parse(originalCanonical)!;
                predecessor["schema_version"] = 2;
                predecessor["schema"] = "sts2.human-annotator/canonical-transition-evidence-2";
                string predecessorBytes = predecessor.ToJsonString(EvidenceJson.Options) + "\n";
                File.WriteAllText(canonicalPath, predecessorBytes);
                string predecessorExport = Path.Combine(root, "canonical-schema2-export.jsonl");
                Assert.Equal(1, SessionBundlePacker.ExportCanonical(session, predecessorExport));
                Assert.Equal(File.ReadAllBytes(canonicalPath), File.ReadAllBytes(predecessorExport));
                Assert.Equal(2, JsonNode.Parse(File.ReadAllText(predecessorExport))!["schema_version"]!.GetValue<int>());
                File.WriteAllText(canonicalPath, originalCanonical);
            }
            Assert.Throws<InvalidDataException>(() => SessionBundlePacker.ExportCanonical(session,
                Path.Combine(session, "illegal-export.jsonl")));
            string journalPath = Path.Combine(session, "run-journal.jsonl");
            string sealedJournal = File.ReadAllText(journalPath);
            File.WriteAllText(journalPath, sealedJournal.Replace("session_closed", "session_close_requested"));
            Assert.Throws<InvalidDataException>(() => SessionBundlePacker.Pack(session, "human-001", "canonical-test",
                Path.Combine(root, "open-bundle"), new string('c', 40), true));
            File.WriteAllText(journalPath, sealedJournal);
            File.AppendAllText(Path.Combine(bundlePath, "export", "canonical-transitions.jsonl"), "tamper\n");
            Assert.Throws<IOException>(() => SessionBundlePacker.Pack(session, "human-001", "canonical-test",
                bundlePath, new string('c', 40), true));
            if (omitLegacy && nativeInput && !potion)
            {
                // Faithful append-loss shape: the tracker proof was durably
                // written, canonical append failed, and no compatibility row
                // was attempted. The loss metadata is not a new success row.
                string canonicalPath = Path.Combine(session, "canonical-transitions.jsonl");
                string originalCanonical = File.ReadAllText(canonicalPath);
                string manifestPath = Path.Combine(session, "recording-manifest.json");
                string originalManifest = File.ReadAllText(manifestPath);
                JsonNode currentManifest = JsonNode.Parse(originalManifest)!;
                currentManifest["disposition_schema_version"] = 1;
                File.WriteAllText(manifestPath, currentManifest.ToJsonString());
                File.WriteAllText(canonicalPath, string.Empty);
                File.WriteAllText(journalPath, string.Join("\n", sealedJournal.Split('\n').Where(line =>
                    !line.Contains("canonical_transition_recorded", StringComparison.Ordinal)
                    && !line.Contains("current_decision_projection_omitted", StringComparison.Ordinal))));
                File.WriteAllText(invalidationPath, JsonSerializer.Serialize(falsePersistence, EvidenceJson.Options) + "\n");
                RecordingAuditResult lossAudit = RecordingSessionAuditor.Audit(session);
                Assert.True(lossAudit.Status == "pass", JsonSerializer.Serialize(lossAudit.Errors));
                CanonicalSessionBundleResult failedBundle = SessionBundlePacker.Pack(session,
                    "human-001", "canonical-loss-test", Path.Combine(root, "failed-bundle"), new string('c', 40), true);
                Assert.Equal(0, failedBundle.CanonicalCount);
                File.WriteAllText(invalidationPath, string.Empty);
                Assert.Contains("proved_action_projection_disposition_missing_or_ambiguous",
                    RecordingSessionAuditor.Audit(session).Errors);
                File.WriteAllText(invalidationPath, JsonSerializer.Serialize(falsePersistence with {
                    DecisionFailure = new("unknown-action", "persistence", "ordinary_combat.play_card") }, EvidenceJson.Options) + "\n");
                Assert.Contains("invalidation_persistence_action_missing", RecordingSessionAuditor.Audit(session).Errors);
                File.WriteAllText(invalidationPath, JsonSerializer.Serialize(falsePersistence with {
                    DecisionFailure = new("execution-semantic-action", "persistence", "undeclared-family") }, EvidenceJson.Options) + "\n");
                Assert.Contains("proved_action_projection_disposition_missing_or_ambiguous",
                    RecordingSessionAuditor.Audit(session).Errors);
                string tracePath = Path.Combine(session, "semantic-boundary-trace.jsonl");
                string originalTrace = File.ReadAllText(tracePath);
                JsonNode[] explicitTrace = File.ReadLines(tracePath).Select(line => JsonNode.Parse(line)!).ToArray();
                foreach (JsonNode row in explicitTrace)
                    row["action"]!["decision"] = JsonSerializer.SerializeToNode(new DecisionOccurrenceIdentity(
                        2, "decision-outside-profile", "execution-semantic-action", null, "combat_turn",
                        "outside.capture.profile", "root", null), EvidenceJson.Options);
                File.WriteAllText(tracePath, string.Join("\n", explicitTrace.Select(row => row.ToJsonString(EvidenceJson.Options))) + "\n");
                RunJournalEvent unsupported = new(2, CurrentRecordingContract.RunJournalSchema,
                    "unsupported-event", Manifest(Profile()).SessionId, "run-0001", Manifest(Profile()).TimelineId,
                    9, DateTimeOffset.UtcNow, "canonical_projection_unsupported",
                    explicitTrace[0]["action"]!["record_id"]!.GetValue<string>(), null, "outside.capture.profile");
                string lossJournal = File.ReadAllText(journalPath);
                var journalRows = lossJournal.Split('\n').Where(line => !string.IsNullOrWhiteSpace(line))
                    .Select(line => JsonSerializer.Deserialize<RunJournalEvent>(line, EvidenceJson.Options)!).ToList();
                journalRows.Insert(journalRows.Count - 1, unsupported);
                File.WriteAllText(journalPath, string.Join("\n", journalRows.Select(row => JsonSerializer.Serialize(row, EvidenceJson.Options))) + "\n");
                File.WriteAllText(invalidationPath, string.Empty);
                RecordingAuditResult outsideAudit = RecordingSessionAuditor.Audit(session);
                Assert.True(outsideAudit.Status == "pass", JsonSerializer.Serialize(outsideAudit.Errors));
                Assert.Equal(0, SessionBundlePacker.Pack(session, "human-001", "outside-profile-test",
                    Path.Combine(root, "outside-bundle"), new string('c', 40), true).CanonicalCount);
                File.WriteAllText(journalPath, lossJournal);
                Assert.Contains("proved_action_projection_disposition_missing_or_ambiguous", RecordingSessionAuditor.Audit(session).Errors);
                File.WriteAllText(tracePath, originalTrace);
                File.WriteAllText(canonicalPath, originalCanonical);
                File.WriteAllText(manifestPath, originalManifest);
                File.WriteAllText(journalPath, sealedJournal);
                File.WriteAllText(invalidationPath, originalInvalidations);
            }
            // Reproduce the former producer defect with valid content hashes:
            // admission A(H) is carried into a queued action's execution S.
            // Integrity alone must not admit this historical shape.
            JsonNode staleSpace = JsonNode.Parse(File.ReadAllText(actionSpacePath))!;
            staleSpace["phase"] = "before_native_action_admission";
            string stalePayload = staleSpace.ToJsonString();
            string staleDigest = EvidenceIdentity.Sha256Bytes(System.Text.Encoding.UTF8.GetBytes(stalePayload));
            string oldDigest = Path.GetFileNameWithoutExtension(actionSpacePath);
            string staleRelative = $"semantic-action-spaces/sha256/{staleDigest[..2]}/{staleDigest}.json";
            string oldRelative = $"semantic-action-spaces/sha256/{oldDigest[..2]}/{oldDigest}.json";
            string stalePath = Path.Combine(session, staleRelative);
            Directory.CreateDirectory(Path.GetDirectoryName(stalePath)!);
            File.WriteAllText(stalePath, stalePayload);
            var originalStreams = new Dictionary<string, string>();
            foreach (string name in new[] { "semantic-boundary-trace.jsonl", "canonical-transitions.jsonl" })
            {
                string path = Path.Combine(session, name);
                originalStreams[path] = File.ReadAllText(path);
                File.WriteAllText(path, originalStreams[path].Replace(oldRelative, staleRelative).Replace(oldDigest, staleDigest));
            }
            RecordingAuditResult staleAudit = RecordingSessionAuditor.Audit(session);
            Assert.Equal("fail", staleAudit.Status);
            Assert.Contains(staleAudit.Errors.Keys, key => key.Contains("queued_action_requires_execution_action_space", StringComparison.Ordinal));
            foreach (var pair in originalStreams) File.WriteAllText(pair.Key, pair.Value);
            File.Delete(stalePath);

            if (!omitLegacy)
            {
                foreach (string path in Directory.GetFiles(session, "run-*.jsonl")
                    .Where(path => Path.GetFileName(path) != "run-journal.jsonl"))
                    File.Delete(path);
                Assert.Contains("decision_file_missing", RecordingSessionAuditor.Audit(session).Errors);
            }
            else
            {
                string journal = Path.Combine(session, "run-journal.jsonl");
                string original = File.ReadAllText(journal);
                File.WriteAllText(journal, original.Replace("current_decision_projection_omitted", "unrelated_event"));
                Assert.Contains("decision_file_missing", RecordingSessionAuditor.Audit(session).Errors);
                File.WriteAllText(journal, original);
            }
            File.AppendAllText(actionSpacePath, "tampered");
            RecordingAuditResult tampered = RecordingSessionAuditor.Audit(session);
            Assert.Equal("fail", tampered.Status);
            Assert.True(tampered.Errors.ContainsKey(
                "execution_semantic_action_space_missing_or_changed"));
        }
        finally
        {
            Delete(root);
        }
    }

    private static IReadOnlyList<string> ReadLiveLines(string path)
    {
        using var stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.ReadWrite | FileShare.Delete);
        using var reader = new StreamReader(stream);
        var lines = new List<string>();
        while (reader.ReadLine() is { } line)
            lines.Add(line);
        return lines;
    }

    [Fact]
    public void ReadBatchPreservesCountsAndPayloads()
    {
        string root = Temp("current-read-batch");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            using RecordingSessionStore store = RecordingSessionStore.Create(root, manifest, profile);
            JsonNode content = JsonNode.Parse("{\"cards\":[\"Strike\"]}")!;
            JsonNode completeness = JsonNode.Parse("{\"status\":\"complete\",\"missing\":[]}")!;
            IReadOnlyList<ReadEvidence> reads = store.PersistReads(new[]
            {
                CapturedRead("run_deck", content, completeness),
                CapturedRead("combat_piles", content, completeness)
            });

            Assert.Equal(2, reads.Count);
            RecordingStoreSnapshot snapshot = store.GetSnapshot();
            Assert.Equal(2, snapshot.Counters.ReadsMaterialized);
            Assert.Equal(0, snapshot.Counters.ReadsFailed);
            Assert.All(reads, read => Assert.True(File.Exists(Path.Combine(store.DirectoryPath, read.PayloadRef!))));
        }
        finally
        {
            Delete(root);
        }

        static CapturedReadPayload CapturedRead(
            string kind,
            JsonNode content,
            JsonNode completeness) => new(
            $"read-{kind}",
            kind,
            "snapshot-a",
            "runtime-1",
            "environment-1",
            "materialized",
            $"sts2.player-environment/read/{kind}-1",
            content.DeepClone(),
            completeness.DeepClone(),
            DateTimeOffset.UnixEpoch,
            null,
            null);
    }

    [Fact]
    public void DeclaredDurableCloseRequiresMatchingReceiptDuringAuditAndPack()
    {
        string root = Temp("close-receipt-audit");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile) with { CloseSchemaVersion = 1 };
            string session;
            using (var store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                HistoricalDecisionRecord source = RecordValidationTests.ValidRecord();
                store.AppendDecision(CurrentRecord(source, (
                    PersistReads(store, source.Pre.SnapshotId), PersistReads(store, source.Successor.SnapshotId))));
                store.AppendRunEvent(new RunJournalEvent(2, CurrentRecordingContract.RunJournalSchema,
                    "closed-event", manifest.SessionId, "run-0001", manifest.TimelineId, 10,
                    DateTimeOffset.UtcNow, "session_closed", null, null, "fixture closed"));
            }
            Assert.Equal("pass", RecordingSessionAuditor.Audit(session).Status);
            string manifestPath = Path.Combine(session, "recording-manifest.json");
            string manifestText = File.ReadAllText(manifestPath);
            JsonNode wrongManifest = JsonNode.Parse(manifestText)!;
            wrongManifest["disposition_schema_version"] = 2;
            File.WriteAllText(manifestPath, wrongManifest.ToJsonString());
            Assert.Contains("invalidation_disposition_schema_mismatch", RecordingSessionAuditor.Audit(session).Errors);
            wrongManifest["disposition_schema_version"] = null;
            wrongManifest["close_schema_version"] = 2;
            File.WriteAllText(manifestPath, wrongManifest.ToJsonString());
            Assert.Contains("session_close_schema_invalid", RecordingSessionAuditor.Audit(session).Errors);
            File.WriteAllText(manifestPath, manifestText);
            string receiptPath = Path.Combine(session, "session-close-receipt.json");
            string receipt = File.ReadAllText(receiptPath);
            File.Delete(receiptPath);
            Assert.Contains("session_close_receipt_invalid_or_missing", RecordingSessionAuditor.Audit(session).Errors);
            Assert.Throws<InvalidDataException>(() => SessionBundlePacker.Pack(session,
                "human-001", "close-receipt-test", Path.Combine(root, "bundle"), new string('c', 40), true));
            File.WriteAllText(receiptPath, receipt.Replace(manifest.SessionId, "wrong-session"));
            Assert.Contains("session_close_receipt_invalid_or_missing", RecordingSessionAuditor.Audit(session).Errors);
            File.WriteAllText(receiptPath, receipt);
            Assert.Equal("pass", RecordingSessionAuditor.Audit(session).Status);
        }
        finally { Delete(root); }
    }

    [Fact]
    public void FailureOnlyClosedSessionCanBeAuditedAndBundledWithoutInventingSuccess()
    {
        string root = Temp("failure-only-bundle");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile) with { DecisionSchemaVersion = 2 };
            string session;
            using (var store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                var occurrence = new HumanActionOccurrenceEvidence("accepted-input", "PlayCardAction",
                    "ordinary_combat.play_card", "play", "card-owner", new Dictionary<string, string>(),
                    null, null, null, null, "native_ui", "failed_closed");
                store.AppendInvalidation(new InvalidationRecord(2, CurrentRecordingContract.InvalidationSchema,
                    "failure-only", manifest.SessionId, "run-0001", DateTimeOffset.UtcNow,
                    "pre_frame_capture_failed", "exact accepted Human input had no frame", null,
                    "PlayCardAction", "native_human_decision") {
                    HumanOccurrence = occurrence, Disposition = "failed_closed",
                    DecisionFailure = new("accepted-input", "capture", "ordinary_combat.play_card") });
                store.AppendRunEvent(new RunJournalEvent(2, CurrentRecordingContract.RunJournalSchema,
                    "closed-event", manifest.SessionId, "run-0001", manifest.TimelineId, 10,
                    DateTimeOffset.UtcNow, "session_closed", null, null, "fixture closed"));
            }
            Assert.Equal("pass", RecordingSessionAuditor.Audit(session).Status);
            string output = Path.Combine(root, "bundle");
            SessionBundlePacker.Pack(session, "human-001", "failure-evidence", output, new string('c', 40), true);
            JsonNode packed = JsonNode.Parse(File.ReadAllText(Path.Combine(output, "session-bundle-manifest.json")))!;
            Assert.Equal(0, packed["canonical_count"]!.GetValue<int>());
            Assert.Empty(File.ReadAllText(Path.Combine(output, "export", "canonical-transitions.jsonl")));
            Assert.Equal(File.ReadAllText(Path.Combine(session, "invalidations.jsonl")),
                File.ReadAllText(Path.Combine(output, "raw", "invalidations.jsonl")));
            File.WriteAllText(Path.Combine(session, "invalidations.jsonl"), "malformed\n");
            Assert.Equal("fail", RecordingSessionAuditor.Audit(session).Status);
        }
        finally { Delete(root); }
    }

    [Fact]
    public void CurrentBundleIsPortableDeterministicAndImmutable()
    {
        string root = Temp("current-bundle");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            string session;
            using (var store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                HistoricalDecisionRecord v1 = RecordValidationTests.ValidRecord();
                store.AppendDecision(CurrentRecord(v1, (
                    PersistReads(store, v1.Pre.SnapshotId),
                    PersistReads(store, v1.Successor.SnapshotId))));
            }
            string output = Path.Combine(root, "bundle");
            SessionBundleResult first = SessionBundlePacker.PackCompatibility(
                session,
                "human-001",
                "human-read-rich-2026-08",
                output,
                new string('c', 40),
                true);
            SessionBundleResult retry = SessionBundlePacker.PackCompatibility(
                session,
                "human-001",
                "human-read-rich-2026-08",
                output,
                new string('c', 40),
                true);
            Assert.Equal(first.BundleContentId, retry.BundleContentId);
            Assert.Equal(first.ChecksumsSha256, retry.ChecksumsSha256);
            Assert.NotEmpty(Directory.GetFiles(
                Path.Combine(output, "raw", "blobs"), "*.json", SearchOption.AllDirectories));
            File.AppendAllText(Path.Combine(output, "export", "decisions.jsonl"), "tamper\n");
            Assert.Throws<IOException>(() => SessionBundlePacker.PackCompatibility(
                session,
                "human-001",
                "human-read-rich-2026-08",
                output,
                new string('c', 40),
                true));
        }
        finally
        {
            Delete(root);
        }
    }

    [Fact]
    public void IndependentSessionsNeverShareTheirTimelineOrStore()
    {
        string root = Temp("current-multiple-sessions");
        try
        {
            HumanCaptureProfile profile = Profile();
            using RecordingSessionStore first = RecordingSessionStore.Create(
                root,
                Manifest(profile, "session-first", "timeline-first"),
                profile);
            using RecordingSessionStore second = RecordingSessionStore.Create(
                root,
                Manifest(profile, "session-second", "timeline-second"),
                profile);

            Assert.NotEqual(first.DirectoryPath, second.DirectoryPath);
            Assert.Equal("session-first", first.Manifest.SessionId);
            Assert.Equal("session-second", second.Manifest.SessionId);
            Assert.Equal("timeline-first", first.Manifest.TimelineId);
            Assert.Equal("timeline-second", second.Manifest.TimelineId);
        }
        finally
        {
            Delete(root);
        }
    }

    [Fact]
    public void ReadBlobWriteFailureIsVisibleInStoreHealth()
    {
        string root = Temp("current-write-failure");
        try
        {
            HumanCaptureProfile profile = Profile();
            using RecordingSessionStore store = RecordingSessionStore.Create(root, Manifest(profile), profile);
            JsonNode payload = JsonNode.Parse("{\"cards\":[{\"name\":\"Strike\"}]}")!;
            byte[] canonical = System.Text.Encoding.UTF8.GetBytes(
                "{\"cards\":[{\"name\":\"Strike\"}]}\n");
            string digest = EvidenceIdentity.Sha256Bytes(canonical);
            string blob = Path.Combine(store.DirectoryPath, "blobs", "sha256", digest[..2], $"{digest}.json");
            Directory.CreateDirectory(Path.GetDirectoryName(blob)!);
            File.WriteAllText(blob, "collision");

            Assert.Throws<IOException>(() => store.PersistRead(new CapturedReadPayload(
                "read-run-deck",
                "run_deck",
                "snapshot-a",
                "runtime-1",
                "environment-1",
                "materialized",
                "sts2.player-environment/read/run-deck-1",
                payload,
                JsonNode.Parse("{\"status\":\"complete\"}")!,
                DateTimeOffset.UnixEpoch,
                null,
                null)));
            RecordingStoreSnapshot status = store.GetSnapshot();
            Assert.Equal("failed", status.AppendHealth);
            Assert.Equal("failed", status.DiskHealth);
            Assert.NotNull(status.LastError);
        }
        finally
        {
            Delete(root);
        }
    }

    [Fact]
    public void CanonicalTransitionBindsExactDecisionFramesAndDetectsTampering()
    {
        string root = Temp("current-canonical-transition");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            string session;
            SemanticFrameReference preRef;
            using (var store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                HistoricalDecisionRecord value = RecordValidationTests.ValidRecord();
                CurrentDecisionRecord record = CurrentRecord(
                    value,
                    (PersistReads(store, value.Pre.SnapshotId),
                        PersistReads(store, value.Successor.SnapshotId)));
                store.AppendDecision(record);
                preRef = store.PersistSemanticFrame(record.Pre);
                var successor = new CurrentDecisionFrame(
                    record.Successor.SnapshotId,
                    record.Successor.InteractionId,
                    record.Successor.InteractionKind,
                    record.Pre.SurfaceSchema,
                    record.Pre.CatalogDigest,
                    record.Pre.CatalogCount,
                    record.Successor.Snapshot.DeepClone(),
                    record.Successor.Reads);
                SemanticFrameReference successorRef = store.PersistSemanticFrame(successor);
                SemanticActionReference semanticAction = new(
                    "ui-action-test",
                    record.Sequence,
                    record.RecordId,
                    record.RunId,
                    record.NativeWitness.NativeActionType,
                    7,
                    record.Pre.SnapshotId)
                {
                    NativeMechanism = "direct_ui_commit",
                    BoundAction = record.Action,
                    NativeWitness = record.NativeWitness,
                    Mapping = record.Mapping
                };
                store.AppendSemanticBoundaryEvents(new[]
                {
                    SemanticEvent(
                        manifest,
                        1,
                        SemanticBoundaryTraceKinds.ActionAccepted,
                        semanticAction,
                        record.Pre),
                    SemanticEvent(
                        manifest,
                        2,
                        SemanticBoundaryTraceKinds.BoundaryObserved,
                        semanticAction) with
                    {
                        Boundary = new SemanticBoundaryObservation(
                            SemanticBoundaryWitnessKinds.BeforeHumanActionExecution,
                            DateTimeOffset.UnixEpoch,
                            record.Pre.SnapshotId,
                            "interactive",
                            "complete",
                            record.Pre.InteractionId,
                            record.Pre.InteractionKind,
                            record.Pre,
                            semanticAction.ActionWitnessId)
                    },
                    SemanticEvent(
                        manifest,
                        3,
                        SemanticBoundaryTraceKinds.ActionStarted,
                        semanticAction),
                    SemanticEvent(
                        manifest,
                        4,
                        SemanticBoundaryTraceKinds.ActionFinished,
                        semanticAction)
                });
                store.AppendSemanticBoundaryEvent(new SemanticBoundaryTraceEvent(
                    SemanticBoundaryTraceContract.SchemaVersion,
                    SemanticBoundaryTraceContract.EventSchema,
                    "semantic-proof-test",
                    manifest.SessionId,
                    manifest.TimelineId,
                    record.RunId,
                    5,
                    DateTimeOffset.UnixEpoch,
                    SemanticBoundaryTraceKinds.TransitionProved,
                    semanticAction,
                    "proved_native_commit_then_boundary",
                    null,
                    new SemanticBoundaryObservation(
                        SemanticBoundaryWitnessKinds.CompleteInteractiveObservation,
                        DateTimeOffset.UnixEpoch,
                        successor.SnapshotId,
                        "interactive",
                        "complete",
                        successor.InteractionId,
                        successor.InteractionKind,
                        successor,
                        null),
                    record.Pre,
                    successor,
                    null,
                    Array.Empty<string>())
                {
                    HumanObservation = record.Pre
                });
                store.AppendCanonicalTransition(Canonical(record, preRef, successorRef));
            }

            RecordingAuditResult pass = RecordingSessionAuditor.Audit(session);
            Assert.True(
                pass.Status == "pass",
                JsonSerializer.Serialize(pass.Errors, EvidenceJson.Options));
            File.AppendAllText(Path.Combine(session, preRef.ObjectRef), "tampered");
            RecordingAuditResult tampered = RecordingSessionAuditor.Audit(session);
            Assert.Equal("fail", tampered.Status);
            Assert.True(tampered.Errors.ContainsKey(
                "canonical_transition_frame_missing_or_changed"));
        }
        finally
        {
            Delete(root);
        }
    }

    [Fact]
    public void PreSerializedRecordingRemainsValidWithoutCanonicalStream()
    {
        string root = Temp("current-pre-serialized-compatibility");
        try
        {
            HumanCaptureProfile profile = Profile();
            CurrentRecordingManifest manifest = Manifest(profile);
            string session;
            using (var store = RecordingSessionStore.Create(root, manifest, profile))
            {
                session = store.DirectoryPath;
                AppendJournal(store, manifest);
                HistoricalDecisionRecord value = RecordValidationTests.ValidRecord();
                store.AppendDecision(CurrentRecord(
                    value,
                    (PersistReads(store, value.Pre.SnapshotId),
                        PersistReads(store, value.Successor.SnapshotId))));
            }
            File.Delete(Path.Combine(session, "canonical-transitions.jsonl"));

            Assert.Equal("pass", RecordingSessionAuditor.Audit(session).Status);
        }
        finally
        {
            Delete(root);
        }
    }

    private static CanonicalTransitionEvidence Canonical(
        CurrentDecisionRecord record,
        SemanticFrameReference preRef,
        SemanticFrameReference successorRef) => new(
        CanonicalTransitionEvidenceContract.SchemaVersion,
        CanonicalTransitionEvidenceContract.Schema,
        $"canonical-{record.RecordId}",
        record.SessionId,
        record.TimelineId,
        record.RunId,
        record.Sequence,
        DateTimeOffset.UnixEpoch,
        CanonicalTransitionEvidenceContract.CollectionMode,
        null,
        "ui-action-test",
        "direct_ui_commit",
        preRef,
        record.Action,
        successorRef,
        "canonical_s_a_s_prime",
        new[]
        {
            "complete_execution_state",
            "chosen_action_exactly_once_in_authoritative_action_space",
            "exact_human_native_action_correlation",
            "native_terminal_or_direct_commit_observed",
            "no_intervening_human_mutation",
            "complete_authoritative_successor"
        },
        new[] { "not_business_completion" })
    {
        ActionSpaceAuthority = "public_bound_actions"
    };

    private static HumanCaptureProfile Profile() => new(
        2,
        CurrentRecordingContract.CaptureProfileSchema,
        "human-combat-read-rich-v2",
        CurrentRecordingContract.RecordSchema,
        new[] { "ordinary_combat.play_card", "ordinary_combat.end_turn" },
        new[]
        {
            new CaptureReadRequirement("pre", "run_deck", true),
            new CaptureReadRequirement("pre", "combat_piles", true),
            new CaptureReadRequirement("successor", "run_deck", true),
            new CaptureReadRequirement("successor", "combat_piles", true)
        },
        new[] { "ordinary_combat_only", "not_full_run" });

    private static CurrentRecordingManifest Manifest(
        HumanCaptureProfile profile,
        string sessionId = "session-test",
        string timelineId = "timeline-test") => new(
        2,
        CurrentRecordingContract.ManifestSchema,
        sessionId,
        timelineId,
        DateTimeOffset.UnixEpoch,
        "0.3.0",
        new string('b', 40),
        "osx-arm64",
        profile.ProfileId,
        EvidenceIdentity.Sha256Json(profile),
        profile.SupportedActionFamilies,
        profile.NonClaims);

    private static void AppendJournal(RecordingSessionStore store, CurrentRecordingManifest manifest)
    {
        store.AppendRunEvent(new RunJournalEvent(
            2,
            CurrentRecordingContract.RunJournalSchema,
            "event-1",
            manifest.SessionId,
            "run-unassigned",
            manifest.TimelineId,
            1,
            DateTimeOffset.UnixEpoch,
            "session_started",
            null,
            null,
            null));
        store.AppendRunEvent(new RunJournalEvent(
            2,
            CurrentRecordingContract.RunJournalSchema,
            "event-2",
            manifest.SessionId,
            "run-0001",
            manifest.TimelineId,
            2,
            DateTimeOffset.UnixEpoch,
            "run_started",
            null,
            "snapshot-a",
            null));
    }

    private static IReadOnlyList<ReadEvidence> PersistReads(RecordingSessionStore store, string snapshotId)
    {
        JsonNode payload = JsonNode.Parse("{\"cards\":[{\"name\":\"Strike\"}]}" )!;
        JsonNode completeness = JsonNode.Parse("{\"status\":\"complete\",\"missing\":[]}")!;
        return new[] { "run_deck", "combat_piles" }
            .Select(kind => store.PersistRead(new CapturedReadPayload(
                $"read-{kind}",
                kind,
                snapshotId,
                "runtime-1",
                "environment-1",
                "materialized",
                $"sts2.player-environment/read/{kind}-1",
                payload.DeepClone(),
                completeness.DeepClone(),
                DateTimeOffset.UnixEpoch,
                null,
                null)))
            .ToArray();
    }

    private static (IReadOnlyList<ReadEvidence> Pre, IReadOnlyList<ReadEvidence> Successor) Reads(
        HistoricalDecisionRecord record)
    {
        ReadEvidence Read(string kind, string snapshotId, string suffix) => new(
            2,
            CurrentRecordingContract.ReadEvidenceSchema,
            $"read-evidence-{kind}-{suffix}",
            $"read-{kind}",
            kind,
            snapshotId,
            record.Environment.RuntimeInstanceId,
            record.Environment.EnvironmentFingerprint,
            "materialized",
            $"sts2.player-environment/read/{kind}-1",
            JsonNode.Parse("{\"status\":\"complete\"}"),
            $"blobs/sha256/aa/{new string('a', 64)}.json",
            new string('a', 64),
            DateTimeOffset.UnixEpoch,
            null,
            null);
        return (
            new[]
            {
                Read("run_deck", record.Pre.SnapshotId, "pre"),
                Read("combat_piles", record.Pre.SnapshotId, "pre")
            },
            new[]
            {
                Read("run_deck", record.Successor.SnapshotId, "successor"),
                Read("combat_piles", record.Successor.SnapshotId, "successor")
            });
    }

    private static CurrentDecisionRecord CurrentRecord(
        HistoricalDecisionRecord value,
        (IReadOnlyList<ReadEvidence> Pre, IReadOnlyList<ReadEvidence> Successor) reads) => new(
        2,
        CurrentRecordingContract.RecordSchema,
        value.RecordId,
        value.SessionId,
        value.RunId,
        "timeline-test",
        value.Sequence,
        value.RecordedAt,
        value.Environment,
        "human-combat-read-rich-v2",
        new CurrentDecisionFrame(
            value.Pre.SnapshotId,
            value.Pre.InteractionId,
            value.Pre.InteractionKind,
            value.Pre.SurfaceSchema,
            value.Pre.CatalogDigest,
            value.Pre.CatalogCount,
            value.Pre.Snapshot,
            reads.Pre),
        value.NativeWitness,
        value.Mapping,
        value.Action,
        new CurrentSuccessor(
            value.Successor.SnapshotId,
            value.Successor.Status,
            value.Successor.InteractionId,
            value.Successor.InteractionKind,
            value.Successor.ObservedAt,
            value.Successor.Snapshot,
            reads.Successor),
        value.DecisionFamily,
        value.Surface,
        value.Eligibility);

    private static SemanticBoundaryTraceEvent SemanticEvent(
        CurrentRecordingManifest manifest,
        long sequence,
        string kind,
        SemanticActionReference action,
        CurrentDecisionFrame? humanObservation = null) => new(
            SemanticBoundaryTraceContract.SchemaVersion,
            SemanticBoundaryTraceContract.EventSchema,
            $"semantic-event-{sequence}",
            manifest.SessionId,
            manifest.TimelineId,
            action.RunId,
            sequence,
            DateTimeOffset.UnixEpoch.AddMilliseconds(sequence),
            kind,
            action,
            kind == SemanticBoundaryTraceKinds.ActionAccepted
                ? "human_observation_recorded"
                : "not_a_successful_action",
            null,
            null,
            null,
            null,
            null,
            Array.Empty<string>())
        {
            HumanObservation = humanObservation
        };

    private static SemanticBoundaryTraceEvent SemanticEvent(
        CurrentRecordingManifest manifest,
        long sequence,
        SemanticBoundaryTraceDraft draft) => new(
            SemanticBoundaryTraceContract.SchemaVersion,
            SemanticBoundaryTraceContract.EventSchema,
            $"semantic-event-{sequence}",
            manifest.SessionId,
            manifest.TimelineId,
            draft.Action.RunId,
            sequence,
            DateTimeOffset.UnixEpoch.AddMilliseconds(sequence),
            draft.Kind,
            draft.Action,
            draft.ProofStatus,
            draft.RelatedActionWitnessId,
            draft.Boundary,
            draft.SemanticPre,
            draft.SemanticSuccessor,
            draft.Detail,
            draft.NonClaims ?? Array.Empty<string>())
        {
            HumanObservation = draft.HumanObservation,
            NativeCompletion = draft.NativeCompletion
        };

    private static NativeSemanticDiscriminatorEvent DiscriminatorEvent(
        CurrentRecordingManifest manifest,
        long sequence,
        string phase,
        string actionWitnessId) => new(
            NativeSemanticDiscriminatorContract.SchemaVersion,
            NativeSemanticDiscriminatorContract.EventSchema,
            $"discriminator-event-{sequence}",
            manifest.SessionId,
            manifest.TimelineId,
            "run-0001",
            sequence,
            DateTimeOffset.UnixEpoch.AddMilliseconds(sequence),
            phase,
            actionWitnessId,
            "PlayCardAction",
            7,
            phase,
            "captured",
            "combat_play_phase",
            null,
            null,
            "semantic-catalog",
            Array.Empty<string>(),
            null,
            null,
            null,
            "snapshot-test",
            "interactive",
            "combat_turn",
            "complete",
            1,
            "ui-catalog",
            null,
            null,
            null,
            null,
            Array.Empty<string>());

    private static SemanticEvidenceEvent SemanticEvidenceEvent(
        CurrentRecordingManifest manifest,
        long sequence,
        string kind,
        SemanticActionReference action) => new(
            SemanticEvidenceContract.SchemaVersion,
            SemanticEvidenceContract.EventSchema,
            $"semantic-evidence-event-{sequence}",
            manifest.SessionId,
            manifest.TimelineId,
            action.RunId,
            sequence,
            DateTimeOffset.UnixEpoch.AddMilliseconds(sequence),
            kind,
            action,
            kind == SemanticBoundaryTraceKinds.ActionAccepted
                ? "human_observation_recorded"
                : "not_a_successful_action",
            null,
            null,
            null,
            null,
            null,
            Array.Empty<string>());

    private static string Temp(string name) =>
        Path.Combine(Path.GetTempPath(), $"sts2-{name}-{Guid.NewGuid():N}");

    private static void Delete(string path)
    {
        if (Directory.Exists(path))
            Directory.Delete(path, true);
    }
}
