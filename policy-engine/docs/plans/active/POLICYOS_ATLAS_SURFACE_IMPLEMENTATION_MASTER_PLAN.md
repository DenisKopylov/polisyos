---
title: PolicyOS Atlas Surface & Frontend Implementation Master Plan
status: ACTIVE - Revision 3 grounded in Phase-A measured reality; activation satisfied (GY-N10 merged); Phase B unblocked
owner: team-design
runtime_co_owner: team-architecture  # producers, bridges, and authz enforcement land in runtime code; named per task plan
created: 2026-06-10
revised: 2026-08-21 (Revision 3.26 - A STOP RULE I WROTE WAS TOO BROAD, AND THE STOP IT CAUSED FOUND A REAL UNREGISTERED RED. I told GY-DEF21's executor to run the plain gate on its advanced base and stop if it was 'not clean'. I meant the GENERATED-FRESHNESS verdict; I wrote the COMPOSITE EXIT CODE. architecture guardrails check bundles deep-import baseline checking with generated freshness, so the agent correctly stopped on a nonzero exit whose cause was neither of the things the receipt was about. THE RECEIPT I ACTUALLY WANTED IS GREEN: runtime-api-client 5/5 clean and runtime-dashboard-api-types 1/1 clean against a scratch expected root on advanced main, with the tree byte-clean before and after. GY-DEF20's owed receipt is therefore DISCHARGED and the DEF21 migration is unblocked; the agent stopped on my specification defect, not on a finding, and consumed no round. THE RULE: a stop condition must name the PREDICATE it guards, never the exit code of a command that bundles several predicates - an exit code is a proxy, and P38 says a gate on a proxy misclassifies at its own boundary. This is that pattern turned on me. WHAT THE STOP FOUND is worth more than the delay: deep_import.json is STALE ON MAIN and the required release gate at core-runtime-release-gate.yml:242 EXITS NONZERO because of it, with six creep edges the checker enumerates itself, in channel_contracts, control/lex_pipeline, control/lex_search_projection and scientist checkpoint. NOT caused by DS7, DEF20 or DEF21 - those four files were last touched by the GAP4/run-terminality lane and GY-DEF3, and DS7 replayed the identical identities at two bases with introducers predating it. It matters more now because DEF20 made that same command carry generated freshness, so ONE STALE BASELINE HOLDS A GATE THAT TWO INDEPENDENT PROPERTIES DEPEND ON, and every lane running the required gate reads a red it did not cause. Registered as deep-import-baseline-stale, owner runtime/GY lane, approval team-architecture; closing it is a GOVERNANCE ACT and not a sync, because guardrails sync would silently accept six new deep-import creeps.) | Revision 3.25 - GY-DEF20 IS CLOSED, GY-DEF21'S MECHANISM IS CLOSED, AND ITS MIGRATION TURNS OUT TO BE UNBLOCKED RATHER THAN BLOCKED. Merged at 518e04da5. DEF20: all six generator-observed outputs now owned exactly once across 59 families / 444 entries; the --run-generated-checks opt-in is GONE FROM THE REPOSITORY, so plain architecture guardrails check runs both OpenAPI families by default and the release-gate call site is fixed WITHOUT BEING EDITED - the defect was the default, not the caller. THE REPAIR IS WIDER THAN I ASKED AND CORRECTLY SO: a reviewer found that removing a family's manifest flag reopened the same omission one level deeper, so membership is derived from source_of_truth independently of the flag, which becomes only a checked record; the CLASS is closed, not the instance. I reproduced the corruption witness myself - both families clean against a scratch expected root, then corrupting exactly one scratch output fails runtime-api-client naming that exact family and path while the sibling stays clean, worktree status empty throughout. DEF21 MECHANISM: the owner-qualified generated_schema_property role sits BESIDE an unchanged type_property inside the existing #ts-identity v1 envelope, DS5's 155 identities pinned byte-for-byte, and all six negatives run against the REAL types.ts and the REAL five-candidate LineageRef-Output.status collision rather than a synthetic substitute. THE FIND IS ABOUT MY OWN DEFERRAL. I split DEF21 on 2026-08-21 and wrote a five-part resume trigger for the migration; DS7's merge satisfied EVERY PART OF IT the same day - both clients carry getDepthNCycleBoardProjection, dc3e50a90 is an ancestor, fea50aadd is a newer regeneration touching both, no generator runs, and the register family is free after DS7 released at df0484301 and DS6 at 71b6189de. The migration only LOOKED blocked because the Group A branch stayed pinned at pre-DS7 1e78542f1, whose own tree has ZERO occurrences of the new operation. A DEFERRAL WHOSE TRIGGER IS A REPOSITORY STATE MUST BE RE-EVALUATED AGAINST THE REPOSITORY, NOT AGAINST THE BRANCH THAT OWNS IT - otherwise a lane sits blocked on a condition that was met days earlier in a tree it never looked at. The migration is authorized with its OWN 0/2 budget, because it is the deferred half of a declared split rather than a continuation of an exhausted one. ONE RECEIPT IS OWED AND ASSIGNED: the default-on gate has not been run against DS7's regenerated clients on merged main, since the generator pipeline moved into a new shell script that narrows uv run to a fixed .venv path; the migration executor takes that receipt as its first act because it advances the base anyway.) | Revision 3.24 - DS6-C19 IS LANDED AND THREE STALE SECTIONS OF THE DS6 PLAN ARE CORRECTED. C19 merged at fffd9013a; DS6 STAYS OPEN and only the i18n-plural-rule-covers-only-{count} row closes. Verified before merge rather than on report: an independent whole-object walk reproduces 2,451 leaves / 244 non-count messages / 360 points / 149 names per active locale with frozen ru at 2,449, and the gate FAILS CLOSED ON A REAL NOVEL VARIABLE, not only on its own synthetic negative - injecting {novelAxis} into a live en.json message turned four tests red naming the exact identity, and reverting returned 38/38 on a byte-clean tree. THE DS6 PLAN'S BLOCKERS WERE RECORDED CORRECTLY BUT ITS STANDING WAS STALE IN THREE PLACES, all corrected by superseding note rather than rewrite: the 2026-08-18 standing table still held C03/C04/C06 on DS5-C21 though they landed at b0249e82d and the artifact reads vitest.disposition = resolved; the Contended-governed-writes section still read as pending instructions for work already executed; and a Not-yet bullet claimed C10-R1 needed a clean-tree session, contradicting the same plan's own record that C10-R2 landed at fa1f3e4d0. DS6 IS HONESTLY BLOCKED and by a shorter route than its own table showed - it had already executed what it could by releasing the scoped print repair at 1fc07ed01 under Revision 3.22's debt-row execution rule; what remains is C13's third conjunct, two consecutive green no-update A4 captures, which DS6 cannot supply because the 724x2113 expectation is a placeholder and its replacement is a FIRST DERIVATION owed by DS8. THE FIND: THERE ARE NOW FOUR A4 STATES AND ONLY THREE ARE MEASURED - 13,269 with neither change, 12,966 with DS6's suppression only, 12,949 with DS7's strangle only, and the combination that main now IS is not_established. DS8 must MEASURE it; the 303 px and ~320 px deltas were taken against different baselines and are not established as disjoint layout regions, so subtracting them is arithmetic dressed as evidence. Separately, the closed DS5 plan - which the 2026-08-20 print-scope commit rewrote IN PLACE rather than appending - regains by APPEND the three measured details that rewrite discarded: the run-deck coordinates run-deck-slide-evidence / .atlas-deck-slide in AtlasRunDeck.tsx and styles.css, the three-consecutive-RGBA-equal-capture verification shape whose attached REPAIR is refuted though the SHAPE is not, and the raw 13,269 figure without which the cited 12,966 reads as a baseline when it is a result. The supersession stands and DS5 is not reopened.) | Revision 3.23 - DS7 IS LANDED AND A DEBT ROW THAT NAMED NO IDENTITY WAS REDISCOVERED AT THE COST OF A LANE. The Cycle Board hero merged at 74f26ca2d; Tasks 6-10 closed at 0/2 and Task 5 at 1/2 after a source-contract conflation was found in the route projection. Verified by the architect before merge, not taken on report: the committed owner artifact carries exactly 8 acquisition_route dicts sharing one strict four-key shape, 2 of 3 domain runs carry a route and education is a REAL ABSENCE; there is exactly one production hook caller and one renderer, both CycleBoardPage; authorization is STRUCTURAL rather than conventional, because the query hook lives in an inner component unreachable before the authz decision settles; the MACHINE download is the exact response bytes captured through response.clone().arrayBuffer() in the fetch impl, one request and no reconstruction; all three run-ID inference sites stop reading cycle-board as a run; and all four register-family closing identities reproduce byte-for-byte after the merge. Both protected line-7 bytes are unchanged. THREE ITEMS ARE CARRIED, AND ONE OF THEM IS THE PART THAT GENERALISES. (1) DS7 found two failing runs-API tests, could not attribute them, and correctly declined to own them - but they are NOT NEW: they are the two failures the Control-plane fixture drift row has carried since DS3, which described them only as test_control_api.py-ADJACENT and named no test. Measured at this merge: test_runs_api.py is 42 passed / 2 failed of 44 and test_control_api.py is 60/60 GREEN, so the row's own locator pointed at a green file; both failures enter feedback.py, a DecisionMonitoringContract consumer, which is the root cause the row already names. NO NEW ROW IS OPENED - the existing row is widened with both identities and both observed statuses. THE RULE: a debt row whose subject is a set of failing tests MUST CARRY THE TEST IDENTITIES, or it will be re-found and re-investigated by every lane that trips over it. A denominator without names is not a register entry, it is a rumour. (2) DS7's strangle MOVED THE DS8 A4 BASELINE to 770x12949 against the unchanged 724x2113 expectation, so all three pixel figures in the DS8 entry question are pre-DS7 - and the new baseline already sits BELOW the suppress-the-signed-target figure of 12966 and only 31 px above suppress-everything at 12918. The chrome hypothesis is untouched and weakly corroborated (~320 px removed, the same order as the entire signed-URL contribution), but DS8 must re-derive before computing. Recorded also: the pre-existing 13229 vs 13269 disagreement predates DS7, so DS8 inherits THREE superseded numbers, not one. (3) Full dashboard ESLint is a NON-RECEIPT across four attempts, three at 120 s and one at 300 s, each interrupted having emitted zero diagnostics; no ceiling was widened and no partial result admitted, which is correct handling, and the consequence is that the population outside DS7's write set is NEITHER PASS NOR FAIL and is not inherited as green. Inherited reds stay red and none is relabelled: DS5 run-deck, DS8 A4, DS6-C11, and the thirteen status diagnostics at 511bfd68...17f9.) | Revision 3.22 - DS6's THREE REGISTER TRANSITIONS ARE LANDED and a SEQUENCING ERROR IN THIS PLAN IS CORRECTED. C03/C04/C06 merged at b0249e82d: the i18n baseline lifecycle rebound to repaired against C16's landed 317/317-file, 983/983-test receipt; exactly one typed baseline_test_debt row created for seven source identities through three evidence refs; and that same row transitioned to repaired against the landed C16 contrast release 97d0c6208. The family lock was taken once, held across all three, and relinquished explicitly. Two P40 ladders TERMINATED rather than being patched - C04's gate bound an initializer node instead of the unique module-owned typed runtime export and widened once to a complete owner/use closure with sandboxed transpilation, and a later reviewer found a whitespace-erasing token digest cannot distinguish a one-line return from the same statement split across a newline under automatic semicolon insertion, so the digest became a canonical TypeScript AST print. TWO DEBT ROWS ARE STRUCK as discharged by that work: the inherited Vitest i18n parity row and the four axe-incomplete contrast clusters. THE CORRECTION IS THE PART THAT GENERALISES. DS6 cannot close because C13 waits on the adjacent-print-export repair, and that repair is SIX LINES OF CSS at apps/runtime-dashboard/src/styles/print.css:82-87 - a global a[href]::after rule printing the full signed public-decision URL, which is exactly why the A4 capture blows from an expected 724x2113 to an actual 770x13269. The row is owned by DS8, DS8 is unentered and gated behind DS7, and so a nearly complete slice waits on a container far larger than the work needs. A DEBT-ROW EXECUTION RULE is therefore added: a registered row with an EXECUTABLE CLOSURE SIGNAL is executable independently of its owning slice's ladder position, because ownership assigns responsibility for CORRECTNESS and not the moment of execution. Two corollaries, both measured: a debt owned by a CLOSED slice must be re-owned at closure - DS5 is closed and still owns GY-DEF21 plus the DS4 three canonical-waist vocabularies, the latter VERIFIED still open with CgfDisposition, DecisionGrade and CacheAge returning zero occurrences in the generated client - and a co-owned row may be executed by whichever owner can act, which the adjacent-print-export row already permits because it names DS6 for independent visual and semantic verification. ARCHITECT ERROR RECORDED: GY-DEF21 was registered against DS5 AFTER DS5 had closed, which is the same defect from the other side. AUDITED, not asserted: of the sixteen rows remaining open after the two closures, SIX name an owner that cannot currently act - two on a closed slice, three on unentered slices, one on a team with no live lane. The rule explicitly does NOT authorize re-owning a CAPABILITY away from its real owner; routing GY-GAP3, GY-GAP5 and GY-GAP6 to the GY-N12 lane stays correct, because a capability belongs to the owner that can hold it while a point repair with an executable closure signal is a different object. DS6 remains OPEN: C13 and C14 stay gated on the print repair, independently established semantic non-overlap and two consecutive stable no-update captures) | 2026-08-20 (Revision 3.21 - A LOAD-BEARING CLAIM IN REVISION 3.16 IS CORRECTED. That entry recorded ValueOuterSet as unfoundable, on the grounds that its only construction is an empty placeholder and .compare has zero callers. The GY-PA1 foundability probe measured it by AST rather than by text and REFUTED the first half: there are 2 direct constructions plus 27 interval_box factory calls, SIX of them in production source - generation_cycle.py:4411, data_state_substrate.py:1143 and four academic SKG paths - creating non-empty numeric sets. The architect grepped the constructor form and missed the factory, which is the registered architect-grep-without-structure pattern recurring; the same probe was handed that claim as an anchor fact and correctly refused to inherit it. THE SECOND HALF SURVIVES with its method corrected: seven textual .compare occurrences reduce to five executable AST calls, all schema-evolution, two of the originals being DOCSTRINGS, so zero production callers of ValueOuterSet.compare is confirmed. CONSEQUENCE FOR DS16, which reads this line at re-entry: the value carrier has real content and the correct type is consumer_missing, not unfoundable. DS16's grammar body was still right not to land - its stated re-entry condition is a SURFACE that renders values rather than refusals, and that condition is unchanged and still arrives with DS7 - but the reason recorded for it was partly wrong, and a slice must not inherit a wrong reason even when the decision was right. No task scope changes and no closed slice is edited) | 2026-08-19 (Revision 3.20 - DS5 IS CLOSED AND MERGED at c77888b7c, and the D4-A1 HYPOTHESIS IS CONFIRMED BY MEASUREMENT rather than argued: 56 component failures fell to ONE, which is external DS6-C11, with ZERO assertions rewritten and ZERO snapshot identities re-anchored - exactly the inversion Revision 3.19 predicted and deliberately recorded as a hypothesis to measure. Final surfaces: components 1,188/1,189, Storybook 98/98, accessibility 85/85 component and 21/21 page, visual 17/19 with only DS8 A4 and DS5's own run-deck residual red. THE PARITY RECONCILIATION IS THE MERGE'S REAL WORK: DS6 owns shared/i18n exclusively and had rewritten parity.test.ts on main by +1,741/-52, while DS5 needed 14 lines there for D4-A1; taking either side wholesale would have destroyed the other, and the landed result keeps every DS6 quantitative, plural and count gate with D4-A1 re-applied on top in exactly +7/-2, suite 34/34. DS5 edited a file it does not own and that is recorded rather than absorbed. COMPONENT POPULATION RECONCILED as 1049 - 8 + 3 = 1044 with no test file, skip, quarantine, collection filter, tolerance, config, threshold or snapshot removed, and one genuine find inside it: a widened /unknown/iu oracle tightened to exact Unknown, which is P38 inside a test rather than in a gate. THE ONE OWN DEBT IS NOW EXECUTABLE - three identical captures proved a STABLE 1094x821 layout delta against the governed 1094x820 baseline, so it is a real regression and not flake; owner team-frontend/@frontend-owners, successor dashboard-run-deck-visual-determinism-reconciliation, closure = correct the run-deck-slide-evidence/.atlas-deck-slide border-box height then three consecutive decoded-pixel matches with no snapshot writer. C21 REGISTER RELEASE ISSUED and activated by this merge; DS6's C03/C04/C06 unblock once DS6 rereads the current hashes. Five governed hashes verified by the architect at the branch tip and unmoved by the closeout. ONE ARCHITECT FINDING THAT RE-SEQUENCES DS7's OPENING: GY-GAP4 is source-complete and merges clean, but it changes schemas/runtime_api_v1.openapi.json and regenerates NEITHER client, while runtime-openapi-snapshot and runtime-dashboard-api-types are both registered generated families carrying stale_output_behavior = fail - so merging GAP4 by itself would put main knowingly RED. GAP4 therefore lands INSIDE DS7's opening cluster together with both client regenerations and the receipt re-anchor, under the DS4 rule that the slice regenerating the client re-anchors every governed receipt in the SAME commit. DS16 now CONFLICTS with main since DS5 landed; its reconciliation is its own task and remains the post-merge job Revision 3.17 named. ONE OPS RULE, measured this week: one lane, one worktree, and a shared checkout is never divided - a lane correctly STOPPED rather than switch a branch another lane held, which preserved that lane's uncommitted work and cost nothing) | 2026-08-19 (Revision 3.19 - D4 AMENDED AS D4-A1 BY ARCHITECT DECISION, reversing its primary/baseline relation: en is the PRIMARY locale and authored source of truth, uk is a TRANSLATION of it however accurate, ru unchanged as legacy_continuity_frozen. D4 ratified uk primary on 2026-07-16 at 7b6933770 and said no slice may loosen it - which is precisely why this took an architect decision and not a slice. ARCHITECT CORRECTION RECORDED alongside it: I first read DS5's C05a-R1 locale-default flip as a scope overrun, citing that cluster's one-line summary instead of the ratified decision governing it. That is P36. C05a-R1 implemented D4 AS RATIFIED and is not at fault, and DS5's 56 component failures, 3 accessibility failures and its locale-driven visual identities are the ratified posture meeting verification written against the pre-D4 one - exactly the mechanical follow-up D4's own text predicted. D4-A1 INVERTS that follow-up: verification written against an en default is restored to correctness rather than updated, so the expected effect is that those surfaces return to green rather than needing 56 assertions and 16 snapshot identities re-anchored. That is a HYPOTHESIS to measure, not a plan - the amendment's blast radius is measured before implementation. Also carried from the DS5-C20 attribution audit under P41: Storybook composition is DS5-owned with a proven one-path 65-second repair, the route-readiness accessibility failure is C09a-R2's, two component failures have not_established introducers, and import-policy is confirmed genuinely external at 90 violations [corrected from 100] with the same normalized hash at the slice base despite 34 of 2,567 intersecting inputs. | 2026-08-18 (Revision 3.18 - DS6 CARRIED DEBT recorded at the programme level so it does not live only inside the slice file. DS6's executable set is EXHAUSTED and the slice is blocked_on_another_plan, NOT closed; C14 is deliberately unentered because closing a slice while executable work waits elsewhere is the overclaim DS6 exists to prevent. C10-R2 landed at fa1f3e4d0 - every gated readiness claim now carries its own separately reported basis, no aggregate reconciliation verdict is emitted anywhere, and the CI exit code is the only place a conjunction over rows exists. Three debts survive with named owners: C03/C04/C06 on the DS5-C21 register release, C13's governed transition on a DS8 print repair plus two consecutive stable no-update captures, and transitive-runner-closure-unbound as absent/unallocated after a falsifier over all 9,870 tracked files found no out-of-band runner identity in this repository. Two Start-Now Ladder rows added so the reopening conditions surface where run-order is decided. Also registered in the inherited-Vitest row: atlas-health-metric-replay-pins-uncommitted-paths, where atlasHealthMetrics.test.ts:649 pins pyproject.toml and uv.lock as non-revision paths and is therefore permanently red on a clean checkout - a P38 defect in the test, not a non-receipt, since the measurement succeeded and the expectation is wrong. | 2026-08-18 (Revision 3.17 - the DS16 INHERITED OBLIGATION recorded in Revision 3.16 is CORRECTED: its stated end state is NOT SATISFIABLE and following it produces checker errors, not zero. Measured on codex/atlas-ds5-enforcement-waist at 94e2c8ca0: _validate_c23_containment_roots pins disposition == rebind_pending for every C23 root, so moving the four rows out of it yields four c23_containment_root_drift plus four successor_on_non_rebound [eight errors], while the minimal variant yields four rebound_consumer_missing because ds16SuccessorContainment.test.ts does not exist on the DS5 branch. The pair goes green ONLY in the merged tree, so this is a POST-MERGE reconciliation belonging to the DS16 merge, not a DS5 task; DS5 records it at C20 as a named non-claim. Also corrected: the anchors :1484/:3410 were DS16-branch coordinates - on DS5 the same symbols are at :5558 and :7966, so cite the SYMBOL, not the line. | Revision 3.16 - DS16 AUTHORITY HALF CLOSED as blocked_on_ds5 on branch codex/atlas-ds16-value-grammar; slice plan at docs/plans/active/atlas-slices/. The DS4-C23 producer binding is DELIVERED and its outcome is not the one the DS16 section anticipated: all ELEVEN inventory families - the record's "readiness composition" collapses six distinct builders into one phrase - have NO runtime producer at all, measured with positive controls, so the binding is a typed contract of eleven REGISTERED REFUSALS served over a new additive endpoint [+411/-0], with completeness enforced by a validator that raises on a dropped member. Both panels bound, the C23 containment witness retired with a strangle proof, MACHINE twin with parity read from the RENDERED DOM. THE GRAMMAR BODY COULD NOT LAND HERE and the reason is structural: DS16 surfaces render refusals and carry ZERO quantity references, so nothing is unit-bearing to chip and nothing derived to open a recipe for - C08/C09 have real exercised substrate [32 call sites on build_derivation_recipe] with zero served and could be bridged tomorrow to no consumer here, while ValueOuterSet is unfoundable [only construction is an empty placeholder, .compare has zero callers]. Re-entry condition stated as a PROPERTY: a surface exists that renders values rather than refusals, arriving with DS7. SEQUENCING CORRECTION: the slice table and section gate DS16 on DS4 while the Start-Now ladder groups its value grammar under "DS5 closed" - BOTH ARE PARTLY RIGHT, DS4 defines the grammar and does not let it land. VOCABULARY CORRECTION: the section provenance triple conflates two enums - deployment_update is a BranchMode member, the provenance enum is ObservationProvenanceClass with FOUR members [observed, proxy, derived, model_output], and the served provenance_class carries ParticipationProvenanceClass [ADR-0167, different owner, same field name]. DS5 INHERITS a written obligation: it owns check_frontend_disposition_register.py which pins C23_SUCCESSOR_REFS, so DS5 reconciles the four rebind_pending rows and the stale C23_RATIONALE; the exact end state is recorded in the DS5 section. DS5 lands BEFORE the DS16 branch. | Revision 3.15 - DS5-LINE-ADDRESS-01 is CLOSED and the five waiting clusters are unblocked. C21b-R1 at ceccb0746 [after the append-only restore 055345536] and C21c at db6c4c350 complete the migration; the architect independently reproduced the final census as 270 total refs, 161 TypeScript identities, 6 structured identities and 15 navigation-only line refs across 11 files, and 161+6+15=182 is exactly the pre-migration line-bearing corpus, so nothing is unaccounted. The decisive property is WITNESSED rather than asserted: the real migrated construct moved with NO register update and the full validator returned no errors, while renaming the same construct returned typescript_reference_binding_missing_or_renamed. Both breaker diagnostics adjudicated as non-behavioural on their actual dataflow - F841 was one dead store with zero reads, E731 a capture-free lambda - which is the repaired P38 predicate working on its first use. C21c's own review caught a real P32/P37 escape before landing, a forged absolute or .. source path passing suffix checks and binding outside the repository root, closed with a canonical repo-relative predicate. Sequencing: 10 of 13 collision pairs migrated, the remaining three Workbox refs navigation-only, so C13b-R1, C16a-R1, C16b-R1, C17a-R1 and C19-R1 all proceed. ONE NEW DEBT ROW from DS6, registered by the architect because it would otherwise be prose only: the i18n plural rule covers only {count} and every other interpolated numeric variable escapes the gate, measured in a message DS6-C01-R1 had just certified - P38 in the i18n gate. It does NOT hold DS6-C03's repaired transition, because the registered debt was the three overBudget signatures and this is an adjacent class the rule never covered. | Revision 3.14 - the class repair is executing and one of this plan's OWN procedural rules turned out to be the defect. DS5-C21a LANDED at 015fb8f08; C21b completed its migration - 161 refs moved to encoded #ts-identity bindings, all 161 carrying a discriminator, residual exactly 21 :line refs accounted for as 6 navigation, 6 Python prose and 9 structured/markdown owned by C21c - and was then PRESERVED at 3b0b721a4 and forward-reverted at f0e138d6b under the two-fix breaker, because a final Ruff pass found an unused local and an assigned lambda and repairing either changes checker bytes. That stop was correct in FORM and the rule was wrong in PREDICATE: the breaker exists to detect a wrong MECHANISM and counts rounds that change mechanism BYTES, so RC1 and RC2 consumed it legitimately while a lint diagnostic on working code carries none of that signal. ONE NEW STANDING PATTERN, P38, defined once in the GY plan §3.5.14 and binding on both programmes - a gate that turns on a PROXY misclassifies exactly at its own boundary - with four measured instances, two of them here: file:line as construct identity, and mechanism-byte rounds as evidence of a wrong design. The breaker predicate is REPAIRED in the Execution Doctrine: a round consumes it when triggered by a failing behavioural test, an independent review finding or a governed RED; a round triggered SOLELY by a non-behavioural static diagnostic does not, provided no test outcome and no governed artifact byte changes and that is PROVEN, and never when the diagnostic marks real dead logic. C21b is therefore restored rather than re-cut, and C21c - one mechanism for the 5 JSON and 1 TOML gated refs, Markdown and Python staying navigational - follows it. DS6 runs in parallel on its own light half and owns shared/i18n exclusively. | Revision 3.13 - DS5 landed C13a-R3 at 653f12d08 and its collision census RE-SEQUENCED the slice's internal queue by measurement: 5 of 10 remaining executable clusters touch line-bound evidence [11 files, 13 cluster-file-row pairs], so the DS5-LINE-ADDRESS-01 class repair now runs FIRST and C13b-R1, C16a-R1, C16b-R1, C17a-R1 and C19-R1 wait. NO task scope change and NO closed slice is edited; the annotations land on the Start-Now Ladder and on the Execution Doctrine. The rule is narrow and it is the transferable part: a file:line reference is legitimate as NAVIGATION and wrong as BINDING - a row may cite a line so a human can find the finding, and no gate may fail because the line moved, while the C08 whole-content baseline hashes stay legitimate because they bind identity. Its cause is measured inside one checker: check_frontend_disposition_register.py mints references as path plus current AST line and then compares them byte-for-byte against a descriptor constant, so C13a legitimately moving a surviving operation from line 80 to line 13 invalidated another cluster's evidence and forced the cross-fence repair that cost C13a its cap. TWO architect measurements are carried into the repair because the landed registration does not state them: the corpus must be partitioned BY RESOLVABLE IDENTITY KIND - of 182 refs carrying a line across 73 files in observed_refs plus evidence_refs, 173 are TS/PY and symbol-resolvable, 5 are JSON, 3 Markdown and 1 TOML, where a JSON or TOML line resolves to a key path and never to a symbol, so this is up to FOUR mechanisms and each bespoke mechanism is its own cluster under the standing sizing bar; and the migration denominator is the GATED subset, not the corpus, because a ref no gate compares stays prose and costs nothing. Note the same-week parallel and record it once: in the GY lane GY-DEF13 bound an absolute filesystem path so main could not verify its own artifact, and here disposition evidence binds a line number - two lanes, one defect, the gate turns on an ADDRESS. ONE NEW INFRASTRUCTURE ROW, DS-INFRA-2: the Atlas lane has a measured-timeout LAW since Revision 3.7 and NO measurement substrate, because the governed gates run through pytest/npm and never enter the repository timing log, which holds zero Atlas lanes - measured this round, a full Atlas module was KILLED at 393.15s with no failures and then closed terminal green at 754.20s under a second ceiling. That is GY-DI2 in Atlas clothing in the same week, and its binding negatives are inherited from the GY ruling GY-DI4: a killed run is a non-receipt and never a duration sample, admission is COMPLETION and not success, and no ceiling is enlarged mid-run to make a run fit, and a measured budget encodes CONTENTION so heavy lanes are scheduled and never overlapped. ALSO CLOSED, a routing that had never reached its owner: run-lifecycle-terminal-fact was reassigned to the runtime/GY lane on 2026-08-01 with DS7 as blocking consumer, and measured 2026-08-11 the string appeared 4x in this plan and 0x in the GY plan, so it is now registered there as GY-GAP4 and the debt row points at it. | Revision 3.12 - the public-verification and disclosure kernel PV-K01-PV-K09 is RATIFIED [docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md], the third act after Stage-0 custody and INT-wave claim semantics; its subject is what a public PROOF and a public PROJECTION may mean. NO task scope changes and NO closed slice is edited - the annotation lands only on DS12, whose gate has not opened; DS13, DS14 and GY-PA3 are named routing consumers but are deliberately left unannotated until their contracts are nearer. The headline for this plan: ALL FOUR of DS12's named research inputs are now closeable AS RESEARCH INPUTS - INT-R1 and INT-R9 ratified 2026-08-04, INT-R7 GO_WITH_REVISIONS with its independent closure gate met at 3883b454, INT-R8 accepted_narrow_scope verified CONFORMS at 286ade10, and the R7/R8 seam adjudicated item by item in both directions and holding. The DS12 GATE ITSELF IS UNCHANGED AND CLOSED: research-input closure is not implementation readiness, custody, institutional competence or publication authority, and the first governed promotion plus DS11 are still required. Binding consumption constraints added: consume the verification VECTOR and never a signature Boolean [PV-K01]; a present evidentiary failure never edits the past, so withdrawn-but-verifiable is first-class [PV-K02]; the inherited public-salt 32-bit FNV token is a LIVE DEFECT rather than a weak checksum and its strangling now has a ratified basis [PV-K01/K03]; reuse the real 2,103-line public_export.py producer, which is bridge_missing and not producer_missing; semantic parity is use-relative conservative protected-query parity and never byte equality, with three categorical blockers - bare delta, hidden negative terminal, missing constitutive step - and a link to the full record does NOT repair a misleading summary [PV-K04/K05]; no canonical numerical disclosure claim, the refusal being premise-relative and NOT an impossibility theorem since determinism is explicitly not the obstruction [PV-K08]; and every future proof candidate must discharge the proof-metadata channel, where key identifiers, certificate paths, log positions, witness sets and proof sizes can reconstruct protected content through the proof machinery itself [PV-K09]. One new dependency is visible to this slice: PV-K07 prefix discipline is ratified but NOT ISSUABLE until GY-GAP3 [controlled release-family transcript, registered in the GY plan Rev 26] closes, so DS12 must not present a release history as governed while that owner is absent. | Revision 3.11 - the INT-wave claim-semantics kernel INT-K01-INT-K08 is RATIFIED [docs/system-design-decisions/int-wave-claim-semantics-ratification.md], a separate decision from the Stage-0 custody kernel because its subject is what a NUMBER may mean. NO task scope changes and NO closed slice is edited - the annotation lands only on DS12, whose gate has not opened. DS12 is the wave's largest product consumer and gains four binding constraints plus one settled default. Its INT-R9 gate input is DISCHARGED and resolved to a NONNUMERIC protocol: INT-R9 was amended to Option B [result-informed repair kept, therefore every sequence-level number withdrawn] and independently verified CONFORMS_WITH_GAPS with both carried gaps closed. So DS12 publishes a CUSTODY claim about firstness - prospectivity, sealing, no prohibited substitution, chronology, adjudication, dissent, published negatives - which is checkable and falsifiable and carries no probability at all [INT-K06]; every rendered delta carries its declared obligation set and the relative-basis rider, which ratifies and sharpens the existing Rev-18 P29 rider from a hedge into part of the claim's meaning [INT-K02]; coverage outcomes feed the EXISTING status lattice with no coverage-specific lattice and no bounded_complete shortcut, since issuance needs constructed independence that is dormant research not pending engineering [INT-K01/K03]; and a terminal refusal, void, dispute or exhaustion is a COMPLETED governed result that no deadline or quota may convert into permission to weaken the gate - the surface may publish that it waited [INT-K08]. Architect default settled: DS12 does NOT need a number and should not ask for one, because asking would activate GY-GAP2 engineering and INT-GAP-01 research simultaneously [the protocol keeps adaptive repair, INT-K07] for less than the custody claim already delivers. DS17 is deliberately UNCHANGED - Revision 3.10 recorded the honest steady state correctly before the research proved it had to be that way. | Revision 3.10 - INT-R1 delivered and independently audited, and it settles what the DS17 delta-conditional bullet was waiting for. No task scope changes. INT-R1's result is accepted_narrow_scope carrying a formal IMPOSSIBILITY finding: while an unobserved decisive obligation remains admissible, no finite trace certifies global obligation completeness, so bounded_complete is always relative to a declared closure basis and obligation language, never to the world. Its audit adds the operative constraint - independence is specified but NOT constructed, so the pinned repository cannot issue bounded_complete at all today [INT-R1-D-003]. Therefore DS17's open_world_unresolved chip is NO LONGER a placeholder pending research: it is the honest STEADY STATE until an independent producer, scorer and governance record exist, and DS17 must render it as a settled position with its reason rather than a loading state. When a value does become issuable it renders WITH its basis - declared scope, obligation-language version, cutoff, unknown remainder, TTL - because a bounded_complete shown bare is the same P29 failure as a bare delta. The typed refusal is the deliverable; the value is not owed. | Revision 3.9 - the Stage-0 custody kernel S0-K01-S0-K16 is RATIFIED [docs/system-design-decisions/stage0-custody-kernel-ratification.md]. Two statements are Atlas-binding and both restate laws this plan already carries, so NO task scope changes: S0-K07 [projection cannot mint authority - publication owners produce governed projections, Atlas renders them and must not create, upgrade or resolve authority, and must preserve operator attribution plus current/stale/corrected/superseded/withdrawn meaning as the canonical owner supplied it] and S0-K05 [no authority by observation, transport, or projection]. One consequence lands in the inherited-debt table: the readiness / scientific-depth producer binding row is re-typed from contained defect to a BREACH OF A RATIFIED RULE - DS4-C23 deleted the two dashboard-local synthesis graphs and renders the panels constant unavailable, which contains but does not close it; DS16 remains the owner and its closure signal is unchanged. Also adopted alongside: the Custody Time Model [docs/system-design-decisions/policy-design-custody-time-model.md], whose reuse map states the Atlas rule as "Atlas projects but never owns temporal truth" - relevant to DS15/DS17/DS18 temporal surfaces when they open. | Revision 3.8 - DS-INFRA-1 added to the Execution Doctrine [measured 2026-08-02 on main, warm deps]: typecheck 60.7s across three tsc runs with no --incremental anywhere while running at every cluster boundary and again inside build; full lint >7min cold because _cache is per-worktree so every new slice worktree pays cold once - the wall DS4 kept recording as a tooling non-receipt; quantity:coverage 10.5s with no --cache at all. Three content-hash-invalidated fixes [incremental tsconfigs, --cache on quantity, shared _cache]; sequenced after DS5 merges because it edits tsconfig*.json and package.json inside DS5's fence. Explicitly declined: Playwright workers:1/fullyParallel:false stays [determinism over speed], and cross-process ts.Program reuse is a gated candidate, not part of the task. Done when before/after times are recorded and EVERY denominator is unchanged. | Revision 3.7 - verification-economics doctrine added [Atlas dual of GY plan §3.5.7 E11/E13/E14, measured across DS4/DS5/GY-N11]: freeze-source-then-review-then-run-the-wave-once [a post-freeze review re-prices the whole wave: GY-N11 paid 7 consecutive full-chain reissues for one repair, 47% of its commits were pure receipt churn]; serialize the CONTENDED resource only [Atlas contended set = Playwright/visual, Storybook runner, fixed-port dev server, same governed atlas_surfaces artifact - ESLint/typecheck/Vitest-logic/build/architecture run in parallel]; measured per-suite timeouts as a slice obligation [DS4 repeatedly lost full Vitest and full ESLint to the default ~90s ceiling]; delta-only re-review [182KB/220KB packages exhausted reviewer quota mid-flight in both lanes; DS4's 28KB delta package is the rule]; silent polling [~15 context compactions in one GY-N11 session from per-minute prose]. These change when verification is paid for and how it is observed - they reduce nothing that is verified. | Revision 3.6 - DS4 CLOSED & MERGED 7f450eb7b after architect review: lint 75->0, architecture 36->0 in both engines, status retirement 19->0, temporal-cursor and a11y-census closed; realized 89-component disposition is 27 package / 41 rebind / 18 use-as-is / 3 retire, superseding the pre-Ruling-3 35/42/12 plan - later slices quote the realized split. Closure is baseline-red by design: 3 DS6 i18n parity failures and an honest 17/18 visual with the DS8 print red byte-unmodified. Six debts inserted into the inherited-debt table with owners and executable closure signals: three DS5 canonical-waist vocabularies with generated-client anchors + single swap modules (the register's flag_for_architect_insertion_at_c20 action, now discharged); run-lifecycle-terminal-fact REASSIGNED from the closed DS3 to the runtime/GY lane with DS7 as blocking consumer and a no-re-derivation negative; DS16 readiness/scientific producer binding; DS8 adjacent-print-export; DS6 i18n parity x3 + four axe-`incomplete` contrast clusters (architect-registered because DS4 left them as prose only). DS5 and DS6 gain explicit inherited entry contracts; DS5 is the sole unblocked Phase-B lane. | Revision 3.5 - DS4 stop-law resolution: re-cut authorized as slice clusters C21-C23 (bounded retirement / structural adapters / readiness-scientific containment), and DS16 gains the inherited producer-binding debt for PublicSectorReadiness + ScientificDepth, which DS4-C23 only contains. | Revision 3.4 - identity-decision audit of all post-DS4 slices [governed by docs/system-design-decisions/policyos-identity-and-custody-boundary.md]: DS5 gains the previously-unapplied §6.5 manifest row [M31·M6·M29 weakest-boundary/one-lattice/recompute-not-pin lints] + the INT-R6 semantic-ID locale rule; DS6's honesty-comprehension protocol seeded as the INT-R3 behavioral benchmark joining the stable bar for interactive authority surfaces; DS11 posture anchored in the ratified custodial identity + anti-role negative; DS12's gate extended with the before-first-public-record research inputs INT-R1/R7/R8 + pre-registered INT-R9; DS15 renders non-data gap routes typed [INT-R2]; DS17 renders the δ obligation-set conditional chip [COND(P29)/INT-R1]. | Revision 3.3 - deep-research distillation §6.5 adoption, sequenced strictly after the in-flight DS4: augment bullets on DS9 [M34·M37 delegation packet + contestability-proven], DS12 [M10·M34·M35 + the P29 "risk ≤ δ relative to the declared obligation set" public-claim rider], DS14 [M38·M13 compression-loss surface + cross-projection disclosure budget], DS16 [M16·M23·M24·M26·M33 full-structure/incomparable/authorization], DS18 [M25·M36 perturbation cascade + supersede-not-silent-edit]; their backend producer duals are GY-PA1/PA2/PA3 in the GY plan; the "Rev 18" tag in those bullets cross-references the distillation ledger's move-series, not the Atlas revision number. | Revision 3.2 - DS20 + DS20-B server authorization floor CLOSED & MERGED 03ebc1ce8; typed cross-fence limitations B3/B5/scorecard/Helm registered as debt with owners; DS4 remains the sole active Phase-B parallel lane)
last_reviewed: 2026-07-20
surface_constitution: ../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
atlas_source_of_truth: ../../brand/ATLAS_SOURCE_OF_TRUTH.md
phase_a_synthesis: ../../reference/frontend/atlas-phase-a-synthesis.md   # the Revision-3 input package: per-slice confirmed/re-scoped/invalidated + PI-01..PI-24
phase_a_audit: ../../reference/frontend/atlas-live-application-audit.md  # DS1: the measured reality of record (261-unit ledger, 23 seeded negatives)
phase_a_adjudication: ../../reference/frontend/atlas-v15-adjudication.md # DS2: 233-unit v15 verdicts; adoption-ledger IDs are the only door for v15 material
disposition_register: ../../../architecture/atlas_surfaces/frontend-disposition-register.json # DS19: the disposition authority (261 units) + standalone checker + baseline-debt manifests
organizing_constitution: ../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
source_design_doc: ../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
governed_inventory: ../../../architecture/policy_design_case/cluster_ownership_map.toml
capability_ratchet: ../../../architecture/policy_design_case/capability_reality_report.json
failure_patterns: ../../reference/policy-design-case-failure-patterns.md
workspace_contract: ../../reference/frontend/workspace-contract.md
upstream_plans:
  - ./layer3-slices/GY-engine-subordination.md  # THE active Layer-3 execution plan (Rev 17): supplies the capstone, value gate, ledgers, censuses, acquisition (N13a/b), confidence ledger (N11), epochs (N12), O-block agent
  - ./POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md  # historical G-naming retained in place; DS0 records no execution authority
