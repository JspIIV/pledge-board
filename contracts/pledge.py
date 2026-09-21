# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Pledge: a public promise, checked against its own source when the time comes.

People and organisations make dated promises all the time: we will ship by
Friday, we will publish the audit this quarter, we will refund within thirty
days. The promise is loud, and the day it comes due is quiet. By then attention
has moved on, the screenshot is forgotten, and whether it was kept is a matter of
whoever still remembers to look.

Pledge writes the promise, its deadline, and the page where it can be checked
onto the chain, and then does the looking. An author states a commitment in plain
words, names one public page where its truth will show, and sets the date it can
be judged. After that date, anyone may check it: the contract fetches the page
itself and a round of GenLayer validators reads it and decides whether the promise
was kept. The verdict is permanent, and it accrues to the author, so a record of
what someone actually delivered builds up next to what they said.

## What it answers

    record(address) -> kept, broken

for anyone deciding whether to trust a party with the next thing: a track record
of promises met and missed, each one judged from a public source, not from the
author's own account of themselves.

## What it refuses

It never judges a promise before its time: check is refused until the deadline
passes, so nobody is marked broken for work still in progress. It never decides on
silence: a page that cannot be read is UNCLEAR, the pledge stays open, and it can
be checked again later. The author is bound to the caller, so nobody is put on the
hook for a promise they did not make, and the deciding evidence is the page the
contract fetched, not the author's word.

## Where it stops, plainly

It judges what a public page says, not whether the page is honest, and the author
chooses the page. A promise worded loosely can be read two ways; name a page a
third party controls and a commitment a stranger could check. It records a
reputation, not a penalty: what a broken promise costs is left to whoever reads
the record.
"""

from genlayer import *
import json

KEPT = "KEPT"
BROKEN = "BROKEN"
UNCLEAR = "UNCLEAR"
DECISIONS = (KEPT, BROKEN, UNCLEAR)

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


def _clip(text: str, limit: int) -> str:
    text = str(text).strip()
    return text if len(text) <= limit else text[:limit] + " [...]"


def _whole(value) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return -1


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


def _task(commitment: str, page: str) -> str:
    return f"""Someone made a public promise with a deadline that has now passed, and named the
page below as where its truth would show. Read the page and decide whether the
promise was kept.

THE PROMISE, in the words of whoever made it:
{commitment}

THE PAGE THEY NAMED AS THE PLACE IT WOULD SHOW:
{page}

Decide one of:
  {KEPT} the page shows the promise was kept
  {BROKEN} the page was read and the promise was not kept, or the page shows the opposite
  {UNCLEAR} the page could not be read, or does not settle whether the promise was kept

Judge only what the page actually says. Small differences of wording are fine if
the page settles the same fact. Do not treat an unreachable or unrelated page as
kept or broken: that is {UNCLEAR}, and the pledge is left open rather than marked
against the author.

Reply with bare JSON and nothing else:
{{"decision": "{KEPT}" or "{BROKEN}" or "{UNCLEAR}",
  "quote": "the sentence on the page that decided it, or empty",
  "reason": "one sentence naming what decided it"}}"""


class Pledge(gl.Contract):
    """Dated public promises, each judged from its own source, building a record per author."""

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

        The author is bound to the caller. `due` is a unix timestamp; the pledge
        cannot be checked until it passes, so nobody is judged on unfinished work.
        """
        author = gl.message.sender_address.as_hex.lower()
        text = _clip(commitment, MAX_COMMITMENT)
        link = str(source_url).strip()
        when = _whole(due)
        if not text:
            return json.dumps({"ok": False, "error": "state the promise in plain words"})
        if not _url_ok(link):
            return json.dumps({"ok": False, "error": "give an http(s) URL the promise can be checked at"})
        if when < 0:
            return json.dumps({"ok": False, "error": "give the deadline as a unix timestamp, or 0 for any time"})

        pid = str(len(self.ids))
        record = {
            "id": pid,
            "author": author,
            "made_at": _now_iso(),
            "commitment": text,
            "source_url": link,
            "due": when,
            "status": PENDING,
            "checks": 0,
            "reason": "",
            "quote": "",
            "judged_at": "",
        }
        self.items[pid] = json.dumps(record)
        self.ids.append(pid)
        return json.dumps({"ok": True, "id": pid, "status": PENDING})

    @gl.public.write
    def check(self, pledge_id: str) -> str:
        """After the deadline, fetch the source and mark the pledge KEPT or BROKEN. Open to anybody.

        The page is fetched by the contract itself inside the round; nobody passes
        in the verdict. The result accrues to the author's record.
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
                return json.dumps({"decision": UNCLEAR, "quote": "",
                                   "reason": "the source page could not be read"})
            try:
                return str(gl.nondet.exec_prompt(_task(commitment, page)))
            except Exception as error:
                return json.dumps({"decision": UNCLEAR, "quote": "",
                                   "reason": _clip("the prompt failed: " + str(error), MAX_REASON)})

        raw = gl.eq_principle.prompt_comparative(
            look,
            principle=(
                f"Both answers must carry the same value in the field named decision, one of "
                f"{KEPT}, {BROKEN} or {UNCLEAR}. That single field decides whether a promise counts "
                "as kept on the author's permanent record, so two readers differing on it are not "
                "wording a judgement differently, they disagree about whether the promise was kept. "
                "The quote and the reason are not compared, and the two readers will not have "
                "fetched byte-identical copies of the page."
            ),
        )

        decision = _field(raw, "decision", DECISIONS, "")
        if not decision:
            return json.dumps({"ok": False,
                               "error": "the round produced no decision this contract recognises",
                               "round_said": _clip(str(raw), 400)})

        record["checks"] = int(record.get("checks", 0)) + 1
        record["reason"] = _text_field(raw, "reason", MAX_REASON)
        record["quote"] = _text_field(raw, "quote", MAX_QUOTE)
        if decision == KEPT or decision == BROKEN:
            record["status"] = decision
            record["judged_at"] = _now_iso()
            author = record["author"]
            rec_raw = self.records.get(author, None)
            rec = json.loads(rec_raw) if rec_raw is not None else {"kept": 0, "broken": 0}
            if decision == KEPT:
                rec["kept"] = int(rec.get("kept", 0)) + 1
            else:
                rec["broken"] = int(rec.get("broken", 0)) + 1
            self.records[author] = json.dumps(rec)
        # UNCLEAR leaves the pledge PENDING, to be checked again later.
        self.items[pid] = json.dumps(record)
        return json.dumps({"ok": True, "id": pid, "decision": decision,
                           "status": record["status"], "reason": record["reason"]})

    # ------------------------------------------------------------------ reads

    @gl.public.view
    def record(self, address: str) -> str:
        """An author's permanent track record: promises kept and broken, judged from sources."""
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
                           "checks": record["checks"], "reason": record["reason"]})

    @gl.public.view
    def get(self, pledge_id: str) -> str:
        """The whole pledge, including the deciding quote and reason once judged."""
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
