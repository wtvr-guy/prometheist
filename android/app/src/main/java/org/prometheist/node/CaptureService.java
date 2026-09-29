package org.prometheist.node;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.hardware.*;
import android.location.*;
import android.media.*;
import android.os.*;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import org.json.*;

/** Explicitly started foreground capture; never starts on boot or remote command. */
public final class CaptureService extends Service implements SensorEventListener, LocationListener {
  public static volatile boolean running;
  public static volatile String status = "Collection paused";
  private SensorManager sensors;
  private LocationManager locations;
  private NodeStore store;
  private HandlerThread thread;
  private Handler handler;
  private final Map<Integer, WindowStats> windows = new HashMap<>();
  private final Map<Integer, Integer> accuracy = new HashMap<>();
  private String windowStart;
  private volatile boolean audioActive;
  private Thread audioThread;
  private AudioRecord audio;
  private double soundSquares;
  private long soundSamples;
  private boolean resourcesClosed;

  @Override
  public void onCreate() {
    super.onCreate();
    sensors = getSystemService(SensorManager.class);
    locations = getSystemService(LocationManager.class);
    thread = new HandlerThread("private-sensor-window");
    thread.start();
    handler = new Handler(thread.getLooper());
  }

  private boolean allowed(String permission) {
    return checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED;
  }

  @Override
  public int onStartCommand(Intent intent, int flags, int startId) {
    if (intent == null || "STOP".equals(intent.getAction())) {
      stopSelf();
      return START_NOT_STICKY;
    }
    if (running) return START_NOT_STICKY;
    try {
      store = NodeStore.get(this);
      JSONObject config = store.config();
      if (config.optBoolean("paused", true)) {
        stopSelf();
        return START_NOT_STICKY;
      }
      if (Build.VERSION.SDK_INT >= 33 && !allowed(Manifest.permission.POST_NOTIFICATIONS))
        throw new IllegalStateException("Enable notifications so collection remains visible");
      boolean useLocation = config.optBoolean("location"),
          useAudio = config.optBoolean("ambient_audio");
      if (useLocation && !allowed(Manifest.permission.ACCESS_COARSE_LOCATION))
        throw new SecurityException("Location permission missing");
      if (useAudio && !allowed(Manifest.permission.RECORD_AUDIO))
        throw new SecurityException("Microphone permission missing");
      NotificationManager manager = getSystemService(NotificationManager.class);
      manager.createNotificationChannel(
          new NotificationChannel(
              "capture", "Private observation", NotificationManager.IMPORTANCE_LOW));
      PendingIntent open =
          PendingIntent.getActivity(
              this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
      PendingIntent stop =
          PendingIntent.getService(
              this,
              1,
              new Intent(this, CaptureService.class).setAction("STOP"),
              PendingIntent.FLAG_IMMUTABLE);
      Notification notification =
          new Notification.Builder(this, "capture")
              .setSmallIcon(R.drawable.ic_node)
              .setContentTitle("Prometheist is observing")
              .setContentText("Private sensor journal · tap Pause to stop")
              .setVisibility(Notification.VISIBILITY_PRIVATE)
              .setContentIntent(open)
              .setOngoing(true)
              .addAction(new Notification.Action.Builder(null, "Pause", stop).build())
              .build();
      if (Build.VERSION.SDK_INT >= 34) {
        int type = ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE;
        if (useLocation) type |= ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION;
        if (useAudio) type |= ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE;
        startForeground(7, notification, type);
      } else startForeground(7, notification);
      running = true;
      status = "Starting selected channels";
      handler.post(() -> begin(config));
    } catch (Exception error) {
      fail(error);
    }
    return START_NOT_STICKY;
  }

  private void begin(JSONObject config) {
    try {
      checkResources();
      windowStart = Instant.now().toString();
      JSONArray selected = config.getJSONArray("sensors");
      int count = 0;
      for (int i = 0; i < selected.length(); i++) {
        int type = selected.getInt(i);
        if (Build.VERSION.SDK_INT >= 29
            && (type == Sensor.TYPE_STEP_COUNTER || type == Sensor.TYPE_STEP_DETECTOR)
            && !allowed(Manifest.permission.ACTIVITY_RECOGNITION)) continue;
        Sensor sensor = sensors.getDefaultSensor(type);
        if (sensor != null
            && sensors.registerListener(this, sensor, Policy.SAMPLE_US, 30_000_000, handler))
          count++;
      }
      if (config.optBoolean("location")) {
        if (checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)
            != PackageManager.PERMISSION_GRANTED)
          throw new SecurityException("Location permission missing");
        boolean precise =
            config.optBoolean("precise_location")
                && allowed(Manifest.permission.ACCESS_FINE_LOCATION);
        String provider = precise ? LocationManager.GPS_PROVIDER : LocationManager.NETWORK_PROVIDER;
        if (!locations.isProviderEnabled(provider)) {
          status = "Location provider unavailable; other channels active";
          store.append(
              "control",
              new JSONObject().put("state", "location_unavailable").put("provider", provider));
        } else locations.requestLocationUpdates(provider, 300_000, 200, this, handler.getLooper());
      }
      if (config.optBoolean("ambient_audio")) startAudio();
      store.append(
          "control",
          new JSONObject()
              .put("state", "capture_started")
              .put("selected_sensor_types", selected)
              .put("location", config.optBoolean("location"))
              .put("ambient_audio", config.optBoolean("ambient_audio"))
              .put("policy", "low-rate-window/v1")
              .put("requested_sample_us", Policy.SAMPLE_US)
              .put("window_ms", Policy.WINDOW_MS));
      status = "Observing · " + count + " sensor channels";
      handler.postDelayed(flush, Policy.WINDOW_MS);
    } catch (Exception error) {
      fail(error);
    }
  }