supersedes_as_execution_master:
  - ./POLICYOS_ATLAS_PRODUCT_MARKETING_CLIENT_SURFACES_MASTER_PLAN.md  # DS0-retained material source for DS11-DS13; no execution authority
  - ../archive/FRONTEND_SOTA_PLAN.md            # archived by DS0; active path is a compatibility stub
  - ../archive/DESIGN_BEST_IN_CLASS_PLAN.md     # archived by DS0; active path is a compatibility stub
evidence:
  atlas_v15_archive:
    path: ../../../design/atlas-v15/PolicyOS_Atlas_Design_System-15_Best_in_Class_Readiness.zip
    sha256: 28d3e51dd452a074d30b7a0afa439302c48d4c208307a6a2d09beb935f71a969
    admission_status: implemented_but_not_orchestrated
scope:
  - design-source-of-truth-admission
  - status-grammar-and-enforcement-waist
  - backend-producers-and-bridges      # in-slice runtime exporters/endpoints; surfaces are full-stack verticals
  - authz-audience-subordination       # PUBLIC/REVIEWER/EXPERT/MACHINE as enforced access classes
  - offline-cache-staleness-discipline
  - proving-ground-board
  - runtime-workspace-deepening
  - capability-discovery-surfaces
  - machine-twins-in-slice
  - trust-docs-posture
  - public-accountability-gated
  - bounded-agent-surface-gated
  - accessibility-performance-evidence-infrastructure
---

# PolicyOS Atlas Surface & Frontend Implementation Master Plan

This plan executes the
[surface constitution](../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md):
it subordinates the frontend, design system, and public surfaces to the runtime
authority discipline, closes `surface_missing` capability links, and admits the
Atlas v15 archive as a governed substrate through the same admission logic the
runtime uses for engines. Atlas renders the authority system; it never produces
authority. DS0 source ownership and governing decisions live once in the
[Atlas source-of-truth record](../../brand/ATLAS_SOURCE_OF_TRUTH.md).

**A surface here is a full-stack vertical, not a React layer.** Every slice
carries its capability from the typed runtime contract through the producer
(runtime exporter or HTTP endpoint), the OpenAPI schema, the generated client,
the UI, and the evidence — because most of the artifacts this plan renders
(capability reality report, cluster map, conversion records, adapter registry)
exist today only as repository files with **no HTTP producer**. Building those
producers and bridges is in-slice work, never an external dependency to wait
on.

## Read This Before Anything Else

**Revision 2 (2026-07-16) — this IS the re-derivation.** The Layer-3 closeout
the original draft waited for has happened, under GY naming: the **GY-N
campaign** (docs/plans/active/layer3-slices/GY-engine-subordination.md, Rev 17)
closed GY-N4–N10 — the full plain-language → generate → ground → simulate →
value → promote cycle is contract-generic across domains, with a frozen
**depth-N universality capstone** (three plain-language runs, three honest
`acquisition_required` terminals with structurally distinct evidence classes),
a 55/390-method value gate, a disposition ledger, two censuses, and the CGF
grounding firewall. The measured system truth: **the machinery is universal and
honest; the substrate is thin; every gap routes to a typed, costed acquisition
plan.** The GY plan's next wave (N13a/N13b acquisition execution → N11
confidence ledger → N12 epochs → Phase-6 learning loop) is exactly the future
data this plan's later surfaces render.

**Revision 3 (2026-07-16) — grounded in Phase-A measured reality.** Phase A
(DS0 governing decisions, DS1 exhaustive live-application audit, DS2 v15
adjudication) is **closed and merged to main** (merge ed74537e8), and GY-N10 is
**merged to main** (7e035a426, GO-CONFIRMED capstone 6fcbd2c11) — **the
activation gate is SATISFIED and Phase B is unblocked.** Revision 3 exists for
one reason: to ground every remaining slice in what the code measurably IS,
and to make false confidence in the system's current abilities structurally
impossible. Three consequences:

1. **The denominators of record are the Phase-A artifacts, never estimates.**
   The measured reality: 944 TS/TSX files (145,033 LOC); 32 route objects / 29
   effective patterns; 17 features; **89 shared/UI implementations in 12
   families (none `stable`)**; 89 OpenAPI operations (45 surface-consumed, 7
   hook-only, **37 uncalled**); **47 UI-local status definitions**; 29/29
   mutating operations without action-permission or step-up; two API-client
   homes; a forgeable browser-side public "signature"; a red structural a11y
   gate; v15 = 233 adjudicated units with **0 `admit_as_is`, 0 `stable`**. Any
   task plan that assumes a capability not backed by the DS1 readiness ledger
   or the DS2 adoption ledger is wrong by construction.
2. **The Phase-B thesis is sharpened**: not "build a system and migrate the
   app" but **project governed runtime truth through ONE client/package waist,
   rebind the useful living families, selectively consume admitted v15
   material by adoption-ledger ID, and strangle every duplicate or false
   owner.** The living v4 estate is the transitional production winner until
   item-specific DS4/DS6 gates close.
3. **Per-slice re-scoping is defined once** in the
   [Phase-A synthesis](../../reference/frontend/atlas-phase-a-synthesis.md)
   (confirmed / re-scoped / invalidated + `PI-01`..`PI-24` per slice) — task
   plans consume it directly; this roadmap does not restate it.

**Activation status (Revision 3).**

- Phase A: **closed** (DS0/DS1/DS2 merged).
- Phase B: **ACTIVE** — DS3 (and DS19, which gates only on DS1 evidence) may
  start now; DS20 starts after DS3.
- Later slices keep their **explicit GY gates** (N13b, N11, N12, first
  governed promotion, Phase-6 agent) stated per slice and in the start-now
  ladder below. GY-N13a is closed on its branch (census artifact + live-probe
  journal) pending architect acceptance; its measured result — **all three
  capstone routes recompute to `not_a_data_gap` (grounding-relation/estimand
  gaps, not row gaps)** — is already reflected in the DS7/DS15 notes below.

**Execution granularity (roadmap vs task plans).** This document is the
**roadmap**: strategy, sequencing, doctrine, the dependency DAG, and the
per-slice closure contract. It is **not** the coding spec. When a slice reaches
the front of the DAG, expand its closure contract into a separate executable
task plan under `docs/plans/active/atlas-slices/DS{N}-*.md` — exact files, typed
contracts, exact test names (negatives written red-first), exact validation
commands, **and the named backend deliverables with their runtime co-owner**.
Task plans are written just-in-time; shared machinery is defined once in
DS0/DS3/DS4 and referenced.

**Sizing principle.** Slices target comparable effort: one task plan, one
closure contract, one review each. If execution reveals a disproportionate
slice, the roadmap is amended and slices are re-cut with continuous numbering —
never suffixed (`DS7a`) and never silently inflated.

**Ownership.** `team-design` owns the plan and the surfaces; producers,
bridges, schema changes, and authz enforcement land in runtime code and are
co-owned with `team-architecture`. A task plan that needs a producer or
endpoint **names it as its own deliverable** with both owners — "blocked on
backend" is not a valid slice state in this plan.

**Honesty defaults.** No slice claims a surface is implemented without the full
capability chain. Fixture data is typed and visually marked `fixture_only` and
never occupies an authority slot. Cached data renders with its staleness.
Public gates are constitutional, not schedule-driven.

## Input Contract — What This Plan Consumes From The GY Campaign (Revision 2)

All GY artifacts are frozen JSON contracts under
`architecture/policy_design_case/` with **recomputing validators, byte-stable
canonical writers, corrupt-drift lanes, and source-flip harnesses** — the
strongest producer substrate a surface plan has ever had here. The HTTP
producers are thin projections of already-verified artifacts, never new logic.

| Input | Source artifact (GY name) | HTTP producer today? | Feeds | Status (2026-07-16) |
| --- | --- | --- | --- | --- |
| Typed terminal + evidence vocabulary: `SearchTerminalState`, evidence classes (`owner_acquisition_route` / `estimand_binding_refusal` / `owner_data_gap`), decision grades, CGF dispositions (`bound`/`shadow_bound`/`candidate_unbound`), acquisition strategies (ADR-0166) | core contracts + the capstone validator's structural recomputation (`_domain_evidence_kind` pattern) | partially (runtime contracts) | DS4 grammar binding; every surface | **live** — frozen + recomputed, not pinned (GY §3.5.10) |
| Depth-N universality capstone: three plain-language runs, per-stage traces, embedded proof recordings, per-domain terminal distributions | `layer3_gy_depth_n_universality_contract.json` | **no — built in DS3** | DS7 Cycle Board hero rows; DS8 drill-down | live on N10 merge (final audit in flight) |
| Value gate: 390/55 method denominator, advisor selection receipts, `ValueOuterSet` (set-valued, `unknown`/incomparable), six-family projections, transport receipts | `layer3_gy_value_gate_contract.json` | **no — built in DS3** | DS16 value grammar; DS7 columns | live on N10 merge |
| Disposition ledger + engine census + Fork-B CG1/L2 census (13,092 relations, 0 admissible positives) | `layer3_gy_generation_cycle_disposition_ledger.json`; census artifacts | **no — built in DS3** | DS7 columns; DS10 discovery; honesty copy | live on N10 merge |
| Acquisition routes with costed plans (N7 planner reports: strategy, cost, VOI, requirement gap) | capstone terminals + `layer3_gy_acquisition_contract` artifacts | **no — built in DS3/DS15** | DS15 refusal-with-a-path; DS7 route column | live on N10 merge |
| Acquisition-layer census: connector scorecard, liveness map, catalog↔runtime metric resolution, D2 growth backlog (VOI-ranked) | GY-N13a census artifact | **no — built in DS15** | DS15 growth surfaces | **pending GY-N13a** |
| World growth: epoch-stamped overlay store, admission passports, quarantine, re-entry traces, derivation certificates + basis vocabulary (GY §3.5.12) | GY-N13b artifacts | **no — built in DS15/DS16** | DS15 live loop; DS16 derived-data provenance | **pending GY-N13b** |
| Confidence ledger: δ-budget, risk-spend per obligation class × instrument, refusal/acquisition instruments as first-class rows | GY-N11 ledger artifact | **no — built in DS17** | DS17 | **pending GY-N11** |
| Epochs: stale certificates, `revalidation_required`, revision triggers, OpenWorldRisk | GY-N12 artifacts | **no — built in DS18** | DS18 chrome; every time-bearing surface | **pending GY-N12** |
| 13-case proving ground (legacy honest signal; still real) | proving-ground artifacts | **no — built in DS3** | DS7 legacy rows | live |
| Bounded-agent contract + orchestration-choice audit ledger | Phase-6 O-block contracts | **no — built in DS14** | DS14 | **pending Phase 6** |
| Updated cluster ownership map (`surface_missing` inventory) | `cluster_ownership_map.toml` | **no — built in DS3** | backlog generator #1; closure targets | live; refresh at N10 merge |

The "no HTTP producer" column is the honest bridge debt this plan owns. Two
binding rules inherited from the GY plan apply to every producer built here:
**§3.5.10 recompute-not-pin** (surface payloads carry recomputed structural
properties, never pinned terminal labels) and **§3.5.11 projection-scoped
provenance** (a surface producer binds to the narrowest upstream projection
hash, so GY artifact churn does not ripple through every endpoint).

