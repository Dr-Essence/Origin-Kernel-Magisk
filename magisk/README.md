# Origin Kernel for Magisk (CMF Phone 1, Tetris)

[Origin Kernel](https://github.com/samakshkambxj/origin-kernel)'s **Tetris-v1** release
(Linux 6.1.162, built for Nothing OS **B4.1-260615-1652**), built for phones rooted with
**Magisk**: everything Origin adds (CASS scheduler, BBRv3, ThinLTO, ZRAM LZ4, IPv6 NAT,
Droidspaces) with three changes:

| Change | Why |
| --- | --- |
| KernelSU-Next and SUSFS off | Magisk (in `init_boot`) stays the only root; two root systems conflict |
| Baseband-Guard off | It denies root writes to boot partitions, which Magisk's *Direct install* needs |
| The stock module-signing certificate trusted | Google-signed `system_dlkm` modules keep their signed status under `CONFIG_MODULE_SIG_PROTECT` |

The source is Origin's own tag, fetched by the build; this repository only holds the
configuration, the checks and the workflow (`.github/workflows/tetris-magisk.yml`).

## What every build is checked against

The official images of the exact phone build (from
[nothing_archive](https://github.com/spike0en/nothing_archive), checksums pinned):

1. **Module CRCs**: every symbol imported by every stock module (vendor_boot, vendor_dlkm,
   system_dlkm) exists in the new kernel with the same CRC.
2. **vermagic** matches past the release string.
3. **Module protection**: unsigned stock modules only use what unsigned modules may use.
4. **Signatures**: the signed stock modules verify with the stock certificate, which the new
   kernel trusts.
5. **Configuration**: the ABI- and boot-relevant options equal the stock kernel's.
6. **QEMU boot** on 8 arm64 CPUs to userspace, with no panic or oops.
7. **Packing** into the stock `boot.img` with the built kernel byte-identical inside.

The workflow publishes nothing when a check fails. The report is `report.txt` in the build's
artifact.

## Flashing (Magisk stays)

The kernel lives in `boot`; Magisk lives in `init_boot`. Only `boot` is replaced.

1. Keep your current boot image (root shell):
   `dd if=/dev/block/by-name/boot_a of=/sdcard/boot_a-stock.img` (`_a` or `_b`: your active slot,
   `getprop ro.boot.slot_suffix`). Copy it to your PC.
2. Reboot to the bootloader: `adb reboot bootloader`.
3. Try it once **without flashing**: `fastboot boot new-boot.img`. If the phone starts and works
   (Wi-Fi, Bluetooth, camera, root), flash it: `fastboot flash boot_a new-boot.img`. If the
   bootloader refuses `fastboot boot`, flash it directly; step 4 is the way back.
4. If anything is wrong: `fastboot flash boot_a boot_a-stock.img`. Your data is never touched.

Only for Nothing OS **B4.1-260615-1652**. After an OTA, rebuild for the new build.
