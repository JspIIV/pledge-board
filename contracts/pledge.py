# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Pledge: a public promise, checked against its own source, and against its own deadline.

People and organisations make dated promises all the time: we will ship by
Friday, we will publish the audit this quarter, we will refund within thirty
days. The promise is loud, and the day it comes due is quiet. By then attention
has moved on, the screenshot is forgotten, and whether it was kept on time is a
matter of whoever still remembers to look.

Pledge writes the promise, its deadline, and the page where it can be checked onto
the chain, and then does the looking. An author states a commitment in plain words,
names one public page where its truth will show, and sets a deadline that must lie
in the future: a promise cannot be made about a date that has already passed. After
that deadline, anyone may check it: the contract fetches the page itself, tells the
round what the deadline was, and a round of GenLayer validators reads the page and
decides whether the promise was fulfilled on or before that deadline.

The deadline is part of the judgement, not a formality. A promise fulfilled late is
not kept: the round is asked to separate work finished on or before the deadline
(KEPT) from work finished only afterwards (LATE), and the contract records a late
promise as broken, the same as one never fulfilled at all. Only fulfilment evidenced
on or before the stored deadline is ever recorded as KEPT.

## What it answers

    record(address) -> kept, broken

for anyone deciding whether to trust a party with the next thing: a track record of
promises met on time and promises missed, each one judged from a public source
against the deadline the author themselves set, not from the author's own account of
themselves.

## What it refuses

It refuses a deadline that is not in the future, so a pledge cannot be back-dated to
a moment that is already settled. It never judges a promise before its time: check is
refused until the deadline passes, so nobody is marked broken for work still in
progress. It never decides on silence: a page that cannot be read is UNCLEAR, the
pledge stays open, and it can be checked again later. The author is bound to the
caller of pledge, so nobody is put on the hook for a promise they did not make.

## Where it stops, plainly

It judges what a public page says, and when the page says it happened, not the wall
clock of the chain: name a page that shows both the fulfilment and its date. A promise
worded loosely can be read two ways; name a page a third party controls and a
commitment a stranger could check. It records a reputation, not a penalty: what a
broken promise costs is left to whoever reads the record.
"""

from genlayer import *
import json

KEPT = "KEPT"
LATE = "LATE"
BROKEN = "BROKEN"
UNCLEAR = "UNCLEAR"
VERDICTS = (KEPT, LATE, BROKEN, UNCLEAR)

PENDING = "PENDING"

MAX_COMMITMENT = 400
MAX_URL = 300
MAX_PAGE = 6000
MAX_REASON = 300
MAX_QUOTE = 300

FETCH_FAILED = "__FETCH_FAILED__"


def _now() -> int:
    from datetime import datetime, timezone
    return int(datetime.now(timezone.utc).timestamp())


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _iso(ts: int) -> str:
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(int(ts), timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(ts)


def _clip(text: str, limit: int) -> str:
    text = str(text).strip()
    return text if len(text) <= limit else text[:limit] + " [...]"


def _whole(value) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return -1


def _valid_due(value, now: int):
    """A deadline is valid only if it is a whole timestamp strictly in the future.

    Returns (True, when) for an acceptable deadline, or (False, message) for an
    invalid or retroactive one. Kept pure so the rule can be tested on its own and
    exercised through pledge().
    """
    when = _whole(value)
    if when <= 0:
        return False, "give the deadline as a unix timestamp in the future"
    if when <= now:
        return False, "the deadline must be in the future; a pledge cannot be back-dated to a date that has already passed"
    return True, when


def _status_for(verdict: str):
    """Map a round verdict to a status and the record deltas. The deadline rule lives here.

    Only KEPT, which the round returns only for fulfilment on or before the deadline,
    is ever recorded as kept. LATE, fulfilment after the deadline, is recorded as
    broken exactly like an unfulfilled promise. UNCLEAR leaves the pledge pending.
    Returns (status, kept_delta, broken_delta).
    """
    if verdict == KEPT:
        return KEPT, 1, 0
    if verdict == LATE or verdict == BROKEN:
        return BROKEN, 0, 1
    return PENDING, 0, 0


def _addr(value) -> str:
    text = str(value).strip().lower()
    if not text.startswith("0x") or len(text) != 42:
        return ""
    for character in text[2:]:
        if character not in "0123456789abcdef":
            return ""
    return text


def _url_ok(url: str) -> bool:
    text = str(url).strip()
    if len(text) < 8 or len(text) > MAX_URL or " " in text:
        return False
    return text.startswith("https://") or text.startswith("http://")


def _field(raw: str, name: str, allowed, fallback: str) -> str:
    try:
        text = str(raw).strip()
        obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
        if isinstance(obj, dict):
            said = str(obj.get(name, "")).strip().upper()
            return said if said in allowed else fallback
    except Exception:
        pass
    return fallback


def _text_field(raw: str, name: str, limit: int) -> str:
    try:
        text = str(raw).strip()
        obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
        if isinstance(obj, dict):
            return _clip(str(obj.get(name, "")), limit)
    except Exception:
        pass
    return ""


def _task(commitment: str, deadline: str, page: str) -> str:
    return f"""Someone made a public promise with a deadline that has now passed, and named the
