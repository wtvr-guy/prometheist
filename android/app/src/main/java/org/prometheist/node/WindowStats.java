package org.prometheist.node;

/** Bounded pre-admission accumulator. Statistics are observations, never raw history. */
public final class WindowStats {
  public long samples;
  public final double[] sum, min, max, last;

  public WindowStats(int dimensions) {
    int count = Math.max(1, Math.min(dimensions, 6));
    sum = new double[count];
    min = new double[count];
    max = new double[count];
    last = new double[count];
    java.util.Arrays.fill(min, Double.POSITIVE_INFINITY);
    java.util.Arrays.fill(max, Double.NEGATIVE_INFINITY);
  }

  public void add(float[] values) {
    for (int i = 0; i < sum.length; i++)
      if (i >= values.length || !Float.isFinite(values[i])) return;
    samples++;
    for (int i = 0; i < sum.length; i++) {
      double value = values[i];
      sum[i] += value;
      min[i] = Math.min(min[i], value);
      max[i] = Math.max(max[i], value);
      last[i] = value;
    }
  }

  public double mean(int index) {
    return samples == 0 ? 0 : sum[index] / samples;
  }
}
