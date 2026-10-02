package org.prometheist.node;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.hardware.*;
import android.os.*;
import android.view.*;
import android.view.inputmethod.EditorInfo;
import android.widget.*;
import java.util.ArrayList;
import org.json.*;

/** Native offline-first UI. No WebView, analytics, embedded browser or cloud SDK. */
public final class MainActivity extends Activity {
  private static final int BG = Color.rgb(16, 26, 26),
      PANEL = Color.rgb(28, 42, 40),
      GREEN = Color.rgb(198, 242, 124),
      TEXT = Color.rgb(235, 241, 231),
      MUTED = Color.rgb(166, 185, 174);
  private NodeStore store;
  private LinearLayout body, root;
  private TextView banner;
  private EditText chatDraft;
  private String unsent = "";
  private final java.util.concurrent.atomic.AtomicBoolean busy =
      new java.util.concurrent.atomic.AtomicBoolean();
  private String tab = "Chat", message = "Your history stays with you.";
  private boolean unlocked, authenticating;
  private char[] exportPassword;
  private final Handler handler = new Handler(Looper.getMainLooper());
  private final Runnable poll =
      new Runnable() {
        @Override
        public void run() {
          if (unlocked && store != null) {
            try {
              if (store.config().optBoolean("auto_sync") && store.paired())
                background(() -> NodeSync.run(MainActivity.this, false), false);
            } catch (Exception ignored) {
            }
            handler.postDelayed(this, 30_000);
          }
        }
      };

  @Override
  public void onCreate(Bundle state) {
    super.onCreate(state);
    getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
    loading("Opening your private node…");
    SyncJob.IO.execute(
        () -> {
          try {
            store = NodeStore.get(this);
            runOnUiThread(
                () -> {
                  if (store.damaged() > 0)
                    message =
                        store.damaged()
                            + " unreadable record(s) were skipped. The rest of your evidence is"
                            + " intact — export an encrypted backup.";
                  if (unlocked) show();
                });
          } catch (Exception e) {
            runOnUiThread(
                () ->
                    loading(
                        "Private storage could not open. Existing evidence has been retained.\n"
                            + safe(e)));
          }
        });
  }

  @Override
  public void onResume() {
    super.onResume();
    if (!unlocked && !authenticating) unlock();
    else if (unlocked) {
      show();
      handler.removeCallbacks(poll);
      handler.postDelayed(poll, 30_000);
    }
  }

  @Override
  public void onStop() {
    super.onStop();
    unlocked = false;
    handler.removeCallbacks(poll);
    if (!authenticating) loading("Prometheist is locked");
  }

  private void unlock() {
    KeyguardManager keyguard = getSystemService(KeyguardManager.class);
    if (!keyguard.isDeviceSecure()) {
      loading("Set a screen lock before opening private history.");
      new AlertDialog.Builder(this)
          .setTitle("Protect your node")
          .setMessage(
              "Prometheist uses your phone's screen lock to protect access to your history.")
          .setPositiveButton(
              "Security settings",
              (d, w) ->
                  startActivity(new Intent(android.provider.Settings.ACTION_SECURITY_SETTINGS)))
          .setNegativeButton("Close", (d, w) -> finish())
          .show();
      return;
    }
    authenticating = true;
    startActivityForResult(
        keyguard.createConfirmDeviceCredentialIntent("Prometheist", "Unlock your private node"),
        10);
  }

  private void loading(String text) {
    TextView view = new TextView(this);
    view.setText(text);
    view.setTextColor(TEXT);
    view.setTextSize(18);
    view.setPadding(dp(24), dp(60), dp(24), dp(24));
    view.setBackgroundColor(BG);
    setContentView(view);
  }

  private int dp(int n) {
    return Math.round(n * getResources().getDisplayMetrics().density);
  }

