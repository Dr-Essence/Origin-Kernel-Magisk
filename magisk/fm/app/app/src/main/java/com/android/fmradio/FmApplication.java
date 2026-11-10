/*
 * Added for the CMF Phone 1 build (not in AOSP).
 *
 * The FM app uses framework APIs Android keeps hidden from apps (AudioSystem, AudioPatch, audio
 * ports, AudioManager.createAudioPatch). Inside the Android source tree it was built against the
 * whole framework and signed with the platform key; here it is a privileged app with its own key,
 * so Android's hidden-API check applies to it. HiddenApiBypass (LSPosed's library) lifts that
 * check for this app only, before any FM code runs.
 */
package com.android.fmradio;

import android.app.Application;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.util.Log;

import org.lsposed.hiddenapibypass.HiddenApiBypass;

public class FmApplication extends Application {
    /**
     * The playing/recording notification's channel. Since Android 8 a notification needs one, and
     * startForeground() with a notification that has none stops the service (the 2016 code had
     * no channels: it targeted Android 5).
     */
    public static final String CHANNEL = "fm_radio";

    @Override
    public void onCreate() {
        super.onCreate();
        NotificationChannel channel = new NotificationChannel(CHANNEL,
                getString(R.string.app_name), NotificationManager.IMPORTANCE_LOW);
        getSystemService(NotificationManager.class).createNotificationChannel(channel);
        try {
            HiddenApiBypass.addHiddenApiExemptions("L");
        } catch (Throwable t) {
            Log.e("FmApplication", "hidden API exemption failed", t);
        }
    }
}
