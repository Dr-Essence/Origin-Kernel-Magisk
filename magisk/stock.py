#!/usr/bin/env python3
"""
Prepares the stock reference from the official images of the phone's build:
  stock.py boot BOOT_IMG OUT_DIR          -> OUT_DIR/Image, OUT_DIR/stock.config
  stock.py vendor-boot VENDOR_BOOT OUT    -> every .ko of the vendor_boot ramdisk into OUT
  stock.py check-image IMAGE RELEASE      -> fails unless IMAGE's banner names RELEASE
"""
import os
import struct
import sys
import zlib

import lz4.block

LZ4_LEGACY = b"\x02\x21\x4c\x18"


def lz4_legacy(data):
    """Decompresses every legacy-LZ4 stream in data (kernels and vendor ramdisks use it)."""
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i:i + 4] != LZ4_LEGACY:
            i += 1
            continue
        i += 4
        while i + 4 <= len(data):
            n = struct.unpack_from("<I", data, i)[0]
            if n == 0x184C2102 or n == 0 or i + 4 + n > len(data):
                break
            out += lz4.block.decompress(data[i + 4:i + 4 + n], uncompressed_size=8 << 20)
            i += 4 + n
    return bytes(out)


def boot(path, out):
    d = open(path, "rb").read()
    assert d[:8] == b"ANDROID!", "not a boot image"
    kernel_size = struct.unpack_from("<I", d, 8)[0]
    version = struct.unpack_from("<I", d, 40)[0]
    assert version >= 3, "unexpected boot header v%d" % version
    kernel = d[4096:4096 + kernel_size]
    image = lz4_legacy(kernel) if kernel[:4] == LZ4_LEGACY else kernel
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "Image"), "wb").write(image)
    start = image.find(b"IKCFG_ST")
    assert start > 0, "no embedded config in the stock kernel"
    config = zlib.decompress(image[start + 8:], 16 + zlib.MAX_WBITS)
    open(os.path.join(out, "stock.config"), "wb").write(config)
    print("stock kernel %d bytes, config %d bytes" % (len(image), len(config)))


def vendor_boot(path, out):
    d = open(path, "rb").read()
    assert d[:8] == b"VNDRBOOT", "not a vendor_boot image"
    page = struct.unpack_from("<I", d, 12)[0]
    ramdisk_size = struct.unpack_from("<I", d, 24)[0]
    header_size = struct.unpack_from("<I", d, 2096)[0]
    start = ((header_size + page - 1) // page) * page
    cpio = lz4_legacy(d[start:start + ramdisk_size])
    os.makedirs(out, exist_ok=True)
    i = n = 0
    while i + 110 <= len(cpio):
        if cpio[i:i + 6] != b"070701":
            i += 1
            continue
        h = cpio[i:i + 110]
        fsz, nsz = int(h[54:62], 16), int(h[94:102], 16)
        name = cpio[i + 110:i + 110 + nsz - 1].decode("utf-8", "replace")
        p = (i + 110 + nsz + 3) & ~3
        data = cpio[p:p + fsz]
        i = (p + fsz + 3) & ~3
        if name.endswith(".ko"):
            open(os.path.join(out, os.path.basename(name)), "wb").write(data)
            n += 1
    print("vendor_boot: %d modules" % n)
    assert n > 0


def check_image(path, release):
    banner = open(path, "rb").read()
    i = banner.find(b"Linux version ")
    line = banner[i:banner.index(b"\n", i)].decode("utf-8", "replace") if i >= 0 else ""
    print(line)
    if release not in line:
        sys.exit("kernel banner does not name %s" % release)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "boot":
        boot(sys.argv[2], sys.argv[3])
    elif cmd == "vendor-boot":
        vendor_boot(sys.argv[2], sys.argv[3])
    elif cmd == "check-image":
        check_image(sys.argv[2], sys.argv[3])
    else:
        sys.exit("unknown command " + cmd)