## Code-Grounded Technical State (Snapshot 2026-06-10; DS1 Recount 2026-07-16)

A deep pass over the app, the client package, and the runtime HTTP layer was
made before activation. The expected pattern — rich content, weak
orchestration — holds, but in a sharper form: **the components are excellent
and the semantics are parallel.** The dashboard is a large, tested, accessible
system that grew its own semantic universe disconnected from the runtime
authority machinery. The dominant work of this plan is therefore **rebinding
and subordination, not greenfield building.**

| Area | What exists (anchors) | What is missing / divergent | Feeds |
| --- | --- | --- | --- |
| Scale & quality infra | dashboard `src`: 908 TS/TSX, 136,827 LOC, 230 `.test` + 3 `.spec`; full frontend zone: 944 TS/TSX, 145,033 LOC, 251 test/spec files; 44 stories; 89 `shared/ui` implementation TSX in 12 families; 67 `.a11y.test`, 390 `aria-` usages, 17 e2e specs, 16 visual baselines | structural shared/UI a11y gate is currently red; route axe covers 17/22 leaf patterns; no manual-AT record or evidence storage/cadence; zero families meet the `stable` bar | DS4, DS6 |
| Typed waist | `openapi-fetch` `createClient<paths>` over generated types with auth-aware fetch and API events (`src/api/client.ts`); 4.4k-line generated TS package client; 89 OpenAPI operations: 45 surface-consumed, 7 hook-only, 37 with no dashboard call; reference shell consumes 8 overlapping operations through the package client | dashboard and reference shell use two client homes; 9 raw `fetch` calls in 5 production files outside `src/api` (Lex is no longer one); **no endpoints** for capability report, cluster map, conversions, adapter registry, public records | DS3, DS5 |
| Status semantics | 23 named + 24 inline UI-local status definitions; `DisputeStatus` defined three times as two vocabularies (`runs/domain/disputes.ts`, `shared/ui/quantity/quantity.types.ts`, `shared/ui/trust-view/trust-glyphs.ts`) | **zero authority-lattice statuses anywhere in the app**; operational and authority-adjacent states share namespaces; P04 is materially broader than the ≥8 recon inventory | DS4, DS5 |
| Evidence ontology | `quantity.types.ts`: `VerificationMetadata` (hash, status, freshness, dispute), bitemporal `TemporalRef`, `LineageRef`, `QuantityClass` (`decision`/`telemetry`/`layout`/`debug`); `ProvenanceStrip`, `trust-view` glyphs, `temporal`, `counterfactual`, `authored-text` families; compounds incl. `DecisionCard`, `EvidenceChain`, `ExplainabilityCard`, `AttributionWaterfall`, `DataFreshnessBadge` | an entire **parallel evidence vocabulary**, UI-local, not bound to runtime contracts | DS4 |
| Publication | `publicationPacket.ts` (~1.4k lines): Toulmin maps and projection normalization; three run-detail builders produce a packet and exactly one link emits a payload + public-salt 32-bit FNV hash in the URL; browser recomputation alone renders `Verified` | forgeable by construction; structural validator does not bind packet hash; private-data scan is not on the builder path; no server signing/verifier/public-record producer or persisted public dependency | DS1, DS12 |
| Authz | `/api/v1/auth/me` with 12 server permission keys; client has 15 and workspace/tab gating; selected handlers enforce tenant ownership; coarse path/role OPA is optional | **29/29 POST operations have no action-permission or step-up dependency**; resource is bound after OPA reads it; client-only collaboration permission delta ×3; fixture identity and 11-permission UI placeholder fail open; production approval accepts self-asserted reviewer/signature | DS5, DS9 |
| Offline | Workbox precaches static assets and denies API caching; IndexedDB has exactly composer drafts + promotion queue; approve/reject is the only queued mutation class and is optimistically finalized/replayed | no live state/permission/step-up/tenant/epoch revalidation; six authority-looking local caches lack tenant+user+expiry+epoch binding; cache freshness rendering absent | DS1, DS5 |
| i18n | `en`/`uk`/`ru` catalogs have structural parity; DS0 measured 2,449 string leaves each, while 80.16% of `ru` equals English; runtime capability contracts admit `en`/`uk` | **D4 RATIFIED 2026-07-16** (`7b6933770`): `uk` primary + `en` baseline + **`ru` = `legacy_continuity_frozen`, not used, not deleted**. The gate is discharged — DS5's locale/semantic-ID lint and DS12's locale claims may proceed against the ratified posture, and no slice may loosen it. Open work is mechanical, not decisional: `parity.test.ts` still enforces full en/ru/uk key parity and must move to the frozen-set rule (**DS6**, with the 3 inherited `overBudget` failures)  **D4-A1 AMENDED 2026-08-19 by architect decision, and this REVERSES D4's primary/baseline relation**: `en` is the **primary** locale and the authored source of truth; `uk` is a **translation** of it, however accurate; `ru` is unchanged as `legacy_continuity_frozen`. Reason: a translation relation makes the authored language primary and the rest derived — `uk primary` inverted that and made English content a translation of Ukrainian, which is not how this product is authored. D4's own "no slice may loosen it" stands and is why only an architect decision can amend it. CONSEQUENCE, and it inverts the follow-up work D4 anticipated: verification written against an `en` default is **restored to correctness**, not updated. DS5's `C05a-R1` implemented D4 **as ratified** and is not at fault; its 56 component, 3 accessibility and locale-driven visual failures are the ratified posture meeting verification written against the prior one. The blast radius of this amendment is measured before implementation, not assumed. | DS5, DS6, DS12 |
| Tokens / design system | `shared/ui/tokens/designTokens.ts` + `AtlasV4Reference.stories` — a living, coded v4; theming `light`/`dark`/`system` + density preferences | DS0 selects future one-way DTCG generation and sunsets hand-maintained TS authority; v15 values/modes remain unadmitted until DS2 and no migration occurs before DS4 | DS2, DS4 |
| Agent surface | `features/clerk` is an app-level interface mode over `POST /control/runs/nl`; live path launches a run and consumes SSE status only; persisted store/renderers contain structured verdict/confidence/diff and `AIDiffView` | structured response and diff have no live producer (`producer_missing`) and would launder candidates if wired as-is; duplicate direct `/` index route is redundant; G6 contracts and storage partition absent | DS1, DS14 |
| Realtime & off-contract endpoints | two real `include_in_schema=False` SSE routes; real review WS hub with three channels; collaboration client declares four REST pairs + four WS channels | review WS browser-auth bridge is absent/undocumented; collaboration server producers are absent, but the whole feature is orphaned so current live UX does not call them; every admitted channel lacks one governed registry | DS1, DS3, DS5 |
| Feature flags & shadow shipping | 12 manifest keys, all defaults true, plus auth-derived `enableReviewCollaboration`; exactly four keys have no production read | causal/command-palette/what-if surfaces remain live outside their missing flags; collaboration feature is orphaned; unknown manifest keys are ignored; DS5 must strictly separate rollout from authz and wire-or-retire four gates | DS1, DS5 |
| Observability & audit | app-wide configurable beacon plus production-only Sentry (`sendDefaultPii:false`); both attach full path/route context and arbitrary payload/extras; server-side append-only access audit, compliance export/retention, CSRF | public-route no-tracker/redaction unproven; signed IDs/run/artifact refs can enter transport context; environment supplies destination ownership; review-effectiveness telemetry not yet drawing on audit trail | DS6, DS9, DS12 |
| Discovery seeds & machine exports | `GET /control/capabilities` (live endpoint), `control/data/catalog/search`, lineage exports (`openlineage`, `prov`), artifact packet export/render, decision-validity endpoints | the capability manifest is a **hand-maintained `CapabilityFeatureInfo` enumeration** in `services/control/capabilities.py` — a live Rule-12 violation; exports cover lineage/packets, not the Layer 3 artifacts | DS3, DS10 |
| Non-web surface artifacts | `packages/cli` styleguide plus email/print/CLI/bureaucratic/glyph/motion/contrast specs | DS0 assigns them to DS2/DS3/DS4/DS6/DS8; email alone is explicitly `surface_out_of_scope` until a typed notification/privacy/delivery slice exists | DS2, DS3, DS4, DS6, DS8 |

Three consequences are folded into the slices below:

1. **DS4 is a rebinding slice, not a component-building slice.** The
   evidence-bearing primitives largely exist; what they lack is binding to the
   authority lattice and the retirement of UI-local vocabularies.
2. **DS2 adjudicates two living systems, not one archive.** The repo already
   runs a coded v4 (tokens + 89 implementation TSX in 12 families with uneven
   a11y/story evidence); v15 admission
   is a migration between two real systems, not an import into a void.
3. **DS12 replaces a decorative mechanism, not a missing one.** Client-side
   "signing" is a useful UX prototype and a live overclaim risk at once; the
   slice's first negative is that a forged packet must stop rendering as
   "Verified".

## Backlog Generators (where slice scope comes from)

Slice deliverables are **derived, not invented**, from three machine-readable
sources:

1. **`surface_missing` / `implemented_but_not_orchestrated` links** in the
   cluster ownership map — the runtime's debt to the glass.
2. **DS0–DS2 adoption-ledger verdicts** — the design system's debt to the
   repo: which v15 components/tokens/patterns are admitted, deferred, or
   rejected.
3. **The `[to build]` enforcement column** of the surface constitution's
   Derived Surface Laws — every named-but-missing lint, test, or registry is a
   first-class deliverable of a named slice.

A deliverable that traces to none of the three generators is out of scope
(anti-P13: contract gravity well). The traceability is recorded per slice.

## Execution Doctrine (every slice obeys these)

- **Vertical and full-stack, with a full closure contract.** Each slice carries
  surfaces end-to-end and must satisfy: **producer** (runtime exporter/endpoint
  — built in-slice when missing) → **persisted artifact** → **bridge** (OpenAPI
  schema → `packages/runtime-api-client` regeneration) → **consumer**
  (route/component) → **verification** (unit, contract, browser, visual,
  accessibility — matched to risk) → **surface**
  (PUBLIC/REVIEWER/EXPERT/MACHINE or explicit out-of-scope) → **negative +
  semantic test**. A missing link is named precisely, never rounded up — and if
  the missing link is a producer or bridge, building it is this slice's work.
- **The MACHINE twin ships in-slice.** Every surface slice delivers its own
  MACHINE projection (typed export, replayable packet, stable URL) using the
  shared export machinery from DS3, with a surface↔twin parity test. A surface
  without its twin does not close — there is no separate "twins later" slice.
- **Audience is access control, not styling.** PUBLIC/REVIEWER/EXPERT/MACHINE
  map to authz permission classes through one define-once mapping (DS5),
  enforced **server-side**. The UI may hide what the server denies; it never
  substitutes for the denial. Rendering an audience without enforcing it is
  laundering.
- **Cached and offline state is honest state.** Anything served from a cache,
  service worker, or offline store renders with its as-of/staleness posture.
  Authority-bearing actions (approval, promotion, publication, revocation)
  never execute from an offline queue without explicit revalidation against
  live state.
- **Laws traceability.** Each slice names the surface-constitution laws (1–12)
  it operationalizes and the `[to build]` enforcement it lands.
- **Pattern-pass negatives.** Each slice carries laundering negatives with
  exact register IDs (P01, P03, P04, P05, P06, P10, P13, P15, P25, P26 as
  applicable), written red-first in the task plan.
- **Real data or marked fixture.** `fixture_only` data is typed, visually
  marked, lint-enforced, and barred from authority slots. Demo data presented
  as live state is P05 at the surface level.
- **Define once, reference.** Grammar, registries, ledgers, mappings, and lints
  live in DS0/DS3/DS4/DS5 and are referenced; no slice re-derives vocabulary
  (anti-P13, constitution Rule 10).
- **Strangle, don't fork.** Changes land in `apps/runtime-dashboard`. A
  parallel rebuild is P06 in code form.
- **The ledger is updated at closure, and CI checks it.** Every slice closure
  updates the surface readiness ledger; a CI validator (DS6) compares ledger
  claims against the tests and evidence that actually exist — the surface
  analogue of the Layer 3 readiness validator.
- **Accessibility evidence is proportional and real.** Archive lint never
  counts as evidence (P10). `stable` components need WCAG 2.2 AA intent, APG
  behavior for custom widgets, browser + keyboard evidence, and manual
  assistive-technology evidence for high-risk patterns.
- **Engineering quality is not optional.** Generated typed client only;
  established libraries over hand-rolled equivalents; performance budgets on
  public routes; deterministic visual regression; fail-closed error rendering.
- **"Not yet" is mandatory.** Every slice states what it explicitly does not
  claim, in the slice plan and in the surface readiness ledger.
- **Seeded negatives are binding task-plan inputs (Revision 3).** DS1 seeded 23
  red-first negative specs (`N001`–`N023`, indexed in the live-application
  audit). A slice that owns any of them **must implement its negatives
  red-first before rebinding or building** — a task plan that starts its
  positive work with its seeded negatives unwritten is not accepted.
- **v15 enters only by adoption-ledger ID (Revision 3).** No v15 path may
  enter a task by package/folder membership; the DS2 ledger row (verdict,
  maturity, consuming surface, rejected deltas) is the only door, and archive
  maturity labels never transfer.
- **The frontend disposition law (Revision 3; the GY-N0 dual).** Every unit of
  the existing estate is eventually **used-as-is, rebound, or deleted** through
  the DS19 disposition register — never left as a live parallel owner. A
  successor closes only when a real consumer exists AND the old owner path is
  proven strangled (the P27/P28 duals on the glass). **The register is now
  LIVE** (`architecture/atlas_surfaces/frontend-disposition-register.json` +
  standalone checker): 261 units — 15 deleted, 200 `rebind_pending`, 25
  `retire`, 16 `wire`, 5 `use_as_is`.
- **Work preservation and history discipline (Revision 3.8; the DS5 lesson — full statement
  in GY plan §3.5.13 and `AGENTS.md`).** Two incidents in one slice put **reviewed,
  completed** work where git does not protect it. Neither was a reasoning failure.
  - **Uncommitted work is not storage.** Commit at every clean boundary. A stash is a
    transient for minutes, never a place to leave work across a stop, a handoff, or a
    context compaction. DS5 left 1,236 insertions of independently reviewed plan work in
    `stash@{0}` for a whole session while a rejected commit sat at HEAD.
  - **Branch history is append-only.** No `rebase`, `reset --hard`, `reset` onto an
    ancestor, `push --force`, `stash drop`/`clear`, or any `checkout` that moves HEAD off
    current work. **One exception:** `--amend` on the immediately preceding commit you
    authored this session and have not handed to review. A `rebase` left the DS5 **worktree
    in detached HEAD** two commits behind its own branch; the branch ref never lost anything
    (its reflog is forward-only), but a full session ran against the stale HEAD. **A detached
    worktree is invisible in ordinary output** — `git log -1` and `git status --short` look
    normal; only `git status -sb` or `git symbolic-ref -q HEAD` show it, and a commit made
    there is orphaned. Verify branch attachment, not just cleanliness, at session start and
    before every commit.
  - **A validator demanding a clean tree is satisfied by committing, not stashing.** That
    fence is legitimate; stashing to clear it is how reviewed work ends up unprotected.
  - **Unexpected history is an architect stop, not a self-repair.** The reflog makes these
    recoverable; improvised recovery is how a recoverable incident becomes permanent.
  - **No plan instruction names a commit hash** — name the relationship ("the immediately
    preceding commit you authored"). The DS5 plan said in four places that `b67084dd6` "is
    amended down"; true when written, impossible after a legitimate recovery moved HEAD past
    it, and literally following it would have required the very rewrite that caused the loss.
    Architect instructions prefer **forward-only** framing ("land the reduction as a commit").
    After any history-affecting recovery, re-read the task plan for instructions that
    referenced the pre-recovery state and correct them in the next commit.
- **Verification economics (Revision 3.7; measured across DS4/DS5 and the GY-N11 lane —
  the Atlas dual of GY §3.5.7 E11/E13/E14).** These rules change **when** verification is
  paid for and **how** it is observed. They reduce nothing that is verified; a slice that
  cites them to skip a gate has misread them.
  - **Freeze the source, then review, then re-run the expensive lanes — once.** Reviews run
    against the exact source **before** the slice pays for its full gate wave. A review that
    lands after the wave re-prices the whole wave: in GY-N11 one post-freeze repair produced
    **seven** consecutive full-chain reissues, and 17 of 36 commits (47%) were pure receipt
    churn. After the freeze, a **cosmetic** finding (import order, naming, docstring) is
    recorded as debt; a **blocking** one is batched with any others so the wave is paid once.
  - **Serialize the contended resource, not the session.** Name the contended set in the task
    plan. For Atlas it is: the Playwright browser/visual-snapshot lane, the Storybook runner,
    a dev server on a fixed port, and any writer touching the same governed
    `architecture/atlas_surfaces/**` artifact. **Everything else runs in parallel** — ESLint,
    typecheck, Vitest logic files, the production build, architecture/dependency-cruiser
    checks, read-only censuses. DS4 and the GY lane both idled non-contending work through
    long runs because the rule was written without a resource list.
  - **Measured timeouts are a slice obligation.** Measure each suite's wall time **once** and
    set explicit per-suite timeouts from that baseline. DS4 repeatedly hit the default ~90 s
    ceiling on full Vitest and full ESLint, recorded honest non-receipts, and re-ran them —
    the loop was pure loss. An **unmeasured** budget that kills a healthy run is a harness
    finding, not a product signal. (Recording the non-receipt was correct; leaving the budget
    unmeasured was not.)
  - **Delta-only re-review.** The first independent review reads the full package; **every
    re-review after a fix reads the fix delta only**, with the original findings as its
    checklist. DS4 and GY-N11 both lost reviewer runs mid-flight to quota exhaustion on
    182 KB / 220 KB packages; DS4 did it right exactly once (a 28 KB delta package) — that is
    the rule, not the exception.
  - **Silent polling.** Poll long runs without narration; report only a state change — stage
    complete with its receipt, a RED, or a stop condition — one line each. Per-minute
    "still running" prose drove ~15 context compactions in a single GY-N11 session, each one
    risking state loss and re-derivation. Heartbeat **evidence** is required; heartbeat
    **prose** is waste.
- **DS-INFRA-1 — restore incrementality where it is provably safe (Revision 3.8; measured
  2026-08-02).** Owner: **team-design / frontend infra**. **Sequence after DS5 merges** — it
  edits `apps/runtime-dashboard/tsconfig*.json` and `package.json`, which are inside DS5's
  writable fence. Not a surface slice; it ships no product change and no test change.
  **Measured on main with warm dependencies:** `typecheck` **60.7 s** — three separate
  `tsc --noEmit` runs with **no `--incremental` anywhere**, and it runs at every cluster
  boundary *and again inside `build`*; full `lint` **>7 min cold** (it does pass
  `--cache`, but `_cache` is per-worktree so **every new slice worktree pays cold once** —
  this is the wall DS4 repeatedly hit and recorded as a tooling non-receipt);
  `quantity:coverage` **10.5 s with no `--cache` at all**, and DS4 ran it constantly against
  the 75-violation debt.
  **Three changes, all content-hash-invalidated and therefore semantics-preserving:**
  (a) `--incremental` + `tsBuildInfoFile` on the three tsconfigs — the largest lever, a
  warm typecheck should fall to seconds; (b) `--cache --cache-location` on
  `quantity:coverage`; (c) move `_cache` to a shared location so a fresh worktree starts
  warm, as uv and pnpm already do at user level (their caches are content-keyed, so
  cross-branch sharing is safe by construction).
  **Explicitly declined — do not "optimize" these:** Playwright `workers: 1` /
  `fullyParallel: false` is deliberate — parallel browsers destabilize visual snapshots and
  a11y routes share dev-server state (DS5 already hit an order-dependent connector
  bootstrap); trading determinism for speed is out of scope. Cross-process reuse of the
  custom scanners' `ts.Program` is a **gated candidate**, not part of this task: a stale
  Program view is the §3.5.6-gate-2 "trusted JSON" class and needs its own measurement gate
  and fail-closed conditions (the GY-INFRA-2 Part C shape).
  **Done when:** before/after wall times are recorded for typecheck, full lint, and
  `quantity:coverage`, and **every denominator is unchanged** — same Vitest file/test
  counts, same lint diagnostic set, same architecture violations, same governance numbers.
  A single changed denominator means the change was not semantics-preserving and is reverted.
- **DS-INFRA-2 — the Atlas lane has a measured-timeout LAW and no measurement SUBSTRATE
  (Revision 3.13; measured 2026-08-11 during DS5-C13a-R3).** Owner: **team-design / frontend
  infra**. Documentation-only registration; it ships no product change.
  **The law already exists** — Revision 3.7 makes measured per-suite timeouts a slice
  obligation, after DS4 repeatedly lost full Vitest and full ESLint to the default ~90 s
  ceiling. **Nothing accumulates the measurements.** The Atlas governed gates run through
  `pytest`/`npm`, never through `tools/cli.py`, so they never enter the repository timing log —
  it holds **zero** Atlas lanes. Every executor therefore guesses its ceiling and pays for the
  guess.
  **Measured this round, in one session:** the full Atlas enforcement module was killed at
  **`393.15` s with no failures** — a non-receipt, not a red — and then closed **terminal green
  at `754.20` s** under a second, larger ceiling; several other gates additionally lost their
  terminal receipts to overlapping scanner-heavy parents. Durable measurements now in hand:
  full Atlas `754.20` s, status-retirement module `135.663` s, disposition corruption battery
  `119.66` s, production build `47.29` s, focused dashboard behavior `14.417` s.
  **This is the GY lane's `GY-DI2` in Atlas clothing, in the same week.** There, a canonical
  writer was killed twice under budgets reconstructed from a different lane while its own six
  successful samples sat unused in the log; here, a module is killed under a guessed ceiling
  because no log exists at all. `GY-INFRA-2` Part A was built to prevent exactly this, and the
  transferable statement is that **a slice obligation without an accumulating substrate is not
  an obligation** — it is a re-discovery tax paid once per executor.
  **Closure:** a durable per-lane budget substrate for the Atlas gates — measured `p95` with a
  `2 x` recommended timeout, derived from **recorded successful runs** rather than a requested
  list, with any lane observed but unbudgeted **named at the point of use** so an executor
  learns its budget is a guess *before* spending one. **Binding negatives, inherited from the
  GY ruling (`GY-DI4`):** a killed run is a **non-receipt, never a duration sample**; admission
  is **completion, not success**, so a lane whose contract declares a non-zero healthy terminal
  is budgeted from its own completed runs while a genuinely failing lane stays unbudgeted; no
  ceiling is enlarged mid-run to make a run fit. **A measured budget encodes CONTENTION and is
  valid only under comparable load** — this host is 16 GB / 8 cores and was already 9 GB into
  swap when both spreads above were recorded (Atlas `393`→`754` s, GY's N10a write
  `194.9`–`426.3` s, `1.9x` and `2.2x` on identical work), so a memory-heavy lane running beside
  a governed lane does not merely slow it: it can push it past a cap the rules then read as a
  genuine regression. Heavy lanes are scheduled, never overlapped. **Sequence:** with `DS-INFRA-1`, after DS5
  merges — but the measured ceilings above are usable **immediately** as declared, labelled
  supplied values by any slice that needs one today.
- **`P38` — a gate that turns on a proxy misclassifies exactly at its own boundary
  (Revision 3.14; defined once, in the GY plan §3.5.14, and binding on both programmes).**
  Four measured instances between 2026-08-03 and 2026-08-11, two of them in this plan's lane:
  `DS5-LINE-ADDRESS-01` binds evidence by `file:line` when the property is *which construct*, and
  **DS5's own two-fix breaker** counts rounds that change mechanism bytes when the property is
  *is the mechanism wrong* — the latter cost C21b a completed migration over an unused local and an
  assigned lambda. **Repaired breaker predicate, binding on every DS slice:** a round consumes the
  breaker when it is triggered by *evidence that the mechanism is wrong* — a failing behavioural
  test, an independent review finding, or a governed RED. A round triggered **solely by a
  non-behavioural static diagnostic** does **not** consume it, provided it changes no test outcome
  and no governed artifact byte and that is **proven**; the exemption never covers a diagnostic that
  marks real dead or dropped logic, which is a mechanism finding like any other. The existing
  "zero mechanism bytes is free" clause is unchanged.
  **Standing rule when writing any gate:** state the property, state what the implementation tests,
  and name one case where they diverge. No divergent case means the implementation is the property;
  a divergent case means the gate consults the distinguishing context or records the divergence as a
  declared, bounded limitation.
- **Baseline-relative gating (Revision 3.1; the DS19 lesson).** Where main
  carries measured inherited debt, a slice's toolchain gates are: **absolute
  green** for typecheck, production build, and every test the slice owns or
  touches; **zero-NEW-diagnostics** against the hashed baseline manifests for
  inherited debt classes (post-state ⊆ baseline; removals shrink the debt,
  additions are RED). Weakening or suppressing an authority-relevant rule to
  make a gate pass is forbidden outright. Debt manifests live beside the
  disposition register and are updated only by the slice that closes the debt.

## Controlled Vocabulary (references, then extends)

Authority statuses, interaction states, and surface states are defined in the
surface constitution's Status Grammar and the Layer 3 controlled vocabulary.
This plan adds only the values below. DS0 encodes them in the
[adoption-ledger schema](../../../architecture/atlas_surfaces/adoption-ledger.schema.json)
and
[surface-readiness schema](../../../architecture/atlas_surfaces/surface-readiness-ledger.schema.json);
the table remains the vocabulary source and later slices reference the schemas
rather than minting local values.

| Kind | Values | Rule |
| --- | --- | --- |
| Surface readiness | `contract_only`, `producer_missing`, `bridge_missing`, `consumer_missing`, `verification_missing`, `surface_missing`, `semantic_test_missing`, `implemented` | reuse capability-reality-bar labels; never invent UI-only readiness states |
| Data provenance posture | `live`, `replay`, `fixture_only` | `fixture_only` is visually marked and lint-enforced; never in authority slots |
| Freshness posture | `live`, `cached(as_of)`, `stale`, `offline_queued` | orthogonal to provenance; rendered wherever data is decision-bearing; `offline_queued` never applies to authority-bearing actions |
| Component maturity | `experimental`, `beta`, `stable`, `deprecated` | from the surface constitution's component bar |
| Adoption verdict (DS2) | `admit_as_is`, `admit_after_refactor`, `wrap_then_strangle`, `reject`, `defer` | reuse G0 triage semantics for design artifacts; `defer` is the default for components without a consuming surface in this DAG |
| Surface audience | `PUBLIC`, `REVIEWER`, `EXPERT`, `MACHINE` | enforced access classes mapped to authz permissions (DS5 mapping); every surface declares its audiences; the server denies, the UI reflects |

## Surface Proving Ground

Two pinned proving grounds, mirroring how the runtime proves mechanisms on
`ua-msme-affordable-loans-2022` before scaling:

1. **The Cycle Board itself (DS7).** The board must render the GY-N10
   capstone's three plain-language domains (first-vertical, education,
   unseen/no-pack — three honest `acquisition_required` terminals with
   structurally distinct evidence classes) plus Layer 3's 13 canonical legacy
   cases truthfully — it is the surface on which every law (fail-closed
   rendering, weakest-boundary, candidate clothing, refusal-with-a-path,
   search-frontier honesty) is first proven.
