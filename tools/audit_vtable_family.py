#!/usr/bin/env python3
"""Extents-aware audit of vtable/jump-table slot targets — v3 (exact extents).

v3 changes (7th device session / iteration 9):
  - loads EXACT registered extents extracted from the generated recomp
    sources (scripts/extract_extents.py -> extents JSON); the antecessor
    fall-through heuristic is RETIRED (it mis-passed mid-function bytes
    hidden behind intra-function forward branches);
  - exact gap check: a candidate inside any registered extent is REJECTED
    (iteration-5 failure mode), using interval union + bisect;
  - candidate extent scan stops at registered barriers; crossing a barrier
    without a terminator is a REJECT;
  - first-instruction plausibility: real function entries cannot start with
    bl/bctrl/bclr/mtctr/conditional branches (mid-function call/return/dispatch
    sites); `b`-first entries are 1-instruction tail thunks with target
    validation;
  - batch acceptance (ascending, extent-overlap detection between accepted
    candidates) + fixpoint unresolved-direct-call downgrade, as in v2.

Why fall-through is no longer checked: registered functions are translated
to a terminator (their exact extents prove it), so linear flow never leaves
a registered function into a gap; gap bytes are reachable only via branches
and indirect calls — exactly what we audit.

Usage:
    python3 tools/audit_vtable_family.py <image.bin> <image_base_hex> \
        <code_start_hex> <code_end_hex> <registry_cpp> <extents_json> \
        <region_start_hex> <region_end_hex>

Sweep mode (all data areas, merged clusters, global overlap handling):
    ... <registry_cpp> <extents_json> --all
"""
import bisect
import json
import re
import struct
import sys

try:
    import capstone
except ImportError:
    sys.exit("capstone is required: pip install capstone")


def load_registry(path):
    reg = {}
    pat_set = re.compile(r"SetFunction\(0x([0-9A-Fa-f]+)\s*,\s*(\w+)\)")
    pat_tbl = re.compile(r"\{\s*0x([0-9A-Fa-f]+)\s*,\s*(\w+)\s*\}")
    with open(path, errors="ignore") as f:
        for line in f:
            m = pat_set.search(line) or pat_tbl.search(line)
            if m:
                reg[int(m.group(1), 16)] = m.group(2)
    return reg


def load_extents(path, registered):
    """Return sorted interval list [(start, end)] covering every registered
    function. Missing-extent functions (import stubs) get a 16-byte barrier."""
    raw = json.load(open(path))
    ivals = [(int(k, 16), v) for k, v in raw.items()]
    have = set(s for s, _ in ivals)
    for a in registered:
        if a not in have:
            ivals.append((a, a + 16))
    ivals.sort()
    # union
    merged = []
    for s, e in ivals:
        if merged and s < merged[-1][1]:
            if e > merged[-1][1]:
                merged[-1][1] = e
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def find_clusters(data, image_base, code_start, code_end, registered,
                  min_per_page=4, merge_gap=0x4000, image_end=None):
    if image_end is None:
        image_end = image_base + len(data)
    areas = [(image_base, code_start), (code_end, image_end)]
    pages = {}
    for lo, hi in areas:
        for page in range(lo, hi, 0x1000):
            cnt = 0
            for a in range(page, min(page + 0x1000, hi), 4):
                w = struct.unpack_from(">I", data, a - image_base)[0]
                if w & 3 == 0 and code_start <= w < code_end and w not in registered:
                    cnt += 1
            if cnt >= min_per_page:
                pages[page] = cnt
    clusters = []
    cur = None
    prev = None
    for page in sorted(pages):
        if cur is not None and prev is not None and page - prev <= merge_gap:
            cur[1] = page + 0x1000
        else:
            if cur:
                clusters.append(cur)
            cur = [page, page + 0x1000]
        prev = page
    if cur:
        clusters.append(cur)
    out = []
    for lo, hi in clusters:
        targets = {}
        for a in range(lo, hi, 4):
            w = struct.unpack_from(">I", data, a - image_base)[0]
            if w & 3 == 0 and code_start <= w < code_end and w not in registered:
                targets.setdefault(w, []).append(a)
        if targets:
            out.append((lo, hi, targets))
    return out


BAD_FIRST = {
    "bl", "bctrl", "bclr", "bcctr", "bcctrl", "mtctr",
    "beq", "bne", "blt", "bge", "bgt", "ble", "bns", "bso", "bdnz",
    "bnelr", "bgelr", "blelr", "bglr", "bllr", "bsolr", "bnectr", "bltctr",
}


