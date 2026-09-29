package org.prometheist.node;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.os.StatFs;
import android.system.Os;
import android.system.OsConstants;
import android.util.AtomicFile;
import java.io.File;
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Arrays;
import java.util.UUID;
import org.json.JSONArray;
import org.json.JSONObject;

/** SQLite is a rebuildable encrypted-payload index; immutable files precede SQL. */
public final class NodeStore {
  private static NodeStore instance;
  private final File root, journal;
  private final SQLiteDatabase db;
  private final Vault vault;
  private final AtomicFile settings;
  private JSONObject config;
  private long journalBytes;

  public static synchronized NodeStore get(Context context) throws Exception {
    if (instance == null) instance = new NodeStore(context.getApplicationContext());
    return instance;
  }

  private NodeStore(Context context) throws Exception {
    root = new File(context.getNoBackupFilesDir(), "node");
    journal = new File(root, "journal");
    if (!journal.mkdirs() && !journal.isDirectory())
      throw new IllegalStateException("Private storage unavailable");
    settings = new AtomicFile(new File(root, "settings.enc"));
    File[] files = journal.listFiles((d, n) -> n.endsWith(".enc"));
    if (!settings.getBaseFile().exists() && files != null && files.length > 0)
      throw new IllegalStateException(
          "Node identity is missing. Preserve the vault and recover from a private backup.");
    vault =
        new Vault(context, settings.getBaseFile().exists() || (files != null && files.length > 0));
    if (settings.getBaseFile().exists()) {
      config =
          new JSONObject(
              new String(vault.open(settings.readFully(), "settings"), StandardCharsets.UTF_8));
    } else {
      config =
          new JSONObject()
              .put("node_id", UUID.randomUUID().toString())
              .put("credential", secret())
              .put("sensors", new JSONArray())
              .put("location", false)
              .put("ambient_audio", false)
              .put("wifi_only", true)
              .put("paused", true)
              .put("auto_sync", false);
      saveConfig();
    }
    db = SQLiteDatabase.openOrCreateDatabase(new File(root, "index.sqlite3"), null);
    db.execSQL("PRAGMA synchronous=FULL");
    db.execSQL(
        "CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY, sequence INTEGER NOT NULL, local"
            + " INTEGER NOT NULL, cipher BLOB NOT NULL, uploaded INTEGER NOT NULL DEFAULT 0, state"
            + " TEXT NOT NULL DEFAULT 'local')");
    db.execSQL("CREATE INDEX IF NOT EXISTS pending ON evidence(local,uploaded,sequence)");
    db.execSQL("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)");
    // One startup reconciliation also repairs a kill after file publication,
    // before SQLite commit. No lifetime scan in sensor or sync polling.
    if (files != null)
      for (File file : files) {
        journalBytes += file.length();
        byte[] plain = vault.open(Files.readAllBytes(file.toPath()), file.getName());
        JSONObject envelope = new JSONObject(new String(plain, StandardCharsets.UTF_8));
        index(envelope);
      }
    // A newly rebuilt DB must replay server receipts, not skip with an old cursor.
    if (!hasMeta("epoch")) putMeta("cursor", "0");
  }

  private static String secret() {
    byte[] bytes = new byte[32];
    new SecureRandom().nextBytes(bytes);
    return android.util.Base64.encodeToString(
        bytes,
        android.util.Base64.URL_SAFE
            | android.util.Base64.NO_WRAP
            | android.util.Base64.NO_PADDING);
  }

  static String hex(byte[] bytes) {
    StringBuilder text = new StringBuilder();
    for (byte b : bytes) text.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
    return text.toString();
  }

  private static byte[] utf8(String s) {
    return s.getBytes(StandardCharsets.UTF_8);
  }

  public synchronized JSONObject config() throws Exception {
    return new JSONObject(config.toString());
  }

  public synchronized void setting(String name, Object value) throws Exception {
    config.put(name, value);
    saveConfig();
  }

  public synchronized void configure(JSONObject value) throws Exception {
    config = new JSONObject(value.toString());
    saveConfig();
  }

  private void saveConfig() throws Exception {
    FileOutputStream out = settings.startWrite();
    try {
      out.write(vault.seal(utf8(config.toString()), "settings"));
      settings.finishWrite(out);
    } catch (Exception e) {
      settings.failWrite(out);
      throw e;
    }
  }

  public synchronized boolean paired() {
    return config.optBoolean("paired", false);
  }

  public synchronized void headroom() {
    if (new StatFs(root.getPath()).getAvailableBytes() < Policy.MIN_FREE_BYTES
        || journalBytes >= Policy.MAX_VAULT_BYTES) {
      throw new IllegalStateException(
          "Storage limit reached. Collection paused; existing evidence is retained.");
    }
  }

