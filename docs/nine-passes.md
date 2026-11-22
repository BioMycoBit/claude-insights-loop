# Nine Passes of `/insights`: What Happens After the First Run

Every write-up of Claude Code's `/insights` report I could find covers one run. The author runs
it, pastes a few of the suggested lines into CLAUDE.md, and closes with "re-run it monthly and see
if the friction drops." None of them shows the second run.

I ran it nine times on one repository between August 12 and November 20, 2026, and turned each
report into a small sprint of work. The corpus grew from 178 sessions on the first pass to 782 at
its widest. After the first pass, most of the work turned out to be deciding which suggestions we
had already answered.

## The setup

I run the report headless, `claude -p "/insights"`, through a small wrapper that scopes it to one
repository's sessions (more on why near the end). Each pass becomes a sprint. Claude breaks the
report into asks, grades each one against the code as it stands that day, and plans sessions only
for the asks that survive. Every session stops at an approval gate where I read the plan before any
code changes.

| Pass | Date | Sessions analyzed | Asks | Already shipped or refused |
|---|---|---|---|---|
| 1 | Aug 12 | 178 | — | no ledger yet |
| 2 | Aug 14 | 359 | — | 5 shipped while the report was being generated |
| 3 | Aug 18 | 699 | 14 | 6 (43%) |
| 4 | Aug 20 | 722 | 15 | 10 (67%) |
| 5 | Aug 22 | 782 | 13 | 9 (69%) |
| 6 | Aug 29 | 746 | 13 | 8 (62%) |
| 7 | Sep 12 | 565 | 16 | 10 (63%) |
| 8 | Nov 3 | 142 | 9 | about 1 |
| 9 | Nov 20 | 381 | 11 | 5 (45%) |

## Pass 1: the advice was right and the premise was wrong

The first report's headline was "mechanize your rules with hooks." Before planning anything, we
checked the hooks we already had, and two of them were dead. They read `.command` and `.file_path`
from the top level of the hook's JSON input, while Claude Code sends `.tool_input.command` and
`.tool_input.file_path`. Both read an empty string and exited 0, which looks exactly like "nothing
dangerous found." They had been dead for five months. The commit that killed them was titled as a
fix to hook input: it fixed how the input arrived and turned a loud per-call error into a silent
success.

The report also asked for rules that already existed and were contradicted elsewhere in the repo.
One instruction file still prescribed `git add . && git commit`, the exact form that had swallowed
a parallel session's staged work. A third rule on top of two contradicting ones would have fixed
nothing. Reconciling the existing ones did.

So the first pass was an audit of the harness I already had. Every guard it shipped was proven by
firing it, with a real force-push and a real bare commit refused live in the session. Reading the
script didn't count.

## Pass 2: the report doesn't know what you shipped

Two days later, the second report's window overlapped the first sprint, and five of its
recommendations had shipped while it was being generated. That is the first thing to understand
about iterating on `/insights`: it reads your session history, and it has no view of your
repository. It will recommend what you finished last week.

Its real finding was bigger than anything on its list: a green check run didn't mean anything. It
counted 54 "buggy code" incidents, mostly Claude's own test harnesses failing before they validated
anything real. Our debugging notes already held 62 entries describing ways a check script had lied.
The report's quick win was "capture the rule as a skill." We had 62 written entries proving that
written entries don't hold, so we built a mutation-proof runner instead. A check's PASS doesn't
count until the defect has been put back and the check has gone red.

## Passes 3 and 4: the re-raise problem

On pass 3, 6 of 14 asks were already shipped. On pass 4, 7 of 15 were shipped and 3 more had been
refused with reasons, so 10 of 15 (67%) were already decided. Establishing that took a `git show`
four versions back, into an archived sprint folder that existed on one machine.

So pass 4 built a ledger: a markdown table in the repo with one row per ask, kept forever, however
many reports raise it.

| Column | Holds |
|---|---|
| Key | a stable id for the ask |
| Ask | the report's request in its own words, never our verdict |
| Pass | every run that raised it, oldest first |
| Verdict | LANDED, OPEN, DEFER or NO-GO |
| Revisit | for LANDED, what shipped; for DEFER and NO-GO, the fact that would reverse it |
| Source | the commit that recorded the decision |

A test refuses any verdict outside those four, and any DEFER or NO-GO row without a Revisit
condition. The ledger now holds 52 rows: 27 landed, 15 refused, 7 open and 3 deferred.

The triage command reads the ledger before it opens the report. It reads only the report's
headings, greps the ledger for two or three anchor words per ask, and checks the grep's exit code
rather than its output, because a broken grep prints nothing just like a clean miss does. A hit
changes the question from "should we do this?" to "has the fact in the Revisit cell come true?"

After that the share held steady: 69%, 62% and 63% already decided on passes 5, 6 and 7.

## Refuse with a number, or have the argument again next month

The report re-raises by construction, so a refusal that rests on preference reads a little weaker
every time it comes back. A refusal that carries a measurement holds.

The clearest case is "document the hook escape hatches in CLAUDE.md," raised on five passes. The
escape hatches were already in an auto-loaded rules file, and the guard tripped twice during that
very planning session with the note in context. A third copy was the intervention that had already
failed. Later passes added counts: 57 refusals in 7,674 Bash calls, each refusal naming its next
move and each recovered in one call. The row's Revisit condition is specific: a trip traced to a
session that did not have the rules file loaded. Nothing has met it yet.

