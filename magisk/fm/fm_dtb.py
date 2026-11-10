#!/usr/bin/env python3
"""
Adds the FM radio's device-tree node to the CMF Phone 1's vendor_boot image.

Why: the phone's FM receiver (in the MT6631 connectivity chip), its firmware, its driver
(fmradio_drv_connac2x.ko) and the audio paths are all there, but the driver only starts when the
device tree has a "mediatek,fm" node, and Nothing commented that node out of mt6878.dts
(NothingOSS/android_kernel_device_modules_6.1_nothing_mt6878, branch mt6878/Tetris/u). This
puts back exactly that node, with Nothing's own values.

How: the node is added to the binary device tree directly. Decompiling to text and compiling
again (dtc) is not safe here: dtc reads "\\00x04" in a string as an octal escape and changes
three strings of the stock tree. Everything else in the image stays byte for byte as stock;
`check` proves it.

  fm_dtb.py patch stock-vendor_boot.img new-vendor_boot.img
  fm_dtb.py check stock-vendor_boot.img new-vendor_boot.img
  fm_dtb.py dump  vendor_boot.img tree.dtb      (the device tree alone, for dtc)
"""
import struct
import sys

FDT_MAGIC = 0xD00DFEED
DT_TABLE_MAGIC = 0xD7B7AB1E
BEGIN_NODE, END_NODE, PROP, NOP, END = 1, 2, 3, 4, 9
GIC_SPI, IRQ_TYPE_LEVEL_HIGH = 0, 4

# Nothing's node, mt6878.dts (commented out there):
#   fm: fm { compatible = "mediatek,fm"; family-id = <0x6983>; host-id = <0x6878>;
#            conn-id = <0x0205>; interrupts = <GIC_SPI 486 IRQ_TYPE_LEVEL_HIGH 0>; };
NODE_NAME = "fm"
NODE_PROPS = [
    ("compatible", b"mediatek,fm\0"),
    ("family-id", struct.pack(">I", 0x6983)),
    ("host-id", struct.pack(">I", 0x6878)),
    ("conn-id", struct.pack(">I", 0x0205)),
    ("interrupts", struct.pack(">4I", GIC_SPI, 486, IRQ_TYPE_LEVEL_HIGH, 0)),
]


def align4(n):
    return (n + 3) & ~3


def vendor_boot_layout(img):
    """(page, header_size, ramdisk_size, dtb_size, dtb_offset) of a v4 vendor_boot."""
    assert img[:8] == b"VNDRBOOT", "not a vendor_boot image"
    version, page = struct.unpack_from("<II", img, 8)
    assert version == 4, "vendor_boot header v%d, expected 4" % version
    ramdisk_size = struct.unpack_from("<I", img, 24)[0]
    header_size, dtb_size = struct.unpack_from("<II", img, 2096)
    pages = lambda n: (n + page - 1) // page * page
    return page, header_size, ramdisk_size, dtb_size, pages(header_size) + pages(ramdisk_size)


def table_entries(table):
    """The DT table (Android's dt_table_header, big endian): its header and its entries."""
    magic, total, hsize, esize, count, eoff, pagesz, ver = struct.unpack_from(">8I", table, 0)
    assert magic == DT_TABLE_MAGIC, "dtb section is not a DT table"
    entries = [list(struct.unpack_from(">8I", table, eoff + i * esize)) for i in range(count)]
    return (magic, total, hsize, esize, count, eoff, pagesz, ver), entries


def fdt_tokens(fdt):
    """Yields (offset, token, name) over the structure block."""
    h = struct.unpack_from(">10I", fdt, 0)
    assert h[0] == FDT_MAGIC
    off_struct, size_struct = h[2], h[9]
    p, end = off_struct, off_struct + size_struct
    while p < end:
        tok = struct.unpack_from(">I", fdt, p)[0]
        at = p
        p += 4
        name = None
        if tok == BEGIN_NODE:
            e = fdt.index(b"\0", p)
            name = fdt[p:e].decode()
            p = align4(e + 1)
        elif tok == PROP:
            ln, _ = struct.unpack_from(">II", fdt, p)
            p = align4(p + 8 + ln)
        yield at, tok, name
        if tok == END:
            return


