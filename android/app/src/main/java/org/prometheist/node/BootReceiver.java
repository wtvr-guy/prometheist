package org.prometheist.node;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;
import org.json.JSONObject;

/**
 * Resumes collection the owner had already started, after a reboot. This never enables a channel
 * the owner did not choose: it only restarts a session that was running when the phone went down,
 * and it does nothing when collection was deliberately paused. The decision is recorded so a
 * missing session is explainable later rather than an unexplained gap.
 */
public final class BootReceiver extends BroadcastReceiver {
  private static final String TAG = "PrometheistBoot";

  @Override
  public void onReceive(Context context, Intent intent) {
    if (intent == null || !Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) return;
    Context app = context.getApplicationContext();
    PendingResult result = goAsync();
    SyncJob.IO.execute(
        () -> {
          try {
            NodeStore store = NodeStore.get(app);
            boolean paused = store.config().optBoolean("paused", true);
            Log.i(TAG, "boot resume check: paused=" + paused);
            store.append(
                "control",
                new JSONObject()
                    .put("state", paused ? "boot_resume_declined" : "boot_resume_started")
                    .put("paused", paused));
            if (!paused) {
              app.startForegroundService(
                  new Intent(app, CaptureService.class)
                      .setAction("START")
                      .putExtra("from_boot", true));
            }
          } catch (Exception unavailable) {
            // A failed resume must never break the boot broadcast. The owner can
            // still start collection from the app.
            Log.w(TAG, "boot resume failed: " + unavailable.getClass().getSimpleName(), unavailable);
          } finally {
            result.finish();
          }
        });
  }
}
