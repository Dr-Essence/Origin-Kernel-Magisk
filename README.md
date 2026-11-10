# Origin Kernel for the CMF Phone 1, Magisk edition

**For the CMF Phone 1 (codename `Tetris`) only, on Nothing OS B4.1-260615-1652.** Not for the CMF
Phone 2 Pro, the Phone (3a) Lite or any other phone, and not for any other Nothing OS build: the
kernel is checked against this exact build's stock images, and after an OTA it has to be built
again for the new one.

This fork builds [Origin Kernel](https://github.com/samakshkambxj/origin-kernel) by
samakshkambxj (release **Tetris-v1**, Linux 6.1.162) for phones rooted with **Magisk**, and adds
the CMF Phone 1's FM radio, which Nothing switched off. For Origin itself, its other devices and
its KernelSU builds, see [the original repository](https://github.com/samakshkambxj/origin-kernel).

> [!WARNING]
> Flashing a kernel or a vendor_boot can leave a phone unable to start until the stock image is
> flashed back. Keep your stock images (and a copy off the phone) before changing anything. The
> steps below always include the way back; your data is never touched by them.

## What is in this repository

| Part | Where | What it gives |
| --- | --- | --- |
| Magisk kernel | [`magisk/`](magisk/README.md), workflow *Tetris Magisk kernel* | Origin's Tetris-v1 kernel with Magisk as the only root |
| FM radio | [`magisk/fm/`](magisk/fm/README.md), workflow *FM radio vendor_boot* | the phone's own FM receiver back on (experimental) |

There are no releases: every build is an artifact of its GitHub Actions run (Actions tab, the
latest green run, *Artifacts*).

## Magisk kernel

Everything Origin adds stays (CASS scheduler, BBRv3, ThinLTO, ZRAM LZ4, IPv6 NAT, Droidspaces),
with three changes:

| Change | Why |
| --- | --- |
| KernelSU-Next and SUSFS off | Magisk (in `init_boot`) stays the only root; two root systems conflict |
| Baseband-Guard off | it denies root writes to boot partitions, which Magisk's *Direct install* needs |
| the stock module-signing certificate trusted | Google-signed `system_dlkm` modules keep their signed status |

Before anything is published, every build is checked against the official images of the exact
phone build: module symbol CRCs, vermagic, module protection lists, signatures, configuration, a
QEMU boot test and the packing into the stock `boot.img`. Details and flashing steps:
[`magisk/README.md`](magisk/README.md).

Only `boot` is replaced; Magisk lives in `init_boot` and stays.

## FM radio (experimental)

The CMF Phone 1's connectivity chip (MT6631) has an FM receiver, and its firmware, driver and
audio paths are all on the phone. Nothing commented the receiver's device-tree node out of the
phone's device tree, so the driver never starts. The *FM radio vendor_boot* workflow puts back
exactly Nothing's node in the stock `vendor_boot` (nothing else changes, checked byte for byte)
and builds `fmscan`, a tool that measures the FM band.

State (10 Nov 2026): on the phone, the driver starts with Nothing's values and `/dev/fm`
appears; `fmscan` switches the receiver on and finds the strongest local stations just at the
station threshold with nothing plugged in. An antenna through wired headphones on a passive
USB-C adapter, and listening (an FM Radio app), are next. Details, flashing (also from the phone
itself, as root) and the way back: [`magisk/fm/README.md`](magisk/fm/README.md).

## Credits

- **Nothing**, for phones that can be opened up: an unlockable bootloader, and the kernel and
  device sources published as [NothingOSS](https://github.com/NothingOSS). Without them neither
  this kernel's checks nor the FM radio's device-tree values would exist. (Independent project,
  not made or endorsed by Nothing.)

- **Origin Kernel**: [samakshkambxj](https://github.com/samakshkambxj/origin-kernel), and the
  projects it credits (Sultan kernels, CASS and the rest; see its README)
- **Magisk**: [topjohnwu](https://github.com/topjohnwu/Magisk)
- **Stock images** for the checks: [spike0en/nothing_archive](https://github.com/spike0en/nothing_archive)
- **Device tree and FM driver sources**: Nothing
  ([NothingOSS](https://github.com/NothingOSS/android_kernel_device_modules_6.1_nothing_mt6878))
  and MediaTek (`connectivity/fmradio`, as published in
  [MiCode/MTK_kernel_modules](https://github.com/MiCode/MTK_kernel_modules))

Licence: GPL v2, as the Linux kernel.