page below as where its truth would show. Read the page and decide whether the
promise was kept, and whether it was kept in time.

THE PROMISE, in the words of whoever made it:
{commitment}

THE DEADLINE the promise had to be fulfilled by (fulfilment after this does not count as kept):
{deadline}

THE PAGE THEY NAMED AS THE PLACE IT WOULD SHOW:
{page}

Decide one of:
  {KEPT} the page shows the promise was fulfilled ON OR BEFORE the deadline above
  {LATE} the page shows the promise was fulfilled, but only AFTER the deadline
  {BROKEN} the page was read and the promise was not fulfilled at all, or the page shows the opposite
  {UNCLEAR} the page could not be read, or does not settle whether or when the promise was fulfilled

Judge from the date the page itself gives for the fulfilment, against the deadline
above, not against today. If the page shows the thing was done but gives no date and
the promise plainly refers to something already visible on the page, treat that as
{KEPT}; if the page shows it was done and dates it after the deadline, that is {LATE}.
Do not treat an unreachable or unrelated page as kept, late or broken: that is
{UNCLEAR}, and the pledge is left open rather than marked against the author.

Reply with bare JSON and nothing else:
{{"verdict": "{KEPT}" or "{LATE}" or "{BROKEN}" or "{UNCLEAR}",
  "fulfilled_on": "the date the page gives for the fulfilment, or empty",
  "quote": "the sentence on the page that decided it, or empty",
  "reason": "one sentence naming what decided it, including timing"}}"""


class Pledge(gl.Contract):
    """Dated public promises, each judged from its own source against its own deadline."""

    # str(id) -> the pledge as JSON.
    items: TreeMap[str, str]
    ids: DynArray[str]
    # address -> {"kept": n, "broken": n} as JSON.
    records: TreeMap[str, str]

    def __init__(self) -> None:
        pass

    @gl.public.write
    def pledge(self, commitment: str, source_url: str, due: str) -> str:
        """Make a public promise: a commitment, the page it can be checked at, and a deadline.

        The author is bound to the caller. `due` is a unix timestamp that must lie in
        the future: a deadline already in the past is refused, so a pledge cannot be
        back-dated. The pledge cannot be checked until the deadline passes, and
        fulfilment after the deadline is not counted as kept.
        """
        author = gl.message.sender_address.as_hex.lower()
        text = _clip(commitment, MAX_COMMITMENT)
        link = str(source_url).strip()
        if not text:
            return json.dumps({"ok": False, "error": "state the promise in plain words"})
        if not _url_ok(link):
            return json.dumps({"ok": False, "error": "give an http(s) URL the promise can be checked at"})
        ok, when = _valid_due(due, _now())
        if not ok:
            return json.dumps({"ok": False, "error": when})

        pid = str(len(self.ids))
        record = {
            "id": pid,
            "author": author,
            "made_at": _now_iso(),
            "commitment": text,
            "source_url": link,
            "due": when,
            "due_iso": _iso(when),
            "status": PENDING,
            "checks": 0,
            "verdict": "",
            "fulfilled_on": "",
            "reason": "",
            "quote": "",
            "judged_at": "",
        }
        self.items[pid] = json.dumps(record)
        self.ids.append(pid)
        return json.dumps({"ok": True, "id": pid, "status": PENDING, "due": when, "due_iso": _iso(when)})

    @gl.public.write
    def check(self, pledge_id: str) -> str:
        """After the deadline, fetch the source and mark the pledge KEPT or BROKEN. Open to anybody.

        The page is fetched by the contract itself inside the round, and the round is
        told what the deadline was, so fulfilment after the deadline is judged LATE and
        recorded as broken. Nobody passes in the verdict. The result accrues to the
        author's record.
        """
        pid = str(pledge_id).strip()
        stored = self.items.get(pid, None)
        if stored is None:
            return json.dumps({"ok": False, "error": "no pledge with that id"})
        record = json.loads(stored)
        if record["status"] != PENDING:
            return json.dumps({"ok": False, "error": "this pledge is already " + record["status"].lower(),
                               "status": record["status"]})
        if _now() < int(record["due"]):
            return json.dumps({"ok": False, "error": "too early; this pledge cannot be checked until its deadline",
                               "due": record["due"], "now": _now()})

        # Copy into locals before the round. Nothing inside the block reads self
        # and nothing inside it raises.
        commitment = record["commitment"]
        url = record["source_url"]
        deadline = record["due_iso"]

        def look() -> str:
            page = ""
            try:
                got = gl.nondet.web.render(url)
                page = got if isinstance(got, str) else getattr(got, "body", "")
                if isinstance(page, (bytes, bytearray)):
                    page = page.decode("utf-8", "replace")
                page = _clip(str(page), MAX_PAGE)
            except Exception:
                page = FETCH_FAILED
            if not page or page == FETCH_FAILED:
                return json.dumps({"verdict": UNCLEAR, "fulfilled_on": "", "quote": "",
                                   "reason": "the source page could not be read"})
            try:
                return str(gl.nondet.exec_prompt(_task(commitment, deadline, page)))
            except Exception as error:
                return json.dumps({"verdict": UNCLEAR, "fulfilled_on": "", "quote": "",
                                   "reason": _clip("the prompt failed: " + str(error), MAX_REASON)})

        raw = gl.eq_principle.prompt_comparative(
            look,
            principle=(
                f"Both answers must carry the same value in the field named verdict, one of "
                f"{KEPT}, {LATE}, {BROKEN} or {UNCLEAR}. That single field decides whether a promise "
                "counts as kept on the author's permanent record, and it already folds in the "
                "deadline: KEPT means fulfilled on or before it, LATE means fulfilled after it. Two "
                "readers differing on that field are not wording a judgement differently, they "
                "disagree about whether, or when, the promise was fulfilled. The other fields are not "
                "compared, and the two readers will not have fetched byte-identical copies of the page."
            ),
        )

        verdict = _field(raw, "verdict", VERDICTS, "")
        if not verdict:
            return json.dumps({"ok": False,
                               "error": "the round produced no verdict this contract recognises",
                               "round_said": _clip(str(raw), 400)})

        status, kept_delta, broken_delta = _status_for(verdict)
        record["checks"] = int(record.get("checks", 0)) + 1
        record["verdict"] = verdict
        record["fulfilled_on"] = _text_field(raw, "fulfilled_on", 80)
        record["reason"] = _text_field(raw, "reason", MAX_REASON)
        record["quote"] = _text_field(raw, "quote", MAX_QUOTE)
        if status != PENDING:
            record["status"] = status
            record["judged_at"] = _now_iso()
            author = record["author"]
            rec_raw = self.records.get(author, None)
            rec = json.loads(rec_raw) if rec_raw is not None else {"kept": 0, "broken": 0}
            rec["kept"] = int(rec.get("kept", 0)) + kept_delta
            rec["broken"] = int(rec.get("broken", 0)) + broken_delta
            self.records[author] = json.dumps(rec)
        # UNCLEAR leaves the pledge PENDING, to be checked again later.
        self.items[pid] = json.dumps(record)
        return json.dumps({"ok": True, "id": pid, "verdict": verdict,
                           "status": record["status"], "reason": record["reason"]})

    # ------------------------------------------------------------------ reads

    @gl.public.view
    def record(self, address: str) -> str:
        """An author's permanent track record: promises kept on time and broken, judged from sources."""
        who = _addr(address)
        if not who:
            return json.dumps({"exists": False, "kept": 0, "broken": 0})
        rec_raw = self.records.get(who, None)
        if rec_raw is None:
            return json.dumps({"exists": False, "address": who, "kept": 0, "broken": 0})
        rec = json.loads(rec_raw)
        return json.dumps({"exists": True, "address": who,
                           "kept": int(rec.get("kept", 0)), "broken": int(rec.get("broken", 0))})

    @gl.public.view
    def status(self, pledge_id: str) -> str:
        """A pledge's current standing and the reason it was judged."""
        pid = str(pledge_id).strip()
        stored = self.items.get(pid, None)
        if stored is None:
            return json.dumps({"exists": False})
        record = json.loads(stored)
        return json.dumps({"exists": True, "id": pid, "status": record["status"],
                           "verdict": record.get("verdict", ""), "checks": record["checks"],
                           "reason": record["reason"]})

    @gl.public.view
    def get(self, pledge_id: str) -> str:
        """The whole pledge, including the deciding verdict, quote and reason once judged."""
        pid = str(pledge_id).strip()
        stored = self.items.get(pid, None)
        if stored is None:
            return json.dumps({"exists": False})
        return stored

    @gl.public.view
    def size(self) -> str:
        """How many pledges are pending, kept and broken."""
        pending = 0
        kept = 0
        broken = 0
        for position in range(len(self.ids)):
            record = json.loads(self.items[self.ids[position]])
            state = record["status"]
            if state == PENDING:
                pending += 1
            elif state == KEPT:
                kept += 1
            elif state == BROKEN:
                broken += 1
        return json.dumps({"total": len(self.ids), "pending": pending,
                           "kept": kept, "broken": broken})

    @gl.public.view
    def page(self, start: str, count: str) -> str:
        """A slice of the board, newest first, for a frontend to render."""
        total = len(self.ids)
        begin = _whole(start)
        want = _whole(count)
        if begin < 0:
            begin = 0
        if want < 1:
            want = 20
        if want > 50:
            want = 50
        out = []
        seen = 0
        position = total - 1 - begin
        while position >= 0 and seen < want:
            out.append(json.loads(self.items[self.ids[position]]))
            position -= 1
            seen += 1
        return json.dumps({"total": total, "start": begin, "count": len(out), "items": out})