def classify_target(md, data, image_base, target, registered, intervals, starts):
    """Return (verdict, reason, extent_end, extra).

    verdicts: SAFE-THUNK / SAFE-REAL / REJECT
    """
    # --- exact gap check: inside any registered extent? -------------------
    i = bisect.bisect_right(starts, target) - 1
    if i >= 0:
        s, e = intervals[i]
        if target < e:
            return "REJECT", (
                f"inside registered extent 0x{s:08X}..0x{e:08X}"), None, None

    off = target - image_base
    ins0 = list(md.disasm(data[off : off + 4], target))
    if not ins0:
        return "REJECT", "undecodable first word", None, None
    mn0 = ins0[0].mnemonic

    # --- thunk forms -------------------------------------------------------
    # 1-insn tail thunk: `b <target>`
    if mn0 == "b" and ins0[0].op_str.startswith("0x"):
        btgt = int(ins0[0].op_str, 16)
        if btgt in registered:
            return "SAFE-THUNK", f"tail-thunk (b) -> 0x{btgt:08X} (registered)", target + 4, btgt
        return "SAFE-THUNK*PENDING", (
            f"tail-thunk (b) -> 0x{btgt:08X} (not registered; may be batch-accepted)"
        ), target + 4, btgt
    # 2-insn reg-setup thunk: li/lis/addi/addis + b
    if mn0 in ("li", "lis", "addi", "addis"):
        ins1 = list(md.disasm(data[off + 4 : off + 8], target + 4))
        if ins1 and ins1[0].mnemonic == "b" and ins1[0].op_str.startswith("0x"):
            btgt = int(ins1[0].op_str, 16)
            if btgt in registered:
                return "SAFE-THUNK", (
                    f"thunk ({mn0}; b) -> 0x{btgt:08X} (registered)"
                ), target + 8, btgt
            return "SAFE-THUNK*PENDING", (
                f"thunk ({mn0}; b) -> 0x{btgt:08X} (not registered; may be batch-accepted)"
            ), target + 8, btgt

    # --- first-instruction plausibility for real functions -----------------
    if mn0 in BAD_FIRST:
        return "REJECT", f"implausible entry insn `{mn0}` (mid-function site)", None, None

    # --- real function: linear extent scan to first terminator -------------
    a = target
    limit = min(target + 0x2000, 0x83300000)
    end = None
    while a < limit:
        if a != target:
            # crossing into any registered interval = over-extension
            ii = bisect.bisect_right(starts, a) - 1
            if ii >= 0 and a < intervals[ii][1]:
                return "REJECT", (
                    f"extent reaches registered 0x{intervals[ii][0]:08X} "
                    f"without terminator"), None, None
        o = a - image_base
        ins = list(md.disasm(data[o : o + 4], a))
        if not ins:
            end = a + 4  # undecodable: stop conservatively
            break
        mn, op = ins[0].mnemonic, ins[0].op_str
        if mn in ("blr", "bctr"):
            end = a + 4
            break
        if mn == "b" and op.startswith("0x"):
            end = a + 4  # any unconditional b exits the linear body
            break
        a += 4
    if end is None:
        return "REJECT", "no terminator within 8 KiB linear scan", None, None
    return "SAFE-REAL", f"real function, extent {end - target} bytes", end, ("extent", target, end)


def overlaps(start, end, accepted):
    for s, e in accepted:
        if start < e and s < end:
            return (s, e)
    return None


