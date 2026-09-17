#!/usr/bin/env python3
"""Extract EXACT guest extents of all registered functions from the generated
recomp .cpp sources.

Each translated function body renders every guest instruction as a comment
line, so the extent is: start (from DEFINE_REX_FUNC name) + 4 * n_commented
instructions. `loc_XXXXXXXX:` labels reset/verify the tracked address.

Output: JSON { "0xSTART": end_addr_int, ... } (end exclusive)
plus a sanity report (function count vs registry, label mismatches).
"""
import glob
import json
import re
import sys

import os
SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "recomp", "generated", "default")
REG = os.path.join(SRC_DIR, "fh2_register.cpp")
OUT = os.path.join(os.path.dirname(__file__), "..", "extents_main.json")

func_re = re.compile(r"DEFINE_REX_FUNC\((\w+)\)")
label_re = re.compile(r"^loc_([0-9A-Fa-f]{8}):")
insn_re = re.compile(r"^\t//")
setfunc_re = re.compile(r"SetFunction\(0x([0-9A-Fa-f]+),\s*(\w+)\)")

name_addr = {}
registered = []
for line in open(REG, errors="ignore"):
    m = setfunc_re.search(line)
    if m:
        a = int(m.group(1), 16)
        registered.append(a)
        name_addr[m.group(2)] = a
reg_set = set(registered)
print(f"registry: {len(registered)} functions")

extents = {}
label_mismatches = 0
parsed = 0
cur = None  # [start_addr, next_addr, last_label]
files = sorted(glob.glob(os.path.join(SRC_DIR, "fh2_recomp.*.cpp")))


def finish():
    global cur
    if cur is not None:
        start, nxt, last_label = cur
        extents[start] = nxt  # end exclusive
        cur = None


for path in files:
    with open(path, errors="ignore") as f:
        for line in f:
            mf = func_re.search(line)
            if mf:
                finish()
                name = mf.group(1)
                if name.startswith("sub_") and len(name) == 12:
                    start = int(name[4:], 16)
                else:
                    start = name_addr.get(name)
                    if start is None:
                        cur = None
                        continue
                cur = [start, start, None]
                parsed += 1
                continue
            if cur is None:
                continue
            ml = label_re.match(line)
            if ml:
                lab = int(ml.group(1), 16)
                if lab != cur[1]:
                    label_mismatches += 1
                    # trust the label: jump target may start a block that
                    # does not follow linearly; reset tracked address
                    cur[1] = lab
                cur[2] = lab
                continue
            if insn_re.match(line):
                cur[1] += 4
                continue
            if line.startswith("}") or line.startswith("\treturn;"):
                # `return;` lines are not guest instructions; `}` ends body
                if line.startswith("}"):
                    finish()
finish()

print(f"parsed: {parsed} function bodies, extents: {len(extents)}")
print(f"label mismatches (resets): {label_mismatches}")
missing = reg_set - set(extents)
extra = set(extents) - reg_set
print(f"in registry but not parsed: {len(missing)}: {[hex(x) for x in list(missing)[:5]]}")
print(f"parsed but not in registry: {len(extra)}: {[hex(x) for x in list(extra)[:5]]}")

# sanity: overlaps between registered extents?
items = sorted(extents.items())
overlaps = 0
prev_s, prev_e = 0, 0
for s, e in items:
    if s < prev_e:
        overlaps += 1
        if overlaps <= 5:
            print(f"  overlap: 0x{s:08X}..0x{e:08X} inside 0x{prev_s:08X}..0x{prev_e:08X}")
    if e > prev_e:
        prev_s, prev_e = s, e
print(f"extent overlaps: {overlaps}")

json.dump({f"0x{s:08X}": e for s, e in items}, open(OUT, "w"))
print(f"saved -> {OUT}")

# verify the crash context: 0x831E77E0 must be OUTSIDE all extents
T = 0x831E77E0
import bisect
starts = [s for s, _ in items]
i = bisect.bisect_right(starts, T) - 1
if i >= 0:
    s = starts[i]
    e = extents[s]
    print(f"\ncrash target 0x{T:08X}: containing interval start 0x{s:08X} end 0x{e:08X} -> "
          f"{'INSIDE (BAD)' if T < e else 'in gap (GOOD)'}")
