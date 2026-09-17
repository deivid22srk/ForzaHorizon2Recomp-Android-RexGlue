#!/usr/bin/env python3
"""Find data-driven indirect call targets that the static analyzer misses.

Why this exists
===============
The FH2 CRT runs its global constructors through a walker function
(sub_82BFF9E8 in the entrypoint module) that loops over function-pointer
tables in the data section and `bctrl`s every entry that is not 0 or -1.
Those targets are invisible to static analysis: they live in DATA, not in
code flow. At runtime an unregistered target aborts with:

    [FATAL] Call to invalid or unregistered function at guest address 0x...

Fix pattern: enumerate the words the walker WILL call, subtract the set of
functions already registered (PPCFuncMappings in recomp/generated/*/),
and tag the remainder in `recomp/fh2_manifest.toml` ([entrypoint.functions]).

Usage:
    python3 tools/scan_indirect_targets.py <image.bin> <init.cpp> \
        --load-base 0x82000000 --code-start 0x823F0000 --code-end 0x832F258C \
        --walker-region 0x83300010:0x8333F88C [--walker-region 0x8333F890:0x8333F8A0] \
        [--out-dir out/]

`--walker-region start:end` is derived by reading the recompiled walker
function (the `addi rX,rX,imm` bounds around its stride-4 table loops).

IMPORTANT LESSON (iteration 5): do NOT bulk-tag vtable/jump-table candidates
whose addresses fall INSIDE an already-registered function's extent — the
codegen splits the containing function and emits REX_FATAL on branches that
no longer resolve (2528 new unresolved-branch warnings when we tried).
Only tag targets that are (a) known call destinations from device evidence,
or (b) proven to start a real function (prologue + extent checks).
"""
import argparse
import os
import re
import struct


def load_registered(init_path):
    regs = set()
    pat = re.compile(r"\{\s*0x([0-9A-Fa-f]+),\s*\w+\s*\}")
    for line in open(init_path):
        m = pat.search(line)
        if m:
            regs.add(int(m.group(1), 16))
    return regs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("init_cpp", help="generated <module>_init.cpp with PPCFuncMappings")
    ap.add_argument("--load-base", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--code-start", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--code-end", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--walker-region", action="append", default=[],
                    help="start:end (guest addresses, end exclusive) of a table the walker iterates")
    ap.add_argument("--single-word", type=lambda x: int(x, 0), default=None,
                    help="guest address of a single pointer loaded before a bctrl")
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()

    img = open(args.image, "rb").read()

    def r32(addr):
        off = addr - args.load_base
        if off < 0 or off + 4 > len(img):
            return None
        return struct.unpack_from(">I", img, off)[0]

    def valid(v):
        return (v is not None and v not in (0, 0xFFFFFFFF)
                and v % 4 == 0 and args.code_start <= v < args.code_end)

    regs = load_registered(args.init_cpp)
    print(f"image 0x{len(img):X} bytes | registered functions: {len(regs)}")

    targets = set()
    for spec in args.walker_region:
        s, e = (int(x, 0) for x in spec.split(":"))
        hits = [(a, v) for a in range(s, e, 4) if valid(v := r32(a))]
        targets.update(v for _, v in hits)
        print(f"walker region {s:#x}..{e:#x}: {len(hits)} candidates")

    if args.single_word:
        v = r32(args.single_word)
        print(f"single word at {args.single_word:#x} = "
              f"({v:#x} if v else 'unmapped'), registered={v in regs if v else '-'}")

    unreg = sorted(t for t in targets if t not in regs)
    print(f"targets: {len(targets)} unique | registered {len(targets) - len(unreg)} "
          f"| UNREGISTERED {len(unreg)}")

    os.makedirs(args.out_dir, exist_ok=True)
    out = os.path.join(args.out_dir, "new_tags.txt")
    with open(out, "w") as f:
        for t in unreg:
            f.write(f"0x{t:08X}\n")
    print(f"unregistered targets -> {out}")


if __name__ == "__main__":
    main()
