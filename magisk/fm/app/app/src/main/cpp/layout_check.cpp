/*
 * Build-time proof that the app's structures match the CMF Phone 1's FM driver byte for byte.
 *
 * The driver copies these structures in and out of the app with fixed sizes, so a difference
 * means either garbage in a field or a refused call. The driver's definitions below are copied
 * from MediaTek's connectivity/fmradio/inc/fm_main.h and fm_rds.h (as published in
 * MiCode/MTK_kernel_modules, the source of fmradio_drv_connac2x.ko); every size and field offset
 * must equal the app's (fm.h), or this file does not compile. No code is generated.
 */
#include <cstddef>
#include "fmr.h"

namespace drv {
struct fm_tune_parm { unsigned char err, band, space, hilo, deemphasis; unsigned short freq; };
struct fm_seek_parm { unsigned char err, band, space, hilo, seekdir, seekth; unsigned short freq; };
struct fm_softmute_tune_t { signed int rssi; unsigned short freq; signed int valid; };
struct fm_cqi { signed int ch, rssi, reserve; };
struct fm_cqi_req { unsigned short ch_num; signed int buf_size; signed char *cqi_buf; };
struct rds_ct_t { unsigned short Month, Day, Year, Hour, Minute;
    unsigned char Local_Time_offset_signbit, Local_Time_offset_half_hour; };
struct rds_flag_t { unsigned char TP, TA, Music, Stereo, Artificial_Head, Compressed, Dynamic_PTY,
    Text_AB; unsigned int flag_status; };
struct rds_af_t { signed short AF_Num; signed short AF[2][25];
    unsigned char Addr_Cnt, isMethod_A, isAFNum_Get; };
struct rds_ps_t { unsigned char PS[4][8]; unsigned char Addr_Cnt; };
struct rds_rt_t { unsigned char TextData[4][64]; unsigned char GetLength, isRTDisplay, TextLength,
    isTypeA, BufCnt; unsigned short Addr_Cnt; };
struct rds_group_cnt_t { unsigned int total; unsigned int groupA[16]; unsigned int groupB[16]; };
struct rds_t { rds_ct_t CT; rds_flag_t RDSFlag; unsigned short PI; unsigned char Switch_TP, PTY;
    rds_af_t AF_Data, AFON_Data; unsigned char Radio_Page_Code;
    unsigned short Program_Item_Number_Code; unsigned char Extend_Country_Code;
    unsigned short Language_Code; rds_ps_t PS_Data; unsigned char PS_ON[8]; rds_rt_t RT_Data;
    unsigned short event_status; rds_group_cnt_t gc; };
}

#define SAME_SIZE(app, d) static_assert(sizeof(app) == sizeof(drv::d), #app " size differs from the driver's " #d)
#define SAME_FIELD(app, d, f) static_assert(offsetof(app, f) == offsetof(drv::d, f), #app "." #f " offset differs")

SAME_SIZE(struct fm_tune_parm, fm_tune_parm);
SAME_FIELD(struct fm_tune_parm, fm_tune_parm, deemphasis);
SAME_FIELD(struct fm_tune_parm, fm_tune_parm, freq);
SAME_SIZE(struct fm_seek_parm, fm_seek_parm);
SAME_FIELD(struct fm_seek_parm, fm_seek_parm, freq);
SAME_SIZE(struct fm_softmute_tune_t, fm_softmute_tune_t);
SAME_FIELD(struct fm_softmute_tune_t, fm_softmute_tune_t, freq);
SAME_FIELD(struct fm_softmute_tune_t, fm_softmute_tune_t, valid);
SAME_SIZE(struct fm_cqi, fm_cqi);
SAME_SIZE(struct fm_cqi_req, fm_cqi_req);
SAME_FIELD(struct fm_cqi_req, fm_cqi_req, cqi_buf);
SAME_SIZE(RDSData_Struct, rds_t);
SAME_FIELD(RDSData_Struct, rds_t, PI);
SAME_FIELD(RDSData_Struct, rds_t, AF_Data);
SAME_FIELD(RDSData_Struct, rds_t, PS_Data);
SAME_FIELD(RDSData_Struct, rds_t, RT_Data);
SAME_FIELD(RDSData_Struct, rds_t, event_status);
SAME_FIELD(RDSData_Struct, rds_t, gc);
