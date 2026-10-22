# Первичные источники инженерного исследования

Полный реестр: [sources.json](sources.json). Одинаковый URL может поддерживать разные узкие утверждения и потому встречаться в нескольких source records. Документация стороннего проекта не подтверждает реализацию, производительность или authority PolicyOS. Дата чтения и ограничения сохранены для каждого источника. Локальные документы сохраняют собственный normative status и source pin.

## R13-CAP-HTTP9110

[RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html)

**Поддерживает:** ETag identifies and validates a selected representation; If-None-Match can produce 304; 304 carries no representation body; Range/206 is optional and If-Range must use a strong matching validator; HTTP idempotence concerns intended server effect, and clients should not automatically retry a non-idempotent request without a means to know it is safe or detect non-application.

**Не доказывает / предел:** HTTP validators are origin assertions about a representation, not cryptographic content hashes, snapshot completeness proofs, rights decisions, or current legal status.

## R13-CAP-HTTP9111

[RFC 9111: HTTP Caching](https://www.rfc-editor.org/rfc/rfc9111.html)

**Поддерживает:** Cache reuse depends on target, method, freshness or successful revalidation, and Vary-selected request fields; a 304 updates an appropriate stored response, and partial responses require matching representation validators before combination.

**Не доказывает / предел:** The HTTP cache model does not admit a PolicyOS use, prove source authority, or ensure that a source's paged records form a stable semantic snapshot.

## R13-CAP-WEBLINK

[RFC 8288: Web Linking](https://www.rfc-editor.org/rfc/rfc8288.html)

**Поддерживает:** The Link header models typed relations between a current context and target resources and defines parsing and relative-target resolution semantics.

**Не доказывает / предел:** A next-like relation is a navigation hint/protocol value, not proof that all pages share a consistent source cut or permission. Every dereference still needs the selected transport and egress policy.

## R13-CAP-SSRF

[OWASP Server-Side Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)

**Поддерживает:** For known destinations, accept a host from an allowlist and construct the request locally; validate resolved IPv4 and IPv6 targets and bind the connection to an approved address because a separate DNS check does not prevent rebinding; redirects and parser disagreement must not bypass destination checks.

**Не доказывает / предел:** This is defensive guidance, not a proof of the repository's proxy, DNS, socket, or firewall behavior; those enforcement points must be verified for the selected deployment.

## R13-CAP-GRAPHDELTA

[Use delta query to track changes in Microsoft Graph data](https://learn.microsoft.com/graph/delta-query-overview)

**Поддерживает:** Graph's opaque nextLink and deltaLink tokens represent state for a change-tracking round; clients continue until deltaLink, preserve query state, and must handle duplicate/replayed items, processing delay, and expired tokens requiring resynchronization.

**Не доказывает / предел:** This is one provider's API contract. It documents that some resource properties outside the main store are not tracked, so a delta feed cannot be generalized into a complete change denominator for other sources.

## R13-CAP-S3CAS

[How to prevent object overwrites with conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)

**Поддерживает:** S3 supports conditional object writes using If-Match/If-None-Match, rejecting mismatched versions with precondition/conflict responses; this is a concrete compare-and-swap pattern for a selected object head.

**Не доказывает / предел:** Provider behavior and multipart/delete races are S3-specific; this is a mechanism comparison, not a recommendation to add S3 or evidence of filesystem/CAS parity.

## R13-CAP-ODRL

[ODRL Information Model 2.2](https://www.w3.org/TR/odrl-model/)

**Поддерживает:** ODRL supplies an interoperable model for asset-linked permissions, prohibitions, duties, parties, and constraints, useful as an input vocabulary for purpose/use evidence.

**Не доказывает / предел:** An ODRL expression can state a policy but does not authenticate its issuer, establish signer competence, decide legal force, or prove that a custodian granted the asserted permission.

## R13-CAP-PROV

[PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/)

**Поддерживает:** PROV-O separates entities, activities, and agents and connects used/generated entities with responsible agents and times, a useful reference for capture and transformation provenance.

**Не доказывает / предел:** A provenance graph records asserted relationships; it does not make an agent's assertion true or supply authority, permission, or verification.

## R13-CAP-EURLEXAUTH

[Verify the authenticity of an electronic edition of the Official Journal](https://eur-lex.europa.eu/content/help/oj/authenticity-eOJ.html?locale=en)

**Поддерживает:** For the EU Official Journal, the electronic edition is the authentic legally effective edition from 1 July 2013, and its signature-verification procedure checks that the signed edition is authentic and unchanged since signature.

**Не доказывает / предел:** This route is specific to the Official Journal and the applicable EU legal rule. It does not make every EUR-Lex page, consolidation, translation, or linked record independently authoritative.

## R13-CAP-ELI

[What is ELI?](https://eur-lex.europa.eu/eli-register/what_is_eli.html)

**Поддерживает:** ELI offers persistent identifiers and a common metadata model for legislation, including identifiers and descriptive/version information that support machine-readable legal-source discovery and citation.

**Не доказывает / предел:** An identifier or metadata record does not prove the authenticity of the fetched bytes, current legal effect, jurisdictional applicability, or an institution's interpretation.

## R13-CAP-EIDAS

[Regulation (EU) No 910/2014 (consolidated text)](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02014R0910-20240520)

**Поддерживает:** The regulation defines electronic seals as linked to origin/integrity and gives qualified seals specified evidentiary presumptions; it also defines qualified timestamp and trust-service semantics.

**Не доказывает / предел:** The specific legal effect depends on the applicable legal regime and trust chain. A verified seal alone does not establish that the signer had authority to issue the legal act or that the act applies to a target policy question.

## R13-CAP-GOVINFO

[Authentication and the 2026 Code of Federal Regulations](https://www.govinfo.gov/about/authentication)

**Поддерживает:** GovInfo's digitally signed publications support verification of certification, integrity, and signer identity at signing; its CFR documentation directs users to the Federal Register and List of CFR Sections Affected to identify amendments and warns that publication and effective dates differ.

**Не доказывает / предел:** This U.S. publication model is jurisdiction-specific; a signed edition still requires its amendment/effective-time context and a source-qualified legal applicability decision.

## R13-CAP-STRIPE

[Idempotent requests](https://docs.stripe.com/api/idempotent_requests)

**Поддерживает:** Stripe documents request-key replay that returns the stored first result, checks parameter equality, and may prune keys after at least 24 hours; concurrent requests and pre-execution validation failures have separate behavior.

**Не доказывает / предел:** This is a vendor-specific bounded idempotency window, not exactly-once execution or a universal provider contract. Once the key expires, a replay may execute again.

## R13-CAP-NITRO

[Cryptographic attestation - AWS Nitro Enclaves](https://docs.aws.amazon.com/enclaves/latest/user/nitro-enclave-concepts.html)

**Поддерживает:** Nitro uses signed attestation documents with enclave measurements that an external service or AWS KMS can check before authorizing selected operations. AWS documents that enclaves have isolated memory/vCPUs, no persistent storage or direct external network connectivity, and communicate through the parent instance's vsock path.

**Не доказывает / предел:** This proves a bounded execution identity under the provider's model, not legal permission, correct result semantics, upstream raw-source truth, every external log/temp sink, or post-run deletion. Third-party verifiers need their own policy and validation.

## R13-CUSTODY-PROV-O

[PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/)

**Поддерживает:** PROV-O represents entities, activities, agents, derivation, invalidation and qualified roles, and allows application-specific specialization.

**Не доказывает / предел:** It records provenance structure; it does not establish relation truth, method validity, independence or admissibility.

## R13-CUSTODY-PG-LOGICAL

[Logical Decoding Concepts, PostgreSQL 18](https://www.postgresql.org/docs/current/logicaldecoding-explanation.html)

**Поддерживает:** A logical slot can pair an exported snapshot with a later ordered change stream; changes may replay after crash, consumers must handle duplicates, and slots retain WAL/catalog resources.

**Не доказывает / предел:** Specific to PostgreSQL and its log scope; does not include external claim, rights or publisher stores.

## R13-CUSTODY-PG-ISOLATION

[Transaction Isolation, PostgreSQL 18](https://www.postgresql.org/docs/current/transaction-iso.html)

**Поддерживает:** Serializable excludes transaction serialization anomalies; weaker Read Committed reads can see distinct snapshots across commands.

**Не доказывает / предел:** Isolation covers only one database transaction.

## R13-CUSTODY-OUTBOX

[Transactional outbox pattern, AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)

**Поддерживает:** A local outbox transaction closes the database/event dual-write gap; relays may duplicate, so consumers must be idempotent and preserve needed order.

**Не доказывает / предел:** Does not atomically commit downstream services or external effects.

## R13-CUSTODY-SAGA

[Saga orchestration pattern, AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/saga-orchestration.html)

**Поддерживает:** Cross-store workflows use local transactions, forward recovery or compensation; participants need idempotency and the pattern is eventually consistent without isolation.

**Не доказывает / предел:** Compensation is another act, not guaranteed rollback or global atomic commit.

## R13-CUSTODY-KAFKA

[Exactly-once source connectors, Apache Kafka Connect 4.2](https://kafka.apache.org/42/kafka-connect/connector-development-guide/)

**Поддерживает:** Exactly-once source support requires meaningful source offsets and exact resume without loss or duplication; task generations can be fenced within Kafka Connect.

**Не доказывает / предел:** Not a transaction across arbitrary external sources, claim ledger, CAS, rights and publisher.

## R13-CUSTODY-HTTP-9110

[RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html)

**Поддерживает:** If-Match uses strong entity-tag comparison to prevent stale state-changing updates; If-Range resumes only on an exact strong validator match.

**Не доказывает / предел:** A validator is an origin assertion, not independent completeness or byte-integrity evidence.

## R13-CUSTODY-HTTP-9111

[RFC 9111: HTTP Caching](https://www.rfc-editor.org/rfc/rfc9111.html)

**Поддерживает:** 304 updates and reuses a suitable stored response selected by URI, request variant and validators.

**Не доказывает / предел:** 304 has no replacement body; without the exact stored representation it cannot reconstruct a complete capture.

## R13-CUSTODY-S3-CAS

[Conditional writes, Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)

**Поддерживает:** If-Match conditional writes fail when current ETag differs; concurrent writes/deletes can produce precondition, conflict or not-found outcomes.

**Не доказывает / предел:** Protects one S3 object update, not another database head or semantic currentness.

## R13-CUSTODY-S3-ETAG

[Object API: ETag, Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/API/API_Object.html)

**Поддерживает:** ETag is not necessarily a full-object MD5 for multipart uploads or some encryption modes.

**Не доказывает / предел:** Conditional-write validator and independently computed content digest are different evidence.

## R13-CUSTODY-TEMPORAL

[Detecting Activity failures, Temporal](https://docs.temporal.io/encyclopedia/detecting-activity-failures)

**Поддерживает:** Retries create another attempt; heartbeat payload can resume progress and cancellation is delivered through heartbeat processing.

**Не доказывает / предел:** Timeout/cancellation does not prove a provider-side operation stopped.

## R13-CUSTODY-STRIPE

[Idempotent requests, Stripe API](https://docs.stripe.com/api/idempotent_requests)

**Поддерживает:** Stripe API v1 saves first response after execution begins, compares request parameters, and may prune keys after at least 24 hours; reuse after pruning starts a new call.

**Не доказывает / предел:** Provider- and API-version-specific; does not prove a remote effect after lost reply.

## R13-CUSTODY-S3-VERSIONING

[Retaining multiple versions of objects with S3 Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html)

**Поддерживает:** Normal delete inserts a current marker and leaves older versions retrievable; permanent removal requires version-specific delete and lifecycle handling.

**Не доказывает / предел:** Shows one S3 bucket behavior, not PolicyOS or every store.

## R13-CUSTODY-S3-LOCK

[Locking objects with Object Lock, Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)

**Поддерживает:** Retention/legal hold applies to specified object versions; compliance mode can prevent deletion during retention and governance mode has authorized bypass.

**Не доказывает / предел:** Storage control is not a legal applicability decision or complete copy inventory.

## R13-CUSTODY-GDPR

[Regulation (EU) 2016/679, Articles 17 and 89](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679)

**Поддерживает:** Erasure is tied to specified grounds and exceptions include legal obligation and qualifying public-interest archiving/research with Article 89 safeguards; Article 17(2) addresses reasonable steps to inform other controllers.

**Не доказывает / предел:** Applicability depends on facts, role, jurisdiction and other law; PolicyOS consumes the competent decision.

## R13-LINEAGE-01

[Handling Overload, Site Reliability Engineering](https://sre.google/sre-book/handling-overload/)

**Поддерживает:** Request counts and static request attributes can be poor capacity proxies because work costs differ and change. The source recommends graceful degradation and transparent errors under overload, and describes isolating batch load from higher-priority traffic.

**Не доказывает / предел:** A serving-system design discussion, not a PolicyOS resource contract or evidence that any local resource is currently measured or enforced.

## R13-LINEAGE-02

[Dominant Resource Fairness: Fair Allocation of Multiple Resource Types](https://www.usenix.org/conference/nsdi11/dominant-resource-fairness-fair-allocation-multiple-resource-types)

**Поддерживает:** Dominant Resource Fairness generalizes max-min fairness to heterogeneous multi-resource demands and studies properties including strategy-proofness and envy-freeness under its model.

**Не доказывает / предел:** Fair allocation is not a normative rule for custody duties, urgency, protected actions, or legal priority. The paper does not implement reservations, terminal fan-in, or PolicyOS process accounting.

## R13-LINEAGE-03

[Control Group v2, Linux Kernel Documentation](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)

**Поддерживает:** cgroup v2 provides hierarchical CPU, memory, and I/O controls and accounting. Its documentation distinguishes weights, protections, and limits; memory.high throttles under reclaim while memory.max can invoke the OOM killer and may be exceeded temporarily.

**Не доказывает / предел:** Only applies where the host, kernel, filesystem, controller, and process placement support the relevant controls. It does not meter every network/provider spend or supply a product-level reserve protocol.

## R13-LINEAGE-04

[Memory Management in DuckDB](https://duckdb.org/docs/current/operations_manual/limits)

**Поддерживает:** DuckDB's documented memory_limit only applies to its buffer manager, and its temporary-directory limit is configurable (the documented default is unlimited). This shows why an engine-specific memory setting is not a whole-process or disk cap.

**Не доказывает / предел:** DuckDB documents limits for its own operators. It is not a governed PolicyOS spill destination or a universal bound on native/process memory.

## R13-LINEAGE-14

[Memory Management in DuckDB](https://duckdb.org/2024/07/09/memory-management)

**Поддерживает:** DuckDB can stream and spill larger-than-memory intermediates to a temporary directory. If memory is exceeded and spilling is disabled, the temporary-directory limit is exceeded, or spilling is unavailable for a query, DuckDB reports an out-of-memory error and cancels the query.

**Не доказывает / предел:** DuckDB documents behavior for its own operators. It does not establish a governed PolicyOS spill destination, retention/right scope, or whole-process memory bound.

## R13-LINEAGE-05

[Skyframe, Bazel Reference](https://bazel.googlesource.com/bazel/+/3b9ed6e9d3570a0c67e0d59e65b3785bbc1fad99/site/en/reference/skyframe.md)

**Поддерживает:** Incremental recomputation depends on functions declaring all inputs through the dependency graph; Bazel describes reverse-transitive invalidation and change pruning after recomputation.

**Не доказывает / предел:** Build-system dependencies do not encode PolicyOS rights, semantic validity, audiences, authority, or scientific independence. Unregistered reads defeat the incremental correctness model.

## R13-LINEAGE-06

[dvc.yaml Files and dvc.lock, DVC Documentation](https://doc.dvc.org/user-guide/project-structure/dvcyaml-files)

**Поддерживает:** DVC lockfiles record stage definitions, dependencies, parameters, and output hashes so the pipeline can detect changed stages and decide which stages to reproduce.

**Не доказывает / предел:** A reproducible pipeline cache does not decide current legal use or whether a derivative is admissible for a particular audience and purpose.

## R13-LINEAGE-07

[Apache Avro Specification](https://avro.apache.org/docs/1.8.1/spec.html)

**Поддерживает:** Avro requires a writer schema to interpret encoded data and defines reader/writer schema resolution, including field matching and default behavior.

**Не доказывает / предел:** Structural schema resolution cannot prove that a field retained the same substantive meaning or is sufficient for a selected consumer.

## R13-LINEAGE-08

[Schema Evolution and Compatibility for Schema Registry](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html)

**Поддерживает:** Backward, forward, full, and transitive compatibility answer different old/new reader questions; transitive checks cover more than the latest prior version, and compatibility choices constrain producer/consumer rollout order.

**Не доказывает / предел:** These compatibility checks are schema-format specific and do not establish semantic equivalence, rights, or source-cut consistency.

## R13-LINEAGE-09

[The Update Framework Specification v1.0.33](https://theupdateframework.github.io/specification/v1.0.33/)

**Поддерживает:** TUF separates trust roles and uses versioned, expiring metadata and snapshots to address rollback, freeze, and mix-and-match attacks in software update repositories.

**Не доказывает / предел:** TUF is a software-update trust framework; it cannot bootstrap PolicyOS institutional authority, settle source rights, or certify semantic compatibility.

## R13-LINEAGE-10

[Language Guide (proto3), Protocol Buffers](https://protobuf.dev/programming-guides/proto3/)

**Поддерживает:** Proto3 preserves unknown fields in binary messages in common round trips, while converting through JSON or rebuilding messages field-by-field can lose them; parseability alone does not protect unknown data through every transformation.

**Не доказывает / предел:** Wire-format compatibility is not a consumer-requiredness or semantic adequacy decision.

## R13-LINEAGE-11

[Stateful Stream Processing, Apache Flink Documentation](https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/stateful-stream-processing/)

**Поддерживает:** Flink checkpoints bind positions in input streams to corresponding operator state; recovery restores the latest completed checkpoint and replays sources from those positions. Exactly-once state consistency depends on replayable sources, and unaligned checkpoints trade lower barrier delay for persisted in-flight data and extra I/O.

**Не доказывает / предел:** This is a coordinated stream-processing snapshot, not evidence that independently sampled PolicyOS sources share a global cut or that a policy claim is true.

## R13-LINEAGE-12

[SLSA Build Provenance v1.2](https://slsa.dev/spec/v1.2/build-provenance)

**Поддерживает:** SLSA provenance defines verifiable build information, including the subject, builder identity, build type, invocation parameters, resolved dependencies, metadata, and useful byproducts.

**Не доказывает / предел:** Build provenance traces how an artifact was built; it does not establish semantic acceptance, complete consumer coverage, independent scientific evidence, or PolicyOS authority.

## R13-LINEAGE-13

[Certified Kubernetes Software Conformance, CNCF](https://www.cncf.io/training/certification/software-conformance/)

**Поддерживает:** The Kubernetes conformance program runs an identical open-source test application, submits results for review, and lets end users rerun that application to check interoperability against required APIs.

**Не доказывает / предел:** The tested Kubernetes API profile and certification do not generalize to PolicyOS semantics; the useful transfer is an exact version/profile-scoped test corpus plus review and rerun identity.

## R13-GYCORE-MLIR-LANG

[MLIR Language Reference](https://mlir.llvm.org/docs/LangRef/)

**Поддерживает:** Multiple dialects can coexist in a module, an analogy for typed stages over common IR.

**Не доказывает / предел:** Compiler analogy only; not policy semantics or reason to adopt MLIR.

## R13-GYCORE-MLIR-CONVERSION

[Dialect Conversion - MLIR](https://mlir.llvm.org/docs/DialectConversion/)

**Поддерживает:** Conversion declares legal/illegal operations and explicit rewrite patterns, optionally type conversion.

**Не доказывает / предел:** Structural translation does not verify meaning or authority.

## R13-GYCORE-MLIR-PASSES

[Pass Infrastructure - MLIR](https://mlir.llvm.org/docs/PassManagement/)

**Поддерживает:** Passes declare dialect dependencies and explicit transformation stages.

**Не доказывает / предел:** No local performance or adoption case.

## R13-GYCORE-CP-SAT

[CP-SAT Solver](https://developers.google.com/optimization/cp/cp_solver/)

**Поддерживает:** Integer constraints and distinct OPTIMAL, FEASIBLE, INFEASIBLE, MODEL_INVALID and UNKNOWN statuses; UNKNOWN can mean incomplete/resource limited.

**Не доказывает / предел:** Only encoded constraint search, not facts, causal validity or admissibility.

## R13-GYCORE-Z3

[Programming Z3](https://z3prover.github.io/papers/programmingz3.html)

**Поддерживает:** SAT/model queries, incremental scopes and tracked assumptions; unsat cores need not be minimal.

**Не доказывает / предел:** Encoded formulas only; cannot validate source truth or grant authority.

## R13-GYCORE-PROV-O

[PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/)

**Поддерживает:** Vocabulary for provenance entities, activities, agents and relations.

**Не доказывает / предел:** Lineage is not truth, independence, admissibility or authority.

## R13-GYCORE-SHACL

[Shapes Constraint Language (SHACL)](https://www.w3.org/TR/shacl/)

**Поддерживает:** Validates RDF graphs against declared shapes and emits reports.

**Не доказывает / предел:** Shape conformance is not real-world truth or institutional act.

## R13-GYCORE-SPIBB

[Safe Policy Improvement with Baseline Bootstrapping](https://proceedings.mlr.press/v97/laroche19a/laroche19a.pdf)

**Поддерживает:** Bounds candidate changes and falls back to baseline for uncertain state-action regions under stated MDP/data assumptions.

**Не доказывает / предел:** Guarantees do not transfer to public policy justification or permission.

## R13-GYCORE-OPA

[Policy Language | Open Policy Agent](https://www.openpolicyagent.org/docs/policy-language)

**Поддерживает:** Rego declaratively evaluates policy over structured data.

**Не доказывает / предел:** Rule evaluation does not supply causal grounds, evidence custody or admissibility.

## R13-GYCORE-CMBPO

[Towards Causal Model-Based Policy Optimization](https://arxiv.org/abs/2503.09719)

**Поддерживает:** Studies SCM intervention simulation in policy optimization and spurious predictive correlations under shift.

**Не доказывает / предел:** Preprint/RL results do not prove local capacity, institutional safety or acceptance.

## R13-GY-LEARNING-HOLDOUT

[Generalization in Adaptive Data Analysis and Holdout Reuse](https://papers.nips.cc/paper/5993-generalization-in-adaptive-data-analysis-and-holdout-reuse.pdf)

**Поддерживает:** Adaptive reuse of a holdout can overfit to that holdout; their reusable-holdout construction controls this through a restricted validation interface and privacy/stability arguments.

**Не доказывает / предел:** This does not make a sealed file or checksum a privacy mechanism. PolicyOS has no adopted query budget or privacy guarantee here, so use this as the reason to protect AS2 and reject post-hoc tuning, not as a transferred guarantee.

## R13-GY-LEARNING-CONFIDENCE-SEQUENCES

[Time-uniform, nonparametric, nonasymptotic confidence sequences](https://doi.org/10.1214/20-AOS1991)

**Поддерживает:** Confidence sequences can give time-uniform coverage over an unbounded horizon under their stated stochastic conditions, including validity at arbitrary stopping times.

**Не доказывает / предел:** A sequential interval does not cure holdout leakage, post-hoc outcome selection, cause misclassification, or context transport. GYD-08 asks for repeated-look failure fixtures, not adoption of a new sequential guarantee.

## R13-GY-LEARNING-SAFFRON

[SAFFRON: an Adaptive Algorithm for Online Control of the False Discovery Rate](https://proceedings.mlr.press/v80/ramdas18a.html)

**Поддерживает:** Online FDR procedures require valid sequential p-values; SAFFRON states conditional super-uniformity assumptions and derives its guarantees from them.

**Не доказывает / предел:** It is a method comparison, not the local controller's theorem and not evidence that PolicyOS DDM outputs satisfy its assumptions.

## R13-GY-LEARNING-BY-DEPENDENCE

[The control of the false discovery rate in multiple testing under dependency](https://doi.org/10.1214/aos/1013699998)

**Поддерживает:** Benjamini-Yekutieli prove FDR control for the linear step-up procedure under positive regression dependence on true-null test statistics.

**Не доказывает / предел:** That condition is not arbitrary dependence, and the result is an offline multiple-testing result rather than an online DDM-stream guarantee.

## R13-GY-LEARNING-ELOND

[Online multiple testing with e-values](https://proceedings.mlr.press/v238/xu24a.html)

**Поддерживает:** The paper's e-LOND procedure gives online FDR control under arbitrary, possibly unknown, dependence when its input e-values meet the e-value validity conditions.

**Не доказывает / предел:** An anomaly score or current p-value is not an e-value by naming. This is a future alternative only if the accepted DDM plan and native producers supply the required evidence; it is not a default replacement.

## R13-GY-LEARNING-TRANSPORT

[Transportability of Causal and Statistical Relations: A Formal Approach](https://ojs.aaai.org/index.php/AAAI/article/view/7861)

**Поддерживает:** Selection diagrams make differences and commonalities between source and target environments explicit and support deciding whether a causal effect is identifiable in the target from available source experiments and target observations.

**Не доказывает / предел:** This does not license automatic generalization to a new population, time, or interference regime. It depends on a causal graph and evidence for its selection assumptions.

## R13-GY-LEARNING-TUF

[The Update Framework Specification, version 1.0.36](https://theupdateframework.github.io/specification/v1.0.36/)

**Поддерживает:** TUF specifies version, signature, hash, and expiry checks that detect rollback, freeze, and mix-and-match attacks in software update metadata.

**Не доказывает / предел:** TUF is not a causal model-update protocol. Transfer only the narrow design lesson that a consumer resolves a pinned version and rejects stale or mismatched lineage; do not import its signing roles or claim its security properties for Fabric.

## R13-GY-LEARNING-MLFLOW

[MLflow Model Registry Workflows](https://mlflow.org/docs/latest/ml/model-registry/workflow/)

**Поддерживает:** MLflow distinguishes exact model-version references from mutable aliases; alias reassignment can change which version a later consumer resolves.

**Не доказывает / предел:** This is an implementation example, not a recommendation to add MLflow or use aliases for PolicyOS authority. Audit and causal lineage should resolve immutable artifact refs.

## R13-GY-LEARNING-SDD-B01

[Adopted reading clarification: competing causal completions and claim-type-specific grounds](../../../../../../policy-engine/docs/system-design-decisions/policy-design-causal-operating-system-north-star.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§10, SDD-B01)

**Поддерживает:** A singular world-model reference may be credal/set-valued and admit competing causal completions. Grounding is claim-type-specific: causal claims need causal grounds, measurement claims need construct/method grounds, and value claims need a declared frame and applicable mandate.

**Не доказывает / предел:** This adopted target clarification does not certify implementation or impose a unique causal structure; actual admission still needs the relevant owner, evidence, and scope.

## R13-GY-LEARNING-SDD-C01

[Adopted target extension: joint evaluation witness](../../../../../../policy-engine/docs/system-design-decisions/policy-design-causal-operating-system-north-star.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§10, SDD-C01)

**Поддерживает:** Whole-design joint evaluation may use simulation or an exact joint derivation/other validated joint witness for the concrete property it actually proves; marginal or pairwise checks do not substitute. Model truth and grounding remain separate.

**Не доказывает / предел:** The alternative needs an explicit property, assumptions, consumer, and falsifier; this target wording does not certify a runtime implementation.

## R13-GY-LEARNING-SDD-C02

[Adopted target extension: inference plurality](../../../../../../policy-engine/docs/system-design-decisions/policy-design-causal-operating-system-north-star.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§10, SDD-C02)

**Поддерживает:** Bayesian confirmatory updates remain supported, while explicitly justified frequentist, sequential, robust, or partial-identification profiles are also permitted for the propositions they support. Posterior probability, coverage, identification sets, and procedural no-number claims must not be silently mixed.

**Не доказывает / предел:** C02 appoints no method owner, authorizes no posterior mutation, and does not transfer any method guarantee without its own assumptions and bridge.

## R13-GY-LEARNING-RULE12

[Universal design system Rule 12: corpus discovery and conforming resource growth](../../../../../../policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§4.3, Rule 12)

**Поддерживает:** Capability is discovered by bounded search over the corpus rather than a hand-maintained central enumeration; a correctly added resource conforming to an existing semantic/protocol class is usable with zero new central code.

**Не доказывает / предел:** A genuinely new transport or semantic capability still needs a typed native extension and conformance; search completeness and capacity remain governed and evidenced.

## R13-GY-LEARNING-S0-K14

[Stage 0 custody kernel K14 scope amendment](../../../../../../policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` ·  (§4.2, S0-K14)

**Поддерживает:** Independence is required for verification claims, including benchmark-oracle claims and assertions of independent validation. A same-code rebuild is permitted and establishes consistency, not correctness.

**Не доказывает / предел:** Do not impose a separately owned evaluator on every ordinary rebuild; independence remains necessary when the claimed property or explicit verification claim requires it.

## R13-VER-GY-PLAN

[GY engine subordination plan, §9 Phase 7 verification criteria](../../../../../../policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` · #phase-7

**Поддерживает:** The original V1–V7 criteria, including V4 negatives a–v, define the evidence this proposal must preserve.

**Не доказывает / предел:** Historical planning source; its implementation and product verification status remain planned_after_E02_acceptance and UNRUN in the assigned input. Rebind to the accepted E02 source before execution.

## R13-VER-GY-WORKSTREAM

[R9/GY/Atlas workstream 03, GY tasks](../../../../../../policy-engine/docs/plans/active/post-e02-r9-unified-implementation/workstreams/03-gy.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895`

**Поддерживает:** The workstream preserves task timing, formal status conflicts, final freeze/replay ordering, shared artifacts and no-duplicate-wave requirements.

**Не доказывает / предел:** Planning evidence only; it cannot establish a product result or accepted tree.

## R13-VER-READINESS

[Execution 07 scoped readiness and edge decisions](../../../../../../policy-engine/docs/plans/active/post-e02-r9-unified-implementation/execution/07-scoped-readiness.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895`

**Поддерживает:** Accepted-source rebind must resolve exact source, affected consumers, schemas/rules and relevant semantic fields; interface agreement is planning only.

**Не доказывает / предел:** Does not turn verification preparation into a global completion barrier or substitute for the named final execution receipt.

## R13-VER-CAP-MATRIX

[GY capability coverage matrix checker](../../../../../../policy-engine/tools/quality/validation/check_layer3_gy_capability_coverage_matrix.py) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895`

**Поддерживает:** A native matrix checker exists and can be extended at its current ownership boundary.

**Не доказывает / предел:** At the historical observation it validates declared matrix content and derived summaries; it does not itself establish the complete moved-row denominator or that each declared capability is behaviorally present and consumed.

## R13-VER-LOOP

[Workspace production loop and production-trigger proof owner](../../../../../../policy-engine/src/polisyos/runtime/quality/workspace/loop.py) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895`

**Поддерживает:** The canonical WorkspaceLoop has a real-CAS production-case path and distinguishes production evidence from fixture execution; the historical implementation describes its refusal-path limits.

**Не доказывает / предел:** Source inspection and a route-shaped ProductionLoopRunProof do not prove an actual measurement-rooted outcome, persisted artifacts, or consumer readback.

## R13-VER-REPLAY

[Research DAG replay owner](../../../../../../policy-engine/src/polisyos/scientist/methods/research_dag/replay.py) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895`

**Поддерживает:** The current owner can reconstruct a persisted high-level agentic decision/provenance trace without making new live calls.

**Не доказывает / предел:** Trace reconstruction is not deterministic provider re-execution, byte-identical output replay, or promoted-artifact revalidation.

## R13-VER-CANON

[GY evidence canonical hash helper](../../../../../../policy-engine/tools/quality/validation/gy_evidence_canon.py) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895`

**Поддерживает:** A native canonical evidence hash helper exists and removes selected volatile values before hashing.

**Не доказывает / предел:** At the historical observation it also strips keys ending in _at and _duration; this is not safe evidence that authority-relevant effective/as-of/source times are preserved in the digest.

## R13-VER-G8

[Health metric governance owner (G8)](../../../../../../policy-engine/src/polisyos/runtime/quality/proving_ground/health_metric_governance.py) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895`

**Поддерживает:** One existing owner normalizes health metric aliases, captures source snapshots, emits trend/cross-metric diagnoses, and distinguishes domain from search ceiling with anti-gaming checks; Cycle Board is an existing surface.

**Не доказывает / предел:** This is a diagnostic metric governance owner, not causal identification or authority for useful-design-rate optimization.

## R13-VER-PATTERNS

[Policy Design Case failure/repair register](../../../../../../policy-engine/docs/reference/policy-design-case-failure-patterns.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895` · #P29-P41

**Поддерживает:** P29–P41 require behavioral proof, resolve/content-bind/verifier provenance, adversarial variants, completed exclusion isolation, complete denominators, gate predicate provenance/property divergence, companion-aware budgeting, and correct-base red replay.

**Не доказывает / предел:** Pattern guidance constrains honest evidence and implementation shape; it does not itself prove any V1–V7 product property.

## R13-VER-HYPOTHESIS

[Hypothesis Quickstart](https://hypothesis.readthedocs.io/en/latest/quickstart.html)

**Поддерживает:** Property-based examples can be generated through ordinary Python test functions and run by pytest/unittest; example volume is configurable.

**Не доказывает / предел:** Generated examples explore the supplied strategy and property; they do not establish oracle correctness, source-set completeness, or proof over all inputs.

## R13-VER-STATEFUL

[Hypothesis stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html)

**Поддерживает:** Rule-based stateful tests generate action sequences, can compare an implementation with a reference model, and shrink failures to shorter sequences.

**Не доказывает / предел:** The reference model and action language can omit the very transition that matters; sequence generation is not evidence that the model covers PolicyOS lifecycle semantics.

## R13-VER-METAMORPHIC

[Metamorphic Testing: A New Approach for Generating Next Test Cases (HKUST-CS98-01)](https://www.cse.ust.hk/faculty/scc/publ/CS98-01-metamorphictesting.pdf)

**Поддерживает:** Metamorphic testing derives follow-up test cases and expected relations from successful cases when a direct oracle is difficult to obtain.

**Не доказывает / предел:** The chosen relation is itself a premise; relations must be reasoned from the original criterion and challenged with adversarial variants, not treated as self-validating.

## R13-VER-MUTATION

[Toward Just-in-time and Language-agnostic Mutation Testing](https://labs.oracle.com/pls/apex/f?p=LABS%3A0%3A111432938371215%3AAPPLICATION_PROCESS%3DGETDOC_INLINE%3A%3A%3ADOC_ID%3A3081)

**Поддерживает:** Mutation testing checks whether tests detect injected faults; full campaigns can be expensive, motivating focused and incremental mutants.

**Не доказывает / предел:** A surviving or killed mutant speaks only to that mutation and test oracle; a small targeted set does not estimate all defect coverage.

## R13-VER-OCI-DIGEST

[Open Containers Initiative Image Specification: Descriptor](https://specs.opencontainers.org/image-spec/descriptor/)

**Поддерживает:** A content consumer should verify referenced bytes against the descriptor digest and size.

**Не доказывает / предел:** A digest binds bytes; by itself it does not establish semantic validity, correct provenance, a runtime environment, or authority.

## R13-VER-PYTORCH-REPRO

[PyTorch reproducibility notes](https://docs.pytorch.org/docs/stable/notes/randomness.html)

**Поддерживает:** Reproducibility is scoped to software/hardware conditions; deterministic choices may be slower or unavailable, and cross-release/platform bit identity is not a general promise.

**Не доказывает / предел:** This documents PyTorch-specific behavior, not the PolicyOS runtime; use it to scope replay claims, not as evidence that local operations are nondeterministic or slow.

## R13-VER-SOURCE-DATE

[SOURCE_DATE_EPOCH reproducible-builds documentation](https://reproducible-builds.org/docs/source-date-epoch/)

**Поддерживает:** Normalizing build timestamps can remove one source of build variation.

**Не доказывает / предел:** Controlling one timestamp does not establish whole-program, model, data, hardware, or semantic reproducibility.

## R13-VER-RUBIN-1974

[Estimating Causal Effects of Treatments in Randomized and Nonrandomized Studies](https://dash.harvard.edu/entities/publication/73120378-82c0-6bd4-e053-0100007fdf3b)

**Поддерживает:** Causal effect estimation requires controlled comparisons and explicit assumptions; randomization is useful where possible, with careful nonrandomized designs sometimes necessary.

**Не доказывает / предел:** A descriptive health-signal dashboard or cross-metric association is not itself an identified causal effect.

## R13-ATLAS-PUBLIC-NARA-RECORDS

[Frequently Asked Questions for OFR](https://www.archives.gov/federal-register/faqs)

**Поддерживает:** NARA says each Federal Register issue and its published documents are permanent records; a published document cannot be altered or unpublished, and a correction, withdrawal or rescission requires the issuing agency to publish a new document.

**Не доказывает / предел:** This is a US federal legal-record rule, not a PolicyOS authority grant. Transfer only the append-and-link history pattern; external institutions retain their own decision authority.

## R13-ATLAS-PUBLIC-GOVINFO

[New govinfo API](https://www.govinfo.gov/features/api)

**Поддерживает:** GovInfo describes unique package and granule identifiers, multiple content renditions, descriptive MODS metadata, and preservation PREMIS metadata including fixity. Its official record example separates an issue package from individual document granules.

**Не доказывает / предел:** GovInfo's package model is an example, not a requirement to add a PolicyOS package database or adopt its IDs. Preserve the local exact ArtifactRef and selected manifest view.

## R13-ATLAS-PUBLIC-GOVINFO-FR

[Federal Register collection help](https://www.govinfo.gov/help/fr)

**Поддерживает:** GovInfo distinguishes the official published Federal Register from its earlier public-inspection material and explains that a granule ID identifies one document inside an issue; it also has an explicit corrections section.

**Не доказывает / предел:** The legal timing and status are specific to the Federal Register. Do not transfer its legal effects, and do not treat FederalRegister.gov's explicitly unofficial XML display as the authoritative record.

## R13-ATLAS-PUBLIC-WCAG22

[Web Content Accessibility Guidelines (WCAG) 2.2](https://www.w3.org/TR/WCAG22/)

**Поддерживает:** WCAG 2.2 defines testable, technology-independent criteria. Relevant examples include text resize, reflow without loss at 320 CSS px, programmatic status messages, keyboard focus visibility/order, and name/role/value.

**Не доказывает / предел:** WCAG conformance is scoped to the tested pages and criteria and does not establish human comprehension or an audience's understanding of policy meaning.

## R13-ATLAS-PUBLIC-DFE-PLAIN-LANGUAGE

[Guidance to meet the Plain Language standard](https://design.education.gov.uk/content-design/plain-language)

**Поддерживает:** DfE distinguishes generic plain-English techniques from plain language adapted to user needs and user-research findings; technical terms can be retained where needed but should be explained.

**Не доказывает / предел:** This is UK public-service guidance. It supports audience-qualified review as a method but does not establish the required PolicyOS audiences, locales, or wording.

## R13-ATLAS-PUBLIC-GOVUK-CONTENT

[Understand content design](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/plan-manage-content/understand-content-design/)

**Поддерживает:** GOV.UK content design starts from user needs, considers the best format and place to publish, calls for clear accessible plain-English content, and distinguishes current content from historical content retained as a record.

**Не доказывает / предел:** This is content guidance, not an archival retention standard and not a decision on PolicyOS Trust/Docs ownership.

## R13-ATLAS-PUBLIC-GSS-UNCERTAINTY

[Communicating quality, uncertainty and change](https://gss.civilservice.gov.uk/policy-store/communicating-quality-uncertainty-and-change/)

**Поддерживает:** The GSS guidance recommends explaining source quality, uncertainty, limitations, context, and intended use so that readers can judge fit for use; it warns that excess certainty can prompt unsupported conclusions.

**Не доказывает / предел:** The page is from 2018, currently marked under review, and says it has not incorporated accessibility legislation. It concerns statistics, so use only as a communication example, not as a PolicyOS rule or legal standard.

## R13-ATLAS-PUBLIC-PROV-O

[PROV-O: The PROV Ontology](https://www.w3.org/TR/2013/REC-prov-o-20130430/)

**Поддерживает:** PROV-O supplies interoperable Entity, Activity, and Agent provenance terms and relations for use, generation, attribution, derivation, and responsibility.

**Не доказывает / предел:** A provenance vocabulary cannot prove lawful use, correct interpretation, source independence, institutional mandate, or PolicyOS admissibility.

## R13-ATLAS-PUBLIC-DCAT3

[Data Catalog Vocabulary (DCAT) - Version 3](https://www.w3.org/TR/vocab-dcat-3/)

**Поддерживает:** DCAT 3 distinguishes a resource's versions and previous-version chain, dataset series, and distributions such as different language or format representations; it also models issued and modified dates separately.

**Не доказывает / предел:** DCAT is a dataset-catalog vocabulary. Its concepts may inform typed projections and links, but it is not a PolicyOS record schema or status/authority calculus.

## R13-ATLAS-SET-UNCERTAINTY

[Visualizing Uncertainty in Sets (IEEE VIS 2024 / IEEE Computer Graphics and Applications)](https://www.files.ieeevis.org/year/2024/program/paper_v-cga-10198358.html)

**Поддерживает:** The paper separates uncertainty affecting set membership, set attributes, and element attributes, and distinguishes certainty, undefined uncertainty, and quantifiable uncertainty. This supports separate display treatment for known sets, uncertain membership, and quantified value.

**Не доказывает / предел:** A conceptual framework and examples, not an evaluation of PolicyOS or an admissibility rule.

## R13-ATLAS-PARETO-VIS

[Approximation and Visualization of Pareto Frontier in the Framework of Classical Approach to Multi-Objective Optimization](https://drops.dagstuhl.de/entities/document/10.4230/DagSemProc.04461.8)

**Поддерживает:** Interactive Decision Maps supports examining a Pareto frontier under conflicting criteria and communicating results in design-variable and objective spaces. This is a precedent for showing a frontier when criteria do not license a single rank.

**Не доказывает / предел:** The paper addresses optimization; it does not define PolicyOS value semantics or authorize scalar aggregation.

## R13-ATLAS-OAS31

[OpenAPI Specification 3.1.1](https://spec.openapis.org/oas/v3.1.1.html)

**Поддерживает:** Schema Objects use JSON Schema; oneOf validates exactly one listed alternative. A discriminator is a selection hint and must not change validation, and alternatives must be listed explicitly beside oneOf.

**Не доказывает / предел:** The specification does not guarantee a configured generator emits a correct client union or that clients validate hostile runtime payloads.

## R13-ATLAS-OAS-GENERATOR

[OpenAPI Generator supported generators](https://openapi-generator.tech/docs/generators/)

**Поддерживает:** The project offers multiple client generators, including TypeScript targets, so the generated client family can remain the API-to-client bridge.

**Не доказывает / предел:** Availability does not prove oneOf fidelity for this repository's selected generator/version; actual generated output and consumer need verification.

## R13-ATLAS-PROV-DM

[PROV-DM: The PROV Data Model](https://www.w3.org/TR/prov-dm/)

**Поддерживает:** The model distinguishes entities, activities, usage, generation, derivation, attribution, time, and invalidation; these relations help describe exact lineage and lifecycle.

**Не доказывает / предел:** PROV does not verify a producer, establish currentness or lawful use, or confer authority.

## R13-ATLAS-TS-UNIONS

[TypeScript Handbook: Narrowing and exhaustiveness](https://www.typescriptlang.org/docs/handbook/2/narrowing.html)

**Поддерживает:** Literal discriminants narrow union members; never-based exhaustiveness makes a new variant fail compilation in an unhandled switch.

**Не доказывает / предел:** Static exhaustiveness does not validate untrusted JSON at runtime or replace an API schema.

## R13-ATLAS-TS-PRIVATE

[TypeScript Handbook: Classes](https://www.typescriptlang.org/docs/handbook/2/classes.html)

**Поддерживает:** TypeScript private modifiers are erased and provide design-time checks; ECMAScript private fields, closures, and WeakMaps provide runtime privacy mechanisms.

**Не доказывает / предел:** Runtime privacy does not authenticate a network payload or appoint an institution.

## R13-ATLAS-PG-ISOLATION

[PostgreSQL 18: Transaction Isolation](https://www.postgresql.org/docs/18/transaction-iso.html)

**Поддерживает:** At Read Committed, a concurrent updater waits and re-evaluates the WHERE predicate on the committed row; Serializable provides serial execution for committed transactions but applications must handle retries after serialization failures.

**Не доказывает / предел:** Docs do not prove DS20 wiring. Pin the deployed PostgreSQL major, schema, isolation level, transaction boundary, and app behavior.

## R13-ATLAS-PG-LOCKS

[PostgreSQL 18: Explicit Locking](https://www.postgresql.org/docs/18/explicit-locking.html)

**Поддерживает:** Row-level FOR UPDATE locks block conflicting writers and lockers until transaction end.

**Не доказывает / предел:** A lock does not cover mutation or persistence after its transaction ends or in another store.

## R13-ATLAS-PG-INSERT

[PostgreSQL 18: INSERT](https://www.postgresql.org/docs/18/sql-insert.html)

**Поддерживает:** A unique conflict target and ON CONFLICT provide an atomic insert/update result under concurrency; RETURNING reports rows actually affected. A unique single-use token row can support one-winner replay handling.

**Не доказывает / предел:** The SQL primitive does not prove the application uses it at the correct boundary or maps a loser to the required response.

## R13-ATLAS-PG-UPDATE

[PostgreSQL 18: UPDATE](https://www.postgresql.org/docs/18/sql-update.html)

**Поддерживает:** UPDATE supports a conditional WHERE predicate and RETURNING values for rows actually updated, exposing whether an expected-revision comparison matched.

**Не доказывает / предел:** A SQL example is not a Fabric capability receipt; a post-check or later mutation is outside its atomic boundary.

## R13-ATLAS-HELM-PROVENANCE

[Helm Provenance and Integrity](https://helm.sh/docs/topics/provenance/)

**Поддерживает:** Helm package provenance binds a chart package checksum to a signature, and helm install --verify aborts when verification fails.

**Не доказывает / предел:** A valid signature does not prove an embedded policy mirror equals the canonical source policy set. The current page warns that it is not fully updated for Helm 4; only generic package checksum/signature integrity is relied on. Rebind command behavior to the actually deployed major before execution.

## R13-ATLAS-VOI-ORIGINAL

[The Value of Information and Stochastic Programming](https://pubsonline.informs.org/doi/10.1287/opre.18.5.947)

**Поддерживает:** Expected value of perfect information is an expected gain in the decision objective and an upper bound on what is worth spending to acquire the information.

**Не доказывает / предел:** This perfect-information bound is not a numeric VOI producer for DS15's finite route or a cost schedule.

## R13-ATLAS-VOI-DECISIONS

[On the Value of Information Across Decision Problems](https://pubsonline.informs.org/doi/10.1287/deca.2024.0187)

**Поддерживает:** Expected utility increase and buying price are distinct value-of-information measures and need not rank information sources identically across decision problems.

**Не доказывает / предел:** The paper does not supply PolicyOS's missing utility, route, cost basis, or numeric producer.

## R13-ATLAS-DSL-MIGRATION

[DSL Migration](https://martinfowler.com/bliki/DslMigration.html)

**Поддерживает:** Versioned DSL change can use small incremental migration programs or version-specific parsers and a semantic model; migrations should preserve information important to authors.

**Не доказывает / предел:** Practitioner guidance, not a PolicyOS schema decision; the native owner chooses the semantics.

## R13-ATLAS-PARALLEL-CHANGE

[Parallel Change](https://www.martinfowler.com/bliki/ParallelChange.html)

**Поддерживает:** Expand/migrate/contract lets clients move incrementally before the old interface is removed; temporary dual support has coordination cost and needs a real completion point.

**Не доказывает / предел:** The pattern does not justify permanently maintaining duplicate semantics or auto-upgrading historical authority.

## R13-FOUNDATIONS-DCAT3

[Data Catalog Vocabulary (DCAT) Version 3](https://www.w3.org/TR/vocab-dcat-3/)

**Поддерживает:** DCAT 3 distinguishes cataloged datasets, distributions, data services and dataset series; it adds version/current-version relations and supports multiple representations and temporal/spatial metadata.

**Не доказывает / предел:** A catalog vocabulary supports interoperability and discovery. It does not establish that content is authentic, lawful to reuse, applicable, current for a claim, or authoritative.

## R13-FOUNDATIONS-PROV

[PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/)

**Поддерживает:** PROV-O provides reusable relations among entities, activities and agents, including generation, use, derivation and attribution, for expressing lineage.

**Не доказывает / предел:** A lineage graph records declared provenance. It does not prove independence, factual truth, legal permission, or source quality unless those properties have their own evidence and verification.

## R13-FOUNDATIONS-SHACL

[Shapes Constraint Language (SHACL)](https://www.w3.org/TR/shacl/)

**Поддерживает:** SHACL validates an RDF data graph against a versioned shapes graph and can emit a validation report.

**Не доказывает / предел:** SHACL is a possible validation format when an owner already uses RDF. Structural conformance alone is not semantic adequacy or authority, and adopting it would not justify a second registry.

## R13-FOUNDATIONS-OECD-SDMX

[OECD SDMX API](https://www.oecd.org/en/data/insights/data-explainers/2024/09/api.html)

**Поддерживает:** The OECD documents separate data queries from structure queries and identifies agency, dataset and dataset version as components of a data query.

**Не доказывает / предел:** API structure and version paths help bind a query and representation. They do not prove completeness, fitness for a local estimand, or stable availability.

## R13-FOUNDATIONS-OECD-API-CONTENT

[OECD API best practices and recommendations](https://www.oecd.org/en/data/insights/data-explainers/2024/11/Api-best-practices-and-recommendations.html)

**Поддерживает:** The OECD recommends its content-constraint query as a way to read a dataset ValidFrom time and observation count and check whether a dataset version changed.

**Не доказывает / предел:** A change detector is a trigger for refresh and revalidation, not an integrity, currentness, or applicability verdict.

## R13-FOUNDATIONS-WB-API

[World Bank Indicators API basic call structures](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581)

**Поддерживает:** The API documents date and source parameters, language variants, page and per_page controls, and returns pagination metadata such as page count and total records.

**Не доказывает / предел:** The endpoint requires complete paging and exact parameter capture where paging is used. The API describes an aggregate indicator service, not a selected case source or household-level dataset.

## R13-FOUNDATIONS-EURLEX-CONSOLIDATION

[Consolidated texts](https://eur-lex.europa.eu/collection/eu-law/consleg.html?locale=en)

**Поддерживает:** EUR-Lex states that consolidated texts show rules applicable at a point in time but have no legal effect; its page identifies the amendments included in a consolidation.

**Не доказывает / предел:** This is an EU publisher's rule about its consolidations, not a universal rule for other jurisdictions. The exact governing legal source and effectivity rules remain case-specific.

## R13-FOUNDATIONS-ELI

[European Legislation Identifier](https://eur-lex.europa.eu/content/help/eurlex-content/eli.html?locale=en)

**Поддерживает:** ELI provides web identifiers and metadata for legislation, including point-in-time versions and language/format distinctions in its URI model.

**Не доказывает / предел:** An identifier resolves a resource or version; it does not determine legal effect, notice, competence, applicability, or the authoritative language for another jurisdiction.

## R13-FOUNDATIONS-AKN

[Akoma Ntoso Version 1.0 XML Vocabulary](https://docs.oasis-open.org/legaldocml/akn-core/v1.0/os/part1-vocabulary/akn-core-v1.0-os-part1-vocabulary.html)

**Поддерживает:** Akoma Ntoso describes legal document lifecycle events and links those events to the individual documents that produced them; it distinguishes original, single and multiple versions.

**Не доказывает / предел:** A document format can preserve and link legal material but cannot make a legal interpretation or establish the competence of the issuer.

## R13-FOUNDATIONS-OECD-IDD-METADATA

[OECD Income Distribution Database metadata](https://www.oecd.org/content/dam/oecd/en/data/datasets/income-and-wealth-distribution-databases/idd-metadata-sources-and-income-years.pdf)

**Поддерживает:** OECD documents its equivalised disposable household income definition, its treatment of income components and persons as the distribution unit, and notes the square-root household scale is a common but arbitrary choice.

**Не доказывает / предел:** The documented OECD convention explains that dataset's construction; it does not establish that the same construct or scale fits a different population or policy question.

## R13-FOUNDATIONS-OECD-IDD-GUIDELINES

[OECD Income Distribution Database guidelines](https://www.oecd.org/content/dam/oecd/en/about/programmes/oecd-data-collection-programme/society/income-distribution-database/income-distribution-guidelines.pdf)

**Поддерживает:** The guidelines distinguish household survey observation units from person-level distribution indicators, weight households by member count, and prescribe an equivalence elasticity of 0.5 for that series.

**Не доказывает / предел:** The prescribed definition harmonizes the OECD series; a shared label does not guarantee local frame, accounting, equivalisation, or period comparability.

## R13-FOUNDATIONS-ATKINSON

[On the measurement of inequality](https://are.berkeley.edu/courses/ARE251/fall2007/Papers/atkinson70.pdf)

**Поддерживает:** Atkinson derives inequality measurement from an explicit social-welfare approach and contrasts ranking distributions with quantifying inequality, illustrating that a measure embeds choices about distributional sensitivity.

**Не доказывает / предел:** This paper supplies a method and assumptions, not authorization to select an inequality-aversion parameter for a case.

## R13-FOUNDATIONS-ALKIRE-FOSTER

[Counting and multidimensional poverty measurement](https://www.aeaweb.org/conference/2009/retrieve.php?pdfid=39)

**Поддерживает:** Alkire and Foster describe within-dimension deprivation cutoffs, a cross-dimension cutoff, and an adjusted headcount measure that captures incidence and breadth.

**Не доказывает / предел:** Dimension weights and cutoffs are substantive choices; the paper does not make them universally correct or supply local authorization.

## R13-FOUNDATIONS-WHAT-IF

[Causal Inference: What If](https://miguelhernan.org/whatifbook)

**Поддерживает:** Hernán and Robins frame observational causal analysis as emulation of a specified target trial and discuss exchangeability, positivity, consistency, treatment versions and longitudinal methods.

**Не доказывает / предел:** The site points to a revisable edition; a use must pin the exact version. Its methods do not choose a policy objective or certify a case's assumptions.

## R13-FOUNDATIONS-TRANSPORT

[External Validity: From Do-Calculus to Transportability Across Populations](https://arxiv.org/abs/1503.01603)

**Поддерживает:** Pearl and Bareinboim use selection diagrams to represent differences between study and target populations and derive conditions under which causal effects can be transported.

**Не доказывает / предел:** The diagram's assumptions require substantive support. Formal transportability does not rescue absent overlap or an ungrounded account of population differences.

## R13-FOUNDATIONS-CALIBRATION

[Calibration: the Achilles heel of predictive analytics](https://link.springer.com/article/10.1186/s12916-019-1466-7)

**Поддерживает:** Van Calster and colleagues distinguish calibration assessment from other predictive-model performance and describe calibration checks for external validation.

**Не доказывает / предел:** Predictive calibration on a target sample is neither causal identification nor proof that the target sample represents a policy population.

## R13-FOUNDATIONS-OECD-DELIBERATION

[Good practice principles for deliberative processes for public decision making](https://www.oecd.org/en/publications/innovative-citizen-participation-and-new-democratic-institutions_339306da-en/full-report/component-9.html)

**Поддерживает:** OECD's principles include a clear remit, accountability, transparency, representativeness, inclusion, accessible information, deliberation, adequate time, independence, privacy and evaluation.

**Не доказывает / предел:** These are process design principles drawn from comparative practice, not a legal mandate, universal representation test, or substitute for the commissioning authority's decision.

## R13-FOUNDATIONS-OECD-PARTICIPATION

[OECD Guidelines for Citizen Participation Processes](https://www.oecd.org/en/publications/oecd-guidelines-for-citizen-participation-processes_f765caf6-en.html)

**Поддерживает:** The guidelines distinguish participation methods and policy-cycle stages, and recommend stating expected outcomes and how citizen input will be used or answered.

**Не доказывает / предел:** Participation can inform issue framing, formulation, decision, implementation or evaluation, but a participation record alone does not establish an authorized decision.

## R13-FOUNDATIONS-GREEN-BOOK

[The Green Book (2026)](https://www.gov.uk/government/publications/the-green-book--2/the-green-book-2026)

**Поддерживает:** The guidance says it does not set objectives or make policy decisions and requires weighted distributional estimates to appear alongside unweighted estimates.

**Не доказывает / предел:** Its weights and procedures are UK-specific policy guidance, not universal defaults. It is useful here as an example of explicitly exposing value choices and preserving the decision maker's role.

## R13-FOUNDATIONS-CARE

[The CARE Principles for Indigenous Data Governance](https://doi.org/10.5334/dsj-2020-042)

**Поддерживает:** The paper articulates collective benefit, authority to control, responsibility and ethics as people- and purpose-oriented considerations in Indigenous data governance.

**Не доказывает / предел:** Apply only where the relevant peoples, communities and their governing authorities make these principles relevant; it is not a generic permission token or replacement for local rights.

## R13-FOUNDATIONS-COCHRANE-SEARCH

[Cochrane Handbook, Chapter 4: Searching for and selecting studies](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04)

**Поддерживает:** Cochrane recommends searches matched to eligibility criteria, broad source coverage, reproducible exact search strategies and record counts, and distinguishes reports from underlying studies.

**Не доказывает / предел:** Search recommendations arise from health evidence synthesis and need adaptation to other fields, languages, source types and lawful access constraints.

## R13-FOUNDATIONS-COCHRANE-LIVING

[Cochrane Handbook, Chapter 22: Prospective approaches to accumulating evidence](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-22)

**Поддерживает:** Cochrane's living-review guidance calls for explicit search methods and update frequency, ongoing surveillance, and communication of what changed between versions.

**Не доказывает / предел:** The handbook does not prescribe a universal refresh interval; use depends on source change rates, decision stakes and resource constraints.

## R13-FOUNDATIONS-BH

[Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x)

**Поддерживает:** Benjamini and Hochberg introduce a step-up procedure that controls false discovery rate under independent test statistics.

**Не доказывает / предел:** Independence conditions and the tested family matter; this is not a blanket license to promote adaptive findings or use the procedure without checking dependence assumptions.

## R13-FOUNDATIONS-REUSABLE-HOLDOUT

[Generalization in Adaptive Data Analysis and Holdout Reuse](https://papers.neurips.cc/paper_files/paper/2015/hash/bad5f33780c42f2588878a9d07405083-Abstract.html)

**Поддерживает:** The paper shows that repeated adaptive reuse of a holdout can overfit it and presents a method for controlling that risk.

**Не доказывает / предел:** The method's guarantees depend on its formal setting and algorithm. It is a warning and possible design family, not evidence that PolicyOS has independent validation.

## R13-OPS-SQLITE-WAL

[Write-Ahead Logging](https://www.sqlite.org/wal.html)

**Поддерживает:** SQLite WAL permits readers alongside a writer but requires all database processes on one host, does not work over a network filesystem, and the WAL file is part of persistent state.

**Не доказывает / предел:** SQLite storage behavior does not establish the durability or locking semantics of an untested filesystem/container volume.

## R13-OPS-SQLITE-BACKUP

[SQLite Online Backup API](https://www.sqlite.org/backup.html)

**Поддерживает:** The Online Backup API can copy a live database as a snapshot while allowing writes between brief source reads; raw file copying has failure and locking limitations.

**Не доказывает / предел:** A database snapshot alone does not capture CAS objects, source rights, revocations, credentials, or provider-side effects.

## R13-OPS-POSTGRES-RECOVERY

[PostgreSQL Backup and Restore](https://www.postgresql.org/docs/current/backup.html)

**Поддерживает:** PostgreSQL presents SQL dump, filesystem backup, and continuous archiving as distinct methods with different assumptions; PITR depends on a base backup and a suitable WAL archive.

**Не доказывает / предел:** The current docs do not select a PolicyOS RPO/RTO or prove the selected operator's backup chain.

## R13-OPS-SYSTEMD

[systemd.service](https://www.freedesktop.org/software/systemd/man/256/systemd.service.html)

**Поддерживает:** systemd supports restart-on-failure for long-running services, and automatic restart is subject to start-rate limits.

**Не доказывает / предел:** Process supervision does not provide durable job leases, exactly-once effects, or cross-store transaction semantics.

## R13-OPS-K8S-PROBES

[Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)

**Поддерживает:** Kubernetes distinguishes liveness from readiness; readiness can remove a temporarily unable pod from service without restarting it.

**Не доказывает / предел:** This is a Kubernetes implementation of a useful distinction, not a requirement to deploy Kubernetes.

## R13-OPS-OWASP-BOLA

[OWASP API1:2023 Broken Object Level Authorization](https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/)

**Поддерживает:** Every endpoint that accepts an object ID and acts on it needs object-level authorization; identifier unpredictability does not replace that check.

**Не доказывает / предел:** OWASP guidance identifies the class and mitigation, not whether the historical PolicyOS job route is vulnerable.

## R13-OPS-GITLAB-TOKEN-INCIDENT

[Project runner registration token security update](https://about.gitlab.com/blog/security-incident-runner-registration-token/)

**Поддерживает:** GitLab reported that a project runner-registration-token vulnerability could expose project-scoped tokens to unauthorized users and reset tokens as mitigation.

**Не доказывает / предел:** This incident supports narrow credential scope and revocation readiness; it is not evidence of a PolicyOS defect.

## R13-OPS-SECRETS

[OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

**Поддерживает:** Secrets should have least-privilege access, lifecycle and audit metadata, expiration/revocation, and short-lived credentials where practicable.

**Не доказывает / предел:** It does not prescribe a single secret manager or eliminate the need for an institution-owned root credential and source-use grant.

## R13-OPS-STRIPE-IDEMPOTENCY

[Idempotent requests](https://docs.stripe.com/api/idempotent_requests)

**Поддерживает:** Stripe supports request idempotency keys for safely retrying supported operations, with provider-specific parameter matching and key retention behavior.

**Не доказывает / предел:** Idempotency behavior differs by provider and endpoint; a timeout or this example does not prove another provider did not execute or charge.

## R13-OPS-CGROUP-V2

[Control Group v2](https://docs.kernel.org/7.0/admin-guide/cgroup-v2.html)

**Поддерживает:** Linux cgroup v2 exposes CPU, memory, process and I/O controls; memory.high throttles/reclaims while memory.max is a hard limit that can invoke OOM handling, and child limits can be overcommitted.

**Не доказывает / предел:** Kernel controls bound OS resources for a configured cgroup; they do not by themselves provide application admission, provider spend limits, scratch quotas, or safe semantic outcomes.

## R13-OPS-PSI

[Pressure Stall Information](https://docs.kernel.org/6.10/accounting/psi.html)

**Поддерживает:** Linux PSI measures CPU, memory and I/O stall time and provides threshold triggers suitable for resource-pressure observation and load shedding.

**Не доказывает / предел:** Pressure measurements are signals for an admission policy, not a universal capacity threshold or hard limit.

## R13-OPS-K8S-RESOURCES

[Resource Management for Pods and Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)

**Поддерживает:** Kubernetes applies CPU limits through throttling and memory limits through kernel OOM behavior; requests guide scheduling and do not assert application-level/provider budgets.

**Не доказывает / предел:** Kubernetes is one placement/enforcement option; these controls do not establish global job admission or semantic authorization.

## R13-OPS-S3-CAS

[How to prevent object overwrites with conditional writes](https://docs.aws.amazon.com/us_en/AmazonS3/latest/userguide/conditional-writes.html)

**Поддерживает:** S3 conditional writes can prevent a put from replacing an existing key and can use If-Match preconditions; concurrent multipart/delete cases have distinct 409/412 behavior.

**Не доказывает / предел:** Provider-specific behavior, multipart handling, and authorization still require tests against the selected adapter and configuration.

## R13-OPS-GCS-CAS

[Request preconditions](https://docs.cloud.google.com/storage/docs/request-preconditions)

**Поддерживает:** Cloud Storage generation/metageneration preconditions support conditional mutation and help prevent races; a lost response can leave the client uncertain whether a request applied.

**Не доказывает / предел:** Generation conditions are provider-specific and do not make object storage transactional with the control database.

## R13-OPS-TUF

[The Update Framework Specification v1.0.37](https://theupdateframework.github.io/specification/v1.0.37/index.html)

**Поддерживает:** TUF uses an out-of-band trusted root, threshold signatures, sequential root versions, expiry, persisted root metadata, and an out-of-band recovery path if the root threshold is compromised.

**Не доказывает / предел:** TUF is a protocol pattern, not an institutional appointment, legal grant, or required PolicyOS dependency.

## R13-OPS-CISA-SOLARWINDS

[CISA Alert AA20-352A: Advanced Persistent Threat Compromise](https://content.govdelivery.com/accounts/USDHSCISA/bulletins/2b1b32d)

**Поддерживает:** CISA documented the SolarWinds supply-chain compromise and follow-on identity abuse, including malicious software delivered through the update chain and valid SAML tokens minted after signing-certificate compromise.

**Не доказывает / предел:** This demonstrates that signatures and a trusted update path do not prove benign content or continuing identity integrity; it does not define a PolicyOS threat threshold.

## R13-OPS-FSYNC

[fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html)

**Поддерживает:** Linux fsync flushes file data/metadata, while durable publication of a directory entry may require fsync of the directory.

**Не доказывает / предел:** Filesystem, mount, device-cache, and network-volume behavior must be qualified on the exact deployment target.

## R13-OPS-OTEL-CARDINALITY

[Metrics: Cardinality limits](https://opentelemetry.io/docs/concepts/signals/metrics/)

**Поддерживает:** OpenTelemetry metrics SDKs bound the number of tracked attribute combinations (the documented default is 2000); additional measurements are folded into an overflow point, preserving overall totals but dropping the original attribute combination. Queries grouping/filtering by those dropped attributes can undercount.

**Не доказывает / предел:** SDK default and behavior are telemetry implementation details, not PolicyOS audit or admission contracts. Exact per-decision evidence still requires a separately authorized durable receipt.

## R13-OPS-K8S-CRD-DATA

[Custom Resources](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/)

**Поддерживает:** Kubernetes documentation advises against using Custom Resources as storage for application, end-user, or monitoring data because this couples normal workload operation to the Kubernetes API; CRDs are intended for resources used with Kubernetes API/controller conventions.

**Не доказывает / предел:** This is deployment guidance for Kubernetes and does not rule out a narrowly scoped configuration/control object when the API is already an owned interface. It gives no reason to make Kubernetes a mandatory dependency.

## R13-DEBT-LOCAL-CUSTODY

[PolicyOS identity and custody boundary](../../../../../../policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895`

**Поддерживает:** The four-way scope test is own when absence makes our published claim false; integrate when external output changes our claim validity; observe when only answerability changes; otherwise out_of_scope. Candidate-band unknowns may be carried as declared limitations; authority-band claims fail closed when required scope is unknown.

**Не доказывает / предел:** This is the ratified PolicyOS rule, not a substitute for content-bound evidence establishing the factual predicate in an individual case.

## R13-DEBT-LOCAL-NORTHSTAR

[Policy design causal operating system north star](../../../../../../policy-engine/docs/system-design-decisions/policy-design-causal-operating-system-north-star.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895`

**Поддерживает:** PolicyOS is an epistemic custodian: it consumes others' signatures as typed evidence, signs only claims it can custody, and must keep published justification honest across time and world change.

**Не доказывает / предел:** Product identity guidance; it does not appoint external institutions or define an unratified numeric metric.

## R13-DEBT-COVERAGE

[Coverage.py configuration reference](https://coverage.readthedocs.io/en/latest/config.html)

**Поддерживает:** The measured source universe is affected by configured source/include/omit selectors, and source selection changes what a coverage result says it has measured.

**Не доказывает / предел:** Coverage.py measures execution, not PolicyOS instrument input reads; transfer only the need to disclose scope selectors, not its coverage metric or runner.

## R13-DEBT-RB-PERIMETER

[What's in a build environment?](https://reproducible-builds.org/docs/perimeter/)

**Поддерживает:** A reproducibility claim has a declared perimeter including tools, versions, operating-system assumptions, locale, timezone, paths, and relevant environment variables; outputs are comparable only within that stated context.

**Не доказывает / предел:** A project guide, not a universal guarantee that two systems will be reproducible or a mandate to adopt containerization.

## R13-DEBT-UV

[Locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)

**Поддерживает:** uv lock/sync can check metadata-lock consistency, and exact sync removes packages outside the lock; frozen and locked modes have different verification semantics.

**Не доказывает / предел:** A lockfile pins package resolution, not OS/locale/environmental inputs or generated artifact semantics. Repository-specific setup commands remain controlling.

## R13-DEBT-OPENAPI

[OpenAPI Specification v3.1.1](https://spec.openapis.org/oas/v3.1.1.html)

**Поддерживает:** An OpenAPI Description consists of its entry document and all referenced documents; reference resolution, base URIs, and cycles affect the meaning and complete surface.

**Не доказывает / предел:** The specification defines the description format, not a particular repository export pipeline or the desired API policy.

## R13-DEBT-JCS

[RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html)

**Поддерживает:** A canonical JSON representation can make hash/signature inputs repeatable across serializers when data satisfies JCS/I-JSON constraints.

**Не доказывает / предел:** Informational RFC, not an Internet Standards Track specification; its number/string constraints may make it unsuitable for some payloads. Reuse an existing canonical serializer first.

## R13-DEBT-PEP387

[PEP 387 – Backwards Compatibility Policy](https://peps.python.org/pep-0387/)

**Поддерживает:** Python's compatibility guidance distinguishes documented public API from merely importable modules and provides a deprecation approach for actual public interfaces.

**Не доказывает / предел:** An ecosystem analogy only. PolicyOS architecture/public_surface/contract.toml and its inventory-review rules control this repository.

## R13-DEBT-PYDANTIC

[Pydantic strict mode and models](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/)

**Поддерживает:** Strict mode reduces implicit coercion, while Pydantic model validation establishes output types and constraints rather than proving truth of input claims.

**Не доказывает / предел:** Strictness is a parsing boundary only. It is not evidence provenance, authority, or semantic adequacy.

## R13-DEBT-JSON-SCHEMA

[Understanding JSON Schema: object properties](https://json-schema.org/understanding-json-schema/reference/object)

**Поддерживает:** JSON Schema permits additional properties by default; `additionalProperties: false` is an explicit closed-object rule.

**Не доказывает / предел:** Schema closure can prevent unreviewed fields but does not itself solve version migration or semantic truth.

## R13-DEBT-PYTHON-IMPORT

[The import system: module cache](https://docs.python.org/3.14/reference/import.html)

**Поддерживает:** Python checks writable `sys.modules` first; deleting a cache entry does not destroy references already held by other modules, and reimport may create a different module object.

**Не доказывает / предел:** Describes import semantics; test isolation choice still depends on the actual patched objects and consumers.

## R13-DEBT-PYTEST

[How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html)

**Поддерживает:** pytest monkeypatch operations are undone at test/fixture teardown, and context scopes can undo earlier; direct global mutation without fixture tracking is not automatically repaired.

**Не доказывает / предел:** Fixture cleanup restores registered state only and cannot erase references leaked into other already-imported modules.

## R13-DEBT-TUF

[TUF roles and metadata](https://theupdateframework.io/docs/metadata/)

**Поддерживает:** Trust decisions are purpose/role-bound and bind key thresholds, signatures, hashes, versions, and expiry; old metadata must be detected rather than silently promoted.

**Не доказывает / предел:** Software-update repository model; use as a design comparison for typed scope/time binding, not as a PolicyOS authority scheme or a call to adopt TUF.

## R13-DEBT-AIOHTTP

[aiohttp client reference](https://docs.aiohttp.org/en/stable/client_reference.html)

**Поддерживает:** ClientSession owns connection pooling and supports context-managed closing; its recommended lifetime is application-level for ordinary use, not per request.

**Не доказывает / предел:** This only supports a bounded lifecycle repair if the original foreign task confirms session cleanup is its criterion; it does not establish that this foreign row has that criterion.

## R13-DEBT-ISPOR-VOI

[Value of Information Analytical Methods: ISPOR VOI Analysis Emerging Good Practices Task Force, Report 2](https://pmc.ncbi.nlm.nih.gov/articles/PMC7373630/)

**Поддерживает:** VOI compares expected decision-payoff improvement from information with acquisition/research cost; EVPI, EVPPI, EVSI and ENBS answer distinct questions, and population value depends on beneficiary population and useful horizon.

**Не доказывает / предел:** Health-technology-assessment application. Transfer the explicit decision model, assumptions, population, horizon, and cost separation; do not import its utility or monetary units into PolicyOS without an owner decision.

## R13-DEBT-ICH-E9

[ICH E9(R1) estimands and sensitivity analysis guideline](https://database.ich.org/sites/default/files/E9-R1_Step4_Guideline_2019_1203.pdf)

**Поддерживает:** A decision estimand needs explicit population, variable, intercurrent-event strategy, and population-level summary; comparability depends on the question and setting.

**Не доказывает / предел:** Clinical-trial-specific guidance; it is an example of fully specified estimands, not a universal PolicyOS metric contract.

## R13-DEBT-BH

[Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing](https://academic.oup.com/jrsssb/article/57/1/289/7035855)

**Поддерживает:** The Benjamini–Hochberg procedure controls FDR under its stated independent-test condition; repeated/exploratory discovery requires the declared testing family and dependence assumptions.

**Не доказывает / предел:** This result does not confer authority to any PolicyOS anomaly or solve longitudinal/repeated-look control without a fitted and justified procedure.

## R13-DEBT-PROV

[PROV Model Primer](https://www.w3.org/TR/prov-primer/)

**Поддерживает:** PROV represents entities, activities, usage/generation, agents, and responsibility so a reader can trace artifact lineage and provenance assertions.

**Не доказывает / предел:** A provenance vocabulary records relationships; it does not decide whether an external function belongs in PolicyOS or whether evidence has admissible authority.

## R13-DEBT-WCAG-EM

[WCAG Evaluation Methodology (WCAG-EM) 2.0](https://www.w3.org/TR/WCAG-EM/)

**Поддерживает:** A documented accessibility evaluation defines its scope, explores the product, selects a representative sample, evaluates it, and reports outcomes; sampling does not silently become whole-product inspection.

**Не доказывает / предел:** Accessibility methodology does not provide an independent countersign, nor replace the exact C13 print/content criteria or required qualified evaluator.

## R13-EXEC-GOOGLE-LSC

[Large-Scale Changes, Software Engineering at Google](https://abseil.io/resources/swe-book/html/ch22.html)

**Поддерживает:** The described LSC process separates authorization, change creation, shard management, and cleanup; independent shards are tested and reviewed, while a train can run affected tests against the combined change set.

**Не доказывает / предел:** This is a Google process with dedicated tooling and different scale. Transfer the shard, owner, and combined-integration principles only; it does not establish PolicyOS throughput, resource limits, acceptance authority, or a need to build an LSC platform.

## R13-EXEC-GITHUB-QUEUE

[Managing a merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)

**Поддерживает:** Required checks are rerun for a temporary integration group based on the latest target branch and queued changes ahead of it; failed or conflicting groups are removed. A PR-head result alone is not the combined-tree result.

**Не доказывает / предел:** This is GitHub merge behavior, not a PolicyOS scheduler or a domain evidence rule. It supports binding final evidence to the integrated tree, not adopting a queue service.

## R13-EXEC-GITHUB-STACKS

[Merging stacked pull requests](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/merging-stacked-pull-requests)

**Поддерживает:** A dependent stack merges bottom-up; the status shown for a stack includes lower changes, and an intermediate change cannot be treated as an isolated integration when its lower dependencies are absent.

**Не доказывает / предел:** Stack semantics vary by host and merge strategy. Use this only to motivate explicit bases and dependency-aware review; PolicyOS keeps its existing root-only integration owner.

## R13-EXEC-GITHUB-REVIEW

[Dismissing a pull request review](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/dismissing-a-pull-request-review)

**Поддерживает:** GitHub treats a review as potentially outdated after the reviewed change changes and requires a reason when an administrator dismisses it.

**Не доказывает / предел:** The exact host behavior is not a universal review protocol. PolicyOS should carry review only across a proven unchanged scope and record why; it should not assume host approval state establishes semantic review.

## R13-EXEC-GOOGLE-REVIEW

[What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)

**Поддерживает:** Reviewers should examine assigned changes in context and identify which portions they reviewed when review responsibility is split; qualified reviewers are needed for specialized concerns.

**Не доказывает / предел:** This is guidance for code review, not evidence of policy admissibility or competent closure of original obligations.

## R13-EXEC-SLSA

[SLSA v1.2 Build Provenance](https://slsa.dev/spec/v1.2/build-provenance)

**Поддерживает:** Build provenance binds an artifact to its build definition, external parameters, resolved dependencies, builder, invocation, and produced subject; consumers verify external parameters and dependency identity.

**Не доказывает / предел:** This is a software supply-chain specification. It informs source/input/run binding but does not prove a PolicyOS replay was semantically adequate, complete, or authorized.

## R13-EXEC-REPRO

[Reproducible Builds documentation](https://reproducible-builds.org/docs/)

**Поддерживает:** Reproduction requires a strategy for recreating the build environment and managing sources of variance such as timestamps, locale, paths, and input order.

**Не доказывает / предел:** PolicyOS replay outputs may be nondeterministic and are not software binaries. Preserve exact conditions and outputs; do not promise bitwise replay equality absent a measured deterministic procedure.

## R13-EXEC-AIRFLOW

[Dags: trigger rules](https://airflow.apache.org/docs/apache-airflow/stable/concepts/dags.html#trigger-rules)

**Поддерживает:** Airflow distinguishes waiting for all upstream tasks to succeed from waiting for them merely to finish; some early-fire rules do not wait for every upstream task.

**Не доказывает / предел:** This is an orchestration example, not a PolicyOS dependency engine. It supports the conceptual distinction between starting independent shards, joining their terminal outcomes, and accepting their results; no Airflow component is proposed.

## R13-ROOT-OPENLINEAGE

[OpenLineage custom facets](https://github.com/OpenLineage/OpenLineage/blob/main/website/docs/spec/facets/facets.md)

**Поддерживает:** Versioned custom facets extend a common event grammar; a same-name facet replaces the previous value.

**Не доказывает / предел:** Not an append-only authority ledger or independent evidence verifier.

## R13-ROOT-ICEBERG

[Apache Iceberg reliability](https://iceberg.apache.org/docs/1.9.2/reliability/)

**Поддерживает:** Immutable metadata and atomic pointer replacement support optimistic table commits with validation.

**Не доказывает / предел:** One table commit is not a cross-store transaction or a rights/currentness proof.

## R13-ROOT-JEPSEN

[Jepsen consistency models](https://jepsen.io/consistency/models)

**Поддерживает:** Consistency properties are scoped; single-object linearizability does not imply multi-object serializability.

**Не доказывает / предел:** A model description is not a measured guarantee for the selected PolicyOS backend.

## R13-ROOT-CEDAR

[Cedar policy validation](https://docs.cedarpolicy.com/policies/validation.html)

**Поддерживает:** Policy schema/type validation is distinct from evaluating a concrete authorization request.

**Не доказывает / предел:** No second policy engine is selected by this analogy.

## R13-ROOT-SLSA

[SLSA artifact verification](https://github.com/slsa-framework/slsa/blob/main/spec/verifying-artifacts.md)

**Поддерживает:** Provenance verification binds artifact subject, expected builder and build claims.

**Не доказывает / предел:** Build provenance does not establish scientific correctness, legal authority or complete input custody.

## R13-ROOT-MATERIALIZE

[Materialize query optimization](https://materialize.com/docs/transform-data/optimization/)

**Поддерживает:** Projection/filter placement and retained state affect computation and memory costs.

**Не доказывает / предел:** Apply only with preserved semantics and measured workload; no benchmark transfer or time-rounding permission.

## R13-ROOT-WP

[Withheld propositions: WP-01/02/03 and activation boundaries](../../../../../../policy-engine/docs/system-design-decisions/withheld-propositions-register.md) · `dc075e7dc0275fb8ea38a5a5bd8cd7a00968b895`

**Поддерживает:** WP-01 retains no posterior mutation pending its live producers and activation; WP-02 supplies no approved routine schedule.

**Не доказывает / предел:** This recommendation does not change or activate a withheld proposition. Reconcile later ratification at accepted-source rebind.