2. **The live route inventory of `apps/runtime-dashboard`** (DS1 recount
   2026-07-16): 32 declared route objects, 29 effective URL patterns, and 22
   leaf UI patterns. The full tree includes `/`, `/login`, `/welcome`,
   `/public/decisions/:signedId`, `/compose`, `/runs`, compare/report/deck and
   eight run-detail tabs, `/artifacts/:artifactId`, `/evidence`, `/knowledge`,
   `/platform`, five legacy redirects, and a catch-all; two sibling index
   objects redundantly target `/`. Feature modules remain
   `artifacts`, `auth`, `causal`, `clerk`, `collaboration`, `commandPalette`,
   `composer`, `dashboard`, `evidence`, `export`, `landing`, `layout`, `lex`,
   `onboarding`, `platform`, `runs`, `whatif`. DS1 audits each route/feature
   against the capability chain and assigns an adoption verdict. This plan does
   not pre-judge dispositions — the audit does.

**Named audit hotspots (DS1 must report on each explicitly; recon findings
from the technical snapshot are recorded inline as confirmed starting points):**

- `public/decisions/:signedId` — inherited public route, **frozen** until
  DS12's gate. *Recon confirmed:* the packet is built **and** verified
  client-side; `signatureForPayload` is a salted hash computed in the browser,
  forgeable by construction; the "Verified" badge is decorative. DS1
  quantifies the blast radius (who links to these URLs, what claims they
  carry).
- `causal`, `whatif`, `lex`, `composer`, `clerk` — engine/LLM-output surfaces
  that predate the candidate-clothing discipline; audit each for P15/P05
  laundering (engine or LLM output rendered in authority dress). `clerk` is a
  full NL chat over `POST /control/runs/nl` and the future DS14 strangle
  target.
- `app/authz/` (`AuthzProvider`, `permissions.ts`), `features/auth`,
  `features/clerk` (incl. `routes.public.ts`) — map the live permission model
  against the audience classes. *Recon confirmed:* the permission vocabulary
  is duplicated server-side (`http/routes/auth.py` `_ROLE_PERMISSIONS`) and
  client-side (`PERMISSION_KEYS`); identity has a fixture fallback; no
  per-permission deny was found on mutating endpoints. DS1 names every
  UI-hides-but-server-allows gap.
- `sw.ts` (Workbox precache) and `app/offline/` (`offlineQueueRepository`) —
  inventory what is cached and what is queued offline. *Recon confirmed:*
  `useQueuedPromotionDecision` queues evidence promotion approve/reject
  offline — a live authority action in the queue. DS1 inventories the full
  cache/queue scope.
- `src/workers/` (`dataTransform.worker.ts` and peers) and
  `shared/lib/domain/projectionFailClosed.ts` — check client-side transforms
  and fail-closed normalization against law 9's boundary: layout/sorting
  derivations are allowed, authority recomputation and authority-adjacent
  re-derivation are not.
- **Off-contract and phantom channels.** *Recon confirmed:* SSE
  `GET /runs/live` and `GET /runs/{id}/live` are `include_in_schema=False`;
  the review WebSocket hub (`/api/v1/review/live`) is unrepresented in the
  contract; the collaboration REST paths the UI calls
  (`/api/v1/collaboration/*`) have **no server route in `runtime/http`** —
  vite only proxies to the runtime, so they are presumed phantom (404). DS1
  inventories every off-contract or phantom path and what UX silently degrades
  when they fail.
- **Feature flags.** *Recon confirmed:* 12 manifest-driven flags gate whole
  workspaces (`enableRunsWorkspace`, `enableClerkMode`, `enableAtlasV2`,
  `enableDarkMode`, …) with a second flag source in `/auth/me`
  `feature_overrides`; no owner/intent/sunset governance found. DS1 audits the
  flag inventory against the DS0 registry decision.
- **Public telemetry.** *Recon confirmed:* Sentry is wired app-wide
  (`shared/telemetry/sentry.ts`). DS1 maps what data leaves the app on which
  routes, feeding DS12's no-tracker posture.

## Strangler Decision

`apps/runtime-dashboard` is the product strangle target and uses a local
`openapi-fetch` generated-type client; `apps/runtime-reference-shell` is a
second live consumer through the generated package class. DS3 must collapse
that two-client seam to one governed home. DS4 primitives land inside the dashboard, admitted v15 substance
replaces its pieces feature-by-feature, and the surface readiness ledger tracks
migration coverage. `apps/runtime-reference-shell` stays an intentionally
narrow read-path diagnostics tool and must not grow product surfaces. A
greenfield rebuild is rejected (P06: canonical ownership ambiguity, in code).

## Slice Sequence (overview)

Phases group slices by readiness, not by team. Numbering is continuous and
roughly chronological; the DAG, not the numbers, governs start order.

| Slice | Theme | Gate / prereqs | Phase |
| --- | --- | --- | --- |
| DS0 | Source-of-truth freeze & governing decisions | **CLOSED** (merged) | A |
| DS1 | Live application audit | **CLOSED** (merged) | A |
| DS2 | Atlas v15 adjudication | **CLOSED** (merged) | A |
| DS3 | Runtime producers & export infrastructure (GY artifact projections; one-client consolidation) | **CLOSED** (merged e451cec56: 13 typed producers, owner-receipt cache law, replay binder, channel registry, canonical client twin) | B |
| DS19 | False-substrate strangle wave + frontend disposition register | **CLOSED** (merged f9f69e807: 33 files / −4,005 LOC; register live) | B |
| DS4 | Status-grammar rebinding & test harness (12 families / 47 statuses) | **CLOSED** (merged 7f450eb7b: 89 components at 27 package / 41 rebind / 18 use-as-is / 3 retire; lint 75→0, architecture 36→0, status retirement 19→0; DTCG token projection; harness + real-panel proof) | B |
| DS20 | **Server authorization enforcement (NEW, Rev 3 — split from DS5)** | **CLOSED** (merged 03ebc1ce8: DS20 29/29-op action-permission floor + step-up + fixture-identity removal + 33-value vocabulary; DS20-B B1 Rego bridge + B2 probe identity + B4 verifier provenance closed, deployment-authority attestation architect-reviewed) | B |
| DS5 | Enforcement waist: lints, audience mapping, cache discipline, flags | DS4; DS20 vocabulary | B |
| DS6 | Evidence workflow & instrumentation | DS4 | B |
| DS7 | **Cycle Board** (hero) | DS5 | C |
| DS8 | Case & evidence workspace: stage-trace drill-down (strangling) | DS7 | C |
| DS9 | Human decision integrity | DS8; DS20 | C |
| DS10 | Capability discovery | DS5 + disposition-ledger/census content | C |
| DS15 | Acquisition routes & data-pool growth surfaces | DS7; read parts after **GY-N13a accepted**, live loop after **GY-N13b** | C |
| DS16 | Value, uncertainty & derived-data grammar | **AUTHORITY HALF CLOSED 2026-08-18** (`blocked_on_ds5`, branch `codex/atlas-ds16-value-grammar`); grammar body deferred to a successor gated on **DS7** — `DS4` defines the grammar but does not let it land | C |
| DS17 | Confidence-ledger & risk-spend surface | DS7; **GY-N11 closed** | C/D |
| DS18 | Epoch & staleness chrome | DS4; **GY-N12 closed** | C/D |
| DS11 | Trust/docs posture | DS9; DS6 | D |
| DS12 | Public publication foundation | **first governed promotion through the GY-N9 gate with N11 δ-accounting and N12 epoch validity live** AND DS11 | D |
| DS13 | Accountability ledgers & transparency | DS12 | D |
| DS14 | Bounded-agent surface | **Phase-6 bounded-agent contracts closed (O-block)** AND DS9 | D |

```text
Phase A: CLOSED (DS0 ─▶ {DS1, DS2} — merged ed74537e8)
        ───── activation: SATISFIED (GY-N10 merged 7e035a426) ─────
Phase B (waist, ACTIVE):    DS3 ─▶ DS4 ─▶ DS5
                            DS19: now, parallel to DS3 (gates on DS1 evidence only)
                            DS20: after DS3, parallel to DS4 (feeds DS5, DS9)
                            DS6: after DS4 (gates all later `stable` claims)
Phase C (workspace):        DS5 ─▶ DS7 ─▶ DS8 ─▶ DS9 (DS9 also needs DS20)
                            DS10: after DS5 + ledger/census producers
                            DS15: after DS7 (+N13a accepted / +N13b live loop)
                            DS16: after DS4 (+N13b for derived-data parts)
                            DS17: after DS7 + GY-N11
                            DS18: after DS4 + GY-N12
Phase D (outward):          DS11: after DS9 + DS6
                            DS12: after DS11 + first governed promotion (N9+N11+N12)
                            DS13: after DS12
                            DS14: after DS9 + Phase-6 O-block
```

The runtime gates encode the constitutional subordination order: public
surfaces never outrun the promotion gate; the agent surface never precedes the
bounded agent.

### Start-Now Ladder (Revision 3 — what runs when)

| Milestone | Unblocked surface work |
| --- | --- |
| **Now** (Phase A + DS19 + DS3 + DS20 + **DS4 all closed & merged**; the typed HTTP waist, the server authorization floor, and the rebound status grammar are live) | **DS5 is mid-slice and its internal queue was re-sequenced by measurement on 2026-08-11 (Revision 3.13): the `DS5-LINE-ADDRESS-01` class repair runs FIRST, ahead of `C13b-R1` and the four other colliding clusters.** The decision was made on the number, not on preference — the complete collision census found **5 of 10** remaining executable clusters touching line-bound evidence (11 files, 13 cluster-file-row pairs), so paying a stop and a re-cut five more times is worse than paying the fix once. The rule it implements is narrow: **a `file:line` reference is legitimate as navigation and wrong as binding** — a row may cite a line so a human can find the finding, and no gate may fail because the line moved. Architect measurement carried into the repair, because the landed registration does not state it: of the `182` refs carrying `:line` across `73` files in `observed_refs` + `evidence_refs`, **`173` are TS/PY (symbol-resolvable), `5` are JSON, `3` Markdown, `1` TOML** — a JSON or TOML line resolves to a key path, never to a symbol, so that is up to **four mechanisms and not one**, and under the standing sizing bar each bespoke mechanism is its own cluster. The migration denominator is the **gated** subset, not the corpus. **`DS5-LINE-ADDRESS-01` is CLOSED (Revision 3.15, verified against the branch by the architect).** `C21a` `015fb8f08` established the TypeScript reference identity; `C21b-R1` `ceccb0746` (after the append-only restore `055345536` of checkpoint `3b0b721a4`) migrated the TypeScript corpus; `C21c` `db6c4c350` migrated the gated structured refs. **Independently reproduced final census: `270` total refs, `161` TypeScript identities, `6` structured identities, `15` navigation-only `:line` refs across 11 files** — and `161 + 6 + 15 = 182`, exactly the line-bearing corpus measured before the migration, so nothing is unaccounted. **The decisive property is witnessed, not asserted:** the real migrated construct moved with **no register update** and the full validator returned no errors, while renaming that same construct returned `typescript_reference_binding_missing_or_renamed`. **Sequencing result: 10 of 13 collision pairs are migrated and the remaining three Workbox refs are navigation-only, so `C13b-R1`, `C16a-R1`, `C16b-R1`, `C17a-R1` and `C19-R1` are all unblocked on this axis.** C21c's own review round caught a real `P32`/`P37` escape before landing — a forged absolute or `..` source path passing suffix checks and binding outside the repository root — closed with a canonical repo-relative predicate and its adversarial witnesses. **DS6 runs in parallel** and owns `apps/runtime-dashboard/src/shared/i18n/**` exclusively; the register, baseline manifest, status inventory, checker, its test and the generated report stay DS5's while C21 is in flight. **DS5** remains the critical-path Phase-B lane and started with three ready inputs: DS20's 33-value server-projected permission vocabulary (audience mapping), DS4's **three typed waist debts with exact generated-client anchors and single swap modules** (see the debt table), and the Rev-3.4 §6.5 lint row (M31·M6·M29) + INT-R6 semantic-ID rule. **DS6** (evidence workflow) is also unblocked by DS4 and owns the two remaining DS4-handed evidence debts (i18n parity ×3, axe-`incomplete` contrast ×4). |
| **DS5 closed** | **DS7 Cycle Board on real capstone data** → DS8 → DS9 (with DS20); DS10; DS16's value/uncertainty grammar (ValueOuterSet is live main-tree data now). |
| **DS5-`C21` register released** | DS6 `C03`/`C04`/`C06` — the three append-only register transitions DS6 is currently blocked on. |
| **DS8 print repair + two stable captures** | DS6 `C13` governed transition, then `C14` closes DS6. |
| **GY-N13a accepted/merged** | DS15 read surfaces: connector scorecard (12-family liveness), the growth backlog (`ranking_only_not_voi`, 15 `binding_gap` residuals), route projections — noting the routes are currently **structural gaps, not data gaps**. |
| **GY-N13b closed** | DS15 live loop (approve-acquisition → world-growth → re-entry), passports/quarantine; DS16 derived-data provenance (derivation certificates, basis chips). |
| **GY-N11 / GY-N12 closed** | DS17 δ-surfaces / DS18 epoch chrome. |
| **First governed promotion** (per Rule 5, may be distant) | DS12 → DS13. |
| **Phase-6 O-block closed** | DS14 (strangles `features/clerk`). |

## Per-Slice Detail

**Phase-A rebaseline binding (Revision 3).** Every slice below is re-scoped by
the [Phase-A synthesis](../../reference/frontend/atlas-phase-a-synthesis.md)'s
per-slice **confirmed / re-scoped / invalidated** matrix and its `PI-01`..`PI-24`
actions — that document is the binding re-scope of record and task plans MUST
consume their slice's section from it (this roadmap does not restate it;
Rule 10). Effort posture per the synthesis: DS4/DS5(+DS20)/DS6/DS9/DS12/DS18
**up** (binding and enforcement are the real work); DS8/DS10/DS14/DS15 **down**
on greenfield (living substrates exist); DS3 re-cut toward client/channel
consolidation. `stable` remains unavailable everywhere until DS6 evidence
exists — the single DS2 `beta` is an evidence method and raises no component.

**Inherited baseline debt of record (measured by DS19, 2026-07-16).** Main's
measured pre-existing debts — hashed manifests live in
`architecture/atlas_surfaces/frontend-baseline-debt-manifest.json`; every
slice gates baseline-relative against them (zero NEW diagnostics; see the
doctrine bullet); only the owning slice closes and re-manifests a debt:

