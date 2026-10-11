"""Tether: controlled peripheral state with boot/connection/sequence fences."""

from base import BaseService, Problem, fields, integer, run


class Service(BaseService):
    KIND = "tether"

    def seed(self):
        return {
            "boot": 1,
            "connection": 0,
            "connected": False,
            "desired": 21,
            "reported": 21,
            "nextSequence": 1,
            "acknowledged": 0,
            "pending": None,
        }

    def view(self, state, now):
        return state

    def apply(self, state, action, args, now):
        if action == "connect":
            fields(args, set())
            state["connection"] += 1
            state["connected"] = True
            state["pending"] = None
            return {"accepted": True}
        if action == "reboot":
            fields(args, set())
            state["boot"] += 1
            state["connected"] = False
            state["reported"] = 20
            state["acknowledged"] = 0
            state["nextSequence"] = 1
            state["pending"] = None
            return {"accepted": True}
        fields(
            args,
            {"boot", "connection"}
            | (
                {"target"}
                if action == "set"
                else {"sequence", "target"} if action == "ack" else set()
            ),
        )
        boot = integer(args["boot"], 1)
        connection = integer(args["connection"], 1)
        if (boot, connection) != (state["boot"], state["connection"]) or not state["connected"]:
            return {"accepted": False, "reason": "Device boot or connection is no longer current"}
        if action == "disconnect":
            state["connected"] = False
            state["pending"] = None
            return {"accepted": True}
        if action == "set":
            target = integer(args["target"], 16, 28)
            sequence = state["nextSequence"]
            state["nextSequence"] += 1
            state["desired"] = target
            state["pending"] = {
                "boot": boot,
                "connection": connection,
                "sequence": sequence,
                "target": target,
            }
            return {"accepted": True, "sequence": sequence}
        if action == "ack":
            sequence = integer(args["sequence"], 1)
            target = integer(args["target"], 16, 28)
            if state["pending"] != args:
                return {
                    "accepted": False,
                    "reason": "Acknowledgement does not match the current desired command",
                }
            state["reported"] = target
            state["acknowledged"] = sequence
            state["pending"] = None
            return {"accepted": True}
        raise Problem("Unknown action")


if __name__ == "__main__":
    run(Service, 8922)
