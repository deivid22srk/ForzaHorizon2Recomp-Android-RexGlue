#!/usr/bin/env python3
"""Extents-aware audit of vtable/jump-table slot targets (iteration 7 method).

Given a flat module image and the generated function registry, this tool:
  1. scans a data region for 4-byte words that point into the code range;
  2. filters out already-registered targets;
  3. for each unregistered target, runs the SAFETY checks:
       a. gap check  — target not inside any registered function's extent
                       (approximated by the registered-neighbour interval,
                        refined by the antecessor terminator scan);
       b. antecessor check — the registered function immediately below must
          divert flow (unconditional b / blr / bctr) before the target;
       c. classification:
            - THUNK: 2-instruction `addi rX,rX,-N; b <registered>` pattern
              (branch target must itself be registered);
            - REAL: clean prologue + linear extent scan to the first
              unconditional terminator, with no registered start inside.
  4. prints a report: SAFE TO TAG / REJECTED (with reason).

Usage:
    python3 tools/audit_vtable_family.py <image.bin> <image_base_hex> \
        <code_start_hex> <code_end_hex> <registry_cpp> \
        <region_start_hex> <region_end_hex>

Requires: capstone (pip install capstone).
"""
import re
import struct
import sys

try:
    import capstone
except ImportError:
    sys.exit("capstone is required: pip install capstone")


def load_registry(path):
    """Extract {addr: name} from the generated init table lines."""
    reg = {}
    pat = re.compile(r"\{\s*0x([0-9A-Fa-f]+)\s*,\s*(\w+)\s*\}")
    with open(path, errors="ignore") as f:
        for line in f:
            m = pat.search(line)
            if m:
                reg[int(m.group(1), 16)] = m.group(2)
    return reg


def classify_target(md, data, image_base, target, registered):
    """Return (verdict, reason, extent_end) for one candidate target."""
    # --- antecessor: nearest registered below -----------------------------
    below = [a for a in registered if a < target]
    if not below:
        return "REJECT", "no registered function below target", None
    antecessor = max(below)
    # antecessor must divert flow before reaching target: scan its first
    # 64 words for an unconditional terminator whose address <= target.
    diverted = False
    for i in range(64):
        a = antecessor + i * 4
        if a >= target:
            break
        off = a - image_base
        ins = list(md.disasm(data[off : off + 4], a))
        if not ins:
            continue
        mn, op = ins[0].mnemonic, ins[0].op_str
        if mn in ("blr", "bctr", "b", "ba"):
            diverted = True
            break
    if not diverted:
        return "REJECT", (
            f"antecessor 0x{antecessor:08X} may fall through into target"
        ), None

    # --- classification ----------------------------------------------------
    off = target - image_base
    w0 = struct.unpack_from(">I", data, off)[0]
    ins0 = list(md.disasm(data[off : off + 4], target))
    if not ins0:
        return "REJECT", "undecodable first word", None

    # thunk?  addi rX,rX,-N  followed by  b <registered target>
    is_addi = ins0[0].mnemonic == "addi" and ins0[0].op_str.split(",")[0] == ins0[0].op_str.split(",")[1]
    if is_addi:
        ins1 = list(md.disasm(data[off + 4 : off + 8], target + 4))
        if ins1 and ins1[0].mnemonic == "b" and ins1[0].op_str.startswith("0x"):
            btgt = int(ins1[0].op_str, 16)
            if btgt in registered:
                return "SAFE-THUNK", (
                    f"thunk -> 0x{btgt:08X} (registered)"
                ), target + 8
            return "REJECT", f"thunk branch target 0x{btgt:08X} NOT registered", None

    # real function: linear extent scan to first unconditional terminator
    a = target
    limit = target + 0x2000
    end = None
    while a < limit:
        o = a - image_base
        ins = list(md.disasm(data[o : o + 4], a))
        if not ins:
            a += 4
            continue
        mn, op = ins[0].mnemonic, ins[0].op_str
        if mn in ("blr", "bctr"):
            end = a + 4
            break
        if mn == "b" and op.startswith("0x"):
            t = int(op, 16)
            if t >= a + 4 or t < target:  # branch out of linear body
                end = a + 4
                break
        a += 4
    if end is None:
        return "REJECT", "no terminator within 8 KiB linear scan", None
    inside = sorted(x for x in registered if target < x < end)
    if inside:
        return "REJECT", (
            f"registered starts inside extent: {[hex(x) for x in inside]}"
        ), None
    return "SAFE-REAL", (
        f"real function, extent {end - target} bytes"
    ), end


def main(argv):
    if len(argv) != 8:
        print(__doc__)
        return 2
    img_path, image_base, code_start, code_end, registry, rstart, rend = argv[1:]
    image_base = int(image_base, 16)
    code_start = int(code_start, 16)
    code_end = int(code_end, 16)
    rstart = int(rstart, 16)
    rend = int(rend, 16)

    registered = load_registry(registry)
    data = open(img_path, "rb").read()
    md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)

    from collections import defaultdict

    slots = defaultdict(list)
    for addr in range(rstart, rend, 4):
        w = struct.unpack_from(">I", data, addr - image_base)[0]
        if code_start <= w < code_end and w not in registered:
            slots[w].append(addr)

    print(f"registered functions: {len(registered)}")
    print(f"unregistered slot targets in 0x{rstart:08X}..0x{rend:08X}: {len(slots)}\n")

    safe, rejected = [], []
    for t in sorted(slots):
        verdict, reason, _ = classify_target(md, data, image_base, t, registered)
        tag = "SAFE   " if verdict.startswith("SAFE") else "REJECT "
        print(f"  [{tag}] 0x{t:08X}  ({len(slots[t])} slots)  {reason}")
        (safe if verdict.startswith("SAFE") else rejected).append((t, verdict, reason))

    print(f"\n=== SAFE to tag: {len(safe)} | REJECTED: {len(rejected)} ===")
    if safe:
        print("\nTOML block:\n")
        for t, verdict, _ in safe:
            print(f"0x{t:08X} = {{}}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
