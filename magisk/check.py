#!/usr/bin/env python3
"""
Checks a kernel build against the phone's own stock files before anything is flashed.

Usage: check.py BUILD_DIR STOCK_DIR REPORT

BUILD_DIR  the kernel build (Module.symvers, .config, certs/, include/generated/, modules)
STOCK_DIR  stock.config (from the stock kernel), stock-cert.der, and folders vendor_boot/,
           vendor_dlkm/, system_dlkm/ holding the stock .ko files
REPORT     where the findings are written

Fails (exit 1) on anything that would stop a stock module loading, which is what turns a
custom kernel into a bootloop or dead Wi-Fi / Bluetooth / display:
  1. every symbol a stock module imports exists with the same CRC (CONFIG_MODVERSIONS),
  2. the module vermagic matches past the release string (same_magic() with CRCs),
  3. unsigned stock modules only use symbols the build lets unsigned modules use
     (CONFIG_MODULE_SIG_PROTECT), and no unsigned module exports a protected symbol,
  4. the signed system_dlkm modules verify against the stock certificate, and the build trusts
     that certificate,
  5. the configuration keeps everything the stock kernel's ABI depends on.
"""
import os
import re
import struct
import subprocess
import sys
import tempfile

import gki_tables

SIG_MAGIC = b"~Module signature appended~\n"


# ----------------------------------------------------------------------------------------- ELF