  public synchronized JSONObject append(String kind, JSONObject data) throws Exception {
    headroom();
    if (utf8(data.toString()).length > Policy.MAX_EVENT_BYTES)
      throw new IllegalArgumentException("Evidence too large");
    long seq;
    try (Cursor c =
        db.rawQuery("SELECT COALESCE(MAX(sequence),0)+1 FROM evidence WHERE local=1", null)) {
      c.moveToFirst();
      seq = c.getLong(0);
    }
    JSONObject event =
        new JSONObject()
            .put("protocol", Policy.PROTOCOL)
            .put("event_id", UUID.randomUUID().toString())
            .put("node_id", config.getString("node_id"))
            .put("sequence", seq)
            .put("observed_at", Instant.now().toString())
            .put("kind", kind)
            .put("data_json", data.toString());
    persist(event.getString("event_id"), seq, true, event);
    return event;
  }

  private void persist(String id, long sequence, boolean local, JSONObject event) throws Exception {
    JSONObject envelope =
        new JSONObject()
            .put("id", id)
            .put("sequence", sequence)
            .put("local", local)
            .put("event", event);
    String name = hex(MessageDigest.getInstance("SHA-256").digest(utf8(id))) + ".enc";
    File target = new File(journal, name);
    byte[] plain = utf8(envelope.toString());
    if (target.exists()) {
      if (!Arrays.equals(vault.open(Files.readAllBytes(target.toPath()), name), plain))
        throw new IllegalStateException("Conflicting immutable evidence");
    } else {
      headroom();
      File temporary = File.createTempFile("stage-", ".tmp", journal);
      try {
        try (FileOutputStream out = new FileOutputStream(temporary)) {
          out.write(vault.seal(plain, name));
          out.getFD().sync();
        }
        Os.link(temporary.getPath(), target.getPath());
        FileDescriptor dir = Os.open(journal.getPath(), OsConstants.O_RDONLY, 0);
        try {
          Os.fsync(dir);
        } finally {
          Os.close(dir);
        }
        journalBytes += target.length();
      } finally {
        if (!temporary.delete() && temporary.exists()) temporary.deleteOnExit();
      }
    }
    index(envelope);
  }

  private void index(JSONObject envelope) throws Exception {
    String id = envelope.getString("id");
    ContentValues row = new ContentValues();
    row.put("id", id);
    row.put("sequence", envelope.getLong("sequence"));
    row.put("local", envelope.getBoolean("local") ? 1 : 0);
    row.put("cipher", vault.seal(utf8(envelope.getJSONObject("event").toString()), id));
    db.insertWithOnConflict("evidence", null, row, SQLiteDatabase.CONFLICT_IGNORE);
  }

  public synchronized JSONArray pending() throws Exception {
    JSONArray events = new JSONArray();
    int bytes = 0;
    try (Cursor c =
        db.rawQuery(
            "SELECT id,cipher FROM evidence WHERE local=1 AND uploaded=0 ORDER BY sequence LIMIT"
                + " 32",
            null)) {
      while (c.moveToNext()) {
        byte[] raw = vault.open(c.getBlob(1), c.getString(0));
        if (events.length() > 0 && bytes + raw.length > 1024 * 1024) break;
        events.put(new JSONObject(new String(raw, StandardCharsets.UTF_8)));
        bytes += raw.length;
      }
    }
    return events;
  }

  public synchronized long count(boolean pending) {
    try (Cursor c =
        db.rawQuery(
            "SELECT COUNT(*) FROM evidence" + (pending ? " WHERE local=1 AND uploaded=0" : ""),
            null)) {
      c.moveToFirst();
      return c.getLong(0);
    }
  }

  public synchronized String meta(String key, String fallback) {
    try (Cursor c = db.rawQuery("SELECT value FROM meta WHERE key=?", new String[] {key})) {
      return c.moveToFirst() ? c.getString(0) : fallback;
    }
  }

  private boolean hasMeta(String key) {
    return !meta(key, "").isEmpty();
  }

  private void putMeta(String key, String value) {
    ContentValues row = new ContentValues();
    row.put("key", key);
    row.put("value", value);
    db.insertWithOnConflict("meta", null, row, SQLiteDatabase.CONFLICT_REPLACE);
  }

  public synchronized void syncResult(JSONObject reply, JSONArray submitted) throws Exception {
    if (!config.getString("subject_id").equals(reply.getString("subject_id")))
      throw new SecurityException("Wrong laptop identity");
    JSONArray accepted = reply.getJSONArray("accepted"), changes = reply.getJSONArray("changes");
    java.util.HashSet<String> ids = new java.util.HashSet<>();
    for (int i = 0; i < submitted.length(); i++)
      ids.add(submitted.getJSONObject(i).getString("event_id"));
    for (int i = 0; i < accepted.length(); i++)
      if (!ids.contains(accepted.getString(i)))
        throw new SecurityException("Laptop acknowledged an unsent event");
    // Independent immutable response evidence precedes projection/cursor update.
    for (int i = 0; i < changes.length(); i++) {
      JSONObject change = changes.getJSONObject(i);
      String state = change.getString("state"), id = change.getString("event_id");
      if (state.equals("completed") || state.equals("failed") || state.equals("interrupted")) {
        JSONObject response =
            new JSONObject()
                .put("event_id", id)
                .put("kind", "response")
                .put("state", state)
                .put("data_json", change.getJSONObject("result").toString());
        persist("reply:" + id + ":" + state, 0, false, response);
      }
    }
    db.beginTransaction();
    try {
      for (int i = 0; i < accepted.length(); i++)
        db.execSQL(
            "UPDATE evidence SET uploaded=1 WHERE id=?", new Object[] {accepted.getString(i)});
      for (int i = 0; i < changes.length(); i++) {
        JSONObject change = changes.getJSONObject(i);
        db.execSQL(
            "UPDATE evidence SET state=? WHERE id=?",
            new Object[] {change.getString("state"), change.getString("event_id")});
      }
      putMeta("epoch", reply.getString("epoch"));
      putMeta("cursor", Long.toString(reply.getLong("cursor")));
      putMeta("last_sync", Instant.now().toString());
      db.setTransactionSuccessful();
    } finally {
      db.endTransaction();
    }
  }

