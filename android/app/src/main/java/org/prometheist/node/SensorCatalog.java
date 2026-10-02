package org.prometheist.node;

import android.hardware.Sensor;
import android.hardware.SensorManager;
import java.util.ArrayList;
import java.util.List;

public final class SensorCatalog {
  private SensorCatalog() {}

  public static List<Sensor> supported(SensorManager manager) {
    List<Sensor> sensors = new ArrayList<>();
    int[] types = {
      Sensor.TYPE_ACCELEROMETER,
      Sensor.TYPE_GYROSCOPE,
      Sensor.TYPE_MAGNETIC_FIELD,
      Sensor.TYPE_LIGHT,
      Sensor.TYPE_PROXIMITY,
      Sensor.TYPE_PRESSURE,
      Sensor.TYPE_GRAVITY,
      Sensor.TYPE_LINEAR_ACCELERATION,
      Sensor.TYPE_ROTATION_VECTOR,
      Sensor.TYPE_RELATIVE_HUMIDITY,
      Sensor.TYPE_AMBIENT_TEMPERATURE,
      Sensor.TYPE_STEP_COUNTER,
      Sensor.TYPE_STEP_DETECTOR
    };
    for (int type : types) {
      Sensor sensor = manager.getDefaultSensor(type);
      if (sensor != null) sensors.add(sensor);
    }
    return sensors;
  }

  public static String label(int type) {
    switch (type) {
      case Sensor.TYPE_ACCELEROMETER:
        return "Acceleration · m/s²";
      case Sensor.TYPE_GYROSCOPE:
        return "Rotation rate · rad/s";
      case Sensor.TYPE_MAGNETIC_FIELD:
        return "Magnetic field · µT";
      case Sensor.TYPE_LIGHT:
        return "Ambient light · lux";
      case Sensor.TYPE_PROXIMITY:
        return "Proximity · cm (may be virtual)";
      case Sensor.TYPE_PRESSURE:
        return "Air pressure · hPa";
      case Sensor.TYPE_GRAVITY:
        return "Gravity · m/s²";
      case Sensor.TYPE_LINEAR_ACCELERATION:
        return "Linear acceleration · m/s²";
      case Sensor.TYPE_ROTATION_VECTOR:
        return "Orientation · rotation vector";
      case Sensor.TYPE_RELATIVE_HUMIDITY:
        return "Relative humidity · %";
      case Sensor.TYPE_AMBIENT_TEMPERATURE:
        return "Ambient temperature · °C";
      case Sensor.TYPE_STEP_COUNTER:
        return "Step counter · since device boot";
      case Sensor.TYPE_STEP_DETECTOR:
        return "Step detections";
      default:
        return "Sensor " + type;
    }
  }
}
