"""The deadline rule, exercised through the real contract methods.

A steward asked that the deadline be part of the contract's adjudication, that
invalid or retroactive deadlines be refused, and that tests prove only fulfilment
evidenced on or before the stored deadline can be marked KEPT. Testing the parsing
helpers alone would not prove that, so pledge.py is loaded against a stub of the
runtime, a real Pledge is built, and the assertions go through pledge() and check().

The one thing the stub controls is what the validators return when the round runs,
because that is the input the contract cannot control and precisely what is being
tested: the round is made to report a promise fulfilled on time, fulfilled late,
not fulfilled, or an unreadable page, and the contract's own handling of the
deadline is checked against each. Time is controlled too, so a deadline can be made
to lie in the future at pledge time and in the past at check time without waiting.

    python tests/pledge_rules.py
"""

import io
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
CONTRACT = os.path.join(HERE, "..", "contracts", "pledge.py")


class _Store:
    def __init__(self, kind): self.kind = kind
    def __class_getitem__(cls, item): return cls("map" if isinstance(item, tuple) else "list")
    def make(self): return {} if self.kind == "map" else []


class _Address:
    def __init__(self, hex_value): self.as_hex = hex_value
    def __str__(self): return str(self.as_hex)


class _Message:
    def __init__(self):
        self.sender_address = _Address("0x" + "0" * 40)
        self.value = 0


class _Web:
    """The page the contract fetches inside the round. `page` is the body it returns;
    set it to None to make render() raise, standing in for an unreadable source."""
    def __init__(self):
        self.page = "a page"

    def render(self, url):
        if self.page is None:
            raise RuntimeError("could not fetch")
        return self.page


class _Nondet:
    def __init__(self, web):
        self.web = web
        self.last_prompt = None
        self.answer = "{}"

    def exec_prompt(self, task):
        # Record what the contract asked the round, so a test can prove the deadline
        # was put in front of the validators, and return the canned verdict.
        self.last_prompt = task
        return self.answer


class _Write:
    def __call__(self, fn): return fn
    def payable(self, fn): return fn


class _PublicNS:
    def __init__(self):
        self.write = _Write()
        self.view = lambda fn: fn


class _EqPrinciple:
    def prompt_comparative(self, run, principle=None): return run()


class _GL:
    def __init__(self):
        self.Contract = object
        self.public = _PublicNS()
        self.message = _Message()
        self.nondet = _Nondet(_Web())
        self.eq_principle = _EqPrinciple()


def load():
    gl = _GL()
    fake = types.ModuleType("genlayer")
    fake.gl = gl
    fake.DynArray = _Store
    fake.TreeMap = _Store
    fake.u32 = int
    fake.u256 = int
    fake.Address = _Address
    sys.modules["genlayer"] = fake
    module = types.ModuleType("pledge_under_test")
    exec(compile(io.open(CONTRACT, encoding="utf-8").read(), CONTRACT, "exec"), module.__dict__)
    return module, gl


def fresh(module):
    contract = module.Pledge.__new__(module.Pledge)
    for field, declared in module.Pledge.__annotations__.items():
        setattr(contract, field, declared.make())
    contract.__init__()
    return contract


RESULTS = []


def check_(label, condition):
    RESULTS.append((label, bool(condition)))
    print(("  ok  " if condition else " FAIL "), label)


SITE = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"

URL = "https://example.org/status"
NOW = 1_000_000_000
FUTURE = NOW + 3600          # one hour ahead of pledge time
DEADLINE_PAST = NOW - 3600   # already gone at pledge time


def verdict(v, fulfilled_on="", reason="r", quote="q"):
    return json.dumps({"verdict": v, "fulfilled_on": fulfilled_on, "reason": reason, "quote": quote})


