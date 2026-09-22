# Pledge

**A public promise, checked against its own source when the time comes.** A dated-accountability primitive for GenLayer, with a live board.

People and organisations make dated promises all the time: we will ship by Friday, publish the audit this quarter, refund within thirty days. The promise is loud, and the day it comes due is quiet. By then attention has moved on, the screenshot is forgotten, and whether it was kept is a matter of whoever still remembers to look.

Pledge does the looking.

## How it works

1. **`pledge(commitment, source_url, due)`** — an author states a promise in plain words, names one public page where its truth will show, and sets a deadline that **must be in the future**. A back-dated deadline is refused. Bound to `gl.message.sender_address`.
2. **`check(id)`** — open to anybody, only **after** the deadline. The contract **fetches the page itself**, tells the round what the deadline was, and a GenLayer round decides `KEPT` / `LATE` / `BROKEN` / `UNCLEAR`. Only fulfilment evidenced **on or before the deadline** is `KEPT`; fulfilment after it is `LATE` and recorded as broken, the same as a promise never kept. The verdict is permanent and accrues to the author; an unreadable page is `UNCLEAR` and the pledge stays open.
3. **`record(address)`** — the author's track record: promises kept on time and broken, each judged from a public source against the deadline they themselves set, not from their own account of themselves.

Reads: `status(id)`, `get(id)`, `size()`, `page(start, count)`.

## The deadline is part of the judgement

The deadline is not a formality the contract stores and forgets. It is refused if it is not in the future, so a pledge cannot be back-dated to a moment already settled; it is injected into the round, so validators judge the fulfilment date the page gives *against that deadline*; and the mapping from verdict to record lives in the contract (`_status_for`), where `LATE` can only ever become broken. Only an on-time `KEPT` verdict is written as kept.

## Why it needs GenLayer

Whether a promise was kept, and kept in time, is a judgement over real-world text that no ordinary contract can make and no single referee should be trusted with. GenLayer validators each fetch the page and reach consensus on one categorical field that already folds in the deadline; the record is built from evidence, judged at the deadline, not from a party grading itself.

## What it refuses

- **Refuses a back-dated deadline.** `pledge` rejects a `due` that is not strictly in the future.
- **Never judges early.** `check` is refused until the deadline passes, so nobody is marked broken for work still in progress.
- **Never credits a late promise.** Fulfilment after the deadline is `LATE`, recorded as broken; only on-or-before fulfilment is `KEPT`.
- **Never decides on silence.** A page that cannot be read is `UNCLEAR`; the pledge stays open and can be checked again.
- **Binds the author to the caller.** Nobody is put on the hook for a promise they did not make, and the deciding evidence is the page the contract fetched.

## Tests

`python tests/pledge_rules.py` — the deadline rule exercised through the real `pledge()` and `check()` on a Pledge built against a stub of the runtime, with time and the round's verdict controlled. It proves back-dated and invalid deadlines are refused, a pledge cannot be checked before its deadline, the deadline is put in front of the round, and — the point of it — a `LATE` verdict is recorded as broken and never as kept, so only fulfilment on or before the stored deadline is ever marked `KEPT`. 26 checks.

## Live

- **Contract (GenLayer Asimov):** `0x093E06AC4D16bB4D4f93e715CBcc6A55BD74Dda5`
- Explorer: https://explorer-asimov.genlayer.com/address/0x093E06AC4D16bB4D4f93e715CBcc6A55BD74Dda5
- **App:** https://jspiiv.github.io/pledge-board/ — reads the board from chain without a wallet; making and checking pledges are transactions on Asimov.

## Proven on Asimov

`scripts/prove.mjs`, `results/proved.json`. Each pledge is made with a deadline a minute out and checked once it has passed:
- a promise its source shows fulfilled before the deadline (`release-shipped.txt`, dated before it) → **KEPT**, and the keeper's `record` gains a kept.
- a promise its source shows never kept (`no-token-sale.txt`) → **BROKEN**, and the breaker's `record` gains a broken.
- a promise whose deadline is still far off → `check` refused, it stays `PENDING`.
- a back-dated deadline → `pledge` refused, the register does not grow.

The `LATE`-is-not-`KEPT` guarantee is proved deterministically in `tests/pledge_rules.py`; `docs/shipped-late.txt` is the illustrative fixture (a release dated after its deadline).

## Try it

Browse the live app, or from the CLI:

```
genlayer call 0x093E06AC4D16bB4D4f93e715CBcc6A55BD74Dda5 size
genlayer call 0x093E06AC4D16bB4D4f93e715CBcc6A55BD74Dda5 get --args '"0"'
```

Reproduce: `AT=0x093E06AC4D16bB4D4f93e715CBcc6A55BD74Dda5 PADV=<pw> PPUB=<pw> node scripts/prove.mjs` (after `npm i`).

## Where it stops, plainly

It judges what a public page says, not whether the page is honest, and the author chooses the page. A promise worded loosely can be read two ways; name a page a third party controls and a commitment a stranger could check. It records a reputation, not a penalty: what a broken promise costs is left to whoever reads the record.

## Licence

AGPL-3.0-or-later.
