package org.prometheist.node;

import android.app.Activity;
import android.graphics.*;
import android.hardware.camera2.*;
import android.hardware.camera2.params.StreamConfigurationMap;
import android.media.*;
import android.os.*;
import android.util.Size;
import android.view.*;
import android.widget.*;
import java.io.ByteArrayOutputStream;
import java.nio.*;
import java.util.Arrays;
import org.json.JSONObject;

/** Deliberate foreground-only capture into private encrypted memory, never gallery. */
public final class CaptureActivity extends Activity {
  private HandlerThread cameraThread;
  private Handler cameraHandler;
  private CameraDevice camera;
  private CameraCaptureSession session;
  private ImageReader images;
  private TextureView preview;
  private Surface previewSurface;
  private TextView status;
  private Button capture;
  private volatile boolean recording, closing;
  private AudioRecord recorder;
  private int orientation;

  @Override
  public void onCreate(Bundle saved) {
    super.onCreate(saved);
    getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
    LinearLayout layout = new LinearLayout(this);
    layout.setOrientation(LinearLayout.VERTICAL);
    layout.setPadding(24, 60, 24, 24);
    layout.setBackgroundColor(Color.rgb(16, 26, 26));
    status = new TextView(this);
    status.setTextColor(Color.WHITE);
    status.setTextSize(20);
    layout.addView(status);
    capture = new Button(this);
    capture.setAllCaps(false);
    if ("photo".equals(getIntent().getStringExtra("kind"))) {
      status.setText("Private photo · nothing saved to gallery");
      preview = new TextureView(this);
      layout.addView(preview, new LinearLayout.LayoutParams(-1, 0, 1));
      capture.setText("Capture photo");
      capture.setOnClickListener(v -> shoot());
      cameraThread = new HandlerThread("private-camera");
      cameraThread.start();
      cameraHandler = new Handler(cameraThread.getLooper());
      preview.setSurfaceTextureListener(
          new TextureView.SurfaceTextureListener() {
            @Override
            public void onSurfaceTextureAvailable(SurfaceTexture surface, int w, int h) {
              openCamera();
            }

            @Override
            public void onSurfaceTextureSizeChanged(SurfaceTexture surface, int w, int h) {}

            @Override
            public boolean onSurfaceTextureDestroyed(SurfaceTexture surface) {
              return true;
            }

            @Override
            public void onSurfaceTextureUpdated(SurfaceTexture surface) {}
          });
    } else {
      status.setText(
          "Voice memo · up to 10 seconds\nAudio is saved privately; no cloud transcription.");
      capture.setText("Start recording");
      capture.setOnClickListener(
          v -> {
            if (recording) {
              recording = false;
            } else record();
          });
    }
    layout.addView(capture);
    Button cancel = new Button(this);
    cancel.setText("Close");
    cancel.setOnClickListener(v -> finish());
    layout.addView(cancel);
    setContentView(layout);
  }

  private void error(String message) {
    runOnUiThread(
        () -> {
          status.setText(message);
          capture.setEnabled(false);
        });
  }

