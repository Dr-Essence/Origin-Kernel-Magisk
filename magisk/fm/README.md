# FM radio on the CMF Phone 1 (experimental)

The CMF Phone 1 has an FM receiver that Nothing switched off. This folder puts back the one
missing piece, the device-tree node, so the driver can start. Whether stations can be received
depends on an antenna path, which is not known yet: that is what the test at the end finds out.

## What was found (Nothing OS B4.1-260615-1652)

| Part | State | Evidence |
| --- | --- | --- |
| FM receiver | present | MT6631 connectivity chip: `vendor.connsys.fm.adie.chipid = 0x6631`; the kernel reads its FM id at boot (`get adie [FM]=[0x6631]`) |
| Firmware | present | `/vendor/firmware/mt6631_fm_v1_patch.bin`, `mt6631_fm_v1_coeff.bin`, `fm_cust.cfg` |
| Driver | present, not loaded | `/vendor_dlkm/lib/modules/fmradio_drv_connac2x.ko` (depends on `conninfra`); loaded only by MediaTek's factory scripts (`factory_init` / `meta_init`) |
| Audio paths | present | `audio_policy_configuration.xml`: `AUDIO_DEVICE_IN_FM_TUNER`, `AUDIO_DEVICE_OUT_FM`, routes to every output |
| Device-tree node | **removed** | Nothing's `mt6878.dts` has the `fm` node commented out ([NothingOSS/android_kernel_device_modules_6.1_nothing_mt6878](https://github.com/NothingOSS/android_kernel_device_modules_6.1_nothing_mt6878), branch `mt6878/Tetris/u`) |
| FM app and libraries | removed | no `libfmjni`, no FM app; `MtkSystemServiceRegistry: Exception while getting FmRadioPackageManager class` |

Loaded by hand (`insmod`), the driver starts (`mt_fm_init done`, chip `adie=0x6631`) but makes
no `/dev/fm`: it is built with `FM_DTS_PROBE` (MediaTek's `connectivity/fmradio/Kbuild.include`,
for connac2x), so it waits for a `mediatek,fm` node, and reads from it what it needs to reach the
chip: `family-id`, `host-id`, `conn-id` (which registers, `fm_register_plat` in
`plat/conn_infra.c`) and its interrupt. A device without those values would point the driver at
the wrong registers, so the node has to be Nothing's own:

```
fm {
	compatible = "mediatek,fm";
	family-id = <0x6983>;
	host-id = <0x6878>;
	conn-id = <0x0205>;
	interrupts = <GIC_SPI 486 IRQ_TYPE_LEVEL_HIGH 0>;
};
```

Interrupt 486 is used by no other node of the stock tree.

## Why vendor_boot

The kernel cannot add the node while running: GKI kernels are built without device-tree overlays
(`CONFIG_OF_OVERLAY` is off in `gki_defconfig`, and no overlay function is in the symbol lists
modules may use). The phone's base device tree is in `vendor_boot` (one tree, `model = "MT6878"`),
so the node goes there.

`fm_dtb.py` adds it to the binary tree directly. Decompiling with `dtc` and compiling again is
not safe for this tree: `dtc` reads `\00x04` in a string as an octal escape and silently changes
three strings (found while testing, `SSPM_SWPM_CPU__CORE_PMU_AI_GROUP0..2`). The workflow
(`.github/workflows/fm-vendor-boot.yml`) checks the result two ways: everything but the device
tree is byte-identical to stock, and `dtc`'s view of the new tree differs from stock by exactly
the 8 lines of the node.

## Flashing (undone by flashing the stock vendor_boot back)

1. Check that your vendor_boot is the stock one this was made from (root shell, your active slot
   from `getprop ro.boot.slot_suffix`):
   `sha256sum /dev/block/by-name/vendor_boot_a` must print
   `9e55fe1a7eb64ef3cf0fc802180c4d260b4a9d53ad5b2f59847343d581c68b44`.
   If it does not, stop: the image would not match your phone.
2. Keep a copy: `dd if=/dev/block/by-name/vendor_boot_a of=/sdcard/vendor_boot_a-stock.img`,
   and copy it to your PC.
3. `adb reboot bootloader`, then `fastboot flash vendor_boot_a fm-vendor_boot.img`, then
   `fastboot reboot`. (`fastboot boot` cannot try a vendor_boot without flashing.)
4. If the phone does not start or anything is wrong:
   `fastboot flash vendor_boot_a vendor_boot_a-stock.img`. Data is never touched.

Nothing loads the FM driver at boot, so with the node in place the phone runs as before until
the driver is loaded by hand.

## Test

```
ls /proc/device-tree/fm
su -c 'insmod /vendor/lib/modules/fmradio_drv_connac2x.ko'
su -c 'ls -l /dev/fm; dmesg | grep -i "fm" | tail -40'
```

The driver should log `mt_fm_probe`, `current compatible:mediatek,fm` and
`family-id:0x6983 host_id:0x6878 conn_id:0x0205 irq_num:...`, and `/dev/fm` should appear
(owner `media`, from `ueventd.rc`). A reboot unloads the driver.

Next: a small tool that powers the receiver on through `/dev/fm`, scans 87.5-108 MHz and
prints each station's signal, once with nothing plugged in and once with wired USB-C earphones:
that answers whether there is an antenna.

## Status

- Not tested on the phone yet: the flash, the probe, `/dev/fm`.
- The antenna is unknown. Nothing removed FM throughout, likely because the phone has no
  headphone jack; reception may be weak or none.