def add_node(fdt):
    h = list(struct.unpack_from(">10I", fdt, 0))
    off_struct, off_strings, size_strings, size_struct = h[2], h[3], h[8], h[9]
    assert off_strings == off_struct + size_struct, "unexpected block order"
    strings = bytearray(fdt[off_strings:off_strings + size_strings])

    depth, root_end = 0, None
    for at, tok, name in fdt_tokens(fdt):
        if tok == BEGIN_NODE:
            depth += 1
            if depth == 2 and name == NODE_NAME:
                raise SystemExit("an fm node is already there")
        elif tok == END_NODE:
            depth -= 1
            if depth == 0:
                root_end = at
    assert root_end is not None, "root node end not found"

    def name_offset(n):
        key = n.encode() + b"\0"
        i = bytes(strings).find(key)
        while i > 0 and strings[i - 1] != 0:  # must be a whole string, not a suffix
            i = bytes(strings).find(key, i + 1)
        if i < 0:
            i = len(strings)
            strings.extend(key)
        return i

    node = bytearray(struct.pack(">I", BEGIN_NODE) + NODE_NAME.encode() + b"\0")
    node.extend(b"\0" * (align4(len(node)) - len(node)))
    for prop, value in NODE_PROPS:
        node += struct.pack(">III", PROP, len(value), name_offset(prop)) + value
        node.extend(b"\0" * (align4(len(node)) - len(node)))
    node += struct.pack(">I", END_NODE)

    struct_block = fdt[off_struct:root_end] + bytes(node) + fdt[root_end:off_struct + size_struct]
    out = bytearray(fdt[:off_struct]) + struct_block + strings
    h[9] = len(struct_block)                 # size_dt_struct
    h[3] = off_struct + h[9]                 # off_dt_strings
    h[8] = len(strings)                      # size_dt_strings
    h[1] = len(out)                          # totalsize
    struct.pack_into(">10I", out, 0, *h)
    return bytes(out)


def patch(stock_path, out_path):
    img = open(stock_path, "rb").read()
    page, header_size, ramdisk_size, dtb_size, dtb_off = vendor_boot_layout(img)
    table = img[dtb_off:dtb_off + dtb_size]
    th, entries = table_entries(table)
    assert len(entries) == 1, "expected one device tree in vendor_boot, found %d" % len(entries)
    e = entries[0]
    fdt = table[e[1]:e[1] + e[0]]
    new_fdt = add_node(fdt)
    # The table: same header and entry, the tree at the same offset, sizes updated.
    new_table = bytearray(table[:e[1]]) + new_fdt
    e[0] = len(new_fdt)
    struct.pack_into(">8I", new_table, th[5], *e)
    struct.pack_into(">I", new_table, 4, len(new_table))  # total_size
    after = dtb_off + ((dtb_size + page - 1) // page) * page
    new_dtb_padded = bytes(new_table) + b"\0" * (-len(new_table) % page)
    rest = img[after:]
    out = bytearray(img[:dtb_off]) + new_dtb_padded + rest
    struct.pack_into("<I", out, 2100, len(new_table))  # vendor_boot dtb_size
    # Sections after the dtb (ramdisk table, bootconfig) move by whole pages only if the dtb
    # grew past a page boundary; then the image would need rebuilding, which is refused.
    assert len(new_dtb_padded) == ((dtb_size + page - 1) // page) * page, \
        "the device tree grew past a page boundary; not handled"
    assert len(out) == len(img)
    open(out_path, "wb").write(out)
    print("fm node added: device tree %d -> %d bytes, image size unchanged (%d)"
          % (len(fdt), len(new_fdt), len(out)))


def check(stock_path, new_path):
    a, b = open(stock_path, "rb").read(), open(new_path, "rb").read()
    la, lb = vendor_boot_layout(a), vendor_boot_layout(b)
    assert len(a) == len(b), "image sizes differ"
    assert la[:3] == lb[:3] and la[4] == lb[4], "header or ramdisk layout changed"
    assert a[:2100] == b[:2100] and a[2104:la[4]] == b[2104:lb[4]], \
        "header or ramdisk bytes changed"
    page = la[0]
    end_a = la[4] + (la[3] + page - 1) // page * page
    assert a[end_a:] == b[end_a:], "bytes after the device tree changed"
    ta, ea = table_entries(a[la[4]:la[4] + la[3]])
    tb, eb = table_entries(b[lb[4]:lb[4] + lb[3]])
    fa = a[la[4] + ea[0][1]:la[4] + ea[0][1] + ea[0][0]]
    fb = b[lb[4] + eb[0][1]:lb[4] + eb[0][1] + eb[0][0]]
    assert ea[0][2:] == eb[0][2:], "table entry ids changed"
    # The new tree is the stock one with exactly the fm node inserted before the root's end.
    assert add_node(fa) == fb, "device tree differs from stock + fm node"
    print("check passed: header, ramdisk and everything after the device tree are stock;"
          " the device tree is stock plus the fm node only")


def dump(img_path, out_path):
    img = open(img_path, "rb").read()
    _, _, _, dtb_size, dtb_off = vendor_boot_layout(img)
    table = img[dtb_off:dtb_off + dtb_size]
    _, entries = table_entries(table)
    e = entries[0]
    open(out_path, "wb").write(table[e[1]:e[1] + e[0]])


if __name__ == "__main__":
    {"patch": patch, "check": check, "dump": dump}[sys.argv[1]](sys.argv[2], sys.argv[3])
