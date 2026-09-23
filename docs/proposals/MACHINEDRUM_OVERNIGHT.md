# Overnight goal: work the Machinedrum packets until morning

Give the text below to the agent as its task.

---

**Goal.** Work through the Machinedrum work packets in
`docs/proposals/MACHINEDRUM_WORKPACKETS.md`, one at a time, until 08:00
local time. Each packet ends with its acceptance check run and its output
recorded, then committed and pushed. Stop earlier only when no packet you
are allowed to do is left.

**Before you start.** Read, in this order:
1. `CLAUDE.md` (all of it: the traps are real);
2. `docs/proposals/MACHINEDRUM_WORKPACKETS.md` (the rules in section 0,
   the tools in section 1, and the status table);
3. section 1 (decisions) and section 12 (findings) of
   `docs/proposals/MACHINEDRUM_MACHINE.md`.

**Where to work.**
- In the existing worktree `.claude/worktrees/md-phase0`, on branch
  `machinedrum-phase0`. The builds (`out/md_reference`,
  `out/md_reference_interp`) and the twelve captures (`out/md_profile/cap4`,
  `cap5`) are already there. Do not create another worktree for the same
  branch.
- Never work in the main checkout. Never rebuild the shared `vendor/`
  toolchain.

**Git: always commit and push to octamad.**
- `origin` is `github.com/repeat98/octamad`. Push only there:
  `git push origin machinedrum-phase0`.
- **Never push to `upstream`** (`sambanks/octabam`). Never force-push.
  Never push or merge to `main`. Never open a pull request.
- Push after every claim commit and after every finished packet. If a push
  fails, do not work around it with force or another remote. Record the
  failure in the night report and keep committing locally.
- Before every push, check that no Elektron byte is in the commit: no
  firmware, snapshot, `.bin`, `.syx`, sample or extracted blob. Run
  `git diff --numstat origin/machinedrum-phase0..HEAD` and look for `-`
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
1. **WP-A1** Core-0 memory ledger.
2. **WP-D1** Is the chord free? A static read.
3. **WP-A2** The layout. Propose it, set it to `review`, and do not wait
   for sign-off.
4. **WP-R3** The interpreter/JIT mismatch.
5. **WP-R5** The c47_2 anomaly.
6. **WP-R2** The TRX-S2 residual. Measure only; decision D3 stays with the
   user.
7. **WP-R1** E12 sample delivery. The measurement and the design options
   only; decision D4 stays with the user.
8. **WP-A3**, then **WP-A4**, then **WP-A6**, **on the proposed layout**,
   while WP-A2 is in `review`. Label every result "on the proposed layout,
   pending the user's sign-off". If the user later changes the layout,
   these are redone.
9. **WP-B1**, then **WP-B2**, on the proposed layout, with the same label.
   `make check` must stay green for the other remixes.

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
  modules, other remixes, the build, and other sessions' worktrees and
  stashes. If a change to the build seems needed, write it up as a
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
