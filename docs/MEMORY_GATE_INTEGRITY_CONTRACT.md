# Memory Gate Integrity Contract v0.1

Status: conservative read-path contract; no Notion schema migration.
Scope: Memory Graph only. No new service, database, or third graph.

## 1. Distinct states and absence

- ACTIVE: explicitly accepted edge whose endpoints, type, direction, and provenance satisfy this contract.
- UNRESOLVED: candidate edge whose identity or meaning is unsettled. It has no ordinary retrieval effect.
- REJECTED: reviewed candidate that was rejected.
- SUPERSEDED: edge replaced or no longer current; retained in history but not applied.
- Not recorded: no edge record exists. This is missing data, not evidence that no relationship exists.
- Missing or unknown status is not ACTIVE.

## 2. Stable identity

Memory Graph node identity is the Notion page UUID. Relation endpoint text must use mem:<Notion page UUID>.

The resolver accepts only this namespace and a valid UUID; it resolves only against Memory Archive records; and it requires exactly one page per endpoint. Titles, text similarity, display labels, and the auto-increment Memory ID are never identity. Same title with different UUIDs means different nodes. Title changes do not change identity. Duplicate page IDs are ambiguous and block activation.

The existing From Memory and To Memory properties are text fields. They can carry explicit IDs without a schema change. Legacy title-valued rows are not rewritten or guessed into IDs.

## 3. Activation and provenance

An edge affects ordinary retrieval only when both endpoints are explicit mem: UUIDs and each resolves uniquely to a Memory Archive page; the relation type is supported; status is exactly ACTIVE; the relation row has a valid Notion UUID; Evidence is non-empty; and direction/type invariants hold.

Missing or invalid endpoints, ambiguous IDs, missing evidence, missing relation identity, or invalid status block activation. A warning is attached where an endpoint record can be identified. Evidence metadata is provenance, not proof that the claim is true.

## 4. Memory Graph relation semantics

| Relation | Direction | Effect |
|---|---|---|
| SUPPORTS | evidence to claim | labels support on the claim; does not promote its evidence status |
| REFUTES | counter-evidence to claim | labels both sides; does not delete either record |
| CONTRADICTS | symmetric between claims | labels both sides only when ACTIVE; never selects a winner |
| SUPERSEDES | newer record to older record | eligible target omitted from ordinary active retrieval, retained for historical retrieval |
| DERIVED_FROM | derived record to source record | provenance relation; must be acyclic; suppresses neither record |

For CONTRADICTS, ACTIVE is a curator assertion that the claims share the relevant scope and are incompatible. The current schema has no structured scope or validity fields. Runtime does not infer contradiction from text, similarity, dates, or negation. Candidates remain UNRESOLVED until that review occurs.

PART_OF, DEPENDS_ON, USES, and component-level TESTS are not interpreted as Memory Graph relations in v0.1; they belong in the separate Architecture Graph.

The legacy schema also contains `CONFIRMS`, `KILLS`, `CITES`, `OPENS`, `RELATED_TO`, `SAME_ENTITY`, and `POSSIBLE_MATCH`. These types are not classified by v0.1 and are ignored by the Memory resolver; omission does not assign them to Architecture Graph. All unsupported relation rows remain unchanged in Notion.

## 5. Cycle invariant

SUPERSEDES and DERIVED_FROM are separate directed acyclic relations. Other relation types are not globally forced to be acyclic.

The resolver detects strongly connected components, including self-loops. Cycle participants remain visible with explicit warnings. SUPERSEDES edges touching a cycle participant cannot suppress a target. An unrelated acyclic SUPERSEDES edge continues to work. The guard also prevents cycle participants already marked SUPERSEDED from disappearing from ordinary retrieval solely because of that status.

This is a read-path guard, not a write API. Any future relation writer must validate the same DAG invariant before accepting an edge.

## 6. Retrieval and time

- UNRESOLVED edges are omitted from ordinary retrieval entirely. A dedicated investigative view is not implemented in v0.1.
- ACTIVE CONTRADICTS labels both claims; neither is chosen or hidden.
- An absent edge is not a negative relationship.
- Unsupported or unclassified legacy relation types have no Memory Graph retrieval effect and are not rewritten or reclassified by omission.
- A newer recorded_at or updated_at does not imply truth or supersession.
- Storage, repeated retrieval, similarity, or graph adjacency does not increase truth status.
- recorded_at, observed_at, valid_from, and valid_until are distinct. Current Notion Created At and Updated At values are not validity intervals.

## 7. Graph separation

Memory Graph and Architecture Graph have separate node identities and relation semantics. The Memory resolver accepts only mem: IDs from Memory Archive. arch: IDs and cross-graph edges are rejected in this version. Combined queries may present information from both graphs only while preserving graph and provenance labels.

No existing Notion relation rows are migrated, renamed, deleted, or reclassified by this contract. The current legacy relations remain untouched until their membership and stable endpoint identities are independently established.

## 8. Acceptance tests

- title-only endpoints do not resolve or suppress;
- valid mem: UUID endpoints resolve exactly one page each;
- same title with different UUIDs remains two distinct nodes;
- missing or duplicate page identity blocks activation;
- UNRESOLVED CONTRADICTS does not become a confirmed conflict;
- ACTIVE CONTRADICTS labels both claims without choosing one;
- missing evidence blocks an ACTIVE edge;
- SUPERSEDES cycles keep all participants visible, including nodes marked SUPERSEDED;
- DERIVED_FROM cycles are detected without removing records;
- a cycle does not disable an unrelated acyclic supersession;
- arch: endpoints do not resolve in Memory Graph;
- absence of an edge does not create a negative relation.