def main(argv):
    if len(argv) not in (9, 8):
        print(__doc__)
        return 2
    img_path, image_base, code_start, code_end, registry, extjson = argv[1:7]
    sweep = len(argv) == 8 and argv[7] == "--all"
    image_base = int(image_base, 16)
    code_start = int(code_start, 16)
    code_end = int(code_end, 16)

    registered = load_registry(registry)
    intervals = load_extents(extjson, registered)
    starts = [s for s, _ in intervals]
    data = open(img_path, "rb").read()
    md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)

    if sweep:
        clusters = find_clusters(data, image_base, code_start, code_end, registered)
    else:
        rstart = int(argv[7], 16)
        rend = int(argv[8], 16)
        targets = {}
        for a in range(rstart, rend, 4):
            w = struct.unpack_from(">I", data, a - image_base)[0]
            if w & 3 == 0 and code_start <= w < code_end and w not in registered:
                targets.setdefault(w, []).append(a)
        clusters = [(rstart, rend, targets)]

    print(f"registered functions: {len(registered)}; extent intervals: {len(intervals)}")
    total_targets = sum(len(t) for _, _, t in clusters)
    print(f"clusters: {len(clusters)}, unregistered slot targets: {total_targets}\n")

    # ---- phase 1: independent classification ----
    verdicts = {}
    for lo, hi, targets in clusters:
        for t in sorted(targets):
            v, r, ext, extra = classify_target(md, data, image_base, t, registered,
                                               intervals, starts)
            verdicts[t] = (v, r, ext, extra, targets[t])

    # ---- phase 2: accept REALs ascending with overlap detection ----
    accepted = []
    accepted_set = set()
    final = {}
    for t in sorted(verdicts):
        v, r, ext, extra, slots = verdicts[t]
        if v != "SAFE-REAL":
            continue
        ov = overlaps(t, ext, accepted)
        if ov:
            final[t] = ("REJECT", f"extent overlaps accepted 0x{ov[0]:08X}..0x{ov[1]:08X}")
        else:
            accepted.append((t, ext))
            accepted_set.add(t)
            final[t] = (v, r)

    # ---- phase 2.5: unresolved direct-call downgrade (fixpoint) ----
    def unresolved_in_extent(start, end):
        bad = []
        a = start
        while a < end:
            o = a - image_base
            ins = list(md.disasm(data[o : o + 4], a))
            if ins and ins[0].mnemonic in ("b", "bl") and ins[0].op_str.startswith("0x"):
                t = int(ins[0].op_str, 16)
                if code_start <= t < code_end and t not in registered and t not in accepted_set:
                    bad.append((a, ins[0].mnemonic, t))
            a += 4
        return bad

    changed = True
    while changed:
        changed = False
        for t in sorted(accepted_set):
            v, r, ext, extra, slots = verdicts[t]
            bad = unresolved_in_extent(t, ext)
            if bad:
                b0 = bad[0]
                final[t] = ("REJECT", (
                    f"extent has direct {b0[1]} to unregistered 0x{b0[2]:08X}"
                    + (f" (+{len(bad)-1} more)" if len(bad) > 1 else "")))
                accepted = [(s, e) for (s, e) in accepted if s != t]
                accepted_set.discard(t)
                changed = True

    # ---- phase 3: accept THUNKs ----
    for t in sorted(verdicts):
        v, r, ext, extra, slots = verdicts[t]
        if not v.startswith("SAFE-THUNK"):
            continue
        btgt = extra
        if btgt not in registered and btgt not in accepted_set:
            final[t] = ("REJECT", f"thunk branch target 0x{btgt:08X} NOT registered/accepted")
            continue
        ov = overlaps(t, ext, accepted)
        if ov:
            final[t] = ("REJECT", f"extent overlaps accepted 0x{ov[0]:08X}..0x{ov[1]:08X}")
            continue
        note = "registered" if btgt in registered else "batch-accepted"
        final[t] = ("SAFE-THUNK", f"thunk -> 0x{btgt:08X} ({note})")

    for t, (v, r, ext, extra, slots) in verdicts.items():
        if t not in final:
            final[t] = ("REJECT", r if v == "REJECT" else f"unresolved: {v}")

    # ---- report ----
    n_safe = 0
    n_rej = 0
    for lo, hi, targets in clusters:
        safe_c = sum(1 for t in targets if final[t][0].startswith("SAFE"))
        rej_c = len(targets) - safe_c
        n_safe += safe_c
        n_rej += rej_c
        print(f"--- cluster 0x{lo:08X}..0x{hi:08X}: {len(targets)} targets, "
              f"{safe_c} safe, {rej_c} rejected ---")
        for t in sorted(targets):
            v, r = final[t]
            tag = "SAFE   " if v.startswith("SAFE") else "REJECT "
            ns = len(verdicts[t][4])
            print(f"  [{tag}] 0x{t:08X}  ({ns} slot{'s' if ns != 1 else ''})  {r}")
        print()

    print(f"=== SAFE to tag: {n_safe} | REJECTED: {n_rej} ===")
    if n_safe:
        print("\nTOML block (ascending):\n")
        for t in sorted(final):
            v, _ = final[t]
            if v.startswith("SAFE"):
                print(f"0x{t:08X} = {{}}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
