package org.prometheist.node;

import java.net.URI;

/** Safety tunables awaiting A16 native calibration, not hardware capacity claims. */
public final class Policy {
  private Policy() {}

  public static final String PROTOCOL = "prometheist-node/v1";
  public static final int MAX_EVENT_BYTES = 768 * 1024;
  public static final int MAX_RESPONSE_BYTES = 2 * 1024 * 1024;
  public static final int MEDIA_BYTES = 512 * 1024;
  public static final long MIN_FREE_BYTES = 256L * 1024 * 1024;
  public static final long MAX_VAULT_BYTES = 512L * 1024 * 1024;
  public static final long WINDOW_MS = 60_000;
  public static final long AUTO_PHOTO_MS = 15 * 60_000L;
  public static final int SAMPLE_US = 200_000; // 5 Hz requested; hardware may differ.

  public static String origin(String value) {
    URI uri = URI.create(value.trim());
    if (!"https".equals(uri.getScheme())
        || uri.getHost() == null
        || uri.getUserInfo() != null
        || uri.getQuery() != null
        || uri.getFragment() != null
        || (uri.getPath() != null && !uri.getPath().isEmpty() && !uri.getPath().equals("/"))
        || uri.getPort() > 65535
        || uri.getPort() == 0) {
      throw new IllegalArgumentException("Use the laptop's private HTTPS origin");
    }
    String normalized = uri.toString();
    return normalized.endsWith("/") ? normalized.substring(0, normalized.length() - 1) : normalized;
  }
}