Three other asks came up five or six times each: audit a plan's premises before implementing it,
mutation-prove every check, and stop rewriting files through a text-mode round trip that silently
strips CRLF line endings. Twenty of the ledger's 52 rows have been raised more than once.

## A re-raise is not evidence. A fired condition is.

What reopens a closed door is its Revisit condition coming true. The line-ending ask shows how. From
pass 3 on, a flip was detected at staging time but not prevented, and the row named its condition:
a flip that lands without the detector seeing it. On pass 9 that happened. An 11-line flip, under
the detector's 50-line floor, landed unseen, and three larger flips were warned about and landed
anyway, each needing a restore commit. The row reopened, and the commit tool now refuses any line
whose ending changed while its text did not.

Measurement reversed decisions in the other direction too. A worktree per parallel session had been
declined a month before the report first asked for it, priced at "five branches and five merges."
That turned out to be a different setup's cost. What reversed it was measured write pressure: daily
same-file commits on the two busiest shared files had gone from 2.6 and 1.7 to 7.1 and 5.9.

A path-blocking hook I had filed as "not this repo's problem" was loosened the same day we counted
its refusals: 1,326 in 30 days, in 529 of 795 sessions, about 85% of them false. Replayed against
those refusals, the old version blocked 1,324 and the new one 183.

## Prefer a door to a sentence

Every pass arrived at the same rule on its own. When an ask amounts to "write the rule down
somewhere else," the better answer is usually a mechanism that refuses the bad action where it
happens. The report's quick wins lean on CLAUDE.md paragraphs and new skills, and our NO-GO list is
mostly those: a safe-commit skill, a debt-filing skill, a kill-mutants skill, and CLAUDE.md blocks
for parallel-session safety, PowerShell quirks and shell gotchas. Each time, a hook or a test
already enforced the rule where it mattered, and the skill or paragraph would have been a second
owner of it. When a rule genuinely has to change, rewrite the line that owns it instead of
appending a competing one beside it.

The asks that did land were almost all doors:

- a hook that refuses a bare `git commit`, because parallel sessions share one git index
- a commit tool that stages through a private index and lands with a compare-and-swap, aborting and
  naming both commits if another session moved the branch first
- a premise check before implementation, later moved to the plan's author, so each plan now carries
  the commands that settle its own premises
- a mutation-proof runner for check scripts, then for tests
- a refusal for `cmd | head; echo $?`, which reports the exit status of `head` rather than of `cmd`
- a test runner that grades a run on what it executed, so a suite that skips itself can't read as
  a pass
- a refusal for secrets passed as command-line arguments

Two agents came out of the reports, each narrowly triggered. One re-checks a plan's central premise
independently, and runs only when the first check refutes it. The other attacks each plan before
work starts. On replayed plans the reviewer caught 7 of 10 known problems on plans its brief had
been written against, and 1 of 5 on plans it had never seen. Across all its findings, 61 of the 62
we re-checked against the code held up. A median run takes 9 minutes, about a fifth of a median
session. Every ask for a swarm of parallel agents was refused under a standing one-agent cap.

## The ledger goes stale too

By pass 7, 4 of the 7 OPEN rows had already shipped, and the ledger hadn't followed, because
nothing wrote a row back when its session shipped. The report forgets what you built, and a ledger
you only touch at triage time forgets too, just more slowly. On that pass the stale rows were the
most useful thing it found.

## When the share drops

Passes 8 and 9 broke the pattern, at about 1 of 9 and 5 of 11 already decided. The ledger was
working. Pass 8 came after a seven-week gap and covered only two weeks of sessions. On pass 9, six
of the eleven asks were about a kind of work, automated mutation-testing lanes, that had started
after the previous pass. The already-decided share measures how much your work changed since the
last pass more than it measures the report. If it drops while your work hasn't changed, check your
lookup anchors first: an anchor that is too specific misses its own row.

## Practical notes

- **Scope the report.** A plain `/insights` reads every session on the machine, across every
  repository. Our wrapper runs the official report over a copy of one repository's session folders,
  under its own config directory. In that copy, detailed analysis covered only the sessions the
  report re-read, and copied summaries stopped the re-reads: 99 of 323 sessions had one. The wrapper
  now clears the summary for up to 50 unanalyzed sessions per run.
- **Keep the reports out of version control.** They quote your session text.
- **Scrub before you share.** We share reports through a tool that converts them to markdown,
  refuses product and personal terms, and asks a fresh Claude with no context to guess the product
  and the author from the text alone. This article went through the same check.
- **Count asks, not reports.** Merge restatements of the same ask and record which row absorbed
  what. Skip the statistics and the narrative, and say that you skipped them, so the count can be
  checked.

## If you are starting your first pass

1. Treat pass 1 as an audit of what you already have. Fire every hook before you trust it.
2. Start the ledger before pass 2: one row per ask, with the commit that settled it.
3. Look the asks up before you read the report.
4. Refuse with a number and a named reversal condition.
5. Prefer a mechanism that refuses to a sentence that asks.
6. Expect most of each later pass to be already answered. Ours sat between 62% and 69% while the
   work was steady.

The premise audit shipped on pass 1. The report asked for it again on five of the next eight
passes.