  private TextView text(String value, int size, int color) {
    TextView v = new TextView(this);
    v.setText(value);
    v.setTextSize(size);
    v.setTextColor(color);
    v.setPadding(0, dp(5), 0, dp(5));
    return v;
  }

  private GradientDrawable shape(int color) {
    GradientDrawable d = new GradientDrawable();
    d.setColor(color);
    d.setCornerRadius(dp(18));
    return d;
  }

  private void section(String title, String note) {
    TextView name = text(title, 26, TEXT);
    name.setTypeface(null, Typeface.BOLD);
    body.addView(name);
    if (!note.isEmpty()) body.addView(text(note, 14, MUTED));
  }

  private LinearLayout card() {
    LinearLayout v = new LinearLayout(this);
    v.setOrientation(LinearLayout.VERTICAL);
    v.setPadding(dp(16), dp(12), dp(16), dp(12));
    v.setBackground(shape(PANEL));
    LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1, -2);
    p.setMargins(0, dp(10), 0, dp(8));
    body.addView(v, p);
    return v;
  }

  private Button button(String label, Runnable action) {
    Button b = new Button(this);
    b.setText(label);
    b.setAllCaps(false);
    b.setTextColor(BG);
    b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(GREEN));
    b.setPadding(dp(12), dp(8), dp(12), dp(8));
    b.setOnClickListener(v -> action.run());
    body.addView(b, new LinearLayout.LayoutParams(-1, -2));
    return b;
  }

  private EditText input(String hint, boolean multiline) {
    EditText v = new EditText(this);
    v.setHint(hint);
    v.setTextColor(TEXT);
    v.setHintTextColor(MUTED);
    v.setTextSize(16);
    v.setPadding(dp(12), dp(12), dp(12), dp(12));
    v.setBackground(shape(PANEL));
    v.setInputType(
        android.text.InputType.TYPE_CLASS_TEXT
            | (multiline ? android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE : 0)
            | android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
    v.setImeOptions(EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING);
    v.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
    if (multiline) {
      v.setMinLines(3);
      v.setMaxLines(6);
    }
    body.addView(v, new LinearLayout.LayoutParams(-1, -2));
    return v;
  }

  private void show() {
    if (!unlocked || store == null) return;
    try {
      if (chatDraft != null) {
        unsent = chatDraft.getText().toString();
        chatDraft = null;
      }
      root = new LinearLayout(this);
      root.setOrientation(LinearLayout.VERTICAL);
      root.setBackgroundColor(BG);
      root.setPadding(dp(20), 0, dp(20), 0);
      root.setOnApplyWindowInsetsListener(
          (v, insets) -> {
            v.setPadding(
                dp(20),
                insets.getSystemWindowInsetTop() + dp(12),
                dp(20),
                insets.getSystemWindowInsetBottom());
            return insets;
          });
      TextView brand = text("P R O M E T H E I S T", 14, GREEN);
      brand.setTypeface(null, Typeface.BOLD);
      root.addView(brand);
      banner = text(message, 12, MUTED);
      root.addView(banner);
      ScrollView scroll = new ScrollView(this);
      scroll.setFillViewport(true);
      body = new LinearLayout(this);
      body.setOrientation(LinearLayout.VERTICAL);
      body.setPadding(0, dp(18), 0, dp(20));
      scroll.addView(body);
      root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
      switch (tab) {
        case "Memory":
          memory();
          break;
        case "Observe":
          observe();
          break;
        case "Connect":
          connect();
          break;
        default:
          chat();
      }
      LinearLayout nav = new LinearLayout(this);
      for (String name : new String[] {"Chat", "Memory", "Observe", "Connect"}) {
        Button b = new Button(this);
        b.setText(name);
        b.setTextSize(12);
        b.setAllCaps(false);
        b.setTextColor(tab.equals(name) ? GREEN : MUTED);
        b.setBackgroundColor(BG);
        b.setOnClickListener(
            v -> {
              tab = name;
              show();
            });
        nav.addView(b, new LinearLayout.LayoutParams(0, dp(54), 1));
      }
      root.addView(nav);
      setContentView(root);
      root.requestApplyInsets();
      SyncJob.schedule(this);
    } catch (Exception e) {
      loading("Could not open this view. " + safe(e));
    }
  }

  private void chat() throws Exception {
    section(
        "One self.\nMore ways to be.",
        "A private node of your Prometheist. Write now; the laptop can respond when connected.");
    LinearLayout status = card();
    status.addView(text(store.paired() ? "LAPTOP PAIRED" : "LOCAL • NOT PAIRED", 12, GREEN));
    status.addView(text(store.count(true) + " events waiting to sync", 18, TEXT));
    status.addView(text("SQLite + encrypted journal · no model on this phone", 13, MUTED));
    EditText draft = input("What's on your mind?", true);
    chatDraft = draft;
    draft.setText(unsent);
    button(
        "Send to Prometheist",
        () -> {
          String value = draft.getText().toString().trim();
          if (value.isEmpty()) return;
          background(
              () -> {
                store.append("chat", new JSONObject().put("text", value));
                runOnUiThread(
                    () -> {
                      draft.setText("");
                      unsent = "";
                    });
                return NodeSync.run(this, true);
              },
              true);
        });
    button(
        "Save as a journal note",
        () -> {
          String value = draft.getText().toString().trim();
          if (value.isEmpty()) return;
          background(
              () -> {
                store.append("note", new JSONObject().put("text", value));
                runOnUiThread(
                    () -> {
                      draft.setText("");
                      unsent = "";
                    });
                return "Saved privately on this phone";
              },
              true);
        });
    body.addView(text("Recent conversations", 18, TEXT));
    renderAsync("", true);
  }

  /**
   * Decrypting up to 200 records is too slow for the UI thread; load them on the IO executor and
   * render only if the user is still on the same view.
   */
  private void renderAsync(String query, boolean chat) {
    LinearLayout target = body;
    TextView placeholder = text("Loading recent evidence…", 15, MUTED);
    target.addView(placeholder);
    SyncJob.IO.execute(
        () -> {
          JSONArray found = null;
          String failure = null;
          try {
            found = store.recent(query, chat);
          } catch (Exception e) {
            failure = safe(e);
          }
          JSONArray rows = found;
          String error = failure;
          runOnUiThread(
              () -> {
                if (!unlocked || body != target) return;
                target.removeView(placeholder);
                try {
                  if (error != null) notice(error);
                  else render(rows);
                } catch (Exception e) {
                  notice(safe(e));
                }
              });
        });
  }

  private void render(JSONArray rows) throws Exception {
    for (int i = 0; i < rows.length(); i++) {
      JSONObject event = rows.getJSONObject(i), data = new JSONObject(event.getString("data_json"));
      String kind = event.getString("kind");
      LinearLayout c = card();
      c.addView(
          text(
              kind.toUpperCase(java.util.Locale.ROOT)
                  + " · "
                  + event.optString("observed_at", event.optString("state")),
              11,
              GREEN));
      String content = data.optString("text", data.optString("message", ""));
      if (content.isEmpty())
        content =
            kind.equals("photo")
                ? "Private photo capture"
                : kind.equals("audio")
                    ? "Private voice memo"
                    : kind.equals("sensors")
                        ? "Motion / environmental window · " + data.optString("window_start")
                        : data.toString();
      if (content.length() > 3000)
        content = content.substring(0, 3000) + "\n… Open laptop artifacts for full evidence.";
      TextView value = text(content, 16, TEXT);
      value.setTextIsSelectable(true);
      c.addView(value);
      c.addView(text(event.optString("delivery"), 11, MUTED));
    }
    if (rows.length() == 0)
      body.addView(text("Your next observation starts the history here.", 15, MUTED));
  }

  private void memory() throws Exception {
    section(
        "Your life, retained.",
        "Browse 200 recent local records. Loaded laptop memories remain available offline.");
    EditText search = input("Search recent evidence", false);
    button(
        "Search",
        () -> {
          String q = search.getText().toString();
          try {
            body.removeAllViews();
            section("Recent evidence", q.isEmpty() ? "All recent records" : q);
            renderAsync(q, false);
          } catch (Exception e) {
            notice(safe(e));
          }
        });
    button(
        "Refresh latest laptop memories",
        () ->
            background(
                () -> {
                  NodeSync.memory(this, true);
                  return "Latest laptop memories saved for offline viewing";
                },
                true));
    button(
        "Load 25 older laptop memories",
        () ->
            background(
                () -> {
                  NodeSync.memory(this, false);
                  return "Laptop memories saved for offline viewing";
                },
                true));
    button("Export encrypted backup", this::exportDialog);
    renderAsync("", false);
  }

  private interface Checked {
    String run() throws Exception;
  }

  private void background(Checked work, boolean refresh) {
    if (!busy.compareAndSet(false, true)) return;
    notice("Working privately…");
    SyncJob.IO.execute(
        () -> {
          String result;
          try {
            result = work.run();
          } catch (Exception e) {
            result = safe(e);
          }
          String value = result;
          runOnUiThread(
              () -> {
                busy.set(false);
                message = value;
                if (unlocked) {
                  if (refresh
                      || (tab.equals("Chat") && chatDraft != null && chatDraft.length() == 0))
                    show();
                  else notice(value);
                }
              });
        });
  }

  private String safe(Exception error) {
    return error instanceof IllegalArgumentException
            || error instanceof IllegalStateException
            || error instanceof SecurityException
        ? error.getMessage()
        : "Connection, permission or storage unavailable ("
            + error.getClass().getSimpleName()
            + "). Your saved evidence is retained.";
  }

  private void notice(String value) {
    message = value;
    if (banner != null) banner.setText(value);
  }

  private void stopCapture() {
    stopService(new Intent(this, CaptureService.class));
    CaptureService.status = "Collection paused";
    try {
      store.setting("paused", true);
    } catch (Exception e) {
      notice(safe(e));
    }
  }

  private void toggle(String title, String key, boolean initial) throws Exception {
    Switch view = new Switch(this);
    view.setText(title);
    view.setTextColor(TEXT);
    view.setPadding(0, dp(10), 0, dp(10));
    view.setChecked(initial);
    view.setOnCheckedChangeListener(
        (button, checked) -> {
          try {
            if (tab.equals("Observe")) stopCapture();
            store.setting(key, checked);
            SyncJob.schedule(this);
          } catch (Exception e) {
            notice(safe(e));
          }
        });
    body.addView(view);
  }

  private void observe() throws Exception {
    section(
        "Choose what you notice.",
        "Collection starts only when you turn it on. Changing channels pauses collection.");
    JSONObject config = store.config();
    ActivityManager.MemoryInfo mem = new ActivityManager.MemoryInfo();
    getSystemService(ActivityManager.class).getMemoryInfo(mem);
    LinearLayout hardware = card();
    hardware.addView(text(Build.MANUFACTURER + " " + Build.MODEL, 18, TEXT));
    hardware.addView(
        text(
            String.format(
                java.util.Locale.ROOT,
                "%.1f GiB physical RAM · Android %s",
                mem.totalMem / 1073741824.0,
                Build.VERSION.RELEASE),
            13,
            MUTED));
    hardware.addView(
        text(CaptureService.running ? CaptureService.status : "Collection paused", 13, GREEN));
    button(
        CaptureService.running ? "Pause collection" : "Start selected collection",
        () -> {
          if (CaptureService.running) {
            stopCapture();
            show();
          } else startCapture();
        });
    toggle("Location (approximate by default)", "location", config.optBoolean("location"));
    toggle("Precise GPS coordinates", "precise_location", config.optBoolean("precise_location"));
    toggle(
        "Ambient sound level (no recording)", "ambient_audio", config.optBoolean("ambient_audio"));
    body.addView(
        text(
            "Sound uses relative dBFS, not calibrated loudness. Raw sound buffers are discarded. No"
                + " speech recognition runs in the background.",
            13,
            MUTED));
    JSONArray selected = config.getJSONArray("sensors");
    java.util.HashSet<Integer> types = new java.util.HashSet<>();
    for (int i = 0; i < selected.length(); i++) types.add(selected.getInt(i));
    for (Sensor sensor : SensorCatalog.supported(getSystemService(SensorManager.class))) {
      Switch view = new Switch(this);
      view.setText(SensorCatalog.label(sensor.getType()));
      view.setTextSize(14);
      view.setTextColor(TEXT);
      view.setPadding(0, dp(9), 0, dp(9));
      view.setChecked(types.contains(sensor.getType()));
      view.setOnCheckedChangeListener(
          (b, checked) -> {
            stopCapture();
            try {
              if (checked) types.add(sensor.getType());
              else types.remove(sensor.getType());
              JSONArray values = new JSONArray();
              for (int type : types) values.put(type);
              store.setting("sensors", values);
            } catch (Exception e) {
              notice(safe(e));
            }
          });
      body.addView(view);
    }
    body.addView(
        text(
            "Only sensors exposed by this phone are shown. Readings are aggregated before admission"
                + " into one-minute windows. Android sleep and battery controls can create gaps.",
            13,
            MUTED));
    button("Take a private photo", () -> manualCapture("photo"));
    button("Record a private voice memo", () -> manualCapture("audio"));
    body.addView(
        text(
            "Photos and voice memos are deliberate captures. Fingerprint images, other apps'"
                + " messages, and call audio are not accessible to this node.",
            13,
            MUTED));
  }

  private void startCapture() {
    try {
      JSONObject c = store.config();
      JSONArray types = c.getJSONArray("sensors");
      if (types.length() == 0 && !c.optBoolean("location") && !c.optBoolean("ambient_audio")) {
        notice("Choose at least one channel first.");
        return;
      }
      ArrayList<String> permissions = new ArrayList<>();
      if (Build.VERSION.SDK_INT >= 33) permissions.add(Manifest.permission.POST_NOTIFICATIONS);
      if (c.optBoolean("location")) {
        permissions.add(Manifest.permission.ACCESS_COARSE_LOCATION);
        if (c.optBoolean("precise_location"))
          permissions.add(Manifest.permission.ACCESS_FINE_LOCATION);
      }
      if (c.optBoolean("ambient_audio")) permissions.add(Manifest.permission.RECORD_AUDIO);
      if (Build.VERSION.SDK_INT >= 29)
        for (int i = 0; i < types.length(); i++)
          if (types.getInt(i) == Sensor.TYPE_STEP_COUNTER
              || types.getInt(i) == Sensor.TYPE_STEP_DETECTOR) {
            permissions.add(Manifest.permission.ACTIVITY_RECOGNITION);
            break;
          }
      permissions.removeIf(p -> checkSelfPermission(p) == PackageManager.PERMISSION_GRANTED);
      if (!permissions.isEmpty()) {
        requestPermissions(permissions.toArray(new String[0]), 20);
        notice("After granting permissions, tap Start selected collection.");
        return;
      }
      store.setting("paused", false);
      startForegroundService(new Intent(this, CaptureService.class).setAction("START"));
      notice("Starting observation; the notification lets you stop it anytime.");
      handler.postDelayed(this::show, 800);
    } catch (Exception e) {
      notice(safe(e));
    }
  }

  private void manualCapture(String kind) {
    stopCapture();
    String permission =
        kind.equals("photo") ? Manifest.permission.CAMERA : Manifest.permission.RECORD_AUDIO;
    if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) {
      requestPermissions(new String[] {permission}, 21);
      notice("After granting permission, tap capture again.");
      return;
    }
    startActivity(new Intent(this, CaptureActivity.class).putExtra("kind", kind));
  }

  private void connect() throws Exception {
    JSONObject c = store.config();
    section(
        "A private connection.",
        "Your laptop is the other end. Connect both devices to your private tunnel, then pair.");
    LinearLayout identity = card();
    identity.addView(
        text(store.paired() ? "Paired with " + c.getString("subject_id") : "Not paired", 18, TEXT));
    identity.addView(text(c.optString("url", "HTTPS + encrypted private tunnel"), 13, MUTED));
    identity.addView(text("Node " + c.getString("node_id"), 11, MUTED));
    EditText enrollment = input("Paste the laptop's pairing JSON", true);
    button(
        "Pair laptop",
        () -> {
          String input = enrollment.getText().toString();
          enrollment.setText("");
          background(
              () -> {
                NodeSync.pair(this, input);
                return "Paired. Choose automatic sync or tap Sync now.";
              },
              true);
        });
    toggle("Sync automatically", "auto_sync", c.optBoolean("auto_sync"));
    toggle("Use unmetered connections only", "wifi_only", c.optBoolean("wifi_only", true));
    button("Sync now", () -> background(() -> NodeSync.run(this, true), true));
    button(
        "Pause all collection and automatic sync",
        () -> {
          stopCapture();
          try {
            store.setting("auto_sync", false);
            SyncJob.schedule(this);
            notice("Collection and automatic sync paused.");
            show();
          } catch (Exception e) {
            notice(safe(e));
          }
        });
    body.addView(text("Last sync: " + store.meta("last_sync", "never"), 13, MUTED));
    body.addView(
        text(
            "No advertising, analytics, automatic cloud backup, or cloud model calls. Unlock is"
                + " required to view history. Android Keystore protects stored evidence and pairing"
                + " credentials. Keep your laptop storage encrypted too.",
            14,
            MUTED));
    button("Export encrypted backup", this::exportDialog);
  }

  private void exportDialog() {
    EditText pass = new EditText(this);
    pass.setInputType(129);
    pass.setHint("At least 12 characters");
    pass.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
    new AlertDialog.Builder(this)
        .setTitle("Encrypted backup")
        .setMessage(
            "Keep this passphrase separately. The backup excludes your pairing credential and can"
                + " be recovered on the laptop.")
        .setView(pass)
        .setNegativeButton("Cancel", null)
        .setPositiveButton(
            "Choose file",
            (d, w) -> {
              if (pass.length() < 12) {
                notice("Use a passphrase of at least 12 characters.");
                return;
              }
              exportPassword = pass.getText().toString().toCharArray();
              pass.setText("");
              startActivityForResult(
                  new Intent(Intent.ACTION_CREATE_DOCUMENT)
                      .setType("application/octet-stream")
                      .addCategory(Intent.CATEGORY_OPENABLE)
                      .putExtra(Intent.EXTRA_TITLE, "prometheist-node.pnode"),
                  30);
            })
        .show();
  }

  @Override
  protected void onActivityResult(int request, int result, Intent data) {
    super.onActivityResult(request, result, data);
    if (request == 10) {
      authenticating = false;
      unlocked = result == RESULT_OK;
      if (unlocked) {
        show();
        handler.postDelayed(poll, 30_000);
      } else finish();
    }
    if (request == 30) {
      char[] pass = exportPassword;
      exportPassword = null;
      if (result == RESULT_OK && data != null && pass != null) {
        android.net.Uri uri = data.getData();
        background(
            () -> {
              try (java.io.OutputStream out = getContentResolver().openOutputStream(uri)) {
                store.export(out, pass);
              }
              return "Encrypted backup saved";
            },
            false);
      } else if (pass != null) java.util.Arrays.fill(pass, '\0');
    }
  }
}