  private void checkResources() throws Exception {
    store.headroom();
    ActivityManager.MemoryInfo memory = new ActivityManager.MemoryInfo();
    getSystemService(ActivityManager.class).getMemoryInfo(memory);
    if (memory.lowMemory)
      throw new IllegalStateException("Phone memory pressure; collection paused");
    PowerManager power = getSystemService(PowerManager.class);
    if (Build.VERSION.SDK_INT >= 29
        && power.getCurrentThermalStatus() >= PowerManager.THERMAL_STATUS_SEVERE)
      throw new IllegalStateException("Phone is hot; collection paused");
    Intent battery = registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
    if (battery != null) {
      int level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, 100),
          scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, 100);
      if (scale > 0
          && level * 100 / scale < 15
          && battery.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) == 0)
        throw new IllegalStateException("Battery below 15%; collection paused");
    }
  }

  private final Runnable flush =
      new Runnable() {
        @Override
        public void run() {
          try {
            checkResources();
            persistWindow();
            deviceObservation();
            handler.postDelayed(this, Policy.WINDOW_MS);
          } catch (Exception error) {
            fail(error);
          }
        }
      };

  private void persistWindow() throws Exception {
    JSONArray values = new JSONArray();
    for (Map.Entry<Integer, WindowStats> entry : windows.entrySet()) {
      WindowStats stats = entry.getValue();
      if (stats.samples == 0) continue;
      JSONArray mean = new JSONArray(),
          min = new JSONArray(),
          max = new JSONArray(),
          last = new JSONArray();
      for (int i = 0; i < stats.sum.length; i++) {
        mean.put(stats.mean(i));
        min.put(stats.min[i]);
        max.put(stats.max[i]);
        last.put(stats.last[i]);
      }
      values.put(
          new JSONObject()
              .put("sensor_type", entry.getKey())
              .put("sensor_name", sensors.getDefaultSensor(entry.getKey()).getName())
              .put("sensor_vendor", sensors.getDefaultSensor(entry.getKey()).getVendor())
              .put("least_reported_accuracy", accuracy.get(entry.getKey()))
              .put("unit_label", SensorCatalog.label(entry.getKey()))
              .put("count", stats.samples)
              .put("mean", mean)
              .put("min", min)
              .put("max", max)
              .put("last", last));
    }
    JSONObject sound = null;
    synchronized (this) {
      if (soundSamples > 0)
        sound =
            new JSONObject()
                .put("samples", soundSamples)
                .put(
                    "rms_dbfs",
                    20
                        * Math.log10(
                            Math.max(1e-9, Math.sqrt(soundSquares / soundSamples) / 32768.0)))
                .put("calibrated_spl", false);
      soundSamples = 0;
      soundSquares = 0;
    }
    String end = Instant.now().toString();
    if (values.length() > 0 || sound != null)
      store.append(
          "sensors",
          new JSONObject()
              .put("policy", "low-rate-window/v1")
              .put("window_start", windowStart)
              .put("window_end", end)
              .put("sensors", values)
              .put("sound", sound == null ? JSONObject.NULL : sound)
              .put("admission", "window_statistics")
              .put("raw_samples_retained", false)
              .put("sleep_gaps_possible", true));
    windows.clear();
    accuracy.clear();
    windowStart = end;
  }

  private void deviceObservation() throws Exception {
    Intent battery = registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
    if (battery == null) return;
    store.append(
        "device",
        new JSONObject()
            .put("battery_level", battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1))
            .put("battery_scale", battery.getIntExtra(BatteryManager.EXTRA_SCALE, -1))
            .put("charging", battery.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) != 0)
            .put("power_save", getSystemService(PowerManager.class).isPowerSaveMode())
            .put("screen_interactive", getSystemService(PowerManager.class).isInteractive()));
  }

  @Override
  public void onSensorChanged(SensorEvent event) {
    if (!running) return;
    WindowStats stats = windows.get(event.sensor.getType());
    if (stats == null) {
      stats = new WindowStats(event.values.length);
      windows.put(event.sensor.getType(), stats);
    }
    stats.add(event.values);
    int type = event.sensor.getType();
    accuracy.put(
        type,
        Math.min(accuracy.containsKey(type) ? accuracy.get(type) : event.accuracy, event.accuracy));
  }

  @Override
  public void onAccuracyChanged(Sensor sensor, int accuracy) {}

  @Override
  public void onLocationChanged(Location location) {
    try {
      JSONObject config = store.config();
      if (!running || !config.optBoolean("location")) return;
      boolean precise =
          config.optBoolean("precise_location")
              && allowed(Manifest.permission.ACCESS_FINE_LOCATION);
      double factor = 100; // Approximate mode deliberately rounds to roughly kilometre cells.
      double lat =
          precise ? location.getLatitude() : Math.rint(location.getLatitude() * factor) / factor;
      double lon =
          precise ? location.getLongitude() : Math.rint(location.getLongitude() * factor) / factor;
      store.append(
          "location",
          new JSONObject()
              .put("latitude", lat)
              .put("longitude", lon)
              .put(
                  "accuracy_m",
                  precise ? location.getAccuracy() : Math.max(1500, location.getAccuracy()))
              .put("precise", precise)
              .put("fix_at", Instant.ofEpochMilli(location.getTime()).toString())
              .put("mock", location.isFromMockProvider())
              .put("provider", location.getProvider()));
    } catch (Exception error) {
      fail(error);
    }
  }

  @Override
  public void onProviderEnabled(String provider) {}

  @Override
  public void onProviderDisabled(String provider) {
    status = "Location disabled by Android; sensor collection continues";
  }

  @SuppressWarnings("deprecation")
  @Override
  public void onStatusChanged(String provider, int status, Bundle extras) {}

  private void startAudio() {
    if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED)
      throw new SecurityException("Microphone permission missing");
    int minimum =
        AudioRecord.getMinBufferSize(
            8000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
    audio =
        new AudioRecord(
            MediaRecorder.AudioSource.MIC,
            8000,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            Math.max(4096, minimum * 2));
    if (audio.getState() != AudioRecord.STATE_INITIALIZED)
      throw new IllegalStateException("Microphone unavailable");
    audio.startRecording();
    audioActive = true;
    audioThread =
        new Thread(
            () -> {
              short[] buffer = new short[2048];
              while (audioActive) {
                int count = audio.read(buffer, 0, buffer.length);
                if (count < 0) {
                  if (audioActive)
                    handler.post(() -> fail(new IllegalStateException("Microphone stopped")));
                  break;
                }
                double squares = 0;
                for (int i = 0; i < count; i++) squares += (double) buffer[i] * buffer[i];
                synchronized (this) {
                  soundSquares += squares;
                  soundSamples += count;
                }
                java.util.Arrays.fill(buffer, (short) 0);
              }
            },
            "ephemeral-sound-level");
    audioThread.start();
  }

  private void fail(Exception error) {
    status =
        error instanceof SecurityException
            ? "Permission changed; collection paused"
            : error instanceof IllegalStateException
                ? error.getMessage()
                : "Storage or sensor unavailable; collection paused";
    stopSelf();
  }

  @Override
  public void onDestroy() {
    running = false;
    if (store != null)
      try {
        store.setting("paused", true);
      } catch (Exception ignored) {
      }
    handler.post(
        () -> {
          if (resourcesClosed) return;
          resourcesClosed = true;
          sensors.unregisterListener(this);
          try {
            locations.removeUpdates(this);
          } catch (SecurityException ignored) {
          }
          audioActive = false;
          if (audio != null) {
            try {
              audio.stop();
            } catch (IllegalStateException ignored) {
            }
            if (audioThread != null)
              try {
                audioThread.join(1000);
              } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
              }
            audio.release();
            audio = null;
          }
          handler.removeCallbacks(flush);
          if (store != null)
            try {
              persistWindow();
              store.append(
                  "control",
                  new JSONObject().put("state", "capture_stopped").put("reason", status));
            } catch (Exception ignored) {
              /* Existing evidence retained; no fabricated successful write. */
            }
          thread.quitSafely();
        });
    stopForeground(STOP_FOREGROUND_REMOVE);
    super.onDestroy();
  }

  @Override
  public IBinder onBind(Intent intent) {
    return null;
  }
}
