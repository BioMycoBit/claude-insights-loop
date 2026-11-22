# Insights Triage

Turn one `/insights` report into a plan, after looking every ask up in the ledger first.

**Change these two lines to fit your repo; nothing else here names a location.**

- Ledger: `ledger/insights-ledger.md`
- Plans: `plans/insights-<YYYY-MM-DD>.md` (or your issue tracker, sprint docs, a TODO file)

**The unit is the ask, not the report.** The report reads your session history and has no view of
your repository, so every pass re-raises asks you already shipped and asks you already refused.
Grading the report as a document answers the wrong question. The ledger answers the right one
("have we decided this?") in one grep, and that lookup is why this command exists.

## Usage

```
/insights-triage <report.html>
```

The report must sit in a folder git ignores, because it quotes your session text. If Claude Code
runs in more than one repository on this machine, take only a report that
`scripts/scoped_insights.py` produced; a plain `/insights` reads every repo's sessions. Never plan
from a summary of a report or a memory of the last one.

## Step 1: Look the asks up BEFORE reading the report

Read only the report's headings: the asks are visible there. Pick two or three anchor words per
ask and run one lookup per ask:

```bash
rg -N '^\| `insight:' ledger/insights-ledger.md | rg -iw -- 'worktree|isolation'; echo "rc=$?"
```

**Judge it by the exit code, never by empty output.** A broken grep (a bad flag, a typo'd option)
prints nothing and exits 2, which looks exactly like a clean miss.

| rc | Means | Do |
|---|---|---|
| `1` | no row matches | A new ask. Carry it to Step 3. |
| `0` | a row matches | Already decided. Read the row. |
| `2` | the grep is broken | Not a verdict. Fix the pattern and re-run. |

`-w` keeps a short anchor from matching inside a longer word: unanchored, `ice` matches inside
`practices`, and a spurious hit turns a new ask's `rc=1` into `rc=0`. Keep `; echo "rc=$?"` on the
last command of the pipe; a `| head` after it reports the pager's exit code instead of the grep's.
When the anchors feel uncertain, read the whole table rather than trusting a miss.

**On a hit, the question changes** from "should we do this?" to "has the fact in the Revisit cell
come true?" A LANDED row is something you have; cite it and move on. **A re-raise is not
evidence.** Append this pass to the row's Pass cell. Only a fired Revisit condition reopens a row.

## Step 2: Sweep the closed doors

Independent of this report, walk every DEFER and NO-GO row and ask whether its condition fired:

```bash
rg -N '^\| `insight:' ledger/insights-ledger.md | awk -F'|' '{v=$5; gsub(/^[ \t]+|[ \t]+$/,"",v); if (v=="DEFER" || v=="NO-GO") print $2 " =>" $6}'
```

A condition that names a fact a command can check gets the command run, not reasoned about. One
that names an event ("a trip traced to a session without the rules loaded") gets "not observed
this pass" unless someone saw it. A fired condition is a candidate for this pass, carried into
Step 3 as an ask like any other; it does not rewrite the row by itself.

## Step 3: One row per distinct ask

Now read the report end to end. Count the distinct asks that survived Step 1.

- **Merge restatements of the same ask into one row**, and say in the plan which row absorbed
  what. An unrecorded merge reads as a dropped ask to the next person who checks the count.
- **Do not extract what carries no ask**: session statistics, corpus summaries, narrative. List
  them as "not extracted" so the count can be checked.

## Step 4: A verdict, with a cite

| Verdict | Means |
|---|---|
| LANDED | Built and running. Cite the commit and the file. |
| OPEN | Real, not built, nothing blocks it. Say where it is planned. |
| DEFER | Not now. Name the condition that would make it now. |
| NO-GO | Decided against. Name the fact that would reverse it. |

1. **Every LANDED cites a commit you looked up**, with `git log` or a search, never from memory.
   An uncited LANDED is OPEN.
2. **Every DEFER and NO-GO names a reversal fact about the world**, never a date.
3. **Refuse with a measurement, and show it.** A refusal that rests on preference reads a little
   weaker each time the report re-raises it, and eventually wins. One that carries a number holds.
4. **Prefer a door to a sentence.** When an ask amounts to "write the rule down somewhere else",
   the better answer is usually a mechanism that refuses the bad action where it happens. If a
   hook or a test already enforces the rule, a new paragraph would be a second owner of it. When a
   rule must change, rewrite the line that owns it instead of adding one beside it.

## Step 5: State the already-decided share

```markdown
**11 asks raised: 4 LANDED before this pass, 1 OPEN, 1 DEFER, 3 NO-GO, 2 new.**
**9 of 11 (82%) were already shipped or already refused.**
```

Expect most of each later pass to be already answered. A pass where most asks look new is a signal
to re-check the Step 1 anchors first: an anchor that is too specific misses its own row. The share
also drops when your work genuinely changed since the last pass.

## Step 6: Route each new ask

| Routing | Means | Goes to |
|---|---|---|
| plan | buildable, with a mechanism and a scope, planned this pass | the plan (Step 7) |
| backlog | buildable, not now | your own backlog, with the trigger that would make it now |
| ledger only | a verdict worth recording and nothing more: every LANDED, every reasoned refusal | the ledger row (Step 8) |

## Step 7: Write the plan, sized by work

Write to the plans location named at the top, never inside the reports folder: plans stay
versioned while reports stay out of git. One section per planned ask:

- the ask, in the report's words, and its ledger key
- what to build, and the mechanism that enforces it
- how it is proven (a check that has been made to fail at least once, not one that only passed)
- its size in work: a session, a day, a week

**Size by work, never by how many asks there are.** Give each new ask its own planned session.
Two surviving asks can differ by an order of magnitude: one a short declaration in an existing
check, the other a template change plus a new detector plus tests. A "three asks or fewer is one
session" rule is how the small one ships and the large one gets squeezed.

## Step 8: Write the ledger rows

One row per ask, forever. Six columns: Key · Ask · Pass · Verdict · Revisit · Source.

```markdown
| `insight:pass-N:<slug>` | <the report's request, not your verdict> | pass-N (YYYY-MM-DD) | OPEN | <what shipped, or what would reverse it> | <commit> |
```

- N is the pass that resolved the ask; a later pass appends to Pass and never opens a second row.
- Write the row for a planned ask now, as OPEN, and flip it to LANDED with its commit when the
  work ships. A ledger you only touch at triage time goes stale: rows stay OPEN after they ship.

Then run `python3 scripts/check_ledger.py` and fix every row it names before committing.

## When something goes wrong

| Situation | Do |
|---|---|
| Every ask hits an existing row | Report the rows and stop. Nothing to plan is the intended steady state. |
| An ask is re-raised and its condition has not fired | Append the pass to the Pass cell. Do not re-verdict. |
| A LANDED row has no commit you can find | It is OPEN. Downgrade it. |
| A refusal has no measurement behind it | Measure it, or make it a DEFER with a real condition. |
