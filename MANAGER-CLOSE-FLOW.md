# Closing an audit

*Proposed successor task flow. This describes the intended experience, not the
current Python commands.*

*This draft is under review for typed submissions and automatic retirement of
disposable working environments.*

1. **Ask Stewart to close the audit.** Use `close` whether the audit is being
   prepared, still under investigation, or has returned an answer.

2. **See what came back.** Stewart arranges any necessary stop and presents the
   available report and supporting material, identifying incomplete work and
   capture gaps. You do not enter the auditor's working environment.

   **Without a handback:** `close --graceless-exit` requests termination without
   waiting for a final report. Stewart preserves obtainable partial work and
   continues closing under the same custody obligations.

3. **Keep what you want to survive.** Stewart offers a working way to save it;
   reading the answer alone does not save it beyond close. You may keep nothing
   where existing obligations allow. Resolve any outstanding choices Stewart
   identifies about gaps, uncaptured material or obligations. Decisions already
   made still count for the same material.

4. **Receive the closing result.** Stewart completes requested preservation
   and authorized removal. It reports what you kept and any loss, saying
   "closed" only when its remaining obligations are resolved.

If closing cannot finish:

- **Material is held:** the working environment may retire safely while Stewart
  keeps the material. Custody stays open until explicit release and the other
  closing conditions are satisfied.
- **A decision or outside action is needed:** Stewart names the obstacle and
  the specific next step. A close request alone does not surrender material,
  cancel a preservation request or release a hold.
- **The operation or reply is interrupted:** continue the same request through
  `close`. Stewart accounts for what already happened without starting another
  investigation.
