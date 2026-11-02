/*
 * The whole userspace of the boot test: the kernel must get as far as running this. It prints
 * what the kernel reports about itself and the features the build should have, then powers off.
 */
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/utsname.h>
#include <unistd.h>

static void show(const char *label, const char *path)
{
	char buf[512] = {0};
	FILE *f = fopen(path, "r");

	if (!f) {
		printf("NLP %s: (missing)\n", label);
		return;
	}
	size_t n = fread(buf, 1, sizeof(buf) - 1, f);
	fclose(f);
	while (n && (buf[n - 1] == '\n' || buf[n - 1] == ' '))
		buf[--n] = 0;
	printf("NLP %s: %s\n", label, buf);
}

int main(void)
{
	struct utsname u;

	mount("proc", "/proc", "proc", 0, NULL);
	mount("sysfs", "/sys", "sysfs", 0, NULL);
	mount("securityfs", "/sys/kernel/security", "securityfs", 0, NULL);
	uname(&u);
	printf("NLP-BOOT-OK %s %s\n", u.release, u.machine);
	show("cpus online", "/sys/devices/system/cpu/online");
	show("tcp congestion", "/proc/sys/net/ipv4/tcp_congestion_control");
	show("tcp available", "/proc/sys/net/ipv4/tcp_available_congestion_control");
	show("lsm", "/sys/kernel/security/lsm");
	show("zram algorithms", "/sys/block/zram0/comp_algorithm");
	show("cmdline", "/proc/cmdline");
	fflush(stdout);
	sync();
	reboot(RB_POWER_OFF);
	return 0;
}
