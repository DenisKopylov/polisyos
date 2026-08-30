# INT-R5 Survey Source Manifest And Admitted Claim Anchors

## 1. Purpose and custody boundary

This manifest identifies the exact five commissioned survey artifacts consumed by INT-R5 and admits
branch-local evidence extracts for every load-bearing transferred claim. It closes the prior ambiguity
about which surveys were used and where each synthesis came from.

The complete original survey bytes were supplied as external conversation artifacts, not created in
the repository. This amendment records their exact byte identity, line denominator and source
version, and commits the passages needed to replay the INT-R5 transfer. A reader of this branch can
replay the package's transferred claims against the admitted extracts below. Verification of the
entire original survey byte streams still requires the external artifact matching the listed SHA-256;
that residual is explicit and is not replaced by a bibliography.

This is custody/evidence metadata. It is not legal advice, repository capability, registered
vocabulary or authority to implement.

## 2. Exact survey identities

Stable package-local reference shape:

```text
urn:polisyos:int-r5:survey:<survey-id>:sha256:<digest>
```

| ID | Exact title | External artifact identity | Lines | Bytes | SHA-256 | Stable package ref |
|---|---|---|---:|---:|---|---|
| `S1` | *Глубокое исследование: как полномочие делегируется, ограничивается, наследуется и отзывается* | `file_000000001e10820aa329804b1bf1dfe1`, version `1` | 617 | 86,930 | `4d6c9e49db74d08c7f2d56590ec9480e3702a908b58cc38139e75b0a2a4b40be` | `urn:polisyos:int-r5:survey:S1:sha256:4d6c9e49db74d08c7f2d56590ec9480e3702a908b58cc38139e75b0a2a4b40be` |
| `S2` | *Когда решение принадлежит коллегиальному органу — и когда оно юридически не существует* | `file_000000007d548243b06f8f47c1ca8a21`, version `1` | 375 | 90,722 | `5c046877c6bbbb1fccd0c30709136ffd55c451b71ac34984ed2d24a937a2606a` | `urn:polisyos:int-r5:survey:S2:sha256:5c046877c6bbbb1fccd0c30709136ffd55c451b71ac34984ed2d24a937a2606a` |
| `S3` | *Рекузал, конфликт интересов и запрет самосогласования: как не дать участнику замкнуть контур контроля на себе* | `file_00000000eb3482469ae708351aa9e291`, version `1` | 424 | 88,604 | `9436cfdfa6f67bd7a79ffe5826ce7862f78ea1bd51856f1e3fad2b009ff82de7` | `urn:polisyos:int-r5:survey:S3:sha256:9436cfdfa6f67bd7a79ffe5826ce7862f78ea1bd51856f1e3fad2b009ff82de7` |
| `S4` | *Предварительная авторизация как проверяемое доказательство: цепочки полномочий, свежесть и отзыв в ходе действия* | `file_000000005e8c81f4b4dd2913ffc49aa9`, version `1` | 829 | 88,763 | `160cfd65d14e79a6cd05b22976ea0a83f0a9cd7ba1a132ce18d5c8a002265845` | `urn:polisyos:int-r5:survey:S4:sha256:160cfd65d14e79a6cd05b22976ea0a83f0a9cd7ba1a132ce18d5c8a002265845` |
| `S5` | *Принятие полномочий другого органа: когда доверие защищаемо и где проходит граница между консультацией, рекомендацией, одобрением и решением* | `file_000000003ce8820aa2796bf8f4f71f68`, version `1` | 485 | 78,489 | `c5ea9693fb63fcd827e09367f92fc655dfa323ee497268b0643813d18605f92b` | `urn:polisyos:int-r5:survey:S5:sha256:c5ea9693fb63fcd827e09367f92fc655dfa323ee497268b0643813d18605f92b` |

Inspection date for all five: `2026-08-29`.

Source classes represented inside the surveys include named statutes/regulations, cases, official
administrative guidance, institutional policies, audits, technical standards, empirical studies and
explicit engineering inferences. Each package claim retains the survey's jurisdiction and source
class; the survey itself is secondary commissioned research unless it reproduces a primary source.

## 3. Claim-to-survey anchor ledger

