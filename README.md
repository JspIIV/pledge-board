# Pledge

**A public promise, checked against its own source when the time comes.** A dated-accountability primitive for GenLayer, with a live board.

People and organisations make dated promises all the time: we will ship by Friday, publish the audit this quarter, refund within thirty days. The promise is loud, and the day it comes due is quiet. By then attention has moved on, the screenshot is forgotten, and whether it was kept is a matter of whoever still remembers to look.

Pledge does the looking.

## How it works

1. **`pledge(commitment, source_url, due)`** — an author states a promise in plain words, names one public page where its truth will show, and sets a deadline. Bound to `gl.message.sender_address`.
2. **`check(id)`** — open to anybody, only **after** the deadline. The contract **fetches the page itself** and a GenLayer round decides `KEPT` / `BROKEN` / `UNCLEAR`. The verdict is permanent and it accrues to the author. An unreadable page is `UNCLEAR` and the pledge stays open.
3. **`record(address)`** — the author's track record: promises kept and broken, each judged from a public source, not from their own account of themselves.

Reads: `status(id)`, `get(id)`, `size()`, `page(start, count)`.

## Why it needs GenLayer

Whether a promise was kept is a judgement over real-world text that no ordinary contract can make and no single referee should be trusted with. GenLayer validators each fetch the page and reach consensus on one categorical field; the record is built from evidence, checked at the deadline, not from a party grading itself.

## What it refuses

- **Never judges early.** `check` is refused until the deadline passes, so nobody is marked broken for work still in progress.
- **Never decides on silence.** A page that cannot be read is `UNCLEAR`; the pledge stays open and can be checked again.
- **Binds the author to the caller.** Nobody is put on the hook for a promise they did not make, and the deciding evidence is the page the contract fetched.

## Live

- **Contract (GenLayer Asimov):** `0xbB6325Ff7A6Dfe776b6CA2784c85275386a5d94D`
- Explorer: https://explorer-asimov.genlayer.com/address/0xbB6325Ff7A6Dfe776b6CA2784c85275386a5d94D
- **App:** https://jspiiv.github.io/pledge-board/ — reads the board from chain without a wallet; making and checking pledges are transactions on Asimov.

## Proven on Asimov

`scripts/prove.mjs`, `results/proved.json`. Two promises against two source pages in `docs/`:
- a promise its source shows kept (a release shipped) → **KEPT**, and the keeper's `record` gains a kept.
- a promise its source shows broken (a token sale that never happened) → **BROKEN**, and the breaker's `record` gains a broken.
- a promise whose deadline is still in the future → `check` refused, it stays `PENDING`.

## Try it

Browse the live app, or from the CLI:

```
genlayer call 0xbB6325Ff7A6Dfe776b6CA2784c85275386a5d94D size
genlayer call 0xbB6325Ff7A6Dfe776b6CA2784c85275386a5d94D get --args '"0"'
```

Reproduce: `AT=0xbB6325Ff7A6Dfe776b6CA2784c85275386a5d94D PADV=<pw> PPUB=<pw> node scripts/prove.mjs` (after `npm i`).

## Where it stops, plainly

It judges what a public page says, not whether the page is honest, and the author chooses the page. A promise worded loosely can be read two ways; name a page a third party controls and a commitment a stranger could check. It records a reputation, not a penalty: what a broken promise costs is left to whoever reads the record.

## Licence

AGPL-3.0-or-later.
