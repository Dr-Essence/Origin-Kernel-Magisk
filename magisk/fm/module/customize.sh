# Installs only where the FM radio can work: a CMF Phone 1 whose device tree has the FM node
# (the FM vendor_boot from Origin-Kernel-Magisk, magisk/fm) and whose vendor has the FM driver.

ui_print "- FM Radio for the CMF Phone 1 (experimental)"
case "$(getprop ro.product.device)$(getprop ro.product.model)" in
  *[Tt]etris*|*A015*) ;;
  *) abort "! Not a CMF Phone 1 ($(getprop ro.product.model)): nothing installed." ;;
esac
if [ ! -d /proc/device-tree/fm ]; then
  abort "! The FM device-tree node is missing: flash the FM vendor_boot first (see magisk/fm/README.md)."
fi
DRIVER=/vendor/lib/modules/fmradio_drv_connac2x.ko
[ -f "$DRIVER" ] || abort "! $DRIVER not found: this Nothing OS build has no FM driver."
ui_print "- FM node and driver found"
set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm "$MODPATH/service.sh" 0 0 0755
