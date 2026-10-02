package org.prometheist.node;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class SyncJob extends JobService {
  public static final ExecutorService IO = Executors.newSingleThreadExecutor();
  private volatile boolean stopped;

  public static void schedule(Context context) throws Exception {
    JobScheduler scheduler = context.getSystemService(JobScheduler.class);
    org.json.JSONObject config = NodeStore.get(context).config();
    if (!config.optBoolean("auto_sync")) {
      scheduler.cancel(42);
      return;
    }
    scheduler.schedule(
        new JobInfo.Builder(42, new ComponentName(context, SyncJob.class))
            .setRequiredNetworkType(
                config.optBoolean("wifi_only", true)
                    ? JobInfo.NETWORK_TYPE_UNMETERED
                    : JobInfo.NETWORK_TYPE_ANY)
            .setRequiresBatteryNotLow(true)
            // Without this the job is dropped at reboot and queued evidence waits
            // until the owner next opens the app. Persistence needs
            // RECEIVE_BOOT_COMPLETED and only resumes upload, never collection.
            .setPersisted(true)
            .setPeriodic(15 * 60_000L)
            .build());
  }

  @Override
  public boolean onStartJob(JobParameters params) {
    stopped = false;
    IO.execute(
        () -> {
          boolean retry = false;
          try {
            if (!stopped) NodeSync.run(this, false);
          } catch (Exception error) {
            retry = true;
          }
          if (!stopped) jobFinished(params, retry);
        });
    return true;
  }

  @Override
  public boolean onStopJob(JobParameters params) {
    stopped = true;
    return true;
  }
}
