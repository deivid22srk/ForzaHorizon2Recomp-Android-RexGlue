#!/usr/bin/env python3
"""Extract the loaded memory image from an Xbox 360 XEX2 file.

Mirrors the XexModule loader of the rexglue-sdk (AES-128-CBC with zero IV +
BASIC block decompression), producing a flat image that starts at the
module's load address (from the security header).

Usage:
    python3 tools/xex_extract.py <file.xex> <out.bin>

Requires: pycryptodome (pip install pycryptodome).

The extracted image is the input of tools/scan_indirect_targets.py, which
finds data-driven indirect call targets (CRT constructor tables, vtables,
jump tables) that the static analyzer cannot reach.
"""
import struct
import sys

from Crypto.Cipher import AES

# Public retail XEX2 master key (same constant used by the SDK loader).
RETAIL_KEY = bytes([0x20, 0xB1, 0x85, 0xA5, 0x9D, 0x28, 0xFD, 0xC3,
                    0x40, 0x58, 0x3F, 0xBB, 0x08, 0x96, 0xBF, 0x91])


def be32(buf, off):
    return struct.unpack_from(">I", buf, off)[0]


def main(xex_path, out_path):
    raw = open(xex_path, "rb").read()
    assert raw[0:4] == b"XEX2", f"bad magic {raw[0:4]!r}"
    header_size = be32(raw, 0x8)
    security_offset = be32(raw, 0x10)
    header_count = be32(raw, 0x14)

    file_format_off = None
    for i in range(header_count):
        off = 0x18 + i * 8
        if be32(raw, off) == 0x000003FF:  # XEX_HEADER_FILE_FORMAT_INFO
            file_format_off = be32(raw, off + 4)
    assert file_format_off is not None, "no FILE_FORMAT_INFO optional header"

    info_size = be32(raw, file_format_off)
    # NOTE: on-disk these are u16 each (encryption @+4, compression @+6).
    encryption = struct.unpack_from(">H", raw, file_format_off + 4)[0]  # 1 = NORMAL
    compression = struct.unpack_from(">H", raw, file_format_off + 6)[0]  # 1 = BASIC
    load_address = be32(raw, security_offset + 0x110)
    aes_key_field = raw[security_offset + 0x150: security_offset + 0x160]
    print(f"encryption={encryption} compression={compression} load=0x{load_address:08X}")

    # Session key = single-block CBC(zero-IV) decrypt with the retail key.
    session_key = AES.new(RETAIL_KEY, AES.MODE_CBC, iv=b"\x00" * 16).decrypt(aes_key_field)
    exe = raw[header_size:]

    if compression == 0:  # NONE
        image = (AES.new(session_key, AES.MODE_CBC, iv=b"\x00" * 16).decrypt(exe)
                 if encryption == 1 else exe)
    elif compression == 1:  # BASIC: blocks of (data_size, zero_size); CBC state persists
        out = bytearray()
        ivec = b"\x00" * 16
        p = 0
        ecb = AES.new(session_key, AES.MODE_ECB)
        for n in range((info_size - 8) // 8):
            data_size = be32(raw, file_format_off + 8 + n * 8)
            zero_size = be32(raw, file_format_off + 12 + n * 8)
            chunk = exe[p:p + data_size]
            p += data_size
            if encryption == 1:
                pt = bytearray()
                for m in range(0, len(chunk) - len(chunk) % 16, 16):
                    blk = ecb.decrypt(chunk[m:m + 16])
                    pt += bytes(a ^ b for a, b in zip(blk, ivec))
                    ivec = chunk[m:m + 16]
                chunk = bytes(pt)
            out += chunk
            out += b"\x00" * zero_size
        image = bytes(out)
    else:
        raise SystemExit(f"unsupported compression {compression} (normal/delta)")

    open(out_path, "wb").write(image)
    print(f"extracted {len(image)} bytes (0x{len(image):X}) -> {out_path} (PE={image[0:2]!r})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