| Package claim | Survey anchor(s) | Source class / jurisdiction | Transfer admitted | Limitation |
|---|---|---|---|---|
| `CL-E01` — role/delegation edge alone is insufficient | `S1:5-9`, `S1:19-43` | comparative UK/Australia/US public law and public financial schemes | source power, function, time, amount, place, office, subdelegation, reserved matters and triggers are distinct coordinates | no universal field set or consequence |
| `CL-E02` — child scope cannot amplify parent | `S1:162-192` | Australian §34AB, UK local-government and US subdelegation comparison; engineering formalization | monotonic attenuation is a conservative reducer invariant | not a free-standing universal legal doctrine |
| `CL-E03` — creation-time subdelegation power matters | `S1:164-192` | Australian and US named rules | validate parent power when child link was created | source-law exceptions remain profile-specific |
| `CL-E04` — acting, succession, implied authorization and emergency are distinct paths | `S1:194-272` | UK Carltona, Australian §33A, US FVRA, UK CCA, HIPAA controls | preserve separate provenance edges and triggers | technical break-glass is not itself public-law emergency power |
| `CL-E05` — amount requires valuation and aggregation | `S1:102-130` | Australian public/university financial-delegation schemes | use economic transaction, currency, valuation and anti-splitting rule | institution-specific valuation rules vary |
| `CL-E06` — legal organ/forum differs from physical membership | `S2:5-13`, `S2:28-54`, `S2:97-103` | Delaware, German, UK and public-meeting regimes | forum/organ identity is a separate predicate | defect consequence is jurisdiction-specific |
| `CL-E07` — quorum is item/profile relative and event-sourced | `S2:50-90`, `S2:120-155` | UK Model Articles, Monecor, German AktG, US House | store event timeline and apply profile temporal scope | no universal definition of presence or persistence |
| `CL-E08` — self-approval is structural | `S3:3-49`, `S3:136-178` | NIST/Oracle SoD, audit independence, judicial analogy and audit findings | controlling-subject role incompatibility is not cured by disclosure | additional role pairs remain profile/risk specific |
| `CL-E09` — undisclosed/off-system conflict absence is not provable | `S3:51-80` | conflict-register, disclosure and apparent-bias comparison | positive claim is bounded to named records and current declarations | evaluative conflicts need competent adjudication |
| `CL-E10` — cross-agency acceptance is purpose-limited | `S5:3-68`, `S5:70-123` | HCCH, EU, UK and NIST regimes | store accepted assertion, legal basis, scope, residual duties and negative perimeter | recognition regimes transfer different assertions |
| `CL-E11` — act type follows legal effect, not label | `S5:125-170`, `S5:172-236` | UK consultation, EU Article 288/Banco Popular, US APA/Bennett | separate formal type, binding effect, condition precedent and operative maker | practical pressure and formal bindingness remain separate axes |
| `CL-E12` — later cure may be permitted, forbidden, saved or unresolved | `S1:328-409` | US FAR, FEC v NRA, FVRA, Doolin and Australian saving rule | cure is profile-specific and a new current result | original pre-action evidence remains immutable |
| `CL-E13` — relation back must be representable but is not automatic | `S1:328-381` | US FAR/FEC ratification comparison | new cure result can carry relation-back effect and temporal limits | relation back can fail because deadline/right intervened |
| `CL-F02` — `t0` evidence cannot determine all `t1` histories | `S4:5-29` | formal/technical TOCTOU synthesis | adopt non-inferability and explicit snapshot/lease/revalidation modes | the survey's illustrative `!=` is not adopted as universal inequality |
| freshness/proof design | `S4:82-173`, `S4:189-375`, `S4:377-550` | SPKI, PKIX, XACML, RBAC/ABAC, OPA/Cedar/Zanzibar, revocation systems | proof chain, exact action commitment, freshness horizon and dependency-aware checkpoints | language expressibility does not establish operand provenance |

## 4. Admitted evidence extracts

The extracts below are the branch-local evidence used to replay the transfer. They are deliberately
bounded: surrounding survey prose does not inherit authority merely by proximity.

### 4.1 `S1` — delegation, scope and cure

`S1:5-9` establishes the core result: `person → role → delegation` is insufficient. The right to make
one decision depends at least on source authority, decision type, facts, time, amount and valuation,
geography, office status, subdelegation chain, reserved matters, live instruments and sometimes
vacancy/emergency state. It also states that absence of authority has no single consequence: surveyed
regimes include no-force/non-ratifiable, nonbinding-but-ratifiable, defect-but-saved and invalidating
outcomes.

`S1:102-130` rejects checking one invoice against a role limit. The surveyed schemes count total
transaction/lifecycle commitment and related variations or instalments and prohibit splitting. The
engineering normalization therefore requires limit, currency, valuation basis, aggregation window,
related-transaction rule, tax treatment and budget scope.

