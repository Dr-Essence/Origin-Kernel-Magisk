/*
 * fmscan: does the CMF Phone 1's FM receiver hear stations, and through which antenna path?
 *
 * Talks to MediaTek's FM driver (/dev/fm, fmradio_drv_connac2x.ko) with its own ioctls, laid
 * out as in MediaTek's connectivity/fmradio/inc/fm_ioctl.h and fm_main.h:
 *   FM_IOCTL_POWERUP          receiver on, at 87.5 MHz, Europe band, 100 kHz steps
 *   FM_IOCTL_ANA_SWITCH       0: long antenna (the earphone cable), 1: short antenna
 *   FM_IOCTL_SOFT_MUTE_TUNE   tune one frequency and measure it (what MediaTek's own scan uses):
 *                             RSSI, and "valid" if every quality value passes fm_cust.cfg
 *   FM_IOCTL_POWERDOWN        receiver off (also on Ctrl-C and on any error)
 * Nothing is played: it only measures. Run as root: su -c ./fmscan
 */
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define FM_IOC_MAGIC 0xf5
/* MediaTek declares the argument type as a pointer, so the encoded size is a pointer's. */
#define FM_IOCTL_POWERUP        _IOWR(FM_IOC_MAGIC, 0, void *)
#define FM_IOCTL_POWERDOWN      _IOWR(FM_IOC_MAGIC, 1, void *)
#define FM_IOCTL_GETCHIPID      _IOWR(FM_IOC_MAGIC, 10, void *)
#define FM_IOCTL_ANA_SWITCH     _IOWR(FM_IOC_MAGIC, 30, void *)
#define FM_IOCTL_SOFT_MUTE_TUNE _IOWR(FM_IOC_MAGIC, 63, void *)

struct fm_tune_parm {             /* fm_main.h */
    unsigned char err;
    unsigned char band;           /* 1: 87.5-108 MHz */
    unsigned char space;          /* 1: 100 kHz */
    unsigned char hilo;
    unsigned char deemphasis;     /* 0: 50 us (Europe) */
    unsigned short freq;          /* 10 kHz units: 8750 = 87.5 MHz */
};

struct fm_softmute_tune_t {       /* fm_main.h */
    int32_t rssi;
    unsigned short freq;
    int32_t valid;
};

#define FREQ_LOW 8750
#define FREQ_HIGH 10800
#define STEP 10                   /* 100 kHz */
#define RSSI_TH -296              /* fm_cust.cfg FM_RX_RSSI_TH_LONG / _SHORT on the phone */
#define CHANNELS ((FREQ_HIGH - FREQ_LOW) / STEP + 1)

static int fd = -1;
static volatile sig_atomic_t stop;

static void power_down(void)
{
    if (fd >= 0) {
        int32_t type = 0;   /* RX */
        ioctl(fd, FM_IOCTL_POWERDOWN, &type);
        close(fd);
        fd = -1;
    }
}

static void on_signal(int sig)
{
    (void)sig;
    stop = 1;
}

static void scan(int antenna, const char *name)
{
    int32_t ana = antenna;
    int32_t rssi[CHANNELS], valid[CHANNELS];
    int count = 0, measured = 0;

    if (ioctl(fd, FM_IOCTL_ANA_SWITCH, &ana) < 0)
        printf("  antenna switch to %s refused: %s (measuring anyway)\n", name, strerror(errno));
    printf("\n%s antenna:\n", name);
    for (int i = 0; i < CHANNELS && !stop; i++) {
        struct fm_softmute_tune_t t = { .freq = (unsigned short)(FREQ_LOW + i * STEP) };
        if (ioctl(fd, FM_IOCTL_SOFT_MUTE_TUNE, &t) < 0) {
            rssi[i] = -9999;
            valid[i] = 0;
            continue;
        }
        rssi[i] = t.rssi;
        valid[i] = t.valid;
        measured++;
        if (t.valid)
            count++;
    }
    if (!measured) {
        printf("  no frequency could be measured (%s)\n", strerror(errno));
        return;
    }
    /* The strongest 15, best first. */
    int shown[CHANNELS] = { 0 };
    printf("  %d of %d frequencies measured; %d pass the driver's station test\n",
           measured, CHANNELS, count);
    printf("  strongest (RSSI is the chip's raw value; the station threshold is %d):\n", RSSI_TH);
    for (int n = 0; n < 15; n++) {
        int best = -1;
        for (int i = 0; i < CHANNELS; i++)
            if (!shown[i] && rssi[i] > -9999 && (best < 0 || rssi[i] > rssi[best]))
                best = i;
        if (best < 0)
            break;
        shown[best] = 1;
        int f = FREQ_LOW + best * STEP;
        printf("    %3d.%d MHz  rssi %5d  %s\n", f / 100, (f % 100) / 10, rssi[best],
               valid[best] ? "STATION" : "");
    }
    int floor_sum = 0, floor_n = 0;
    for (int i = 0; i < CHANNELS; i++)
        if (rssi[i] > -9999) {
            floor_sum += rssi[i];
            floor_n++;
        }
    printf("  average over the band: %d\n", floor_n ? floor_sum / floor_n : 0);
}

int main(void)
{
    signal(SIGINT, on_signal);
    signal(SIGTERM, on_signal);
    fd = open("/dev/fm", O_RDWR);
    if (fd < 0) {
        printf("cannot open /dev/fm: %s (driver loaded? run as root?)\n", strerror(errno));
        return 1;
    }
    unsigned short chip = 0;
    if (ioctl(fd, FM_IOCTL_GETCHIPID, &chip) == 0)
        printf("chip id 0x%04x\n", chip);

    struct fm_tune_parm p = { .band = 1, .space = 1, .hilo = 0, .deemphasis = 0,
                              .freq = FREQ_LOW };
    if (ioctl(fd, FM_IOCTL_POWERUP, &p) < 0) {
        printf("power up failed: %s (err %d); see dmesg | grep -i fm\n", strerror(errno), p.err);
        close(fd);
        return 1;
    }
    printf("receiver on (err %d)\n", p.err);
    scan(0, "long (earphone cable)");
    if (!stop)
        scan(1, "short (inside the phone)");
    power_down();
    printf("\nreceiver off\n");
    return 0;
}