def main():
    module, gl = load()
    clock = {"now": NOW}
    module._now = lambda: clock["now"]

    def as_(address): gl.message.sender_address = _Address(address)

    # ---- the pure rules the public methods are built on ----
    print("the deadline rule, on its own")
    ok, when = module._valid_due(str(FUTURE), NOW)
    check_("a future timestamp is a valid deadline", ok and when == FUTURE)
    check_("a deadline already in the past is refused", not module._valid_due(str(DEADLINE_PAST), NOW)[0])
    check_("a deadline equal to now is refused", not module._valid_due(str(NOW), NOW)[0])
    check_("zero, meaning any time, is refused", not module._valid_due("0", NOW)[0])
    check_("a non-numeric deadline is refused", not module._valid_due("whenever", NOW)[0])

    print("\nonly an on-time verdict maps to kept")
    check_("KEPT maps to a kept record", module._status_for("KEPT") == ("KEPT", 1, 0))
    check_("LATE maps to broken, never kept", module._status_for("LATE") == ("BROKEN", 0, 1))
    check_("BROKEN maps to broken", module._status_for("BROKEN") == ("BROKEN", 0, 1))
    check_("UNCLEAR leaves it pending, no record moved", module._status_for("UNCLEAR") == ("PENDING", 0, 0))

    # ---- the same rules, through pledge() ----
    print("\na pledge cannot be back-dated")
    c = fresh(module)
    as_(SITE)
    back = json.loads(c.pledge("We will ship v2.", URL, str(DEADLINE_PAST)))
    check_("a retroactive deadline is refused at pledge time", not back["ok"] and "back-dated" in back["error"])
    check_("nothing was recorded for it", json.loads(c.size())["total"] == 0)
    bad = json.loads(c.pledge("We will ship v2.", URL, "not-a-date"))
    check_("an invalid deadline is refused", not bad["ok"])
    good = json.loads(c.pledge("We will ship v2.", URL, str(FUTURE)))
    check_("a future deadline is accepted", good["ok"] and good["status"] == "PENDING")

    print("\na pledge cannot be checked before its deadline")
    clock["now"] = NOW + 10  # still before FUTURE
    early = json.loads(c.check(good["id"]))
    check_("checking before the deadline is refused", not early["ok"] and "too early" in early["error"])
    check_("and it stays pending", json.loads(c.status(good["id"]))["status"] == "PENDING")

    print("\nafter the deadline, only fulfilment on or before it is KEPT")
    clock["now"] = FUTURE + 10  # deadline has now passed
    gl.nondet.web.page = "v2 shipped on 2020-01-01, well before the date promised."
    gl.nondet.answer = verdict("KEPT", "2020-01-01")
    on_time = json.loads(c.check(good["id"]))
    check_("fulfilment on or before the deadline is KEPT", on_time["verdict"] == "KEPT" and on_time["status"] == "KEPT")
    check_("the deadline was put in front of the round",
           gl.nondet.last_prompt is not None and json.loads(c.get(good["id"]))["due_iso"] in gl.nondet.last_prompt)
    check_("the keeper's record gains a kept, no broken",
           json.loads(c.record(SITE)) == {"exists": True, "address": SITE, "kept": 1, "broken": 0})

    print("\na promise fulfilled after the deadline is broken, not kept")
    as_(OTHER)
    clock["now"] = NOW
    late_id = json.loads(c.pledge("We will publish the audit.", URL, str(FUTURE)))["id"]
    clock["now"] = FUTURE + 10
    gl.nondet.web.page = "the audit was published, on a date after the promised one."
    gl.nondet.answer = verdict("LATE", "2031-06-01")
    late = json.loads(c.check(late_id))
    check_("a late fulfilment is not KEPT", late["status"] != "KEPT")
    check_("a late fulfilment is recorded BROKEN", late["status"] == "BROKEN" and late["verdict"] == "LATE")
    check_("the late author's record gains a broken and no kept",
           json.loads(c.record(OTHER)) == {"exists": True, "address": OTHER, "kept": 0, "broken": 1})

    print("\nthe other outcomes")
    as_(SITE)
    clock["now"] = NOW
    broken_id = json.loads(c.pledge("We will refund everyone.", URL, str(FUTURE)))["id"]
    clock["now"] = FUTURE + 10
    gl.nondet.web.page = "no refund has been issued."
    gl.nondet.answer = verdict("BROKEN")
    broken = json.loads(c.check(broken_id))
    check_("an unfulfilled promise is BROKEN", broken["status"] == "BROKEN")

    clock["now"] = NOW
    unclear_id = json.loads(c.pledge("We will open source it.", URL, str(FUTURE)))["id"]
    clock["now"] = FUTURE + 10
    gl.nondet.web.page = None  # the source cannot be read
    unclear = json.loads(c.check(unclear_id))
    check_("an unreadable page is UNCLEAR", unclear["verdict"] == "UNCLEAR")
    check_("and leaves the pledge pending, to be checked again",
           json.loads(c.status(unclear_id))["status"] == "PENDING")

    print("\nno verdict ever writes kept for a late or broken promise")
    counts = json.loads(c.size())
    rec_site = json.loads(c.record(SITE))
    check_("exactly one pledge is kept across the whole board", counts["kept"] == 1)
    check_("and it is the one fulfilled on time", rec_site["kept"] == 1)

    failed = [label for label, ok in RESULTS if not ok]
    print()
    if failed:
        print("%d of %d checks failed" % (len(failed), len(RESULTS)))
        return 1
    print("%d checks, all through pledge() and check() on a real Pledge, with the deadline enforced"
          % len(RESULTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