  public synchronized void memories(JSONObject reply) throws Exception {
    if (!config.getString("subject_id").equals(reply.getString("subject_id")))
      throw new SecurityException("Wrong laptop identity");
    JSONArray items = reply.getJSONArray("items");
    for (int i = 0; i < items.length(); i++) {
      JSONObject item = items.getJSONObject(i);
      persist(
          "memory:" + item.getString("event_id"),
          item.getLong("sequence"),
          false,
          new JSONObject()
              .put("event_id", item.getString("event_id"))
              .put("kind", "memory")
              .put("observed_at", item.getString("observed_at"))
              .put("data_json", item.toString()));
    }
    putMeta("memory_before", Long.toString(reply.getLong("before")));
  }

  /** Bounded decrypt/search: 200 recent records; never load a lifetime corpus. */
  public synchronized JSONArray recent(String query, boolean chat) throws Exception {
    JSONArray rows = new JSONArray();
    try (Cursor c =
        db.rawQuery(
            "SELECT id,cipher,state,uploaded FROM evidence ORDER BY rowid DESC LIMIT 200", null)) {
      while (c.moveToNext() && rows.length() < 50) {
        JSONObject event =
            new JSONObject(
                new String(vault.open(c.getBlob(1), c.getString(0)), StandardCharsets.UTF_8));
        String kind = event.getString("kind");
        if (chat && !kind.equals("chat") && !kind.equals("response")) continue;
        if (!query.isEmpty()
            && !event
                .toString()
                .toLowerCase(java.util.Locale.ROOT)
                .contains(query.toLowerCase(java.util.Locale.ROOT))) continue;
        event.put(
            "delivery",
            c.getInt(3) == 0
                    && !c.getString(0).startsWith("reply:")
                    && !c.getString(0).startsWith("memory:")
                ? "On this phone"
                : c.getString(2));
        rows.put(event);
      }
    }
    return rows;
  }

  /** Encrypted portable backup; passphrase protects a fresh independent key. */
  public synchronized void export(java.io.OutputStream target, char[] passphrase) throws Exception {
    if (passphrase.length < 12) throw new IllegalArgumentException("Use at least 12 characters");
    byte[] salt = new byte[16], iv = new byte[12];
    SecureRandom random = new SecureRandom();
    random.nextBytes(salt);
    random.nextBytes(iv);
    javax.crypto.spec.PBEKeySpec spec =
        new javax.crypto.spec.PBEKeySpec(passphrase, salt, 600_000, 256);
    byte[] key =
        javax.crypto.SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
            .generateSecret(spec)
            .getEncoded();
    spec.clearPassword();
    javax.crypto.Cipher cipher = javax.crypto.Cipher.getInstance("AES/GCM/NoPadding");
    cipher.init(
        javax.crypto.Cipher.ENCRYPT_MODE,
        new javax.crypto.spec.SecretKeySpec(key, "AES"),
        new javax.crypto.spec.GCMParameterSpec(128, iv));
    byte[] magic = utf8("PNODE01\n");
    cipher.updateAAD(magic);
    target.write(magic);
    target.write(salt);
    target.write(iv);
    try (javax.crypto.CipherOutputStream encrypted =
            new javax.crypto.CipherOutputStream(target, cipher);
        java.util.zip.ZipOutputStream zip = new java.util.zip.ZipOutputStream(encrypted)) {
      zip.putNextEntry(new java.util.zip.ZipEntry("identity.json"));
      zip.write(
          utf8(
              new JSONObject()
                  .put("protocol", Policy.PROTOCOL)
                  .put("node_id", config.getString("node_id"))
                  .put("subject_id", config.optString("subject_id"))
                  .toString()));
      zip.closeEntry();
      File[] files = journal.listFiles((d, n) -> n.endsWith(".enc"));
      if (files != null)
        for (File file : files) {
          zip.putNextEntry(new java.util.zip.ZipEntry("evidence/" + file.getName() + ".json"));
          zip.write(vault.open(Files.readAllBytes(file.toPath()), file.getName()));
          zip.closeEntry();
        }
    } finally {
      Arrays.fill(key, (byte) 0);
      Arrays.fill(passphrase, '\0');
    }
  }
}