  private void openCamera() {
    try {
      if (checkSelfPermission(android.Manifest.permission.CAMERA)
          != android.content.pm.PackageManager.PERMISSION_GRANTED)
        throw new SecurityException("Camera permission missing");
      CameraManager manager = getSystemService(CameraManager.class);
      String id = null;
      for (String candidate : manager.getCameraIdList()) {
        CameraCharacteristics c = manager.getCameraCharacteristics(candidate);
        if (id == null) id = candidate;
        if (Integer.valueOf(CameraCharacteristics.LENS_FACING_BACK)
            .equals(c.get(CameraCharacteristics.LENS_FACING))) {
          id = candidate;
          break;
        }
      }
      if (id == null) throw new IllegalStateException("No camera");
      CameraCharacteristics characteristics = manager.getCameraCharacteristics(id);
      orientation = characteristics.get(CameraCharacteristics.SENSOR_ORIENTATION);
      StreamConfigurationMap map =
          characteristics.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP);
      Size chosen = null;
      for (Size size : map.getOutputSizes(ImageFormat.JPEG)) {
        if (size.getWidth() <= 1280
            && size.getHeight() <= 1280
            && (chosen == null
                || size.getWidth() * size.getHeight() > chosen.getWidth() * chosen.getHeight()))
          chosen = size;
      }
      if (chosen == null) {
        error("Camera offers no bounded capture size");
        return;
      }
      images = ImageReader.newInstance(chosen.getWidth(), chosen.getHeight(), ImageFormat.JPEG, 2);
      images.setOnImageAvailableListener(
          reader -> {
            try (Image image = reader.acquireLatestImage()) {
              if (image == null) return;
              ByteBuffer buffer = image.getPlanes()[0].getBuffer();
              byte[] bytes = new byte[buffer.remaining()];
              buffer.get(bytes);
              if (bytes.length > Policy.MEDIA_BYTES) {
                Bitmap bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
                ByteArrayOutputStream compressed = new ByteArrayOutputStream();
                bitmap.compress(Bitmap.CompressFormat.JPEG, 55, compressed);
                bitmap.recycle();
                bytes = compressed.toByteArray();
              }
              save("photo", "image/jpeg", bytes);
            } catch (Exception e) {
              error("Capture could not be saved; existing evidence retained");
            }
          },
          cameraHandler);
      Size previewSize = map.getOutputSizes(SurfaceTexture.class)[0];
      for (Size s : map.getOutputSizes(SurfaceTexture.class))
        if (s.getWidth() <= 1280 && s.getHeight() <= 1280) {
          previewSize = s;
          break;
        }
      preview
          .getSurfaceTexture()
          .setDefaultBufferSize(previewSize.getWidth(), previewSize.getHeight());
      previewSurface = new Surface(preview.getSurfaceTexture());
      manager.openCamera(
          id,
          new CameraDevice.StateCallback() {
            @Override
            public void onOpened(CameraDevice device) {
              if (closing) {
                device.close();
                return;
              }
              camera = device;
              try {
                camera.createCaptureSession(
                    Arrays.asList(previewSurface, images.getSurface()),
                    new CameraCaptureSession.StateCallback() {
                      @Override
                      public void onConfigured(CameraCaptureSession configured) {
                        if (closing) {
                          configured.close();
                          return;
                        }
                        session = configured;
                        try {
                          CaptureRequest.Builder request =
                              camera.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);
                          request.addTarget(previewSurface);
                          session.setRepeatingRequest(request.build(), null, cameraHandler);
                        } catch (CameraAccessException e) {
                          error("Preview unavailable");
                        }
                      }

                      @Override
                      public void onConfigureFailed(CameraCaptureSession s) {
                        error("Camera configuration unavailable");
                      }
                    },
                    cameraHandler);
              } catch (CameraAccessException e) {
                error("Camera unavailable");
              }
            }

            @Override
            public void onDisconnected(CameraDevice d) {
              d.close();
              error("Camera disconnected");
            }

            @Override
            public void onError(CameraDevice d, int code) {
              d.close();
              error("Camera unavailable");
            }
          },
          cameraHandler);
    } catch (Exception e) {
      error("Camera permission or hardware unavailable");
    }
  }

  private void shoot() {
    if (session == null || camera == null) return;
    capture.setEnabled(false);
    try {
      CaptureRequest.Builder request =
          camera.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE);
      request.addTarget(images.getSurface());
      request.set(CaptureRequest.JPEG_QUALITY, (byte) 70);
      int rotation = getWindowManager().getDefaultDisplay().getRotation();
      int degrees =
          rotation == Surface.ROTATION_90
              ? 90
              : rotation == Surface.ROTATION_180 ? 180 : rotation == Surface.ROTATION_270 ? 270 : 0;
      request.set(CaptureRequest.JPEG_ORIENTATION, (orientation - degrees + 360) % 360);
      session.capture(request.build(), null, cameraHandler);
    } catch (Exception e) {
      error("Capture failed");
    }
  }

  private void record() {
    try {
      if (checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)
          != android.content.pm.PackageManager.PERMISSION_GRANTED)
        throw new SecurityException("Microphone permission missing");
      int minimum =
          AudioRecord.getMinBufferSize(
              16000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
      recorder =
          new AudioRecord(
              MediaRecorder.AudioSource.MIC,
              16000,
              AudioFormat.CHANNEL_IN_MONO,
              AudioFormat.ENCODING_PCM_16BIT,
              Math.max(8192, minimum * 2));
      if (recorder.getState() != AudioRecord.STATE_INITIALIZED) throw new IllegalStateException();
      recorder.startRecording();
      recording = true;
      capture.setText("Stop and save");
      status.setText("Recording privately…");
      new Thread(
              () -> {
                try (ByteArrayOutputStream pcm = new ByteArrayOutputStream()) {
                  byte[] buffer = new byte[4096];
                  int budget = 16000 * 2 * 10;
                  while (recording && pcm.size() < budget) {
                    int count =
                        recorder.read(buffer, 0, Math.min(buffer.length, budget - pcm.size()));
                    if (count < 0) break;
                    pcm.write(buffer, 0, count);
                  }
                  recording = false;
                  recorder.stop();
                  recorder.release();
                  recorder = null;
                  Arrays.fill(buffer, (byte) 0);
                  if (pcm.size() == 0) {
                    error("No audio captured");
                    return;
                  }
                  byte[] raw = pcm.toByteArray();
                  ByteBuffer wave =
                      ByteBuffer.allocate(raw.length + 44).order(ByteOrder.LITTLE_ENDIAN);
                  wave.put(new byte[] {'R', 'I', 'F', 'F'})
                      .putInt(raw.length + 36)
                      .put(new byte[] {'W', 'A', 'V', 'E', 'f', 'm', 't', ' '})
                      .putInt(16)
                      .putShort((short) 1)
                      .putShort((short) 1)
                      .putInt(16000)
                      .putInt(32000)
                      .putShort((short) 2)
                      .putShort((short) 16)
                      .put(new byte[] {'d', 'a', 't', 'a'})
                      .putInt(raw.length)
                      .put(raw);
                  save("audio", "audio/wav", wave.array());
                  Arrays.fill(raw, (byte) 0);
                } catch (Exception e) {
                  error("Microphone or storage unavailable");
                } finally {
                  recording = false;
                  if (recorder != null) {
                    try {
                      recorder.stop();
                    } catch (IllegalStateException ignored) {
                    }
                    recorder.release();
                    recorder = null;
                  }
                }
              },
              "private-voice-memo")
          .start();
    } catch (Exception e) {
      if (recorder != null) {
        recorder.release();
        recorder = null;
      }
      error("Microphone unavailable");
    }
  }

  private void save(String kind, String mime, byte[] bytes) throws Exception {
    if (bytes.length > Policy.MEDIA_BYTES) throw new IllegalStateException("Capture too large");
    NodeStore.get(this)
        .append(
            kind,
            new JSONObject()
                .put("mime_type", mime)
                .put(
                    "base64",
                    android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP))
                .put("deliberate_capture", true));
    Arrays.fill(bytes, (byte) 0);
    runOnUiThread(
        () -> {
          if (!closing) {
            status.setText("Saved privately. Sync to your laptop when ready.");
            capture.setEnabled(false);
          }
        });
  }

  @Override
  public void onPause() {
    super.onPause();
    closing = true;
    recording = false;
    if (session != null) session.close();
    if (camera != null) camera.close();
    if (images != null) images.close();
    if (previewSurface != null) previewSurface.release();
    if (cameraThread != null) cameraThread.quitSafely();
    finish();
  }
}
