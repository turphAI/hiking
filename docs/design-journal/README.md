# Design journal

Append-only, numbered entries that record the **why** behind a hiking surface as
it is ideated, scoped, and built. Adopted from turph's `docs/design-journal/`
(itself from turphViz), where the practice became the canonical record of intent
and the suite's Navigator agent reads it as planning corpus.

## When to open an entry

A new **initiative** or a **major rework of an existing surface** opens an entry
*before* code. The first entry is the ideation/scoping pass — the brainstorm, the
framing, the open questions — not a finished plan. Later entries record decisions
as they're made.

Per-*initiative* trigger, not per-repo. A dormant surface needs no entry until it
gets reworked. Going forward only; we don't backfill history.

## Convention

- One journal per app: this directory. Many entries, never a new dir per initiative.
- Files: `NNN-short-slug.md`, zero-padded, monotonic. Append-only — supersede a past
  decision in a *new* entry, don't rewrite the old one (the trail is the value).
- **Ideation, not execution.** An entry holds the *messy thinking*: the brainstorm,
  the forks, the framing, and the **decision + why**. **Scope, spec, and build detail
  are execution and live with the code** — `CLAUDE.md`, the code itself, `STATUS.md`,
  the PR — never in a journal entry. The test: if you're writing *how* to build it
  (schemas, data shapes, function layouts, step plans), that's execution → wrong
  place; if you're capturing *why / which fork / what-if*, that's ideation → right
  place. When an idea graduates, the entry records the **decision and why** and
  **points to where the work lives**; it does not grow into a spec.
- **Current-state-first, trail below.** The top of an entry always reads clean: a
  short "Where this stands" block (decided / open / owed), then the *current*
  thinking. History annotates the bottom — resolved forks, superseded reasoning,
  and dated trail sections record how the state came to be, but never sit above it.
- Each entry: a title, a date, a **Status** (`OPEN · ideating` → `SCOPED` →
  `BUILDING` → `LANDED`), and prose. Status is a lightweight pointer to where the
  idea sits in its life; the detail it implies lives in the repo, not the entry.
- Keep it honest about uncertainty. "Undecided, here are the forks" beats pretending
  a decision was made.
- **Two optional facets, maintained organically**: **Risk** (`accepted` /
  `mitigated` / `eliminated` when a tradeoff is at stake) and **Change** (one
  retrospective line at `LANDED`: what's true now that wasn't, and was it
  intended?). Capture a facet when it earns its place; skip honestly otherwise.

## Index

- [001 — Two peak lists, a preferred order, and a log — not a live hike tool](001-hiking-pwa-ideation.md) · BUILDING
