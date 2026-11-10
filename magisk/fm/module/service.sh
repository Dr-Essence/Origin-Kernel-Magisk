#!/system/bin/sh
# At each boot: load MediaTek's FM driver (it makes /dev/fm from the FM device-tree node; the
# phone's own scripts load it only in factory mode) and grant the FM app the runtime permissions
# its 2016 code never asks for (it was written as a system app for Android 5).
MODDIR=${0%/*}
LOG=$MODDIR/fm.log

until [ "$(getprop sys.boot_completed)" = 1 ]; do sleep 2; done
sleep 5
{
  echo "boot $(date)"
  if ! grep -q '^fmradio_drv_connac2x ' /proc/modules; then
    if [ -d /proc/device-tree/fm ]; then
      insmod /vendor/lib/modules/fmradio_drv_connac2x.ko && echo "driver loaded" \
        || echo "driver load failed"
    else
      echo "no FM device-tree node: driver not loaded"
    fi
  fi
  ls -lZ /dev/fm 2>&1
  for p in RECORD_AUDIO WRITE_EXTERNAL_STORAGE READ_EXTERNAL_STORAGE POST_NOTIFICATIONS; do
    pm grant com.android.fmradio android.permission.$p 2>&1 && echo "granted $p"
  done
} > "$LOG" 2>&1
