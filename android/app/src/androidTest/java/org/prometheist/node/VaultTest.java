package org.prometheist.node;

import static org.junit.Assert.*;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

/** Run only in a disposable emulator/test app profile, never against user history. */
@RunWith(AndroidJUnit4.class)
public class VaultTest {
  @Test
  public void testCiphertextAuthentication() throws Exception {
    Vault vault = new Vault(InstrumentationRegistry.getInstrumentation().getTargetContext(), false);
    byte[] raw = "PRIVATE DATA".getBytes(StandardCharsets.UTF_8), cipher = vault.seal(raw, "a");
    assertFalse(new String(cipher, StandardCharsets.UTF_8).contains("PRIVATE DATA"));
    assertEquals("PRIVATE DATA", new String(vault.open(cipher, "a"), StandardCharsets.UTF_8));
    try {
      vault.open(cipher, "b");
      fail("AAD must bind identity");
    } catch (javax.crypto.AEADBadTagException expected) {
    }
    cipher[cipher.length - 1] ^= 1;
    try {
      vault.open(cipher, "a");
      fail("Tamper must fail");
    } catch (javax.crypto.AEADBadTagException expected) {
    }
  }

  @Test
  public void testOfflineAppendAndExactEvidence() throws Exception {
    NodeStore store =
        NodeStore.get(InstrumentationRegistry.getInstrumentation().getTargetContext());
    JSONObject record =
        store.append("note", new JSONObject().put("text", "Instrumented fictional note"));
    assertEquals("note", record.getString("kind"));
    assertTrue(store.count(true) > 0);
    assertTrue(store.recent("Instrumented fictional note", false).length() > 0);
  }
}
