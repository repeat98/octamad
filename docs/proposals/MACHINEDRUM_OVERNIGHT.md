# Overnight goal: work the Machinedrum packets until morning

Give the text below to the agent as its task.

---

**Goal.** Work through the Machinedrum work packets in
`docs/proposals/MACHINEDRUM_WORKPACKETS.md`, one at a time, until **07:00
local time**. The morning report
`docs/proposals/machinedrum_reports/NIGHT-2026-09-24.md` is due at 07:00.
Each packet ends with its acceptance check run and its output recorded, then
committed and pushed. Stop earlier only when no packet you are allowed to do
is left.

**Before you start.** Read, in this order:
1. `CLAUDE.md` (all of it: the traps are real);
2. `docs/proposals/MACHINEDRUM_WORKPACKETS.md` (the rules in section 0,
   the tools in section 1, and the status table);
3. section 1 (decisions) and section 12 (findings) of
   `docs/proposals/MACHINEDRUM_MACHINE.md`.

**Where to work.**
- In the main checkout, `/Users/jannikassfalg/coding/octamad`, on the
  branch `machinedrum`. The builds (`out/md_reference`,
  `out/md_reference_interp`) and the twelve captures
  (`out/md_profile/cap4`, `cap5`) are already there.
- Do not create worktrees; nothing goes under `.claude/`. Do not rebuild
  the shared `vendor/` toolchain. Never `git stash`.
- This overrides `CLAUDE.md`'s "ALWAYS WORK IN A GIT WORKTREE" for the
  Machinedrum work. It is the user's decision (23 Sep 2026): the work must
  be visible in the checkout, not hidden in the gitignored `.claude/`.

**Git: always commit and push to octamad.**
- `origin` is `github.com/repeat98/octamad`. Push there:
  `git push origin machinedrum`.
- **The one prohibition: never push to `upstream`** (`sambanks/octabam`).
- Push after every claim commit and after every finished packet. If a push
  fails, do not work around it with another remote. Record the failure in
  the night report and keep committing locally.
- Before every push, check that no Elektron byte is in the commit: no
  firmware, snapshot, `.bin`, `.syx`, sample or extracted blob. Run
  `git diff --numstat origin/machinedrum..HEAD` and look for `-`
  (binary) entries. Anything under `out/` stays uncommitted.

**The loop, once per packet.**
1. Pick the first packet in the **night order** below whose status is
   `todo` and whose dependencies are `done` (or, where the order says so,
   `review`).
2. Claim it: set its row to `claimed` with the branch and date, then
   commit and push.
3. Do the packet exactly as written. Do not widen its scope.
4. Run its acceptance check. Paste the command and its output into
   `docs/proposals/machinedrum_reports/<packet>.md`, from `TEMPLATE.md`.
5. Put new measurements into `MACHINEDRUM_MACHINE.md` section 12, marked
   ✅, 🟡 or *inferred*, with retractions marked ❌ and propagated.
6. Set the row to `done`, `review` (it needs the user's sign-off) or
   `blocked` (with the reason). Commit everything for the packet in one
   commit, then push.
7. Go back to step 1.

**Night order.** Skip any packet that is blocked.
1. **Finish WP-A1**. Follow items 1–2 under "Open and handover" in
   `machinedrum_reports/WP-A1.md`: write `docs/firmware/CORE0_MEMORY.md`
   from `WP-A1-ledger-all.txt`, `WP-A1-ledger-noreverb.txt` and the report's
   tables, classifying every word of X `0–0x8fff`, Y `0–0xbfff` and the shared
   window with evidence per range; add a section 12 entry to
   `MACHINEDRUM_MACHINE.md`; mark `DSP.md` §7's "X 0x1d9f–0x483f delay
   region for PLATE/DARK" as ❌ and point it to `CORE0_MEMORY.md`; run one
   heavier project (all eight tracks playing, a slice machine, and a recorder
   armed) with `tools/harness/md_reference/core0_wordmap.sh` and
   `core0_ledger.py` to test whether X `0x2840–0x3fff` stays untouched (each
   run takes about 40 s); then set WP-A1 to `done`.
2. **WP-D1**. Continue from item 4 of the WP-A1 report: disassemble
   `0x40060b58` and `0x400501d8` with the command in that report and check
   whether either tests for a held track key.
3. **WP-A2**. Propose the layout in `modules/machinedrum/layout.py`, with
   an overlap check. Include the new FX1-slot option from item 3 of the
   WP-A1 report. Set it to `review`; do not wait for sign-off.
4. Then **WP-R3**, **WP-R5**, **WP-R2** (measure only), and **WP-R1**
   (measurement and design options only).
5. Then **WP-A3**, **WP-A4**, **WP-A6**, **WP-B1**, and **WP-B2**, all on the
   proposed layout. Label every result "pending the user's sign-off". If the
   user later changes the layout, these are redone. `make check` must stay
   green for the other remixes.

Do not start WP-A5 (decision D1), WP-B3 or later packets, WP-D2 or later,
or anything that needs hardware.

**Hard limits.**
- **No flashing and no hardware.** Nothing is sent to the unit. An image
  may be built but is never called flashable.
- **Decisions stay with the user.** When a packet reaches a choice (D1–D4,
  a layout trade-off, a new one), write the options with their measured
  costs into the report, set the packet to `review` or `blocked`, and move
  on.
- **Long jobs run in the background, with progress lines.** Estimate
  first. Never sit in a silent wait loop. When you kill a job, kill its
  children (`pkill -P <pid>`).
- **Two failed attempts is enough.** When an acceptance check fails for a
  reason the packet does not cover, and two honest attempts have not fixed
  it, stop: record the evidence, set the packet to `blocked`, and move on.
- **Don't break what works.** Run the twelve-kit gate after any change to
  the driver, the relocator or the layout. A regression is reverted before
  the commit, not reported afterwards.
- **Don't touch anything outside the Machinedrum.** That means other
  modules, other remixes, the build, and other sessions' files. If a change to the build seems needed, write it up as a
  proposal and do not make it.

**In the morning.** Write
`docs/proposals/machinedrum_reports/NIGHT-<date>.md`, then commit and push
it. It contains:
- the packets finished, with their commits;
- the packets in `review` or `blocked`, and exactly what each needs from
  the user;
- every result that rests on the proposed layout;
- anything surprising, and anything retracted;
- what to hand out next.

Keep it short enough to read in five minutes.
