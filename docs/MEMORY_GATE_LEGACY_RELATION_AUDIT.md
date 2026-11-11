# Memory Gate — legacy relation audit (2026-11-10)

## Scope and method

Read-only snapshot of the Notion data sources `Memory Relations` and `Memory Archive`, followed by direct fetches of the one relation candidate and both matching archive pages. No Notion rows were changed.

The relation data source contained 9 rows at the time of inspection. All 9 had `Status=ACTIVE` and non-empty `Evidence`. Their type counts were:

| Relation type | Rows |
|---|---:|
| SUPPORTS | 2 |
| USES | 5 |
| PART_OF | 1 |
| TESTS | 1 |
| **Total** | **9** |

The Memory Archive contained 4 pages.

Endpoint-title reconciliation across the 18 stored endpoint values found **3 exact matches**, **15 unmatched labels**, and **0 ambiguous matches**. Two matches are the source and target of the SUPPORTS candidate above; the third is the source endpoint of the PART_OF row. This comparison is an audit measurement only; runtime resolution does not use titles.

## Candidate Memory Graph edge — not migrated

One `SUPPORTS` row has endpoint labels that exactly identify two distinct Memory Archive pages. The stable Notion page IDs were confirmed by fetching the relation and both archive pages:

- Relation row: `3f30fddd-05e9-8117-b500-f0814fd20856`
- Source page (`RESULT`, `VERIFIED`): `3f30fddd-05e9-812b-b6e3-caf8ad073dd7`
- Target page (`USER_DECISION`, `SUPPORTED`): `3f30fddd-05e9-811e-9046-c2d6a5df3325`

Existing relation note: "Supports the protocol's statement that the Z3 bridge is VERIFIED for the explicitly tested scope."

This is an identity-resolvable candidate, not an automatically approved active edge. The target is a page representing the entire canonical protocol, while the evidence appears to support a narrower statement within it. The relation therefore still needs scope review before its text endpoints are changed to `mem:<UUID>`. No migration was performed.

## Remaining 8 rows — outside current Memory resolver scope

- 5 `USES`, 1 `PART_OF`, and 1 `TESTS` row describe component/plugin/workflow relationships. They are candidates for the separate Architecture Graph, but this audit does not independently certify each endpoint's architectural identity.
- The second `SUPPORTS` row points from the collection-level label "Memory Archive" to "WORKFLOW CORE". The source label is not a specific Memory Archive page, and the target is not one of the four Memory Archive pages. It is therefore not a valid page-to-page Memory Graph edge under v0.1.

These eight rows remain untouched. Their `ACTIVE` property in the legacy database is not sufficient evidence that they are valid Memory Graph edges.

## Result

- Confirmed relation rows inspected: 9.
- Memory Archive pages inspected: 4.
- Candidate Memory Graph edges with both endpoint pages uniquely identified: 1.
- Candidate semantically approved and migrated: 0.
- Other rows migrated, deleted, or reclassified: 0.

The resolver's fail-closed behavior is appropriate: old display-name endpoints do not resolve as graph identity. Do not bulk-convert titles to IDs. Review each remaining row's domain, endpoint identity, direction, and scope separately.
