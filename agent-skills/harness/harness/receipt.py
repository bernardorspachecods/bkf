"""The gate receipt: a record that the gate commands passed on one checkout tree.

A receipt lives in `<unit_dir>/receipt/receipt.json` and holds the checkout's tree after the gate ran, the gate
commands, and how many of them failed. `receipt_passes` accepts it only when it is green and still matches the tree
and the commands. The gate logs sit beside it in `<unit_dir>/receipt/gate/`.
"""
import json
from pathlib import Path

from harness.engine.diffbase import snapshot_tree
from harness.gate import run_gate


def _receipt_dir(unit_dir):
    return Path(unit_dir) / "receipt"


def receipt_path(unit_dir):
    return _receipt_dir(unit_dir) / "receipt.json"


def receipt_gate_file(unit_dir):
    return _receipt_dir(unit_dir) / "gate" / "gate.md"


def forget_receipt(unit_dir):
    receipt_path(unit_dir).unlink(missing_ok=True)


def write_receipt(unit_dir, checkout, commands, timeout):
    """Run the gate on the checkout, then record its result. Returns the `run_gate` data."""
    forget_receipt(unit_dir)
    data = run_gate(checkout, timeout, str(_receipt_dir(unit_dir) / "gate"), commands)
    receipt = {"tree": snapshot_tree(checkout), "commands": commands, "red": data["red"]}
    receipt_path(unit_dir).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return data


def receipt_passes(unit_dir, checkout, commands):
    """True only when the receipt is green and was taken on this tree with these gate commands."""
    try:
        receipt = json.loads(receipt_path(unit_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(receipt, dict):
        return False
    red = receipt.get("red")
    return (type(red) is int and red == 0 and receipt.get("commands") == commands
            and receipt.get("tree") == snapshot_tree(checkout))