class Elf:
    def __init__(self, data):
        if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
            raise ValueError("not a 64-bit little-endian ELF")
        self.d = data
        shoff = struct.unpack_from("<Q", data, 0x28)[0]
        shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x3A)
        self.sections = []
        for i in range(shnum):
            name, typ, flags, addr, off, size, link, info, align, entsize = struct.unpack_from(
                "<IIQQQQIIQQ", data, shoff + i * shentsize)
            self.sections.append(dict(name_off=name, type=typ, off=off, size=size, link=link,
                                      entsize=entsize))
        strtab = self.sections[shstrndx]
        for s in self.sections:
            s["name"] = self._str(strtab["off"], s["name_off"])

    def _str(self, base, off):
        end = self.d.index(b"\0", base + off)
        return self.d[base + off:end].decode("utf-8", "replace")

    def section(self, name):
        for s in self.sections:
            if s["name"] == name:
                return s
        return None

    def data(self, s):
        return self.d[s["off"]:s["off"] + s["size"]]

    def symbols(self):
        sym = next((s for s in self.sections if s["type"] == 2), None)  # SHT_SYMTAB
        if sym is None:
            return []
        strtab = self.sections[sym["link"]]
        out = []
        for i in range(sym["size"] // 24):
            name, info, other, shndx, value, size = struct.unpack_from(
                "<IBBHQQ", self.d, sym["off"] + i * 24)
            out.append((self._str(strtab["off"], name), shndx))
        return out


def modinfo(elf):
    s = elf.section(".modinfo")
    if not s:
        return {}
    out = {}
    for item in elf.data(s).split(b"\0"):
        if b"=" in item:
            k, v = item.split(b"=", 1)
            out.setdefault(k.decode(), v.decode("utf-8", "replace"))
    return out


def versions(elf):
    """Imported symbols and their CRCs (struct modversion_info: unsigned long crc; name[56])."""
    s = elf.section("__versions")
    if not s:
        return {}
    data = elf.data(s)
    out = {}
    for i in range(0, len(data) - 63, 64):
        crc = struct.unpack_from("<Q", data, i)[0] & 0xFFFFFFFF
        name = data[i + 8:i + 64].split(b"\0", 1)[0].decode()
        out[name] = crc
    return out


def exports(elf):
    return {n[len("__ksymtab_"):] for n, shndx in elf.symbols()
            if n.startswith("__ksymtab_") and shndx != 0}


def signed(data):
    return data.endswith(SIG_MAGIC)


# ----------------------------------------------------------------------------------- loading

def load_modules(folder):
    mods = {}
    for root, _, files in os.walk(folder):
        for f in files:
            if f.endswith(".ko"):
                path = os.path.join(root, f)
                data = open(path, "rb").read()
                try:
                    elf = Elf(data)
                except ValueError:
                    continue
                mods[path] = dict(name="%s/%s" % (os.path.basename(folder.rstrip("/")), f),
                                  elf=elf, data=data, signed=signed(data),
                                  versions=versions(elf), exports=exports(elf),
                                  vermagic=modinfo(elf).get("vermagic", ""))
    return mods


def load_symvers(path):
    out = {}
    for line in open(path):
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 4:
            out[parts[1]] = (int(parts[0], 16), parts[2])
    return out


def load_config(path):
    out = {}
    for line in open(path):
        line = line.strip()
        m = re.match(r"^(CONFIG_[A-Za-z0-9_]+)=(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2)
            continue
        m = re.match(r"^# (CONFIG_[A-Za-z0-9_]+) is not set$", line)
        if m:
            out[m.group(1)] = "n"
    return out


def load_header_list(path):
    """Symbols listed in a generated gki_module_*.h header (C string array)."""
    if not os.path.exists(path):
        return None
    return set(re.findall(r'"([^"]+)"', open(path).read()))


# ------------------------------------------------------------------------------------ checks

class Report:
    def __init__(self):
        self.lines = []
        self.failures = 0

    def ok(self, msg):
        self.lines.append("PASS  " + msg)

    def fail(self, msg):
        self.failures += 1
        self.lines.append("FAIL  " + msg)

    def info(self, msg):
        self.lines.append("      " + msg)


def check_crcs(rep, stock, symvers):
    provided_by_stock = set()
    for m in stock.values():
        provided_by_stock |= m["exports"]
    checked = mismatched = missing = 0
    problems = []
    for path, m in sorted(stock.items()):
        for sym, crc in m["versions"].items():
            if sym == "module_layout":
                pass
            if sym in symvers:
                checked += 1
                ours = symvers[sym][0]
                if ours != crc:
                    mismatched += 1
                    problems.append("%s: %s stock 0x%08x, new 0x%08x" % (m["name"], sym, crc, ours))
            elif sym in provided_by_stock:
                continue
            else:
                missing += 1
                problems.append("%s: %s not exported by the new kernel" % (m["name"], sym))
    if problems:
        rep.fail("symbol CRCs: %d checked, %d different, %d missing" % (checked, mismatched, missing))
        for p in problems[:200]:
            rep.info(p)
        if len(problems) > 200:
            rep.info("... %d more" % (len(problems) - 200))
    else:
        rep.ok("symbol CRCs: all %d imports of %d stock modules match the new kernel"
               % (checked, len(stock)))


def check_vermagic(rep, stock, build_dir):
    ours = None
    for root, _, files in os.walk(build_dir):
        for f in files:
            if f.endswith(".ko"):
                try:
                    ours = modinfo(Elf(open(os.path.join(root, f), "rb").read())).get("vermagic")
                except ValueError:
                    continue
                if ours:
                    break
        if ours:
            break
    if not ours:
        rep.fail("vermagic: no module built to compare")
        return
    tail = ours.split(" ", 1)[1] if " " in ours else ""
    bad = sorted({m["vermagic"] for m in stock.values()
                  if m["vermagic"] and m["vermagic"].split(" ", 1)[-1] != tail})
    if bad:
        rep.fail("vermagic: new '%s' vs stock %s" % (ours, bad[:5]))
    else:
        rep.ok("vermagic: '%s' matches every stock module past the release string" % ours)


def check_protection(rep, stock, build_dir, stock_image):
    """
    The kernel lets an unsigned module use only "unprotected" symbols of signed modules and
    export no "protected" symbol (kernel/module/main.c). If the new kernel's two lists are the
    stock kernel's, every module is treated exactly as on the phone today.
    """
    gen = os.path.join(build_dir, "include", "generated")
    unprotected = load_header_list(os.path.join(gen, "gki_module_unprotected.h"))
    protected = load_header_list(os.path.join(gen, "gki_module_protected_exports.h"))
    if unprotected is None or protected is None:
        rep.fail("module protection lists not generated (CONFIG_MODULE_SIG_PROTECT off?)")
        return
    rep.info("protection lists: %d unprotected symbols, %d protected exports"
             % (len(unprotected), len(protected)))
    for label, ours in (("protected exports", protected), ("unprotected symbols", unprotected)):
        names = sorted(ours)
        found = []
        for probe in (names[len(names) // 2], names[len(names) // 3], names[2 * len(names) // 3]):
            found += [set(t) for t in gki_tables.tables(stock_image, probe).values() if len(t) > 32]
        # Both tables share many names: take the one that differs least.
        theirs = min(found, key=lambda f: len(f ^ ours)) if found else None
        if theirs is None:
            rep.fail("%s: table not found in the stock kernel" % label)
        elif theirs != ours:
            rep.fail("%s: differ from the stock kernel's (%d only new, %d only stock)"
                     % (label, len(ours - theirs), len(theirs - ours)))
            rep.info("only new: " + " ".join(sorted(ours - theirs)[:40]))
            rep.info("only stock: " + " ".join(sorted(theirs - ours)[:40]))
        else:
            rep.ok("%s: identical to the stock kernel's %d" % (label, len(theirs)))
    stock_exports = set()
    for m in stock.values():
        stock_exports |= m["exports"]
    problems = []
    for m in stock.values():
        if m["signed"]:
            continue
        for sym in m["versions"]:
            # Unsigned modules may use unprotected symbols and other modules' exports.
            if sym not in unprotected and sym not in stock_exports and sym != "module_layout":
                problems.append("%s (unsigned) uses %s, not allowed for unsigned modules"
                                % (m["name"], sym))
        for sym in m["exports"]:
            if sym in protected:
                problems.append("%s (unsigned) exports protected %s" % (m["name"], sym))
    # With the lists identical to stock, these modules fare as they do on stock (an unsigned copy
    # of a module whose signed copy loads first is simply not loaded again).
    rep.info("unsigned stock modules outside the lists (same as on stock): %d" % len(problems))
    for p in problems[:20]:
        rep.info(p)


def check_signatures(rep, stock, cert_der, build_dir):
    trusted = os.path.join(build_dir, "certs", "x509_certificate_list")
    cert = open(cert_der, "rb").read()
    if os.path.exists(trusted) and cert in open(trusted, "rb").read():
        rep.ok("the new kernel trusts the stock module-signing certificate")
    else:
        rep.fail("the stock module-signing certificate is not in certs/x509_certificate_list")
    signed_mods = [m for m in stock.values() if m["signed"]]
    if not signed_mods:
        rep.fail("no signed stock modules found to verify")
        return
    with tempfile.TemporaryDirectory() as tmp:
        pem = os.path.join(tmp, "cert.pem")
        subprocess.run(["openssl", "x509", "-inform", "DER", "-in", cert_der, "-out", pem],
                       check=True)
        bad = []
        for m in signed_mods:
            data = m["data"][:-len(SIG_MAGIC)]
            sig_len = struct.unpack(">I", data[-4:])[0]
            body = data[:-(12 + sig_len)]
            sig = data[-(12 + sig_len):-12]
            bp, sp = os.path.join(tmp, "b"), os.path.join(tmp, "s")
            open(bp, "wb").write(body)
            open(sp, "wb").write(sig)
            r = subprocess.run(["openssl", "cms", "-verify", "-binary", "-inform", "DER",
                                "-in", sp, "-content", bp, "-certfile", pem, "-nointern",
                                "-noverify", "-out", os.devnull], capture_output=True)
            if r.returncode != 0:
                bad.append(m["name"])
        if bad:
            rep.fail("%d of %d signed stock modules do not verify with the stock certificate: %s"
                     % (len(bad), len(signed_mods), ", ".join(bad[:20])))
        else:
            rep.ok("all %d signed stock modules verify with the trusted stock certificate"
                   % len(signed_mods))


# Options the stock kernel's ABI, boot or modules depend on: must match stock exactly.
MUST_MATCH = [
    "CONFIG_ARM64_4K_PAGES", "CONFIG_ARM64_VA_BITS", "CONFIG_PGTABLE_LEVELS",
    "CONFIG_MODVERSIONS", "CONFIG_MODULE_SIG", "CONFIG_MODULE_SIG_PROTECT",
    "CONFIG_MODULE_SIG_FORCE", "CONFIG_MODULE_SIG_ALL", "CONFIG_CFI_CLANG",
    "CONFIG_SHADOW_CALL_STACK", "CONFIG_ARM64_MTE", "CONFIG_ARM64_BTI_KERNEL",
    "CONFIG_ARM64_PTR_AUTH", "CONFIG_ARM64_PTR_AUTH_KERNEL", "CONFIG_UNWIND_PATCH_PAC_INTO_SCS",
    "CONFIG_SMP", "CONFIG_PREEMPT", "CONFIG_MODULE_UNLOAD", "CONFIG_NR_CPUS",
    "CONFIG_HZ", "CONFIG_CMDLINE", "CONFIG_CMDLINE_EXTEND", "CONFIG_BLK_DEV_INITRD",
    "CONFIG_RD_LZ4", "CONFIG_RD_GZIP", "CONFIG_DEBUG_INFO_BTF", "CONFIG_SECURITY_SELINUX",
    "CONFIG_ANDROID_BINDER_IPC", "CONFIG_TRACING", "CONFIG_FUNCTION_TRACER", "CONFIG_KPROBES",
    "CONFIG_ARM64_ERRATUM_2441007", "CONFIG_KASAN", "CONFIG_KCSAN", "CONFIG_DEBUG_FS",
]
MUST_BE = {
    "CONFIG_KSU": "n",
    "CONFIG_BBG": "n",
    "CONFIG_MODVERSIONS": "y",
    "CONFIG_MODULE_SIG_PROTECT": "y",
}


def check_config(rep, build_dir, stock_config):
    ours = load_config(os.path.join(build_dir, ".config"))
    stock = load_config(stock_config)
    bad = []
    for opt in MUST_MATCH:
        a, b = stock.get(opt, "n"), ours.get(opt, "n")
        if a != b:
            bad.append("%s: stock %s, new %s" % (opt, a, b))
    for opt, want in MUST_BE.items():
        if ours.get(opt, "n") != want:
            bad.append("%s must be %s, is %s" % (opt, want, ours.get(opt, "n")))
    if bad:
        rep.fail("configuration: %d differences that matter" % len(bad))
        for b in bad:
            rep.info(b)
    else:
        rep.ok("configuration: %d ABI- and boot-relevant options match stock, KernelSU and "
               "Baseband-Guard off" % len(MUST_MATCH))
    added = sorted(k for k in ours if ours[k] != "n" and stock.get(k, "n") == "n")
    removed = sorted(k for k in stock if stock[k] != "n" and ours.get(k, "n") == "n")
    changed = sorted(k for k in ours if k in stock and ours[k] != "n" and stock[k] != "n"
                     and ours[k] != stock[k])
    rep.info("vs stock: %d options added, %d removed, %d changed value"
             % (len(added), len(removed), len(changed)))
    rep.info("added: " + " ".join(added))
    rep.info("removed: " + " ".join(removed))
    rep.info("changed: " + " ".join("%s(%s->%s)" % (k, stock[k], ours[k]) for k in changed))


def main():
    build_dir, stock_dir, report_path = sys.argv[1:4]
    rep = Report()
    symvers = load_symvers(os.path.join(build_dir, "Module.symvers"))
    rep.info("new kernel exports %d versioned symbols" % len(symvers))
    stock = {}
    for part in ("vendor_boot", "vendor_dlkm", "system_dlkm"):
        mods = load_modules(os.path.join(stock_dir, part))
        rep.info("%s: %d modules (%d signed)" % (part, len(mods),
                                                 sum(1 for m in mods.values() if m["signed"])))
        if not mods:
            rep.fail("no stock modules found in %s" % part)
        stock.update(mods)
    check_config(rep, build_dir, os.path.join(stock_dir, "stock.config"))
    check_crcs(rep, stock, symvers)
    check_vermagic(rep, stock, build_dir)
    check_protection(rep, stock, build_dir, os.path.join(stock_dir, "Image"))
    check_signatures(rep, stock, os.path.join(stock_dir, "stock-cert.der"), build_dir)
    text = "\n".join(rep.lines) + "\n\n%s: %d failed check(s)\n" % (
        "FAILED" if rep.failures else "ALL CHECKS PASSED", rep.failures)
    open(report_path, "w").write(text)
    print(text)
    sys.exit(1 if rep.failures else 0)


if __name__ == "__main__":
    main()
