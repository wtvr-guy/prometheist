package org.prometheist.node;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.HttpsURLConnection;
import org.json.JSONArray;
import org.json.JSONObject;

/** HTTPS only, system trust, no redirects, fixed paired destination, bounded I/O. */
public final class NodeSync {
  private static final Object LOCK = new Object();

  public static String run(Context context, boolean manual) throws Exception {
    synchronized (LOCK) {
      NodeStore store = NodeStore.get(context);
      JSONObject config = store.config();
      if (!store.paired()) return "Pair your laptop to sync. Offline records are safe here.";
      if (!manual && !config.optBoolean("auto_sync")) return "Automatic sync is paused";
      ConnectivityManager manager = context.getSystemService(ConnectivityManager.class);
      NetworkCapabilities net = manager.getNetworkCapabilities(manager.getActiveNetwork());
      if (net == null) return "Offline — queued evidence stays on this phone";
      if (config.optBoolean("wifi_only", true)
          && !net.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_METERED))
        return "Waiting for an unmetered connection. You can change this in Connect.";
      for (int page = 0; page < 4; page++) { // Safety bound: 4 pages per job, not lifetime upload.
        JSONArray pending = store.pending();
        JSONObject payload =
            new JSONObject()
                .put("protocol", Policy.PROTOCOL)
                .put("node_id", config.getString("node_id"))
                .put("subject_id", config.getString("subject_id"))
                .put("epoch", store.meta("epoch", ""))
                .put("after", Long.parseLong(store.meta("cursor", "0")))
                .put("events", pending);
        JSONObject reply = request(config, "/v1/sync", payload, true);
        if (!Policy.PROTOCOL.equals(reply.getString("protocol")))
          throw new SecurityException("Unsupported laptop protocol");
        store.syncResult(reply, pending);
        if (pending.length() == 0 && reply.getJSONArray("changes").length() < 32) break;
      }
      return "Synced privately · " + store.count(true) + " events still queued";
    }
  }

  public static void pair(Context context, String input) throws Exception {
    synchronized (LOCK) {
      NodeStore store = NodeStore.get(context);
      JSONObject existing = store.config(), enrollment = new JSONObject(input);
      if (!Policy.PROTOCOL.equals(enrollment.getString("protocol")))
        throw new IllegalArgumentException("Unsupported pairing format");
      String origin = Policy.origin(enrollment.getString("url")),
          subject = enrollment.getString("subject_id");
      if (existing.optBoolean("paired")
          && (!origin.equals(existing.optString("url"))
              || !subject.equals(existing.optString("subject_id"))))
        throw new SecurityException(
            "Already bound to a different laptop or identity. Export first; use a separate app"
                + " installation for another identity.");
      JSONObject config = new JSONObject(existing.toString()).put("url", origin);
      JSONObject request =
          new JSONObject()
              .put("node_id", config.getString("node_id"))
              .put("credential", config.getString("credential"))
              .put("code", enrollment.getString("code"))
              .put("label", android.os.Build.MANUFACTURER + " " + android.os.Build.MODEL);
      JSONObject reply = request(config, "/v1/pair", request, false);
      if (!subject.equals(reply.getString("subject_id"))
          || !origin.equals(reply.getString("public_url"))
          || !config.getString("node_id").equals(reply.getString("node_id")))
        throw new SecurityException("Pairing identity mismatch");
      store.configure(config.put("subject_id", subject).put("paired", true));
    }
  }

  public static void memory(Context context, boolean latest) throws Exception {
    synchronized (LOCK) {
      NodeStore store = NodeStore.get(context);
      if (!store.paired()) throw new IllegalStateException("Pair first");
      store.memories(
          request(
              store.config(),
              "/v1/memory?before="
                  + (latest
                      ? Long.toString(9007199254740991L)
                      : store.meta("memory_before", Long.toString(9007199254740991L))),
              null,
              true));
    }
  }

  private static JSONObject request(
      JSONObject config, String path, JSONObject payload, boolean auth) throws Exception {
    String origin = Policy.origin(config.getString("url"));
    HttpsURLConnection connection = (HttpsURLConnection) new URL(origin + path).openConnection();
    connection.setInstanceFollowRedirects(false);
    connection.setConnectTimeout(15_000);
    connection.setReadTimeout(30_000);
    connection.setRequestProperty("Accept", "application/json");
    if (auth) {
      connection.setRequestProperty("Authorization", "Bearer " + config.getString("credential"));
      connection.setRequestProperty("X-Node-ID", config.getString("node_id"));
    }
    try {
      if (payload != null) {
        byte[] raw = payload.toString().getBytes(StandardCharsets.UTF_8);
        connection.setRequestMethod("POST");
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json");
        connection.setFixedLengthStreamingMode(raw.length);
        try (java.io.OutputStream out = connection.getOutputStream()) {
          out.write(raw);
        }
      }
      int status = connection.getResponseCode();
      if (status != 200)
        throw new IllegalStateException(
            status == 401
                ? "Device revoked or pairing expired"
                : status == 409
                    ? "Evidence conflict. Sync stopped without overwriting history."
                    : "Laptop returned HTTP " + status);
      try (InputStream in = connection.getInputStream();
          ByteArrayOutputStream out = new ByteArrayOutputStream()) {
        byte[] bytes = new byte[8192];
        int size;
        while ((size = in.read(bytes)) != -1) {
          if (out.size() + size > Policy.MAX_RESPONSE_BYTES)
            throw new IllegalStateException("Laptop response too large");
          out.write(bytes, 0, size);
        }
        return new JSONObject(out.toString(StandardCharsets.UTF_8.name()));
      }
    } finally {
      connection.disconnect();
    }
  }
}
