#!/usr/bin/env python3
"""
Reads the GKI module-protection tables out of a kernel Image: gki_protected_exports_symbols and
gki_unprotected_symbols are sorted arrays of fixed-width, NUL-padded names (see
kernel/module/gki_module.c). Given one name known to be in a table, the table is walked from
there in both directions at its stride.
"""
import re
import sys

NAME = re.compile(rb"^[A-Za-z_][A-Za-z0-9_.$]*$")


def entry(d, pos, width):
    raw = d[pos:pos + width]
    name = raw.split(b"\0", 1)[0]
    if not name or not NAME.match(name) or raw[len(name):].strip(b"\0"):
        return None
    return name.decode()


def table_at(d, pos):
    """The table holding the name that starts at pos: (width, names) or None."""
    end = d.find(b"\0", pos, pos + 256)
    if end < 0 or not NAME.match(d[pos:end]):
        return None
    name = d[pos:end].decode()
    for width in range(len(name) + 1, 257):
        nxt, prv = entry(d, pos + width, width), entry(d, pos - width, width)
        if nxt and prv and prv < name < nxt:
            names = [name]
            p = pos - width
            while (n := entry(d, p, width)) and n < names[0]:
                names.insert(0, n)
                p -= width
            p = pos + width
            while (n := entry(d, p, width)) and n > names[-1]:
                names.append(n)
                p += width
            return width, names
    return None


def tables(image, probe):
    d = open(image, "rb").read()
    found = {}
    for m in re.finditer(re.escape(probe.encode()) + b"\0", d):
        t = table_at(d, m.start())
        if t:
            found[t[0]] = t[1]
    return found


if __name__ == "__main__":
    for width, names in sorted(tables(sys.argv[1], sys.argv[2]).items()):
        print(width, len(names), names[0], names[-1])