`S1:162-192` supports attenuation: a child is bounded by parent power, source-law delegability,
instrument scope, subdelegation permission, child eligibility, time, amount and place. It separately
requires the parent to have had power to create the child edge at creation time.

`S1:328-381` rejects both universal extremes about cure. FAR permits conditioned ratification; FEC v
NRA shows relation back can fail when the ratifier could not act within the original time window;
FVRA expressly makes a defined class non-ratifiable; Doolin and Australian §33A illustrate other cure
or saving mechanisms. The package therefore represents `prospective`, `relation_back`, `saved_act`,
`limited` and `unresolved` while leaving the original certificate unchanged.

### 4.2 `S2` — body, forum, quorum and co-signature

`S2:5-13` distinguishes a signed/minuted document from an act of the legally competent body. The
validation model requires organ, permitted forum/process, composition, quorum, vote and any
constitutive form; legal consequences still differ by regime.

`S2:50-90` makes the two adversarial cases explicit. Correct people in a committee do not become the
full board for a reserved matter. Opening quorum is not a permanent Boolean: UK Model Articles,
Monecor and US House procedure attach different temporal consequences to a later departure.

`S2:120-155` separates `at_vote`, `throughout_meeting` and procedural presumption, and distinguishes
presence, abstention and affirmative vote. It also shows that remote participation tests differ by
regime. The target model therefore stores an event timeline plus a versioned rule profile.

### 4.3 `S3` — structural SoD and detectability

`S3:3-49` separates structural role incompatibility from manageable conflict of interest. One
controlling subject closing both proposal and approval is a toxic combination; disclosure does not
neutralize it. Identity comparison must resolve aliases and impersonation, and the subject of a
conflict cannot be the sole producer of their exception.

`S3:51-80` partitions conflict knowledge into record-established, record-indicated, self-known or
off-system, and evaluative appearance classes. The survey explicitly rejects “no conflict exists” as
an automated conclusion. The strongest defensible statement is that no prohibited overlap or
registered conflict was found in named records and current declarations were received; undisclosed
facts are not disproved.

### 4.4 `S4` — proof, non-inferability and freshness

`S4:5-29` states that a pre-action certificate proves authorization only relative to the state used at
check time and cannot contain a future revocation event. The survey then presents snapshot,
issuer-authorized lease and revalidation as distinct semantics. INT-R5 retains the prose information
limit but corrects the illustrative `authority at check != authority at use`: equal histories are
allowed, while two histories identical through `t0` can diverge later.

`S4:82-173` distinguishes a signed decision receipt from an authority proof that lets an independent
verifier recompute the result. Required evidence includes exact action commitment, chain, scope,
validity, trusted time, freshness evidence/horizon, policy identity, external-state provenance,
quorum branches, algorithm/profile identity and mid-operation semantics.

`S4:189-375` supports root-to-actor reduction, scope/validity intersection, path-level invalidation,
threshold branches and the proposition that a policy language can express a predicate without
proving provenance or freshness of its operands.

### 4.5 `S5` — recognition and act effect

`S5:3-68` defines defensible cross-agency acceptance as reliance on a particular assertion, from a
particular source, for a particular purpose/scope under a legal gateway, with current status,
authenticity/assurance, refusal grounds, retained duties and attributable responsibility. It rejects
`trusted_authority=true` and requires provenance, recognition, approval and final decision to remain
separate.

`S5:70-123` adds the negative perimeter: authentication of origin does not establish truth, identity
does not establish authorization, and recognition does not transfer every local duty or competence.

`S5:125-170` classifies consultation, recommendation, approval and binding decision by legal effect,
freedom to depart, condition precedent, operative act and responsibility rather than title. It also
preserves the distinction between formal bindingness and practical departure cost.

## 5. Replay procedure

A branch-only transfer audit should:

1. resolve a package claim ID in §3;
2. inspect its admitted source identity and line range;
3. read the corresponding extract in §4;
4. verify that `external-evidence-ledger.md` preserves source class, jurisdiction and limitation;
5. verify that the specification does not strengthen the claim beyond the extract;
6. for full-survey custody, obtain the external artifact and verify bytes against the SHA-256 in §2.

Step 6 is the explicit residual. Steps 1-5 are fully replayable from the branch. No claim may describe
the full external bytes as committed or independently retrievable from this repository.

## 6. Non-effect

This manifest does not make an external survey authoritative, ratify its primary citations, appoint a
legal-profile owner, or make the full capability anything other than:

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```