| Debt | Measured | Owner | Closure expectation |
| --- | --- | --- | --- |
| ~~`policyos/quantity-must-be-wrapped` lint violations~~ | ~~75 errors across 22 untouched files~~ | **DS4** | **CLOSED** (7f450eb7b): 0 errors / 0 files across C06 20 + C07 37 + C08 18 exact resolutions; the rule was never weakened; live JSON comparator passes |
| ~~Inherited Vitest failures~~ | **5 → 3.** Closed: a11y coverage census (DS4-C12 added the real companion, no allowlist), temporal-cursor (DS4-C09 injected a test clock, product time meaning unchanged). **Open: 3 i18n parity** (`panels.agentPipeline.overBudget` en/uk/ru, one file) | i18n parity → **DS6** (Ruling 2 reassigned it from DS5; register class `i18n-count-message-parity`) | **CLOSED** (DS6-C03, merge `b0249e82d`): `baseline-test-i18n-count-debt` transitions to `repaired` against C16's landed 317/317-file, 983/983-test receipt through the canonical lifecycle producer, with two frozen receipt hashes and a content-bound landed-release binding. |
| **`atlas-health-metric-replay-pins-uncommitted-paths`** (registered by the architect 2026-08-18 while landing DS6-C10-R2) | `atlasHealthMetrics.test.ts:649` asserts `pyproject.toml` and `uv.lock` appear in `replay.non_revision_paths` — it pins a transient working-tree state as a governed expectation. Those files were uncommitted on the DS6 branch when C11 measured them and are committed in `main` since `fa708f2bc`, so the assertion is **permanently red on a clean checkout**. `P38`: revision status stands in for membership in the persistence-implementation set; the two agreed while the files were uncommitted and diverge now. It is a defect in the test, not a non-receipt — the measurement succeeded and the expectation is wrong. | **DS6** owns the test; the repair is to assert the implementation set directly rather than through revision status | open, carried at the DS6 slice standing |
| ~~**`i18n-plural-rule-covers-only-`{count}`**~~ (registered by the architect 2026-08-11 while verifying DS6-C01-R1; C01's repair remains correct and C19 closes the adjacent class it never covered) | DS6-C19 independently reconciled the complete active denominator at 2,451 string leaves, 244 non-`{count}` message paths, and 360 path-variable points in each locale: 720 locale instances, 149 names, zero parse failures, point-set SHA-256 `f463ac23…a362`. The owner partition is 71 quantitative-capable / 78 nonquantitative names. Each locale's 183 quantitative point uses was manually adjudicated: four require agreement and 179 do not. The old `blocked = 1` copy fails `plural_ownership_missing`; repaired output is `1 blocked packet` / `1 заблокований packet`, with English one/other and Ukrainian one/few/many/other branches. An invented variable fails `variable-kind-undeclared`; a numeric AST use contradicting a nonnumeric declaration fails `numeric-kind-conflict`; no-agreement and existing `{count}` cases remain admitted. The nonnumeric declaration is `institutionally_supplied` and retains a bounded P37 residual: the gate cannot recompute producer types without a typed producer-to-message argument manifest/call graph. `panels.reviewCollaboration.reviewers` is explicitly `declared, unenforced`. | **DS6 / C19** | **CLOSED** (DS6-C19, `c552d5b5ccce077b24f5126deb699400263186e9`): focused parity 38/38, targeted ESLint green, dashboard app TypeScript check exit 0; `ru` remains `legacy_continuity_frozen`. DS7 Task 8 must satisfy the widened fail-closed declaration rule for new active locale copy. |
| ~~Dashboard architecture-layer violations~~ | ~~36 violations across 28 files~~ | **DS4** severing, **DS5** lint enforcement | **CLOSED** (7f450eb7b): 0 violations in *both* engines (custom checker + dependency-cruiser over 1,019 modules / 4,150 edges) via C06 13 + C09 7 + C10 1 + C11 9 + C13 5 + C18 1. Note DS4 does **not** claim an independently measured 23→0 API/app denominator — Phase A never left a provenance-bound 23-item manifest; the governed claim is 36→0. **DS5 still owes the recurrence lints** |
| Worktree tooling gap | agent worktrees carry invalid `.venv`s (Playwright/py tooling non-receipts in DS1/DS19) | ops note — every future slice prompt | slices declare their toolchain baseline gate up front (the DS19 pattern) |
| ~~**`GY-DEF20`~~ — generated-client family staleness can pass a declared fail gate** (registered by DS7 on 2026-08-20 after the `P41` exact-base falsifier; `GY-DEF19` was already taken and a complete main-tree search found no `GY-DEF20` reservation) | At DS7's immutable slice base `40ef040bd`, with GAP4 absent and the workspace bootstrapped, regenerating both OpenAPI clients left `packages/runtime-api-client/types.ts` byte/AST-identical at 8,165 fields but moved the dashboard client from 7,672 to 8,165 fields: 7,632 unchanged / 40 changed / 0 removed / 493 added. The only changed pre-existing leaf is `AuthMeResponse.permissions`, `string[]` → `RuntimePermission[]`; 39 changes are derived containers. Complete manifest census: 59 families; `apps/runtime-dashboard/src/api/types.ts` has one output owner (`runtime-dashboard-api-types`, `drift_gate = automated`, `stale_output_behavior = "fail"`), while the current package `types.ts` has **zero** output owners. Its `runtime-api-client` family lists only raw TS/JS even though the package generator also emits `types.ts` and canonical TS/JS. The ordinary architecture check validates declarations but executes family freshness commands only with `--run-generated-checks`, so the declared gate is not itself an always-entered gate. Pattern: `P37`/`P38`; inherited `team-polisyos` generated-family defect, not GAP4 or DS7 mechanism drift. | **team-polisyos** (both generated-client families and the architecture generated-artifact gate) — **RE-OWNED to the Group A executor (2026-08-20)**; `team-polisyos` has no live lane. | Register every committed output emitted by the package generator under exactly one OpenAPI-derived family; make the required closeout/CI path execute both families' freshness checks without an opt-in omission; regenerate both clients from one pinned snapshot; then corrupt one declared output while leaving source and declarations intact and prove the required gate fails. Closure also requires a clean regeneration with zero diff and a complete output-owner census with no generated client unowned or multiply owned. **PREPARATION MEASURED 2026-08-20, and it names the omission exactly.** The opt-in is `architecture guardrails check --run-generated-checks`: the flag is `store_true` and family freshness commands run **only** when it is supplied, while the core release workflow calls plain `architecture guardrails check` and therefore executes **no** family freshness check at all. Standard CI checks both current clients separately, but the package checker compares only the raw TS/JS pair, leaving `types.ts` and both canonical outputs invisible. Reconciliation: **six** emitted outputs against **three** registered; three package outputs (`types.ts`, `canonicalRuntimeApiClient.ts`, `canonicalRuntimeApiClient.js`) are declared by **no** OpenAPI family; declared-by-more-than-one is empty; declared-but-no-longer-emitted is empty. **AUTHORIZED FOR EARLY EXECUTION**: both generators already accept explicit output paths, so the corruption falsifier runs entirely in scratch and the repair is uncontended end to end — it does not wait on DS7's regeneration.  **CLOSED 2026-08-21, merged at `518e04da5` (mechanism `390c754a8`).** All six generator-observed outputs are now owned exactly once across 59 families / 444 output entries — five by `runtime-api-client`, one by `runtime-dashboard-api-types`; unowned and multiply-owned are both empty. The `--run-generated-checks` opt-in is **gone from the repository**: plain `architecture guardrails check` runs both OpenAPI families by default, so the release-gate call site at `core-runtime-release-gate.yml:242` is unchanged and fixed by the default — the defect was the default, not the caller. **The repair is wider than the brief asked, and correctly so:** a reviewer found that removing a family's manifest flag reopened the same omission one level deeper, so membership is now derived from `source_of_truth == RUNTIME_OPENAPI_CLIENT_SOURCE` independently of the flag, which is only a checked record — the class is closed, not the instance, and its falsifier is `test_runtime_openapi_client_cannot_escape_default_check_by_removing_flag`. Architect-reproduced corruption witness: both families clean against a scratch expected root, then corrupting exactly one scratch output fails `runtime-api-client` naming that exact family and path while `runtime-dashboard-api-types` stays clean, with worktree status **empty before, between and after**. Five behavioural negatives green, including the emitted-but-unregistered escape that let three outputs hide. Because the gate is now default-on it needs a provisioned Node workspace; both affected release-gate jobs gained `./.github/actions/setup-runtime-dashboard` in the same commit. **One receipt is owed and is assigned:** the gate has not been run against DS7's regenerated clients on merged `main`, because the generator pipeline moved into `packages/runtime-api-client/scripts/generate-runtime-api-client.sh` (a faithful extraction, with `uv run` narrowed to `${PROJECT_ROOT}/.venv/bin/python`). The `GY-DEF21` migration executor takes that receipt as its first act, since it advances the base anyway. |
| **`GY-DEF21` — generated-client line addresses remain semantic bindings in the status inventory** (registered by DS7 on 2026-08-20; `git grep -F GY-DEF21` returned zero across all 9,883 tracked PolicyOS paths at current `main` `11781974d`, and zero at immutable DS7 base `40ef040bd`) | `architecture/atlas_surfaces/status-retirement-inventory.json` carries 383 integer line-bearing leaves, including 15 generated-anchor records carrying 30 `canonical_line` / `schema_line` integer bindings. GAP4's additive two-field regeneration changed no pre-existing symbol or field, yet eight records moved uniformly by canonical `+2` / schema `+7` and made the status gate fail. This is the `DS5-LINE-ADDRESS-01` / `P38` class surviving in a second governed family: the property is generated construct identity, while the gate binds a coordinate that moves by construction. DS7's derivable census (`architecture/atlas_surfaces/generated_client_receipt_census.py --check`) reconciles 18 fully enumerated structured records / 38 integer bindings across two binding artifacts; it separately enumerates 38 navigation-only references across two other artifacts. The status command consumes the census, so completeness is gated rather than manual. | **DS5** (status inventory, checker, and pinning test owner) — **RE-OWNED to the Group A executor (2026-08-20)**; DS5 is closed and merged. | Every generated-client anchor binds a uniquely resolvable construct identity; rename or removal fails, duplicate resolution fails as ambiguous, and a numeric line remains navigation-only and cannot fail the gate merely because it moved. Forbidden closures: a longer remembered anchor list, a line-drift tolerance or range, and scheduled re-anchoring. Preserve the Atlas register-family whole-file hash contract during migration. **SPLIT RECORDED 2026-08-20: the mechanism lands now, the inventory migration lands after DS7's Task 6 client regeneration.** The mechanism — the additive owner-qualified identity role, its census consumption and its negatives — needs no regeneration and is uncontended. Migrating the inventory writes `status-retirement-inventory.json` and requires the Atlas register-family lock, so it waits for the regeneration that proves a move is green and for a free family. **Measured in preparation:** 383 integer line-bearing leaves decompose exactly as `145 line + 103 start_line + 103 end_line + 15 canonical_line + 15 schema_line + 1 current_inline + 1 ds1_inline`; 18 primary anchors reconcile with 18 independently derived; the 15 status anchors carry 30 bindings resolving to **21 distinct constructs**. DS5's `#ts-identity` v1 shape **transfers, proven by parser replay** — all 30 hints minted and validated with zero errors — but needs **one additive role** inside the same envelope, because the existing `type_property` role collapses nested properties to names like `components.status`, where the measured 47-property population collides: two candidates for `RunWorkflowNodeView.status`, two for `ScenarioRef.status`, **five** for the lineage output. Changing the existing role would invalidate DS5's 155 current identities; adding one keeps them byte-identical.  **MECHANISM CLOSED 2026-08-21 at `60f089143`, merged `518e04da5`; MIGRATION AUTHORIZED, NOT BLOCKED.** The owner-qualified role `generated_schema_property` binding `components.schemas.<owner>.<field>` is added **beside an unchanged `type_property`**, inside the existing `#ts-identity` v1 envelope. The 155 existing DS5 identities are pinned byte-for-byte at `f1ac4d933af3c980190ee9ba31faae8e823d928ea651ff6d6117ec86f5fc42e2`. Move and reorder green; rename, removal and content drift red; duplicate resolution ambiguous; mixed legacy/identity mode red; numeric lines navigation-only. The proof runs against the **real** `types.ts` and the **real** five-candidate `LineageRef-Output.status` collision, where owner qualification resolves to exactly one match — not a synthetic substitute. Both `P40` rounds were consumed and both findings repaired: canonical-alias multiplicity must be exactly one match rather than one distinct owner, and scratch replay must be a closed source universe that cannot fall through to same-named real-worktree files. `status-retirement-inventory.json` is deliberately unmigrated (**zero** `ts-identity` references). **The deferral I recorded on 2026-08-21 is spent: every resume condition is met on `main`.** Both clients carry `getDepthNCycleBoardProjection`; `dc3e50a90` is an ancestor of `main`; `fea50aadd` (DS7 Task 6) is a regeneration newer than it touching both; no generator is running; and the Atlas register family is free (DS7 released explicitly at `df0484301`, DS6 released at `71b6189de`). What made the migration look blocked is only that the Group A branch was pinned at pre-DS7 `1e78542f1`, whose own tree has **zero** occurrences of the new operation — that is a base advance, not a blocker. The migration gets its **own** `0/2` budget: it is the deferred half of a declared split, not a continuation of an exhausted one. |
| Control-plane fixture drift | 2 pre-existing test failures in `tests/unit/runtime/http/test_control_api.py`-adjacent run-control paths (`DecisionMonitoringContract` rejects fixture fields; reproduced on pre-DS3 base in isolation). **Identities supplied by the architect 2026-08-21 at DS7's merge, and the denominator measured:** the two are `tests/unit/runtime/http/test_runs_api.py::test_evaluate_feedback_endpoint_persists_monitoring_report` (`400`, expected `200`) and `tests/unit/runtime/http/test_runs_api.py::test_reissue_endpoint_fails_closed_without_durable_control_plane` (`400`, expected `422 durable_worker_required`). Both enter `ctx.feedback.evaluate_run_feedback` / the reissue path in `src/polisyos/runtime/http/services/feedback.py`, which is a `DecisionMonitoringContract` consumer — the same root cause this row already names. Measured on `main` at the DS7 merge: `test_runs_api.py` is **42 passed / 2 failed of 44**, and `test_control_api.py` is **60/60 green** — so the failures are adjacent to the control API, not in it. **DS7 rediscovered these two independently and could not attribute them, because this row named no test identity.** That is the finding worth keeping: a debt row whose subject is a set of failing tests must carry the test identities, or it will be re-found and re-investigated at the cost of a lane each time. No new row is opened; this one is widened | **runtime/GY lane** (the contract's owner) — not an Atlas surface debt | the owner reconciles fixture vs contract red-first; DS3's focused selections exclude exactly these two, documented; closure requires both named identities green with no fixture re-baselining |
| Producer availability denominator | DS3 measured 5 available / 7 `invalid_source` / 1 `artifact_missing` from a worktree WITHOUT `production_data` — environment-relative fail-closed, not artifact corruption | **DS7** (first consumer) re-measures on main with the catalog mounted and records the true availability row in the readiness ledger | the Cycle Board consumes measured availability, never the worktree-relative snapshot |
| DS20-B B3 promotion CAS | promotion authorize→mutate is not atomic — DS20 binds the revision before OPA and re-verifies after (409 on drift), but no public Fabric compare-and-set producer exists; N13b owns `fabric/retrieval/service.py` | **GY / fabric lane** — expose a generic public revision-CAS primitive (the scenario-head CAS is the reference shape); DS20's HTTP consumer is ready to call it | the fabric lane lands the primitive; a follow-on wires the promotion path to it and removes the typed limitation |
| DS20-B B5 PostgreSQL linearizability proofs | step-up one-use consumption and scenario-head CAS are proven on SQLite; the real-PG harness exists but is `environment_blocked` (no local DSN/`pg_isready`/docker daemon) — `tests/unit/runtime/http/test_runtime_postgres_linearizability.py`, run with `POLISYOS_..._POSTGRES_DSN` set | **cloud verification** (the user's backend-verify environment) | the four proofs run against real PostgreSQL with a DSN; the harness reports pass, never a SQLite fallback |
| DS20-B scorecard producer provenance | the production-approval path binds a persisted scorecard before OPA and refuses cross-run/absent `run_id`, but the authoritative scorecard *producer's* provenance is configured outside the DS20 fence | **DS9** (decision integrity) / ops config | DS9 binds the scorecard producer's declared provenance into the approval decision |
| DS20-B Helm policy mirror | the Helm chart carries a separate stale copy of the OPA policy; the canonical `ops/policy/policies/**` Rego is DS20-current, the Helm mirror was outside the extended fence | **ops / deploy lane** | the deploy lane regenerates the Helm mirror from the canonical Rego (or removes the duplicate in favor of the canonical source) |
| aiohttp Fabric connector cleanup | two unclosed `aiohttp` session/connector diagnostics surface from the authorized `discover_data_sources`/`resolve_data_needs` handler witnesses opening Fabric connector pools (not a test failure; DS20 added no HTTP bypass) | **GY / fabric lane** (connector lifecycle owner) | the fabric lane closes the connector-pool lifecycle; not an Atlas surface debt |
| **DS4 three canonical-waist vocabularies** (registered 2026-08-01; the register rows carry `master_inherited_debt_action = flag_for_architect_insertion_at_c20`, i.e. this insertion) | three vocabularies the generated client does not project, each already reduced to **one** presentation-only swap module that renders novel owner labels as explicit `unrecognized` and exports no value-level constants: **CGF disposition** (`canonicalRuntimeApiClient.ts:516`; `types.ts:5850-5879` `GenerationCycleDispositionPayload`) → `shared/ui/compounds/cgfDispositionPresentation.ts`; **decision grade** (missing `DecisionGrade` export; client export block `333-394`) → `shared/ui/compounds/decisionGradePresentation.ts`; **cache-age lattice** (`canonicalRuntimeApiClient.ts:737`; `types.ts:8164-8182` `ProjectionFreshness`) → `shared/ui/temporal/cacheAgePresentation.ts`. Authority: `architecture/atlas_surfaces/ds4-waist-debt-register.json`; estate denominator effect **none** | **DS5** (waist) — **RE-OWNED to the Group A executor (2026-08-20)**; DS5 is closed and merged. | DS5 supplies each closed union through the generated client and swaps it in at the single named module; **the two negatives per module survive** (novel label → explicit `unrecognized`; module exports no vocabulary constants). Terminal kinds and evidence classes stay opaque extensions end to end — DS5 does not close or order them **THE ROW SPLITS INTO THREE DIFFERENT STATES (measured 2026-08-20). All three names return zero occurrences in the generated package client and zero components among all 351 OpenAPI schemas, but the reason differs per vocabulary and the single closure signal is not executable as written.** (1) **`DecisionGrade` — EXECUTABLE.** A real canonical union exists: `Literal["unsupported", "descriptive_only", "advisory_admissible", "decision_admissible"]` in `pdc/_impl/layer2_readiness.py`. It rides the next regeneration through a real DTO/producer bridge and must not be bound to an unrelated evaluator or closeout verdict. (2) **`CgfDisposition` — re-typed `producer_missing`.** There is no public typed server owner. A private validator carries `USE_AS_IS` / `REWORK_TO_FIT` / `DELETE` while the generation-cycle disposition payload's owners field stays opaque JSON; copying that private set into a public contract would **invent authority**. The canonical generation-cycle owner must declare the public contract first — a producer decision, not a presentation bridge. (3) **`CacheAge` — RETIRED AS SUPERSEDED by architect decision.** No server owner exists and none should: **cache age is client-local by construction** — the server cannot know how long a given browser has held a copy. `ProjectionFreshness` is a different time role and says so in its own docstring, *"Separate source time from the time the HTTP producer observed it"*; equating the two would conflate source observation with cache staleness. `DS6-C11a`/`C11b` already answered this correctly a different way, making the branded dashboard `CacheObservation` the QueryObserver-lifecycle owner of the live/cached posture. This is a debt solved better by a later slice, not an abandoned one; the executor confirms the two negatives still hold under that answer and records the retirement. |
| **`run-lifecycle-terminal-fact`** — producer-signed run terminality | `GY-GAP4` now supplies producer-owned lifecycle terminality through the core run/trace contracts, governed event contracts, `RunSummary`, OpenAPI, and both generated clients. Lifecycle terminality remains distinct from design-search `terminal_kind`. The DS7 hero consumer and its absent-not-false and no-proxy semantic negatives have not landed yet. Anchors: `runtime/http/services/adapters/core_run.py`, `canonicalRuntimeApiClient.ts:865`, `types.ts:9240/9259/9286`, `docs/superpowers/journals/2026-08-16-gy-gap4-run-terminality.md` | **DS7** — receiving first consumer and current closure owner. The runtime / GY producer route is complete through `GY-GAP4`; DS7 projects the signed fact and never owns or re-derives temporal truth | DS7 renders `RunSummary.run_terminality` without status/timestamp derivation, renders an unbound lifecycle fact as absent rather than false, and keeps the C22 semantic negatives plus DS5 ownership lint green. Novel status labels remain opaque |
| **Readiness / scientific-depth producer binding** | `PublicSectorReadinessPanel` and `ScientificDepthPanel` had dashboard-local synthesis minting unsigned readiness and scientific-composition values; DS4-C23 physically deleted both synthesis graphs and renders the panels constant `unavailable` / no-input. States: `producer_missing`, `artifact_missing`, `bridge_missing`, `semantic_test_missing`. **Re-typed 2026-08-02: this is a breach of ratified `S0-K07` — projection cannot mint authority** (`docs/system-design-decisions/stage0-custody-kernel-ratification.md`); dashboard-local synthesis of an unsigned readiness value is the prohibited case exactly, and DS4-C23 **contained** it without closing it | **DS16** (already carried in the DS16 section, Rev 3.5) | every named value resolves to a generated field or a registered typed refusal, and the C23 containment negatives (two no-input panels, exactly three prop-less mounts, zero reachability to the deleted graphs, six AST corruption witnesses) remain green |
| **`adjacent-print-export` — run-detail A4 print regression** | **Institutionally supplied adjudication:** the committed 724×2,113 PNG is a **bulk-publish placeholder never derived against this surface**. `45f330235` assigned the same 231,141-byte blob to all five A4 names, while the active 770-pixel shell rule from `3535d89f` predates that PNG by six weeks. The governed no-update command measures the placeholder against 770×12,966 current. A no-writer complete 19-anchor / 4-rendered-anchor diagnostic measured 770×13,269 with the original cascade, 770×12,966 with only the 17,206-character signed target suppressed, 770×12,918 with all targets suppressed, and 12,893 pixels of main content. The signed target accounts for 303 pixels (about 2.7% of the pre-repair excess) and cannot cause the 46-pixel width difference. `3f7af28e59` later introduced print-visible reviewer workflow chrome; `OperatorCraftPanel` mixes controls with rendered browser-persisted annotation body/target/snapshot hash, threshold and impact values, saved evidence references, and onboarding progress/evidence references/completion duration, so the correct paper projection is `not_established` pending DS8 adjudication. | **DS8** (product repair and owed paper-semantics adjudication, `team-design`); **DS6** owns independent visual + semantic verification | DS8 adjudicates the mixed panel's paper projection; the repair then enters the existing print-chrome boundary once, a complete-tree real-browser guard proves no rendered interactive control remains, the signed-target non-overlap remains true, and the run-detail expectation is **derived for the first time, not re-baselined**, with a content-bound host/browser/font receipt and two consecutive stable no-update captures. The 724→770 branch is unsupported and closed. |
| ~~**Four axe-`incomplete` contrast clusters** (registered by the architect 2026-08-01 — DS4 recorded them honestly in its closure/journal but left **no machine-readable row**, so this table is their authority until DS6 creates one)~~ | axe reports these foregrounds as `incomplete` — neither violations nor passes — because translucent/gradient ancestors defeat computed contrast: **C01** neutral `Badge` variant; **C06** `ProvenancePopover` + `ProvenanceMiniGraph`; **C09** `TimeSemanticsLabel` inheritance; **C14** `CandidateFrame`, `NegativeCertificateCard`, `WeakestLinkExplainer`. They are not suppressed and not counted green; the automated a11y denominator (85/85 component, 21/21 browser) is green *around* them | **DS6** (a11y evidence owner) | **CLOSED** (DS6-C04 admitted the typed row, DS6-C06 repaired it; merge `b0249e82d`): `baseline-test-a11y-rendered-contrast-incomplete-debt` covers seven source identities through three evidence refs and is bound to the landed C16 contrast release `97d0c6208`. The real-browser opaque-background probe exists at `apps/runtime-dashboard/src/test/a11y/opaqueBackgroundContrast.ts`. |
| **`deep-import-baseline-stale` — the required release gate fails on `main`** (registered by the architect 2026-08-21, surfaced when GY-DEF21's executor stopped at the DEF20 receipt gate) | `architecture/baselines/imports/deep_import.json` is stale on `main` `04fa1b3b0`, and `uv run polisyos-tools architecture guardrails check` therefore **exits nonzero** — the exact command the core release gate runs at `core-runtime-release-gate.yml:242` and standard CI runs at `ci.yml:151`. The checker enumerates **six** unregistered creep edges itself: `http.services.channel_contracts → core.artifacts.manifest`; `→ core.contracts.decision_validity`; `http.services.control.lex_pipeline → lex.knowledge.store`; `http.services.control.lex_search_projection → core.contracts.runtime`; `→ lex.knowledge.types`; and `scientist.orchestration.engine.checkpoint → core.security.tenant_context`. DS7's replay reported a removed side of three; I did not independently re-derive that count and it is `not_established` here. **Not caused by DS7, DEF20 or DEF21** — the four source files were last touched by the GAP4/run-terminality lane (`dc3e50a90`, `1775cf8a5`, `ec7228eff`) and GY-DEF3 (`b66bf3f82`), and DS7 replayed the identical identities at both its slice base and its Task 6 base with edge-level introducers predating it. **The reason it matters more now:** GY-DEF20 made this same command carry generated-client freshness, so one stale baseline holds a gate that two separate properties depend on, and every lane that runs the required gate reads a red it did not cause. Closing it is a **governance act, not a sync** — `guardrails sync` would silently accept six new deep-import creeps. | **runtime/GY lane** (the owner of all four source modules); approval `team-architecture` | the owner adjudicates each of the six edges — stable facade, intentional baseline acceptance with a recorded reason, or a registered temporary exception — and the plain gate then exits zero on `main` with generated freshness still clean for both families |

**Debt-row execution rule (Revision 3.22, measured 2026-08-20).** A registered
debt row with an **executable closure signal** is executable independently of
where its owning slice sits in the Start-Now Ladder. **Ownership assigns
responsibility for correctness — who adjudicates that the repair is right — not
the moment of execution.** Reading an owner as a schedule parks real, small work
behind a container far larger than the work needs, and this plan has now measured
that happening.

Two corollaries, both from measurement rather than principle:

1. **A debt owned by a closed slice must be re-owned at closure.** DS5 is closed
   and merged, and two open rows still name it: `GY-DEF21` and the DS4 three
   canonical-waist vocabularies. The second was verified still open — `CgfDisposition`,
   `DecisionGrade` and `CacheAge` return **zero** occurrences in
   `packages/runtime-api-client/types.ts`, so the generated client does not project
   them. Neither row has an executor. The architect registered `GY-DEF21` against
   DS5 *after* DS5 had closed; that is the same error stated from the other side.
2. **A co-owned row may be executed by whichever owner can act.** The
   `adjacent-print-export` row already names **DS8** for the product repair and
   **DS6** for independent visual and semantic verification. DS8 is unentered and
   gated behind DS7; DS6 is live and blocked *by this row*. The live co-owner
   executes and the absent owner's adjudication is recorded as owed, rather than the
   whole row waiting.

**Measured audit at this revision:** of the sixteen open rows remaining after the
two DS6 closures, **six name an owner that cannot currently act** — `GY-DEF21`
and the waist vocabularies (DS5, closed), `adjacent-print-export` (DS8,
unentered), the DS20-B scorecard provenance (DS9, unentered), the readiness /
scientific-depth binding (DS16, unentered and gated on DS7), and `GY-DEF20`
(`team-polisyos`, no live lane). That is a distribution, not an incident, and it
is why this rule is written into the plan rather than applied once.

**What this rule does not authorize:** re-owning a capability away from its real
owner. Routing `GY-GAP3`, `GY-GAP5` and `GY-GAP6` to the GY-N12 lane is correct
and stays — a *capability* belongs to the owner that can hold it. This rule
governs *point repairs with executable closure signals*, which are a different
object.


The five formerly-phantom dependency declarations (+ the `workbox-window`
peer) and the `audience` fixture drift are already repaired (d01eaa572) and
recorded in the register.

**DS4 closure note (merged 7f450eb7b, 2026-08-01).** The rebinding waist is live
on main. The dashboard now projects producer-owned authority, time, evidence,
provenance, and quantity semantics through rebound families and the single
`@polisyos/atlas-ui` owner, and it no longer maintains a parallel status grammar.
Three architect-level facts govern how later slices read this closure:

1. **The realized 89-component disposition is `27 package / 41 rebind /
   18 use-as-is / 3 retire`** — not the pre-Ruling-3 plan of `35 / 42 / 12`.
   Five primitives were re-adjudicated (`DropdownMenu`/`Separator`/`Sheet` →
   retired for `no_production_consumer`; `ScrollArea`/`Tabs` → `use_as_is` under
   their exact DS2 conditions), and the C15/C16 live-consumer censuses moved a
   further four. **Later slices must quote the realized split**, never the plan
   numbers: refusing to migrate a component with no live consumer, or one whose
   DS2 ledger condition is unmet, is correct behavior, not shortfall.
2. **The closure is baseline-red on purpose.** Full Vitest keeps exactly three
   DS6-owned i18n parity failures; Playwright visual is honestly 17/18 with the
   DS8 print regression red and its expectation byte-unmodified. No gate was
   weakened, suppressed, quarantined, or tolerance-widened to produce green.
   Any later slice that reports these as green is reporting a regression in
   honesty, not progress.
3. **Everything DS4 refused to build was handed over typed**, not dropped: the
   three DS5 waist vocabularies, the DS16 producer binding, the reassigned
   `run-lifecycle-terminal-fact`, the DS8 print defect, and the DS6 i18n +
   contrast evidence — all now rows in the table above, each with an owner and
   an executable closure signal.

**Merge-time finding — content-bound receipts collide across parallel slices
(architect, 2026-08-01).** DS4 and DS20 ran in parallel and both bound governed
receipts to the *same* generated client. DS20 regenerated it (`+3` lines in
`canonicalRuntimeApiClient.ts`, `+6` before the affected anchors in `types.ts`,
purely additive for the permission vocabulary); DS4 branched earlier and pinned
the pre-DS20 hashes and line anchors. The merge was code-clean, but the status
inventory went **red on main** with 2 `inventory_source_hash_drift` + 7
`generated_anchor_drift`. Resolution: the architect re-anchored the seven units
after proving the shift is mechanical — every `export_symbol` still exists
exactly once, every `field` is unchanged, and the offset is uniform (+3 / +6) —
and refreshed the two client hashes. No semantic claim, ownership, denominator,
or classification moved; the corruption probes still pass, so the receipts kept
their protective power. **Two standing rules follow.** (1) A slice that
regenerates the client — **DS5 does** — must re-anchor every governed receipt
that points into it, in the same commit; anchor drift is expected mechanical
bookkeeping, hash drift with a *changed symbol or field* is a real finding and
must stop the slice. (2) The same merge exposed that a fresh `main` checkout had
never installed the workspace, so `@polisyos/*` did not resolve and the TypeScript
scanner reported two **false** `retired_semantic_definition_survives` findings
against live replacement adapters. Generated-owner proofs are only meaningful
under an installed workspace: **run `corepack pnpm install --frozen-lockfile`
before believing any red from the status scanner.**

Independently recomputed at architect review: status governance
`47 / 15 / 55 / 0 / 3` (classifications 15 lattice-derived / 24 interaction-state
/ 8 removed); disposition register 261 roots (denominator unmoved: 15 deleted /
200 rebind / 25 retire / 16 wire / 5 use-as-is), 13 supplemental findings, 23
seeded negatives, 8 censuses; Atlas governance unittests 98/98; the baseline
manifest carries `violations: []` for lint (75 resolutions) and architecture
(36 resolutions) and exactly one open Vitest debt class. The full Vitest,
production build, ESLint, Playwright, a11y-browser, and Storybook denominators
are the slice's and its independent reviewers' receipts, not re-run at architect
review. Fence: 669 paths, zero backend/schema/generated-client/v15/frozen-locale/
CI writes; lockfile `+106/−0`, importer-only.

**DS20 / DS20-B closure note (merged 03ebc1ce8, 2026-07-20).** The server
authorization floor is live on main: 29/29 unsafe operations structurally gated,
step-up for the 6 high-stakes ops, fixture identity prohibited outside dev, the
33-value permission vocabulary projected through OpenAPI into the generated client
(consumed by **DS5** audience mapping and **DS9** decision integrity), Rego↔server
vocabulary + decision parity guards standing. The deployment-authority attestation
hardening (`c33c4d450..7fa1b5f27` — forgery / same-object-mutation / TOCTOU /
perimeter-flip / WebSocket-fall-through defenses) received architect review in lieu
of the credit-blocked final automated pass and is sound. Guardrails carry the same
5 inherited DS3 deep-import edges (owner: runtime lane) with zero DS20 additions;
the SSE order-sensitive flake is inherited and isolated. The B3/B5/scorecard/Helm
typed limitations above must clear before a production-readiness claim.

### Phase A — Pre-Activation (Layer-3-independent)

#### DS0 — Source-Of-Truth Freeze & Governing Decisions

The surface analogue of G0's discipline freeze: decisions and schemas, before
any audit or build.

Canonical governing record:
[Atlas Source-Of-Truth And Governing Decisions](../../brand/ATLAS_SOURCE_OF_TRUTH.md).

**Status (2026-07-16):** DS0 is complete on
`codex/atlas-ds0-source-of-truth` and awaits architect review. **D4 was
RATIFIED the same day** (`7b6933770`, owner `@DenisKopylov`; recorded
`ratified` in `docs/brand/ATLAS_SOURCE_OF_TRUTH.md` §D4 and pinned in the
disposition register's DS0 source block, `decision_date: 2026-07-16`): `uk`
primary Ukraine-facing, `en` baseline/fallback, **`ru` UI catalog
`legacy_continuity_frozen` — not used, not deleted** (retained in-tree,
excluded from active locale exposure and from any public locale-support
claim). The 2026-06-11 DS0 draft's "frozen-but-served" wording is superseded.
Loosening the ratified posture is out of scope for every slice.

- **Goal:** one canonical design source of truth and the governing decisions
  every later slice references.
- **Deliverables:** v4/v7/v15 **supersession decision**
  (`docs/brand/ATLAS_DESIGN_SYSTEM.md`, `ATLAS_V4_ADOPTION.md` superseded as
  governing sources but retained as v4 evidence; `FRONTEND_SOTA_PLAN.md` and
  `DESIGN_BEST_IN_CLASS_PLAN.md` archived via docs lifecycle; v7 retained only
  as DS11-DS13 material; historical G naming retained without execution
  authority);
  **token pipeline decision** (one source of truth, sunset for the loser —
  closes T6); **package home + versioning decision** (e.g. `packages/atlas-ui`,
  release policy, Figma source-vs-projection status with parity ownership);
  **i18n/locale evidence package and recommendation** (delivered, and
  **ratified as D4 on 2026-07-16** — `ru` is `legacy_continuity_frozen`:
  not used, not deleted; includes RTL posture and owner);
  **feature-flag registry decision** (the 12
  manifest-driven flags get owner, intent, sunset, and an explicit role in the
  shadow-shipping discipline; the dual flag source — manifest vs `/auth/me`
  overrides — collapses to one governed path); **non-web surface disposition**
  (`packages/cli` styleguide, `docs/brand/` email/print/CLI/glyph/motion
  specs: each named surface family is admitted into a slice's scope or
  recorded explicitly out-of-scope); **adoption ledger schema** and **surface
  readiness ledger schema**, each with a valid example and in-fence
  self-validation, under `architecture/atlas_surfaces/`.
- **Laws / patterns:** Rule 10; closes P06.
- **Negative controls:** every decision records rejected alternatives and
  revisit conditions.
- **Not yet:** nothing is audited, adjudicated, or shipped here — DS0 decides
  and defines.

#### DS1 — Live Application Audit

- **Goal:** an honest chain status for everything the app already ships.
- **Prereqs:** DS0 (ledger schemas).
- **Deliverables:** **route/feature chain audit** of the full proving-ground
  inventory with an adoption verdict and capability-chain status per
  route/feature; the five **named audit hotspots** reported explicitly
  (inherited public route incl. signing mechanics; `causal`/`whatif`/`lex`/
  `composer` P15/P05 laundering check; **authz/audience gap report** — every
  UI-hides-but-server-allows gap named; **cache/offline policy report** — what
  may be cached with what staleness rendering, what is barred from the offline
  queue; workers boundary check against law 9); seeded red-first negatives for
  later slices.
- **Laws / patterns:** capability reality bar; seeds P15/P05/P26 negatives.
- **Negative controls:** the audit itself is evidence-bearing — every verdict
  links to the code it judged.
- **Not yet:** findings are classified, not fixed; nothing is unfrozen.

#### DS2 — Atlas v15 Adjudication

- **Goal:** the v15 archive fully adjudicated into the adoption ledger —
  against the **living coded v4** (`shared/ui` 89 implementation TSX across 12
  families with uneven a11y/story coverage, `designTokens.ts`), not into a void: every verdict is a
  migration decision between two real systems.
- **Prereqs:** DS0 (ledger schema, token/package decisions).
- **Deliverables:** **conformance battery** for archive claims (what "PASS" in
  the zip proves; what requires browser/AT/runtime evidence); per
  token-set/component/pattern **verdict** (`admit_as_is` /
  `admit_after_refactor` / `wrap_then_strangle` / `reject` / `defer`) with
  maturity, evidence, consuming surface, rejected deltas, sunset dates,
  **and the disposition of the in-repo v4 counterpart** where one exists;
  `defer` by default where no surface in this DAG consumes the item (anti-P13).
- **Laws / patterns:** Rule 10; P06, P10, P13.
- **Negative controls:** archive PASS reports cannot mark anything `stable`;
  every rejection records its reason and revisit condition.
- **Not yet:** admission into the ledger is not admission into production
  surfaces; no component ships to users from this slice.

### Phase B — The Waist (post-activation)

#### DS3 — Runtime Producers & Export Infrastructure

- **Goal:** the artifacts this plan renders get real HTTP producers, plus the
  shared export machinery every later twin reuses.
- **Gate:** GY-N10 merged to main.
- **Producer & bridge work (the slice IS producer work):** typed runtime API
  endpoints (or governed static exports) for the **GY frozen artifacts** — the
  depth-N capstone (`layer3_gy_depth_n_universality_contract.json`), the value
  gate contract, the disposition ledger, the engine + Fork-B censuses, the
  acquisition planner reports — plus `capability_reality_report.json`,
  `cluster_ownership_map.toml`, the 13-case proving-ground records,
  health-metric ledgers, and the surface readiness ledger — each payload
  carrying **as-of/freshness metadata** and each producer **binding the
  narrowest upstream projection hash (GY §3.5.11)**, so artifact rebaselines
  upstream do not ripple through every endpoint; payloads expose recomputed
  structural properties, never pinned terminal labels (GY §3.5.10); **shared export machinery**: stable
  addressing, replay pinning, typed packet conventions — **extending the
  existing export endpoints** (lineage `openlineage`/`prov`, artifact packet
  export/render, decision-validity), not reinventing them; **off-contract
  channel governance**: the two `include_in_schema=False` SSE endpoints and
  the review WebSocket hub get typed/governed contract coverage or an explicit
  out-of-scope record, and the phantom collaboration REST gets a
  build-or-remove decision; OpenAPI schema + `runtime-api-client`
  regeneration.
- **Laws:** 9; the producer/bridge half of the capability bar.
- **Negative controls:** P01 at the producer level — an endpoint that
  re-derives instead of projecting the governed artifact fails its semantic
  test; payloads without as-of metadata fail contract tests.
- **Not yet:** no UI; producers are proven by contract tests and the
  reference shell, not by new screens.

#### DS4 — Status-Grammar Rebinding & Test Harness

- **Goal:** the define-once visual grammar of authority, bound to generated
  contracts. Per the technical snapshot this is a **rebinding slice, not a
  component-building slice**: `ProvenanceStrip`, `trust-view`, `quantity`,
  `temporal`, `Badge`, `EmptyState` and peers already exist with a11y tests —
  what they lack is binding to the authority lattice.
- **Gate:** DS3 (regenerated client types).
- **Deliverables:** evidence-bearing primitives — `AuthorityBadge`,
  `CandidateFrame`, `BlockerCard`, `EnvelopeChip`, `EvidenceLink`,
  `ProvenancePopover`, `TimeSemanticsLabel` (covers `cached(as_of)`/`stale`
  rendering), `WeakestLinkExplainer` — **built by rebinding the existing
  component families to generated client types** (names indicative; task plan
  finalizes the build-vs-rebind call per component); **retirement of UI-local
  status vocabularies** — the 23 named + 24 inline local definitions (incl. `DisputeStatus` ×3)
  migrate to lattice-derived types or get explicit non-authority
  classification; `fixture_only` marking machinery (type + visual treatment);
  the existing Storybook/a11y harness and the **existing Playwright visual
  spec + snapshots** extended to cover the primitives and wired into CI;
  primitives proven on one existing strangled panel.
- **Laws:** 1, 2, 3, 4, 6, 8, 10.
- **Negative controls:** candidate output rendered in authority dress fails
  visual regression; weakest-boundary explanations come from the API, and a
  client-side recomputation fails its semantic test; a revived UI-local status
  enum fails review against the retirement ledger.
- **Not yet:** no new product routes; no lints yet (DS5).

#### DS5 — Enforcement Waist: Lints, Audience Mapping, Cache Discipline

- **INHERITED OBLIGATION from DS16 (registered 2026-08-18; corrected by the architect the same day
  after measuring it against DS5's own checker) — this is a POST-MERGE reconciliation, and neither
  branch can discharge it alone.** DS16 retired `readinessScientificContainment.test.ts` and bound
  both panels, which leaves the disposition register pointing at a deleted file. The first
  registration named DS5 as owner because the pinning checker is DS5's. That is where the checker
  lives, but it is **not** a task DS5 can execute, and the end state first recorded here was **not
  satisfiable**: following it produces checker errors, not zero. Measured on
  `codex/atlas-ds5-enforcement-waist` at `94e2c8ca0`:

  | fact | anchor on the DS5 branch |
  | --- | --- |
  | `C23_ROOT_IDS` — the four rows | `check_frontend_disposition_register.py:5549` |
  | `C23_SUCCESSOR_REFS` — third entry still the retired test | `:5558` |
  | `C23_RATIONALE` — still "until DS16 provides…" | `:5563` |
  | exact-equality compare on `consumer_refs` | `:7966` |
  | generic existence check on `consumer_refs` | `:7339` |

  The anchors `:1484` / `:3410` in the first registration are **DS16-branch coordinates**; on DS5 the
  same symbols sit at `:5558` and `:7966`. Cite the symbol, not the line.

  **Why the first end state fails.** `_validate_c23_containment_roots` pins
  `disposition == "rebind_pending"` for every root and compares `consumer_refs` for exact equality;
  the generic path additionally existence-checks each `consumer_ref` under
  `rebind_pending and strangled`, and emits `successor_on_non_rebound` when a successor survives any
  other disposition. Against those three guards:

  1. Following the instruction literally — change the third ref **and** move the four rows out of
     `rebind_pending` while keeping their successor blocks — yields four
     `c23_containment_root_drift` plus four `successor_on_non_rebound`: **eight errors**.
  2. The minimal variant — change the third ref and leave the rows in `rebind_pending` — yields four
     `rebound_consumer_missing`, because `ds16SuccessorContainment.test.ts` **does not exist on the
     DS5 branch**; it exists only on `codex/atlas-ds16-value-grammar`: **four errors**.
  3. Removing the successor blocks to escape (1) contradicts the same validator's
     `successor.unit_id == C23_SUCCESSOR_ID` requirement.

  **Correct disposition.** The pair goes green only in the **merged** tree, where the successor test
  file and the pinning checker coexist. Merge order is unchanged — DS5 lands first — so the
  reconciliation belongs to the **DS16 merge**, editing DS5's checker at that point.

  - **DS5 must not touch** the four C23 rows, `C23_SUCCESSOR_REFS`, or `C23_RATIONALE`. At C20 it
    records this as a named non-claim in the closure's explicit "what is not claimed" section,
    carrying the error identifiers above, so the successor inherits a proven statement rather than a
    guess.
  - **The DS16 reconciliation** then changes the third `C23_SUCCESSOR_REFS` entry to
    `ds16SuccessorContainment.test.ts`, rewrites `C23_RATIONALE` to the delivered state — its own
    condition, *"until DS16 provides producer-signed fields or registered typed refusal"*, is
    satisfied by the registered typed refusal — and **leaves the four rows in `rebind_pending`**,
    which is what the validator requires and what the successor block presupposes. Both closure
    conditions are already established on the DS16 branch: real consumer — panels bound to
    `useRunAuthorityValues` rendering typed refusals with behavioural proof; strangled — minting
    modules deleted at `bc1d01001`, witness retired in the rewire commit, successor covering 10 of 11
    ancestor corruptions with the one gap declared.

  **Also inherited:** `census_observation_drift:census-browser-signing-protected-live:reference_count`
  is a **coordinate move, not a membership change** — `quantityDecisionProducerHarness.tsx:139 → :148`,
  byte-identical line content, count unchanged at `28`. DS16 deliberately did not bump it because DS5
  is replacing line-numbered census references with content-addressed identity tokens, which removes
  this drift class structurally; it resolves on that migration rather than by editing a number.
  **Merge ordering:** DS5 lands **before** the DS16 branch — DS5 carries `+2,372` lines of the same
  register DS16 edited (measured at `94e2c8ca0`; `+2,315` was the figure at first registration), so
  the later DS16 merges the more it costs.

- **Goal:** the laws become mechanical. **(Revision 3 re-cut: the server-side
  authorization half — per-permission deny, step-up, fixture prohibition,
  OPA resource binding — moved to DS20; DS1 measured it as systemic (29/29
  mutating operations) and it must not wait behind the status grammar. DS5
  consumes DS20's single permission vocabulary.)**
- **Gate:** DS4 (**closed & merged 7f450eb7b**); DS20 vocabulary; DS1 reports
  (cache policy). **All gates are satisfied — DS5 is the critical-path Phase-B
  lane. DS6 is independently unblocked by DS4 and may run in parallel** (its
  paths are the evidence harness and i18n; DS5 must not take DS6's work).
- **Inherited entry contract from DS4 (registered 2026-08-01 — read this before
  scoping):** DS4 hands DS5 **three canonical-waist vocabularies the generated
  client does not project**, each already narrowed to exactly **one**
  presentation-only swap module, with the generated-client anchor measured:
  **CGF disposition** → `shared/ui/compounds/cgfDispositionPresentation.ts`
  (`canonicalRuntimeApiClient.ts:516`; `types.ts:5850-5879`
  `GenerationCycleDispositionPayload` — owner JSON currently passes opaquely);
  **decision grade** → `shared/ui/compounds/decisionGradePresentation.ts`
  (missing `DecisionGrade` export; client export block `333-394` — every owner
  label currently renders `unrecognized`); **cache-age lattice** →
  `shared/ui/temporal/cacheAgePresentation.ts` (`canonicalRuntimeApiClient.ts:737`;
  `types.ts:8164-8182` `ProjectionFreshness` — source freshness stays source
  truth, cache age is never inferred from timestamps). Authority:
  `architecture/atlas_surfaces/ds4-waist-debt-register.json`; estate denominator
  effect **none**. DS5 supplies the closed unions through the generated client
  and swaps them at those three modules — **it does not invent a frontend
  vocabulary**, and the two negatives per module (novel owner label → explicit
  `unrecognized`; module exports no value-level constants) must survive the
  swap. Terminal kinds and evidence classes remain opaque extensions end to end;
  DS5 does not close or order them. DS5 also inherits the **architecture
  recurrence lints**: DS4 severed 36→0 in both engines, and the DS5 battery is
  what makes the class unrepeatable.
- **Fence authorization (architect, 2026-08-01 — granted at the DS5-C00 stop
  gate).** DS5's C00 correctly refused to widen its own fence and stopped: the
  slice must regenerate the typed client, but the original writable list named
  only `src/polisyos/runtime/http/**` and omitted both the generated snapshot in
  between and the mirrored contract tests. That omission made a *governed
  obligation* a fence violation —
  `architecture/generated_artifacts.toml` declares
  `schemas/runtime_api_v1.openapi.json` with
  `source_of_truth = "src/polisyos/runtime/http/**"`, `commit_policy =
  "committed"`, `stale_output_behavior = "fail"`, and a freshness rule requiring
  regeneration whenever runtime routes or DTOs change; the client
  (`packages/runtime-api-client/**`) in turn declares the snapshot as *its*
  source of truth. Both ends of that chain were writable and the middle was not.
  **Now admitted, narrowly:** (a) `policy-engine/schemas/runtime_api_v1.openapi.json`
  **exclusively through the registered exporter** (`regenerate_commands` in
  `generated_artifacts.toml`) — any hand-authored diff to any `schemas/**` path
  is a STOP; (b) exactly five existing mirrored tests under
  `policy-engine/tests/unit/runtime/http/` —
  `test_authorization_audience_denials.py`,
  `test_runtime_permission_vocabulary.py`, `test_governed_projection_api.py`,
  `test_governed_projection_service.py`,
  `test_runtime_api_contract_hardening.py` — edited only for the DS5 HTTP/schema
  contract, in the same commits as their HTTP models and generated output. Any
  sixth backend test path is a STOP. Verified disjoint from the concurrent GY
  `runtime/quality` lane.
- **Enforcement-mechanism ruling (architect, 2026-08-02 — binding on every DS5
  lint).** DS5-C01 was stopped after three independent NO-GO reviews, each
  finding a *new* bypass class in a whole-program TypeScript dataflow analyzer
  (points-to, heap identity, CFG, abrupt completion, closures, HOFs — 1,609
  scanner lines). Three reviews finding three new classes is not an
  implementation-quality signal; it is proof the **mechanism** is wrong. Deciding
  "no unauthorized value reaches this sink by any path" is undecidable over real
  TypeScript, so a scanner that claims that invariant is P31/P33 — an optimistic
  completeness envelope that licenses false confidence.
  **The sound mechanism already exists and DS4 built it.**
  `packages/atlas-ui/src/primitives/AuthorityBadge.tsx` defines
  `AuthorityPresentation` as a branded type keyed by a **module-private, never
  exported** `unique symbol`; `createPresentation` is module-private; only three
  exported factories issue it, each deriving clothing from a *generated owner DTO
  field* rather than a caller-selected tone; runtime guards reject
  `fixture_only`, reject labels absent from the owner list, `Object.freeze` the
  result, and record issuance in a `WeakSet`; exhaustiveness is already compiled
  in via `satisfies Record<OperatorProjectionLabel["state"], BadgeTone>`. A raw
  unauthorized string therefore **cannot** be assigned to
  `AuthorityBadge.presentation` — TypeScript's assignability check, which *is*
  sound, rejects it regardless of how the value flowed. The decisive evidence is
  the third reviewer's own refutation witness: all six carriers (dynamic-key
  spread, computed key, assignment destructuring, component alias, `Array.map`,
  module-level JSX) require an explicit `cast(...)` assertion to reach the sink.
  That is the brand working, defeated only by an enumerable escape hatch.
  **Therefore every DS5 lint is re-cut onto this shape:** put the obligation in
  the **type system** (branded authority values, module-private issuers,
  compile-time exhaustiveness against generated unions) and let `tsc` be the
  enforcement engine; reduce the bespoke checker to **decidable, local, syntactic
  invariants** — the brand is constructed only inside authorized modules; no
  `as` / `as unknown as` / `any` / `@ts-ignore` / `@ts-expect-error` / unsafe
  `satisfies` on authority paths except through *typed, enumerated* exemptions;
  adapters bind exhaustively and return explicit `unrecognized` for runtime-novel
  values. **State the residual honestly:** the brand is compile-time, the
  escape-hatch lint is syntactic, runtime novelty is the adapters' job — DS5
  claims those three, and does not claim a complete flow invariant. No DS5 lint
  may reassert one.
- **Execution-order law (architect, 2026-08-02 — added after the ruling above was
  over-applied).** The mechanism ruling binds each lint **when that lint is
  built**; it is not a licence to re-derive the whole plan before writing code.
  Read literally as a task, it produced a session with **zero net output**: the
  slice plan grew 1,104 → 1,902 lines across ~15 independent plan reviews while
  HEAD stayed on a rejected commit and the work sat in a stash. That is the
  *over-specified-contract gravity well* and P01 contract-only capability — the
  exact anti-patterns this programme distilled. Three rules follow, binding on
  every Atlas slice.
  **(1) Re-derive at entry, not ahead.** A cluster's mechanism re-derivation
  happens in that cluster's own commit, when it is entered. Planning a cluster
  you are not about to execute is deferred work, not progress.
  **(2) Plan-only commits are capped.** After a slice's C00 is committed, a
  plan-only commit is allowed **once** per architect ruling that forces one.
  Every other commit must change product or test code. Plan prose has no
  fixpoint — code does (its tests pass) — so unbounded review of a document
  converges on nothing. Independent review remains mandatory for **code**;
  for plan text it is **one round**, scoped to the cluster about to be entered.
  **(3) A downstream owner gap never halts upstream clusters.** Pre-sized
  clusters exist to execute independently. When cluster N hits a canonical-owner
  gap, record it as a typed integrate-debt row with its owner and closure signal,
  **defer cluster N**, and continue with the clusters that do not depend on it.
  Halting the slice is correct only when the gap blocks the cluster actually in
  hand.
- **Producer & bridge work (in-slice):** the **audience↔permission mapping**
  over DS20's server-projected vocabulary; the three waist unions above;
  weakest-boundary/status composition exposed in the schema where not yet
  projected; client regeneration through the registered exporter.
- **Deliverables:** the `[to build]` lints from laws 8/9/10/12 —
  unauthorized-status-enum lint, no-hand-written-authority-fetch lint (the 9
  known production calls in 5 files are its first targets, with typed exemptions
  for sanctioned auth/flag/telemetry adapters), capability-menu lint,
  duplicate-label/static-copy lint; **cache/staleness rendering rules**
  implementing the DS1 policy (cached payloads carry as-of; authority actions
  barred from the offline queue or carrying an explicit revalidation protocol —
  `useQueuedPromotionDecision` is the first migration; tenant/user/expiry
  partition on the six authority-like local stores DS1 found); **the D5 flag
  registry** — one strict exposure registry, unknown-key rejection,
  wire-or-retire for the four `consumer_missing` flags, rollout hard-separated
  from authorization; server-side **deny tests** per audience class (over
  DS20's enforcement).
- **Laws:** 8, 9, 10, 12; 11 (audience enforcement half).
- **Negative controls:** a UI-defined status enum turns the lint red; a
  hand-written fetch to an authority endpoint fails CI; a PUBLIC-class request
  for REVIEWER data is denied server-side in a contract test; an authority
  action enqueued offline fails its negative test.
- **Distillation augment (Rev 3.4, post-DS4; §6.5 · M31·M6·M29 — the manifest row
  previously unapplied):** the lints enforce **weakest-boundary composition into the ONE
  lattice** — a composed status is the minimum over its load-bearing inputs, a passing lane
  can never lint-silently compensate a failing one, and a veto (`blocked`, rights-bar) can
  never be averaged away in any client-side aggregation; **recompute-not-pin** becomes
  mechanical — a status trusted by presence (pinned, cached without as-of revalidation,
  copied between stores) turns the lint red, extending the DS1 cache policy from payloads
  to statuses. **Research input (INT-R6):** the duplicate-label/static-copy and i18n
  enforcement anchor on **canonical semantic IDs, never string comparison**; a translation
  that upgrades a status's semantic strength (`limited` → "confirmed with caveat",
  `may_not_use_for` → optional recommendation) is the red-first negative of the locale
  lint. **D4 is ratified and D4-A1 amended it on 2026-08-19**, so this lint is
  unblocked and anchors on the amended posture: `en` authored primary, `uk`
  translation, `ru` `legacy_continuity_frozen` — a lint or exemption that re-exposes `ru` as an active
  product locale is itself a red-first negative.
- **Not yet:** enforcement covers the waist and existing strangled panels;
  un-migrated legacy features carry honest lint-debt entries in the ledger.

#### DS6 — Evidence Workflow & Instrumentation

- **Goal:** the machinery that makes "stable" and "honest" measurable —
  gates every later `stable` claim.
- **Gate:** DS4 (harness) — **closed & merged 7f450eb7b; DS6 is unblocked.**
- **Inherited entry contract from DS4 (registered 2026-08-01):** DS6 owns the
  two evidence debts DS4 refused to absorb. **(a) Three i18n parity failures**
  (`panels.agentPipeline.overBudget` en/uk/ru in
  `shared/i18n/parity.test.ts:88` — count-sensitive message without ICU plural
  syntax or an allowlist entry). Ruling 2 moved this class from DS5 to DS6; the
  register class is `i18n-count-message-parity` and the baseline comparator
  accepts exactly these three signatures. **(b) Four axe-`incomplete` contrast
  clusters** — C01 neutral `Badge`; C06 `ProvenancePopover` +
  `ProvenanceMiniGraph`; C09 `TimeSemanticsLabel` inheritance; C14
  `CandidateFrame`, `NegativeCertificateCard`, `WeakestLinkExplainer`. These are
  neither violations nor passes: translucent/gradient ancestors defeat computed
  contrast, so axe returns `incomplete`. DS4's automated a11y denominator
  (85/85 component, 21/21 browser) is green *around* them and does not count
  them green. **DS6 lands the real-browser opaque-background probe** that
  computes a WCAG-AA result for each named identity without attributing an
  `incomplete` node to the source — and **creates the typed register row**,
  since DS4 left this class as prose only and prose does not survive a census.
  DS6 also owns independent visual + semantic verification of the DS8-owned
  `adjacent-print-export` regression.
- **Deliverables:** browser + keyboard + manual **AT evidence workflow** with
  a storage convention for evidence artifacts, wired to the component maturity
  bar; **surface-readiness-ledger CI validator** (ledger claims vs the tests
  and evidence that actually exist); **health-metric instrumentation** for the
  metrics table below, incl. review-effectiveness telemetry collection;
  **honesty-comprehension protocol** — a lightweight recurring reviewer-task
  procedure (find the weakest link, find the active blockers) with cadence and
  owner.
- **Laws:** 5; P10 closure.
- **Negative controls:** a component claiming `stable` without stored evidence
  fails the validator; a ledger entry claiming `implemented` without its
  negative/semantic test fails CI.
- **Research-input augment (Rev 3.4, post-DS4; INT-R3):** the honesty-comprehension
  protocol is the seed of the Wave-2 `AuthorityUIComprehensionBenchmark` — when that
  research lands, the reviewer-task procedure upgrades from "find the weakest link" to the
  **behavioral** battery (`false_action`, `false_pass`, `missed_blocker`,
  `unsafe_override`, time-to-correct, confidence-vs-correctness calibration; `unknown` ≠
  zero ≠ missing; `incomparable` = no-admissible-ranking; refusal of stale/quarantined —
  under keyboard-only, screen-reader, low-numeracy, time-pressure) and its thresholds
  join the `stable` bar for every **interactive authority surface** (DS7/DS9/DS15–DS18).
  DS6 owns the instrument; the benchmark's content arrives from INT-R3, not invented here.
- **Not yet:** no product surfaces; DS6 measures, it does not ship screens.
- **CARRIED DEBT (Rev 3.18, recorded 2026-08-18) — DS6's executable set is exhausted and the
  slice is `blocked_on_another_plan`, NOT closed.** `C14`, its own closure cluster, is deliberately
  unentered: closing it while executable work waits elsewhere is the overclaim this slice exists to
  prevent. Landed through `C10-R2` at `fa1f3e4d0`. Three debts survive the slice and each has a
  named owner, so none of this is re-derived when DS6 reopens:
  - **`C03`/`C04`/`C06` wait on DS5-`C21`.** The governed writes stay descriptive until the register
    owners are released. They then run as three separate append-only transitions, each rereading
    current owners and content-hash anchors at entry.
  - **`C13`'s governed transition waits on DS8** — a print repair, an independently established
    semantic-non-overlap result, and two consecutive stable no-update captures. `C13`'s verification
    half is already landed; only the transition is held.
  - **`transitive-runner-closure-unbound` is `absent/unallocated`.** `observed_by_reconciler` attests
    intake closure, not runner integrity under local code modification. Closing it needs an
    out-of-band runner identity; a falsifier over all `9,870` tracked files found none in this
    repository, so the label is earned rather than assumed.
  - Also open under their own owners: the `atlas-health-metric-replay-pins-uncommitted-paths` test
    defect in the inherited-Vitest row above, the `scenario composer dark theme` visual-lane
    instability, and the DS8 A4 print baseline.
  **Order on reopening:** DS5-`C21` → `C03`/`C04`/`C06`; DS8 repair → `C13`; then `C14` closes DS6.

### Phase C — Workspace Surfaces

#### DS7 — Cycle Board (the hero surface; supersedes "proving-ground board")

- **Goal:** the REVIEWER/EXPERT board — the interface that is proud to say
  "we do not know yet", **and shows exactly what it would take to know**.
  Revision 2 upgrades the hero from the static 13-case board to the living
  board of the GY cycle.
- **Gate:** DS5. **Producer input closed by `GY-GAP4`:** `RunSummary` now
  carries the producer-owned lifecycle fact through OpenAPI and both generated
  clients. A missing binding remains `not_established` and must render absent,
  never `false`. DS7 is the first consumer and now owns the remaining
  consumer/surface/semantic-test debt. **DS7's own negative control: the board
  may not re-derive terminality** from status substrings, `finished_at`, or any
  other proxy — a re-derivation attempt turns the C22 semantic negatives red.
- **Shape:** one row per `DesignProblem` the cycle has ever run — the three
  N10 capstone domains first (first-vertical, education, unseen/no-pack), the
  13 legacy proving-ground cases as a second cohort, and every future
  plain-language submission. Columns: typed terminal kind; **structural
  evidence class** (`owner_acquisition_route` / `estimand_binding_refusal` /
  `owner_data_gap` — recomputed, never a label); weakest missing link; the
  **costed acquisition route** (strategy, cost, VOI from the N7 planner
  report) with its execution status; responsible slice (GY-N13+ / DS-slice);
  stage-trace drill-down link (DS8); surface readiness; public-safe
  explanation. The board displays the **as-of/staleness of its own data
  sources** (law 7 applies to the board too) and renders the **surface
  readiness ledger** — this plan's own progress is an Atlas surface.
- **The refusal-with-a-path pattern is the board's core interaction:** a
  blocked row never dead-ends — it opens into what is known, the exact typed
  missing link, and the costed route; after GY-N13b, a route that closes
  renders as **movement** ("gap closed by acquisition {date} → case
  re-entered → deeper terminal"), making the flywheel visible.
  **Revision 3 (the N13a lesson):** the pattern generalizes beyond data
  fetches — GY-N13a recomputed all three capstone routes as
  `not_a_data_gap` (grounding-relation / estimand-binding gaps, not row
  gaps). The board's "missing link" column renders **whatever the typed gap
  is** (a grounding relation, an owner lever, an estimand binding, OR a data
  need), each with its owning route — and never launders adjacent row counts
  into support for a structural gap.
- **MACHINE twin (in-slice):** typed JSON export on DS3 machinery with a
  parity test.
- **Laws:** 3, 4, 5, 12; P25 negatives (frontier shown as control-plane
  evidence, never as exhaustiveness).
- **Closure:** semantic test — the board's weakest-link and evidence-class
  claims equal the artifact's recomputed values, not a client-side
  recomputation and not a pinned string.
- **Not yet:** REVIEWER/EXPERT only; the board does not go PUBLIC before
  DS12's gate; the movement row is honest-empty until N13b actually closes a
  route (no simulated motion).
- **DS7 branch closure (2026-08-21; no plan revision assigned):** the static
  v2 board is the sole human renderer and its MACHINE download preserves the
  exact response bytes. The real rendered-DOM decoder closes the semantic
  parity test with dropped-row, duplicate-row, defaulted-absence,
  omitted-source, fabricated-movement, and localized-raw mutations. GAP5 and
  GAP6 render as typed `not_established` absences with their owner routes and
  closure signals; known membership stays non-exhaustive and movement stays
  honestly empty. The surface renders owner-supplied terminal, structural,
  source, accounting, and bound planner-economics values, but policy substance
  remains refusal/gap-shaped: it renders no policy quantity, effect, or
  welfare value. DS16's stated value-surface re-entry condition is therefore
  **not satisfied**. The gate remains `runs.review`, audiences remain
  REVIEWER/EXPERT, and no PUBLIC claim is made.
- **DS7 verification standing, carried not closed (architect, 2026-08-21 at
  merge `74f26ca2d`).** The slice was merged on verified mechanism; two
  measurements did not complete and are recorded as unmeasured rather than
  green:
  - **Full dashboard ESLint is a non-receipt across four attempts** — three at
    a fixed 120 s ceiling and one at 300 s, each interrupted by its controller
    having emitted zero diagnostics. No ceiling was widened mid-run and no
    partial result was admitted, which is the correct handling; the consequence
    is that the whole-app lint population is **neither pass nor fail** at this
    merge. The exact Task 8 and Task 9 write-set lint receipts are green, so
    what is unmeasured is the population outside DS7's write set. Any lane that
    needs a whole-app lint receipt must take it on an uncontended host; it is
    not inherited as green from here.
  - **Raw-v1 API byte parity remains an environment non-receipt** — this
    worktree has no `production_data/manifest.json`, so the owner packet is a
    real `invalid_source` without the four replay pins. No mock, root-checkout
    read, or weaker tuple was substituted. This is the same standing environment
    gap the *Producer availability denominator* row already carries; it is not a
    DS7 finding.
  - Task 6's atomic generated commit has a 283,577-byte raw patch and its
    contemporaneous record did not preserve per-review-package byte breakdowns,
    so Task 6 per-package size compliance is **`not_established`** — not
    inferred from the later Task 8/9/10 review layout, which was individually
    bounded below 28 KB.

#### DS8 — Case & Evidence Workspace (strangling)

- **Goal:** case inspection over real artifacts, and the legacy features
  brought through the waist.
- **Gate:** DS7.
- **Producer & bridge work (in-slice):** case/DesignRecord inspection
  endpoints where missing; schema + client regeneration.
- **Deliverables:** DesignRecord/case inspection with grounding/admission/
  promotion state; blockers, limitations, objections, abstentions as
  first-class objects; **strangle moves**: `evidence`, `runs`, `artifacts`
  features migrate to DS4 primitives, with ledger-tracked migration coverage;
  MACHINE twin per shipped view.
- **Laws:** 3, 4, 6, 7.
- **Inherited debt from DS4 (registered 2026-08-01):** the
  `adjacent-print-export` run-detail A4 print regression — the global
  `a[href]::after` print rule emits the full long signed public-decision URL
  into the report, overlapping content and preventing a stable capture
  (expected 724×2113, actual 770×13229). DS4 left the committed expectation
  **byte-unmodified** and reported the visual suite honestly as 17/18 rather
  than re-baselining a defect into green. DS8 owns the product repair; DS6
  owns independent verification. Closure signal: no generated link URL overlaps
  the report **and** two consecutive no-update real-browser A4 captures are
  stable.
- **ENTRY QUESTION FOR DS8, with a starting hypothesis and NOT a decision (recorded
  2026-08-20 after the DS6 diagnostic).** The `adjacent-print-export` cause recorded in
  the bullet above is **measured false** and is superseded here rather than rewritten.
  Three things were established by no-writer measurement and DS8 should not re-derive
  them:

  1. **The signed URL is not the cause.** Suppressing only the 17,206-character signed
     target moves the capture from `770×13269` to `770×12966`; suppressing *every* link
     target reaches `770×12918`. It contributes ~303 px of roughly 10,850 excess, and it
     cannot explain the width at all — pseudo-content cannot change an element's border-box
     width. DS6 landed the narrow signed-target exclusion; ordinary printed destinations
     are preserved.
  2. **The `724×2113` expectation was never a capture of this surface.** All five A4
     snapshot names were assigned the same 231,141-byte blob in bulk commit `45f330235`;
     four have since been re-derived to distinct dimensions and pass, while `run-detail`
     still holds that original blob. Independently: `.atlas-shell-frame` computed
     `100vw − 24px = 770px` from `3535d89f` on 2026-03-10, six weeks *before* the snapshot,
     so a 724-wide PNG cannot be a capture of a 770-wide element. Deriving a replacement is
     therefore a **first derivation**, not a re-baseline.
  3. **The real regression is print-visible interactive chrome.** `3f7af28e59` (2026-05-01)
     introduced `OperatorCraftPanel` — its own source calls it *reviewer workflow chrome* —
     and `AmbientTelemetryHud`, mounted at `RunDetailLayout.tsx:793`, neither print-hidden,
     although `print.css` already defines a chrome-exclusion boundary. A printed decision
     report containing forms, sliders, buttons and wallet actions is wrong on its own terms,
     independent of any pixel count.

  **The question DS8 must answer:** *what does a printed decision report contain from a
  mixed-content panel?* `OperatorCraftPanel` is not affordance-only. A complete source
  census found seven control sites **plus** persisted reviewer annotations, threshold state
  and impact values, saved evidence references, and onboarding audit state. And
  `AmbientTelemetryHud` is not separable overlay chrome: it holds
  `operatorCraftVersion`/`refreshOperatorCraft` and therefore *mounts* the panel, and it
  builds the signed public decision packet. Excluding it takes the panel with it.

  **Three answers, with their costs.** Exclude the panel wholesale — cheap, and it discards
  real report and audit content from paper. Leave it as-is — prints affordances, wrong by
  construction. Split it, so persisted state prints and affordances do not — more work,
  because it requires marking inside the panel what is state and what is control.

  **Starting hypothesis, explicitly not a ruling: the split.** It is where the architect
  would begin, for two reasons: printing values while suppressing the buttons that set them
  is ordinary print practice, and this codebase **already encodes that principle** — the
  `print.css` chrome-exclusion boundary lists `nav`, `aside.dashboard-shell`,
  `.app-sidebar`, `[data-a11y-overlay]`, `[data-print-hidden]`, and the two panels were
  simply never brought under it.

  **This is a base for the search, not its conclusion.** DS8 is expected to test it and may
  well find better. Reasons it could fail: some of the panel's state may be browser-local
  and genuinely out of scope for paper, which the DS6 census deliberately did **not**
  classify; the split may require a boundary the panel's structure cannot express without
  restructuring; or the honest answer may be that the run-detail print surface needs a
  distinct paper projection rather than a filtered screen tree. If a fourth answer fits the
  evidence better, take it and record why the split lost.

  **Also unresolved and DS8-adjacent:** whether a full-element raster of an unbounded-height
  surface is a valid governed expectation at all, or a `P38` gate that cannot distinguish a
  regression from legitimate growth. It failed for six weeks while pointing at the wrong
  cause. DS6 was stopped before adjudicating it; the candidates recorded are a paginated PDF
  under `@page size: A4` asserting page count and geometry, a bounded-region capture,
  semantic DOM invariants, or dimensions with a declared tolerance and growth policy.

  **BASELINE MOVED BY DS7 — every pixel figure above is pre-DS7 (recorded by the architect
  2026-08-21 at the DS7 merge).** DS7's strangle removed the stale in-panel run-detail
  renderer, which changes this same screenshot payload. DS7's serialized visual lane
  measured the run-detail A4 capture at **`770×12949`, 704,292 differing pixels**, against
  the unchanged committed expectation `724×2113`. DS7 did not update this block — correctly,
  since DS8 is not its slice — and it did not relabel the red or re-baseline the snapshot.
  Three consequences, and DS8 must not compute on the old numbers:

  1. **The entry question's arithmetic is stale.** Point 1 above reasons from `770×13269`:
     suppressing the signed target reaches `770×12966`, suppressing every link target reaches
     `770×12918`. The post-DS7 baseline of `12949` already sits **below** the
     signed-target figure and only **31 px** above the suppress-everything figure. Those three
     deltas must be re-derived at the post-DS7 base before any of them is used as evidence.
  2. **The hypothesis is untouched, and weakly corroborated.** DS7 removed print-visible
     interactive chrome and the capture fell by roughly 320 px — the same order as the entire
     ~303 px signed-URL contribution DS6 measured. That is consistent with point 3's claim
     that chrome, not the URL, is the regression. It is corroboration, not proof: DS7 removed
     a renderer for its own reasons and no controlled comparison was run.
  3. **Two pre-DS7 figures already disagreed, and neither is DS7's doing.** The inherited-debt
     bullet above and the debt-table row both record actual `770×13229`; Revision 3.22 and
     point 1 of this entry question record `770×13269`. That 40 px gap predates DS7 and is
     unexplained — most likely two captures at different commits recorded as one value. DS8
     inherits **three** superseded numbers, not one, and its first derivation should establish
     the post-DS7 value itself rather than reconcile the historical pair.

  **AMENDED at the DS6-C19 merge `fffd9013a` (2026-08-21): there are four states and three
  are measured.** DS6's scoped signed-target suppression (`1fc07ed01`) and DS7's strangle
  are now **both** in `main`, and no capture has been taken on that combination:

  | tree | A4 actual |
  | --- | --- |
  | neither change | `770×13,269` |
  | DS6 scoped repair only | `770×12,966` |
  | DS7 strangle only | `770×12,949` |
  | **both — current `main`** | **`not_established`** |

  DS8 must **measure** the fourth cell, never derive it. The `303` px signed-target
  contribution and the roughly `320` px of removed chrome were measured against different
  baselines, and nothing establishes them as disjoint layout regions, so subtracting them is
  arithmetic dressed as evidence. This does not change the verdict: the `724×2113`
  expectation is a placeholder, and a placeholder is wrong at all four heights.

- **Negative controls:** closed-case views pin versions (law 7) and a mutation
  attempt fails; P15 negatives land on any engine-output panel the audit
  flagged.
- **Not yet:** no public projection of cases; no NL entry points; approval
  flows stay read-only until DS9.

#### DS9 — Human Decision Integrity

- **Goal:** approval, override, and blocking flows a principal can be
  accountable for.
- **Gate:** DS8.
- **Producer & bridge work (in-slice):** `HumanDecisionRecord` read/write
  endpoints with **step-up authentication** enforcement (law 11's `[to build]`
  half) and review-effectiveness telemetry events — drawing on the existing
  **append-only access-audit trail** (`http/access_audit.py`) rather than a
  new log. The existing `POST /runs/{run_id}/production-approval` endpoint
  (recon: no per-permission deny) is brought under the same enforcement.
- **Deliverables:** approval/override/blocking flows showing mandate, evidence
  exposure, dissent, override reason; step-up auth on high-stakes actions;
  MACHINE twin of decision records.
- **Laws:** 11; 7.
- **Negative controls:** P26 negatives — a rubber-stamp approval (no evidence
  opened, no mandate shown) is blocked and surfaced; an approval attempted
  from the offline queue is rejected pending revalidation.
- **Distillation augment (Rev 18, post-DS4; §6.5 · M34·M37):** render the **GY-PA2** delegation
  packet as a **pre-action gate**, not a post-hoc log — identity ∩ permission ∩ mandate-bounded
  delegation ∩ envelope ∩ live accountability; a wrong-role or expired-TTL approval, and a
  search-authority reused for `data_request`, both render `blocked` with reason. Contestability is
  **proven, not gestured**: an "Appeal here" control bound to no case, and a rubber-stamp review
  (reviewer independence / change-authority absent), both fail red.
- **Not yet:** delegation-chain UI now lands via **GY-PA2** (superseding the base deferral); no
  public rendering of decisions (DS12).

#### DS10 — Capability Discovery

- **Goal:** navigation and pickers that are search-driven over typed indexes —
  the Rule 12 dual, made real.
- **Gate:** DS5; meaningful adapter-registry content.
- **Producer & bridge work (in-slice):** typed search/discovery endpoints over
  the corpus indexes and the search-frontier ledger projection (request,
  selected and rejected candidates, cutoffs, incompleteness reasons);
  **re-grounding of the existing capability manifest** — `GET
  /control/capabilities` is today a hand-maintained `CapabilityFeatureInfo`
  enumeration (`services/control/capabilities.py`), a live Rule-12 case: DS10
  rebuilds it on registry/discovery search or re-classifies it as fixed app
  chrome with a strangle note; `control/data/catalog/search` is the discovery
  seed to extend.
- **Deliverables:** discovery surfaces for methods, datasets, sources, legal
  norms, cases, agents rendering the three postures (`discoverable` /
  `executable` / `admitted_authority`) and the frontier honestly; fixed
  workspace chrome explicitly separated from capability discovery.
- **Laws:** 2, 12.
- **Negative controls:** the capability-menu lint goes red on a hardcoded
  enumeration; the **free-growth UI test** — a correctly admitted new adapter
  appears with zero frontend code change; P25 negatives on no-hit/recall
  rendering.
- **Not yet:** discovery never implies admission; `discoverable` is visibly
  candidate-grade.

### Phase D — Outward Surfaces

#### DS11 — Trust / Docs Posture

- **Goal:** posture honestly stated before any performance claims exist.
- **Gate:** DS9; DS6 (evidence workflow operational).
- **Producer & bridge work (in-slice):** the **claims register** as a typed,
  owned artifact (source, jurisdiction, owner, review date,
  `authoritative_for` / `may_not_use_for` per claim) with its producer and CI
  check.
- **Deliverables:** methodology, envelope and limitations, accessibility
  conformance evidence surfaces; supported/planned/blocked register; MACHINE
  twin of the register.
- **Laws:** 5, 6.
- **Identity augment (Rev 3.4, post-DS4):** the posture story is anchored in the
  **ratified identity** (`docs/system-design-decisions/policyos-identity-and-custody-boundary.md`):
  the public copy states what the system IS — the epistemic custodian of policy
  justification (grounded design or costed refusal; signatures kept honest over time) —
  and what it is NOT (the binding anti-roles: not an administrator, executor,
  case-management system, court, notification channel, or payment system). The claims
  register carries the custody promise as a first-class claim family: "every published
  signature is watched for staleness and superseded, never silently edited."
- **Negative controls:** P05 negative — copy that upgrades `planned` or
  `candidate` to `supported` fails the claims-register check; posture copy implying an
  anti-role capability (e.g., "manages your cases") fails the identity check.
- **Not yet:** no grounded-performance claims until the runtime earns them.

#### DS12 — Public Publication Foundation

- **Gate (constitutional, re-stated in Revision 2; research inputs added in
  Rev 3.4):** the **first governed promotion** exists — a design promoted through the
  GY-N9 gate with GY-N11 δ-accounting and GY-N12 epoch validity live — **and** DS11,
  **and** the Wave-2 research inputs that must close **before the first public record,
  not during it**: `INT-R7` (public-verification key lifecycle: rotation, revocation,
  archival verification, anti-equivocation, offline verification), `INT-R8`
  (compression-loss + cross-projection disclosure budget for the public views), `INT-R1`
  (the δ-conditional the public claim must carry), and the `INT-R9` first-promotion
  protocol **pre-registered before any promotion candidate is inspected**. Per Rule 5
  the runtime never forces this milestone; the public surface waits honestly. Before it,
  the public-facing story is DS11 posture + the Cycle Board's public-safe projection
  (honest status, not recommendations).
- **Goal:** the first honest public surface: one promoted decision record,
  published end-to-end, verifiable by a citizen.
- **Producer & bridge work (in-slice):** public record/certificate endpoints;
  the **signing and verification chain** — server-side signing with real keys,
  server-backed verification, citizen verification UX, key-management/
  transparency posture, published not implied. This **replaces the decorative
  client-side mechanism** found in recon (browser-computed salted hash,
  forgeable): the existing packet builder is kept only as a rendering view
  model, never as the authority or signature source.
- **Deliverables:** the **public operational bar as CI checks** — no
  third-party trackers, Core Web Vitals budgets, security headers,
  mobile/responsive support, the DS0 i18n decision implemented,
  plain-language register; an explicit **public telemetry posture** (Sentry is
  wired app-wide today — on PUBLIC routes error telemetry is self-hosted,
  scrubbed, or absent; never silently third-party); the inherited
  `public/decisions/:signedId` route strangled onto the server-backed chain;
  public MACHINE twin.
- **Laws:** 4, 5, 7.
- **Negative controls:** **a forged packet must stop rendering as
  "Verified"** — the first red-first negative of the slice; P05 negatives at
  the public boundary; a public page ahead of the runtime envelope fails the
  envelope check; an unauthenticated request for non-PUBLIC data is denied
  server-side.
- **Distillation augment (Rev 18, post-DS4; §6.5 · M10·M34·M35 + P29 rider):** any public δ /
  promotion claim carries the explicit obligation-completeness conditional — **"risk ≤ δ *relative
  to the declared obligation set*"**, never unconditional (the INT-R1 dependency; distillation §6.3).
  The audience views are **one substrate → four projections** (PUBLIC/REVIEWER/EXPERT/MACHINE); the
  MACHINE twin must preserve reconstructable source/authority/audit refs (a projection that drops
  them is red). Contestability is proven (real recourse to a competent, change-authorized reviewer),
  not an "Appeal here" link. Any third-party model/data behind the claim carries a **graded
  supplier-evidence envelope** (vendor-run eval ≠ independent; "no incident found" ≠ "no incidents").
- **Ratified claim-semantics constraints (Revision 3.11; `INT-K01`–`INT-K08`,
  `docs/system-design-decisions/int-wave-claim-semantics-ratification.md`).** The INT-wave kernel is
  ratified, and DS12 is its largest product consumer. Four constraints bind this slice, and one
  architectural default is settled in its favour.
  - **The `INT-R9` gate input is discharged, and it resolved to a *nonnumeric* protocol.** The
    first-promotion protocol was amended to **Option B** — result-informed repair is kept, so every
    sequence-level number is withdrawn — and its independent conformance verification returned
    `CONFORMS_WITH_GAPS` with both gaps closed. The pre-registration requirement in the gate above
    is unchanged; what changed is what pre-registration buys. DS12 consumes a **custody** claim.
  - **What DS12 may publish about firstness (`INT-K06`).** A bounded custody and anti-selection
    statement: prospectivity, firstness, substitutions, chronology, adjudication, deviations,
    negative terminals, publication, correction — and the statement that no prohibited substitution
    was found in the governed record. It may **not** be projected as statistical family control,
    population performance, compliance, competence, or production readiness. This is a real public
    claim, checkable and falsifiable; it simply carries no probability.
  - **Every rendered `delta` carries its declared set (`INT-K02`).** A public δ must identify the
    declared obligation set and maintained assumptions and visibly carry the relative-basis rider.
    This ratifies and sharpens the Rev-18 P29 rider above: the conditional is not stylistic hedging,
    it is part of the claim's meaning, and a bare δ is not a smaller claim but a different and false
    one.
  - **No new lattice, no shortcut (`INT-K01`, `INT-K03`).** Coverage outcomes feed the **existing**
    status lattice; DS12 introduces no coverage-specific lattice. `bounded_complete` is **not
    issuable** and is not a fallback for an unresolved coverage disposition — issuing it requires
    constructed independence, which is dormant research (`INT-GAP-02`), not pending engineering.
  - **Architect default, settled: DS12 does not need a number, and should not ask for one.** A
    numeric first-promotion family claim would activate `GY-GAP2` (engineering: family declaration,
    chronology verifier, aggregate current-head projection) **and** `INT-GAP-01` (research: a
    selection-valid theorem for outcome-dependent repair) simultaneously, because the protocol keeps
    adaptive repair (`INT-K07`). The cost is disproportionate to what the number would add over the
    custody claim. Reopening this default is an architect decision, not a slice decision.
  - **`INT-K08` binds the empty case.** If the first-promotion protocol terminates with refusal,
    void, dispute, or exhaustion without promotion, that is a **completed** governed result. No
    launch deadline, success quota, substitution, or public compression may turn it into permission
    to weaken this slice's gate or hide the chronology. Per Rule 5 the public surface waits honestly
    — and under `INT-K08` it may also *say* that it waited, which is itself publishable.
- **Ratified public-verification and disclosure constraints (Revision 3.12; `PV-K01`–`PV-K09`,
  `docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md`).**
  The INT-R7/INT-R8 wave closed and its nine invariants are ratified. DS12 is their primary
  consumer, and the practical headline is about this slice's **gate**:
  - **All four named research inputs are now closeable as research inputs.** `INT-R1` and `INT-R9`
    were ratified 2026-08-04; `INT-R7` is `GO_WITH_REVISIONS` with its independent closure gate met
    (controlling head `3883b454`); `INT-R8` is `accepted_narrow_scope`, independently verified
    `CONFORMS` (controlling head `286ade10`). The seam between R7 and R8 was adjudicated item by
    item in both directions and holds. **The DS12 gate itself is unchanged and remains closed** —
    research-input closure is not implementation readiness, custody, institutional competence, or
    publication authority, and the gate still requires the first governed promotion and DS11.
  - **Consume the verification vector, never a signature Boolean (`PV-K01`).** A valid signature
    supports issuer-issuance authenticity and nothing more. Issuer issuance, projection
    faithfulness, public-history establishment, durable verifiability, current authority,
    status-snapshot selection and evidence obtainability are **separately falsifiable** and must be
    separately reportable. This is what makes the citizen surface useful rather than merely strict:
    it can say *which* dimension failed.
  - **Never let a present failure edit the past (`PV-K02`).** Withdrawal, revocation, supersession
    or stale currentness make current authority false without erasing a historically authentic
    record; historical authenticity never establishes current authority. `withdrawn-but-verifiable`
    is a first-class outcome this surface must render.
  - **The forged-packet negative control now has a ratified basis (`PV-K01`, `PV-K03`).** The
    inherited public-salt 32-bit FNV token is recomputed over attacker-selectable content; it is a
    `live_defect`, not a weak checksum. Strangle it so no recomputed packet can render a governed
    positive, and never let projection, transport or possession mint authority.
  - **Reuse the real producer (`bridge_missing`, not `producer_missing`).**
    `runtime/quality/public_export.py` is a real 2,103-line producer with no proof, evaluator or
    production route. Connect it; do not erase or duplicate it.
  - **Projection semantics (`PV-K04`, `PV-K05`).** Semantic parity is use-relative conservative
    protected-query parity, not byte equality: reduce detail, never amplify truth, certainty,
    authority, currency or permission. Three omissions block categorically — a bare `delta` without
    its declared basis, a hidden negative terminal, and a no-number custody claim missing a
    constitutive step. A link to the full record does **not** repair a misleading visible summary.
  - **No number, and the default is settled (`PV-K08`).** No canonical numerical disclosure claim
    may be projected. The refusal is premise-relative, not an impossibility theorem — determinism
    is explicitly *not* the obstruction — but the premises do not exist here and DS12 does not need
    a number.
  - **Any proof candidate must discharge the metadata channel (`PV-K09`).** Key identifiers,
    certificate paths, transparency-log positions, witness sets and proof-object sizes can
    reconstruct protected content through the proof machinery itself. A candidate that cannot show
    a proved-safe treatment under the declared model is blocked — and only that candidate.
  - **One dependency is newly visible:** `PV-K07` prefix discipline is ratified but **not issuable**
    until `GY-GAP3` (controlled release-family transcript) closes. DS12 must not present a release
    history as governed while that owner is absent.
- **Not yet:** one record published well beats many published loosely;
  dispute/consultation/history surfaces arrive in DS13.

#### DS13 — Accountability Ledgers & Transparency

- **Goal:** the public record becomes contestable and historical, not just
  visible.
- **Gate:** DS12.
- **Producer & bridge work (in-slice):** dispute/consultation ledger and
  supersession/revocation history endpoints; transparency feed producer.
- **Deliverables:** dispute and consultation ledgers with
  response-to-comment records; supersession, revocation, and learning history
  (law 7 rendering: "this case" vs "new evidence"); transparency feed; MACHINE
  twins throughout.
- **Laws:** 5, 7.
- **Negative controls:** a closed public record cannot be mutated by new
  evidence — only superseded with visible lineage; P26 negatives on
  consultation-response accountability.
- **Not yet:** no automated dispute resolution; ledgers record and project,
  humans decide.

#### DS14 — Bounded-Agent Surface

- **Gate:** Phase-6 bounded-agent contracts closed (the GY plan's O-block /
  bounded LLM agent, formerly "G6"); DS9. The agent surface obeys the GY
  §3.5.9 live-carrier gates by construction — its transcript UI renders the
  constrained-carrier lifecycle honestly (typed refusals, truncation
  dispositions, characterization posture), never a smoothed chat illusion.
- **Goal:** the NL/orchestration interface in **candidate clothing**:
  request → grounded-result-or-abstention flows, the orchestration-choice
  audit view, abstention-first UX. The agent's fluency never upgrades its
  authority.
- **Producer & bridge work (in-slice):** agent session and orchestration-audit
  endpoints over the G6 contracts; schema + client regeneration.
- **Strangle target:** `features/clerk` — the existing NL chat (streaming,
  history, structured responses) is the UX substrate; DS14 re-grounds it on G6
  contracts and candidate clothing instead of building a second chat. Recon:
  `clerk` is **one of two app-level interface modes** (`clerk | analyst`,
  flag- and permission-gated) — the chat-first posture may be the default for
  non-analyst users, which makes candidate-clothing discipline here
  product-critical, not cosmetic.
- **Laws:** 1, 2, 11.
- **Negative controls:** P15 negatives — fluent agent text cannot populate an
  authority slot, an approval field, or a public claim; orchestration choices
  render with their audit trail.
- **Distillation augment (Rev 18, post-DS4; §6.5 · M38·M13·M14):** render the **GY-PA3**
  compression-loss ledger — each orchestration choice (selection / tool / framing / compression)
  shows its **authority delta** (candidate universe + rejected set + decision-policy;
  `authoritative_for = ∅`). A `CompressionLossReceipt` surfaces retained vs dropped limitations /
  denied-uses / counterevidence; a summary that dropped a retained-limitation renders **blocked, not
  clean**. Add a **cross-projection disclosure budget**: repeated PUBLIC/REVIEWER/MACHINE reveals
  cannot let a hidden fact be reconstructed via diff / hash / ordering / timing.
- **Not yet:** no agent output on PUBLIC surfaces; agent surfaces stay
  REVIEWER/EXPERT until a separate, explicit decision.

### New Slices (Revision 2 — the GY-N13/N11/N12 surface duals)

#### DS15 — Acquisition Routes & Data-Pool Growth Surfaces

- **Goal:** the surface dual of GY-N13 — the product's distinctive loop:
  **refusal-with-a-path becomes refusal-with-a-button.** The user sees why a
  case is blocked, what closing it costs, and (post-N13b) approves the
  acquisition and watches the world grow and the case re-enter.
- **Gate:** DS7. Read surfaces after **GY-N13a is accepted/merged**; the live
  loop after **GY-N13b**. **Revision 3 reality note:** N13a's census exists
  (12-family connector scorecard, 18 journaled live probes, the
  `ranking_only_not_voi` growth backlog with 15 `binding_gap` residuals) and
  measured that the current capstone routes are structural gaps, not data
  gaps — DS15's read surfaces render that truth as-is; the "approve
  acquisition" loop demonstrates on whatever honestly data-shaped gap N13b
  selects, never on a resurrected stale hypothesis.
- **Producer & bridge work (in-slice):** projections of the N13a census
  (connector scorecard, liveness map, catalog↔runtime metric resolution, the
  D2 VOI-ranked growth backlog) and, post-N13b, the acquisition execution
  surfaces (route status, admission passports, quarantine ledger, overlay
  epoch events, re-entry traces); schema + client regeneration.
- **Deliverables:** route detail view (typed requirement → costed plan →
  strategy → VOI → status); growth-backlog board ("what the system wants to
  learn next and why"); connector scorecard + liveness surfaces with tier
  decay honestly shown; post-N13b: the **approve-acquisition flow** (a
  DS9-class human decision with mandate + step-up, never one-click), the
  passport view (schema/units/alignment/license/PII/trust checks, each typed),
  the quarantine view (what arrived but was NOT admitted, and why), and the
  world-growth event feed; MACHINE twins throughout.
- **Laws:** 3, 5, 11, 12; GY §3.5.12 D1–D6 rendered, never re-derived.
- **Negative controls:** a fetched row without a full passport must render as
  quarantined, never as world data (P05 at the data plane); an acquisition
  approval from the offline queue is rejected; the growth backlog cannot be
  reordered client-side against its VOI ranking without showing the override.
- **Research-input augment (Rev 3.4, post-DS4; INT-R2):** the route detail view renders
  **non-data gap types as typed, visually distinct routes** — grounding-relation gap,
  estimand-binding gap, owner-writability gap, legal-mandate gap, capacity-evidence gap,
  human-decision gap — never forced into dataset-acquisition clothing (the N13a finding:
  the capstone routes were structural, not data gaps). Each type shows its own
  sufficiency bar and authority ceiling from the `GapAcquisitionCase` union when INT-R2
  lands; until then the surface renders the honest typed refusal, not a generic
  "fetch more data" affordance. **Falsifier (rendered):** adding rows must visibly NOT
  advance a relation/estimand/mandate route.
- **Not yet:** no auto-execution UX — acquisition stays a gated human
  decision; no PUBLIC projection of the backlog before DS12's gate.

#### DS16 — Value, Uncertainty & Derived-Data Grammar

- **Goal:** the visualization grammar that makes set-valued honesty readable:
  values as sets/intervals with `unknown` and `incomparable` as **designed
  states**, and every derived number wearing its recipe.
- **Gate:** DS4. Value/uncertainty parts are live at N10 merge
  (`ValueOuterSet`, advisor receipts); derived-data parts after **GY-N13b**.
- **Producer & bridge work (in-slice):** value-gate projections (outer sets,
  advisor receipts, method denominators); post-N13b: derivation-certificate
  projections (recipe = inputs × method+params × auxiliaries) and the basis
  vocabulary (GY §3.5.12-D6).
- **Deliverables:** the set-valued value viz family (never collapses to a
  point; `unknown`/incomparable rendered as first-class, not as gaps); basis
  chips on every monetary/unit-bearing chart (`real, base-2020,
  deflator=CPI` — the assumption is a visible, clickable element resolving to
  its certificate); derivation-recipe popover (what this number was computed
  from, by what, under which declared assumptions); provenance-class marking
  (`observed` / `derived` / `deployment_update`) wherever data is
  decision-bearing.
- **Laws:** 1, 3, 4, 5; the chart obligations of the constitution's Data And
  API Boundaries (source, uncertainty, time semantics — extended with basis).
- **Negative controls:** a set-valued value rendered as a point estimate fails
  visual regression; a derived series rendered without its provenance class
  fails the semantic test; a class-(iv) model output styled as observed data
  is the data-plane P15 and must fail.
- **Distillation augment (Rev 18, post-DS4; §6.5 · M16·M23·M24·M26·M33):** the canonical object is
  the full set / partial-order — a scalar is a lossy view, never the authority. `incomparable`
  renders as **"no admissible ranking exists"**, distinct from `unknown` (missing) and from zero. A
  tail / worst-case-over-process value may **not** be shown as a cancelling average. A single ranked
  recommendation renders **only** when a **GY-PA1** `NormativeAuthorizationRecord` authorizes the
  aggregation; absent it, the surface shows the frontier + a `NormativeDecisionRequest`, never a
  silent scalarization.
- **Inherited debt from DS4-C23 (registered 2026-07-20, owner: DS16):** the DS4
  return-union census found two surfaces **minting** evidence-grade authority the
  runtime never produced — `PublicSectorReadinessPanel` composed readiness from
  local thresholds/regexes/dwell-state/disputes, and `ScientificDepthPanel`
  invented remedies, acquisition refs, **E-values, claim extinction, cohort
  timelines, and stress rankings** (`P15`/`P05`; "dashboards may project
  authority, they may not mint it"). **DS4-C23 performs containment only** —
  it strips the synthesis and renders `unavailable`/opaque. **DS16 owns the
  binding**: define/consume the typed producer contract for readiness
  composition and scientific-depth values, so these surfaces render a producer
  value or an honest `unknown`, never a locally computed one. *Closure signal:*
  each named value resolves to a generated field or a registered typed
  refusal; the DS4 containment negatives stay green afterwards. This is
  value/uncertainty semantics, which is why it is not DS4 work.
- **Not yet:** no transform-planner UI (the GY plan defers transform chains);
  single-transform provenance only.
- **Status (2026-08-18) — the authority half is CLOSED; the grammar body is not.** Branch
  `codex/atlas-ds16-value-grammar`, slice plan
  `docs/plans/active/atlas-slices/DS16-value-uncertainty-and-derived-data-grammar.md`.
  **The DS4-C23 producer binding is delivered**, and its outcome is not the one this section
  anticipated: all **eleven** inventory families — the record's "readiness composition" collapses six
  distinct builders into one phrase — have **no runtime producer at all**, measured with positive
  controls. So the binding is a typed contract of **eleven registered refusals**, each carrying its
  reason code and owning surface, served over `GET /api/v1/runs/{run_id}/authority-values`, with
  completeness enforced by a validator that raises on a dropped member. Both panels are bound, the
  `C23` containment witness is retired with a strangle proof, and the MACHINE twin ships with parity
  read from the rendered DOM.
- **The grammar body could not land here, and the reason is structural rather than a shortfall.**
  DS16's own surfaces render refusals and carry **zero** quantity references, so there is nothing
  unit-bearing to attach a basis chip to and nothing derived to open a recipe for. `C08` and `C09`
  have **real, exercised substrate** — `BasisSignature`/`BasisAttribute`/`BasisParameterBinding` and
  `DerivationRecipe`/`DerivationCertificate`, the latter with 32 call sites on
  `build_derivation_recipe` — and **zero served**; they could be bridged tomorrow and still have no
  consumer here. `ValueOuterSet` is different again: its only construction in the whole source tree is
  an empty placeholder and `.compare()` has zero callers, so bridging it would serve a placeholder.
  **Re-entry condition, stated as a property:** a surface exists that renders values rather than
  refusals — arriving with **DS7** on real capstone data.
- **Sequencing correction, and it is a finding about this plan.** The slice table and this section
  gate DS16 on `DS4`; the Start-Now ladder groups its value grammar under "DS5 closed". **Both are
  partly right:** `DS4` is the correct gate for *defining* the grammar, and it is insufficient for
  *landing* it. Read the two together, not as a contradiction to resolve in favour of one.
- **Vocabulary correction, measured and load-bearing.** This section's provenance triple
  `observed`/`derived`/`deployment_update` **conflates two enums**: `deployment_update` is a
  `BranchMode` member (world-branch semantics), not a provenance class. The provenance enum is
  `ObservationProvenanceClass` with **four** members — `observed`, `proxy`, `derived`, `model_output` —
  and the fourth is the "class-(iv) model output" this section's own negative polices. Worse for a
  consumer: the `provenance_class` that **is** served carries `ParticipationProvenanceClass`
  (ADR-0167, grades A–D, owned by `participation_requirement/`) — the **same field name, a different
  vocabulary, a different owner**. `ObservationProvenanceClass` is served nowhere under any name.
- **`OuterSetValue`** is built, proven against the slice's negatives, a11y-clean and has **zero
  production importers** — a finished component awaiting a surface, recorded as such and deliberately
  not mounted over a refusal string.

#### DS17 — Confidence-Ledger & Risk-Spend Surface

- **Goal:** δ-accounting on the glass: what promotion risk has been spent, on
  which obligation classes, through which instruments.
- **Gate:** DS7; **GY-N11 closed**.
- **Producer & bridge work (in-slice):** ledger projections (δ-split,
  risk-spend per obligation class × instrument, good-event posture); schema +
  client regeneration.
- **Deliverables:** the δ-budget view (spent vs remaining, per class); the
  instrument register — **refusal and acquisition instruments first**, because
  that is the data that exists (positive promotion certificates render
  honestly empty until they exist); over-spend and non-anytime-valid
  certificate states rendered as hard blockers; MACHINE twin.
- **Laws:** 3, 4, 5, 8.
- **Negative controls:** an over-spent scope cannot render as promotable; a
  Bayesian credible interval without a coverage argument cannot appear as a
  promotion certificate (the N11 negative, surfaced).
- **Distillation augment (Rev 3.4, post-DS4; §6.3 COND(P29) · INT-R1):** every rendered
  δ figure carries its **obligation-set conditional visibly** — "≤ δ *relative to the
  declared obligation set*" — as a first-class chip resolving to the
  `ObligationCoverageEnvelope` (declared scope, searched sources, exclusions, unknown
  remainder, TTL) once INT-R1 lands; until then the chip renders the honest
  `open_world_unresolved` state. A δ number displayed without its conditional is the
  surface-level P29 and fails the semantic test — the ledger's math is only as complete
  as the obligations the system knows.
  **INT-R1 has now landed (2026-08-03) and it changes what this bullet was waiting for.** Its
  result is `accepted_narrow_scope` with a formal *impossibility* finding: while an unobserved
  decisive obligation remains admissible, no finite trace can certify global obligation
  completeness — so the envelope's `bounded_complete` is always **relative to a declared closure
  basis and obligation language**, never to the world. Its independent audit adds the operative
  constraint: independence is specified but **not constructed**, therefore the pinned repository
  **cannot issue `bounded_complete` at all** today (`INT-R1-D-003`). Two consequences for DS17,
  neither of which is a wait: (1) `open_world_unresolved` stops being a placeholder pending
  research and becomes the **honest steady state** until an independent producer, scorer, and
  governance record exist — DS17 must render it as a settled position with its reason, not as a
  loading state; and (2) when a coverage value does become issuable, the chip renders it **with
  its basis** — declared scope, obligation-language version, cutoff, unknown remainder, TTL — and
  a `bounded_complete` shown without that basis is the same P29 failure as a bare δ. The typed
  refusal is the deliverable here; the value is not owed.
- **Not yet:** no public δ claims before DS12; the view is REVIEWER/EXPERT
  accounting, not a marketing score.

#### DS18 — Epoch & Staleness Chrome

- **Goal:** time semantics as universal chrome: every decision-bearing
  surface shows `as_of`, epoch, and validity — and stale things look stale.
- **Gate:** DS4 (the `TimeSemanticsLabel` primitive); **GY-N12 closed** for
  real epoch semantics.
- **Producer & bridge work (in-slice):** epoch/staleness projections (current
  epoch per scope, stale-certificate sets, revision triggers, OpenWorldRisk);
  schema + client regeneration.
- **Deliverables:** epoch badges and `revalidation_required` states wired into
  DS4 primitives everywhere; the stale-certificates view (what went stale,
  which revision trigger, what revalidation would take); derived-data
  staleness inheritance rendered (input revision → dependent derivations
  flagged, recompute status); OpenWorldRisk freeze states; MACHINE twin.
- **Laws:** 3, 6, 7.
- **Negative controls:** a stale certificate rendered as current fails the
  semantic test; a chart without `as_of` on a decision-bearing surface fails
  the DS5 lint battery (extended here); crossing an epoch boundary in a replay
  view must show the boundary, not blend across it.
- **Distillation augment (Rev 18, post-DS4; §6.5 · M25·M36):** render the GY-N12 **post-publication
  perturbation cascade** — incident / appeal / correction / retraction / legal-change / bias are
  *distinct* event classes (not one "reopen"), each downgrade-only until adjudicated; a single upheld
  appeal shows **instance-scope, not class-scope**. A published record is **superseded with visible
  lineage, never silently edited** (recency ≠ strength); an `EvidenceValidityEvent` on an underlying
  source propagates source → evidence-line → claim → publication, and a claim that lost its support
  cannot stay current.
- **Not yet:** epoch chrome does not invent time semantics — it renders GY-N12
  and §3.5.12-D6 outputs only; scopes without regime data render honest
  `epoch_scope_unresolved`.

### New Slices (Revision 3 — grounded in Phase-A measurements)

#### DS19 — False-Substrate Strangle Wave + Frontend Disposition Register

- **Goal:** shrink every later slice's denominator by deleting what is
  provably false, and give the whole migration ONE disposition authority — the
  frontend dual of the GY-N0 disposition ledger: every estate unit is
  eventually **used-as-is / rebound / deleted**, never a live parallel owner.
- **Gate:** DS1 evidence (merged) — **may start now, parallel to DS3.**
- **Deliverables:** the **disposition register** (typed, in
  `architecture/atlas_surfaces/`, seeded from the DS1 readiness ledger and the
  DS2 adoption ledger) with per-unit disposition, evidence link, and strangle
  status; the **first deletion wave** over DS1's zero-consumer/false units —
  phantom collaboration REST/WS (+ its orphaned feature), orphan onboarding,
  latent legacy WhatIf, the duplicate Clerk index route, the empty
  feature-layout owner, the three zero-consumer worker modules, and the
  browser-side "signing" **call sites that nothing depends on** (the route
  itself stays frozen for DS12's strangle — deletion here covers only
  proven-dead paths); a **wire-or-retire disposition** (not implementation)
  for the 37 uncalled OpenAPI operations and the four `consumer_missing`
  flags, consumed by DS3/DS5.
- **Laws:** Rule 10; P06/P27/P28 duals; anti-P13 (deletion is scope reduction,
  not ceremony).
- **Negative controls:** every deletion carries its zero-consumer proof
  (DS1 evidence link + a fresh reference census at deletion time); a deletion
  without the fresh census is rejected; the register's CI check fails when a
  unit marked `deleted` still has references or a unit marked `rebound` lacks
  a successor consumer.
- **Not yet:** no rebinding (DS4), no producer building (DS3); DS19 deletes
  and registers only. Anything with ANY live consumer is out of scope for the
  wave and merely registered.

#### DS20 — Server Authorization Enforcement (split from DS5)

> **CLOSED & MERGED** (03ebc1ce8, 2026-07-20). DS20 (29/29-op action-permission
> floor, step-up for 6 high-stakes ops, fixture-identity removal, 33-value
> vocabulary through OpenAPI→client) + DS20-B cross-fence closure (B1 Rego bridge,
> B2 probe identity, B4 verifier provenance) landed; deployment-authority
> attestation architect-reviewed. Typed limitations carried as registered debt
> (see the inherited-debt table): B3 promotion CAS → fabric lane; B5 PostgreSQL
> proofs → cloud verification; scorecard producer provenance → DS9; Helm policy
> mirror → deploy lane.

- **Goal:** close the systemic authorization gap DS1 measured — this is
  today's production security posture, not UI debt, and it gates every
  authority-bearing surface that follows.
- **Gate:** DS3 (schema/client regeneration path); runs **parallel to DS4**.
- **Producer & bridge work (the slice IS server work, co-owned with
  team-architecture):** **generic action-permission dependency on all 29
  mutating operations** (a new mutating route cannot ship without one —
  enforced structurally, not by convention); **step-up authentication** for
  the high-stakes classes (promotion, production approval, publication,
  revocation, acquisition approval); **fixture identity prohibition in
  production mode** (the fail-open UI identity fallback dies with it);
  **resource binding before OPA evaluation**; the **single permission
  vocabulary** projected through the schema (collapsing the
  `_ROLE_PERMISSIONS` / `PERMISSION_KEYS` duplication); client regeneration.
- **Deliverables:** per-operation **server-side deny tests** (29/29, plus the
  audience classes); the DS1 seeded negatives N009–N013 implemented red-first;
  review-effectiveness telemetry hooks on the existing append-only access
  audit (consumed later by DS9).
- **Laws:** 9, 11 (enforcement half); the audience-is-access-control doctrine.
- **Negative controls:** a mutating endpoint without an action-permission
  dependency fails a structural test; a fixture identity in production mode is
  refused; an approval without step-up is denied server-side; UI-hides-but-
  server-allows is proven closed for every DS1-named gap.
- **Not yet:** no approval-flow UX (DS9 owns mandate/dissent/receipts); no
  audience mapping lints (DS5); DS20 is the server floor everything else
  stands on.

## Tensions (watch these or they go silent)

| # | Tension | Mitigation |
| --- | --- | --- |
| T1 | Status-lattice churn during late Layer 3 vs DS4 freeze | DS4 binds to generated types, not strings; Phase B waits for closeout re-derivation; lattice changes trigger re-derivation, not patching |
| T2 | v15 gravity well: 56 components invite bulk adoption (P13) | DS2 admission is per-component and consumer-driven; `defer` is the default verdict without a consuming surface in the DAG |
| T3 | Design polish cadence vs evidence bar | `fixture_only` work is allowed in Storybook/`experimental` freely; the bar applies at `beta`/`stable` and authority slots |
| T4 | Pressure for public surfaces before promotion exists | DS12's gate is constitutional; DS11 posture surfaces give marketing honest material earlier |
| T5 | Reference-shell drift into a parallel product | ownership note + review check: diagnostics-only scope |
| T6 | Token drift between v15 DTCG pipeline and current dashboard styles | DS0 picks one token source of truth with a sunset for the loser |
| T7 | Offline/cache capability vs staleness honesty | freshness posture vocabulary + DS1 cache policy + DS5 rendering rules; authority actions barred from the offline queue |
| T8 | Cross-team coupling: surface slices needing runtime producers stall | full-stack slice definition + named backend deliverables with runtime co-owner in every task plan; "blocked on backend" is not a valid slice state |
| T9 | Slice-count creep: 15 slices invite ceremony (P13) | one task plan, one closure contract, one review per slice; re-cut via roadmap amendment when disproportionate, never suffix or inflate |
| T10 | Off-contract channels: SSE/WS and `include_in_schema=False` quietly grow a second, untyped API beside the waist | DS3 brings channels under typed/governed contracts or explicit out-of-scope; the DS5 lint battery covers raw `EventSource`/`WebSocket`/fetch construction outside the sanctioned transports |
| T11 | GY frozen-artifact churn (rebaselines, provenance ripples) vs UI binding stability | producers bind narrow projection hashes (GY §3.5.11) and recomputed structural properties (GY §3.5.10); a rebaseline that changes only provenance must not break a surface contract test |
| T12 | The refusal-with-a-button loop (DS15) creates product pressure to "make acquisitions succeed" — the surface twin of forcing `useful_design_rate` | Rule 5 on the glass: quarantine and failed passports render as prominently as admissions; the growth backlog shows VOI ranking, not conversion targets; no surface KPI rewards acquisition volume |
| T13 | DS19's deletion wave removes substrate a later slice silently depended on | every deletion carries a fresh zero-consumer census at deletion time (not only DS1's snapshot); the disposition register is the single authority and its CI check guards `deleted`-with-references |
| T14 | Post-Phase-A false confidence: task plans quietly assuming June-estimate capabilities | the Phase-A artifacts are the denominators of record; a task plan citing a capability without a DS1/DS2 ledger reference is rejected at review |

## Health Metrics (instrument these, or the honesty goes silent)

| Metric | Definition | Honest direction |
| --- | --- | --- |
| Primitive adoption | share of decision-bearing renders flowing through DS4 primitives | rising; 100% for authority slots |
| Fail-closed fidelity | share of blocker/abstention/out-of-envelope/stale-cached states rendered as typed states (vs generic empty/error) | rising to 100% |
| Audience enforcement | share of audience-scoped endpoints with passing server-side deny tests | 100% before DS12 |
| `surface_missing` closure | open `surface_missing` / `implemented_but_not_orchestrated` links in the cluster map | falling |
| Evidence coverage | share of `stable` components with browser + AT evidence | 100% for `stable` |
| Machine-twin parity | share of shipped surfaces with a passing twin parity test | 100% — twins ship in-slice |
| Honesty comprehension | reviewer-task success at locating the weakest link / active blockers (DS6 protocol) | measured and reported |

Never targeted: screen fullness, dashboard green-ness, conversion copy
performance (constitution Rule 5). `useful_design_rate` remains a runtime
metric and is reported on the board, never optimized by surface work.

## Validation (plan closure contract)

This plan is closed when all of the following hold:

1. Every `[to build]` enforcement item in the surface constitution's laws table
   exists and runs in CI.
2. The v15 archive is fully adjudicated in the adoption ledger (no `pending`
   verdicts); v4/v7 docs are superseded; the legacy plans are archived.
3. The Cycle Board runs on the live GY artifacts (capstone + ledgers +
   censuses + 13 legacy cases) **through in-repo HTTP producers** with its
   MACHINE twin and semantic test green, and its evidence-class claims are
   recomputed, never pinned (GY §3.5.10).
4. The `surface_missing` closure target — set at activation from the post-L3
   cluster map count — is met, with each closure traceable to a slice.
5. At least one public decision record is published end-to-end through the
   promotion gate with provenance certificate, working citizen verification,
   and MACHINE twin (DS12).
6. Audience enforcement is proven: server-side deny tests cover every
   audience-scoped endpoint; step-up auth covers high-stakes actions; no
   UI-hides-but-server-allows gap from the DS1 report remains open.
7. The cache/offline policy is enforced: cached renders carry freshness;
   authority actions cannot execute from the offline queue without
   revalidation.
8. DS6 machinery is operational: evidence workflow, ledger CI validator,
   health-metric instrumentation, honesty-comprehension protocol.
9. Every shipped surface carries its MACHINE twin with a passing parity test
   (in-slice doctrine, no retrofit backlog).
10. The surface readiness ledger is green-or-honestly-red in CI and rendered
    on the board.
11. The refusal-with-a-path loop is proven end-to-end: at least one
    acquisition route renders with its costed plan (DS15 read), and — once
    GY-N13b has closed a route — the world-growth re-entry renders truthfully
    with its passports and quarantine honestly shown.
12. (Revision 3) The disposition register is complete and green: every estate
    unit carries a disposition, the DS19 deletion wave landed with
    zero-consumer proofs, no live parallel owner remains, and every DS1
    seeded negative (N001–N023) is implemented red-first in its owning slice.

Closure converts the surface constitution's Promotion Criteria into fact:

| Surface-constitution promotion criterion | Satisfied by |
| --- | --- |
| 1. DS0 classifies v4/v7/v15 adoption | DS0 + DS2 |
| 2. Proving-ground board slice plan accepted | DS7 task plan |
| 3. Status-grammar lint/contract tests | DS5 |
| 4. API/client boundary checks | DS5 |
| 5. Accessibility evidence in CI/browser/manual workflows | DS6 |
| 6. ≥1 real `surface_missing` closure without weakening authority | DS7/DS8 |

## Relationship To Existing Plans And Docs

| Document | Disposition |
| --- | --- |
| `layer3-slices/GY-engine-subordination.md` (Rev 17) | **the upstream dependency** — supplies the Input Contract, the artifact vocabulary, and the gate milestones (N10 merge, N13a/b, N11, N12, first promotion, O-block) |
| `POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md` | historical G-naming context retained in place with no execution authority; GY Rev 17 owns current vocabulary, artifacts, and gates |
| `POLICYOS_ATLAS_PRODUCT_MARKETING_CLIENT_SURFACES_MASTER_PLAN.md` | superseded as execution master; retained material source for DS11–DS13 until those task plans disposition every item |
| `docs/plans/archive/FRONTEND_SOTA_PLAN.md` | archived 2026-07-16 as vision-superseded; active path is a compatibility stub |
| `docs/plans/archive/DESIGN_BEST_IN_CLASS_PLAN.md` | archived 2026-07-16 as vision-superseded v4 history; active path preserves provenance anchors |
| `docs/brand/ATLAS_DESIGN_SYSTEM.md`, `docs/brand/ATLAS_V4_ADOPTION.md` | superseded as governing sources; retained as v4 baseline/adoption evidence for DS2/DS4 |
| `docs/brand/ATLAS_SOURCE_OF_TRUTH.md` | canonical DS0 source-disposition and governing-decision record |
| `docs/reference/frontend/workspace-contract.md` | binding; DS5 lints implement its boundary mechanically |
| `design/atlas-v15/` archive | evidence source under DS2 admission; never a source of authority by itself |
