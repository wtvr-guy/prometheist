package org.prometheist.node;

import static org.junit.Assert.*;

import org.junit.Test;

public class PolicyTest {
  @Test
  public void secureOriginOnly() {
    assertEquals("https://laptop.tail.ts.net", Policy.origin("https://laptop.tail.ts.net/"));
    for (String value :
        new String[] {
          "http://host",
          "https://user:password@host",
          "https://host/path",
          "https://host?token=1",
          "https://host/#x",
          "https://host:99999"
        }) {
      try {
        Policy.origin(value);
        fail(value);
      } catch (IllegalArgumentException expected) {
      }
    }
  }

  @Test
  public void accumulatorRejectsNonfiniteAndBoundsDimensions() {
    WindowStats stats = new WindowStats(20);
    assertEquals(6, stats.sum.length);
    WindowStats motion = new WindowStats(3);
    motion.add(new float[] {1, 2, 3});
    motion.add(new float[] {3, 4, 5});
    motion.add(new float[] {Float.NaN, 2, 3});
    assertEquals(2, motion.samples);
    assertEquals(2, motion.mean(0), 0);
    assertEquals(1, motion.min[0], 0);
    assertEquals(3, motion.max[0], 0);
  }
}
