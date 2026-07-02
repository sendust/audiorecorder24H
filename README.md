# Segment Recorder + Dual RTSP Stream

A Python + GStreamer based stereo audio recorder that simultaneously:

- Records stereo audio as **two independent mono WAV files (L/R)**
- Streams each channel independently over **RTSP (Opus)**
- Automatically creates **10-minute recording segments**
- Renames completed WAV files with the **maximum RMS level (dB)**
- Supports configuration through a simple JSON file

---

# Features

- Stereo ALSA audio capture
- Split Left / Right into independent mono WAV files
- RTSP streaming for each channel
- Automatic 10-minute segmentation
- Manual segmentation (Press **Enter**)
- RMS monitoring using GStreamer `level`
- Automatically appends maximum RMS value to filename
- JSON configuration
- Console progress display

---

# Pipeline

```text
                         ALSA Input
                             │
                             ▼
                        +------------+
                        |  alsasrc   |
                        +------------+
                             │
                             ▼
                           tee
                    ┌────────┴────────┐
                    │                 │
                    │                 │
                    ▼                 ▼
             Recording Path     Streaming Path
                    │                 │
                    ▼                 ▼
             appsink (PCM)      deinterleave
                    │            ┌────┴────┐
                    │            │         │
                    ▼            ▼         ▼
           Audio Queue        Left      Right
                    │          │          │
                    ▼          ▼          ▼
             Writer Thread   opusenc   opusenc
                    │          │          │
           ┌────────┴──────┐   │          │
           │               │   │          │
           ▼               ▼   ▼          ▼
      Left WAV        Right WAV RTSP0   RTSP1
```

---

# Recording Flow

```text
ALSA
  │
  ▼
Capture Stereo PCM
  │
  ▼
Split L/R
  │
  ├────────► Write Left WAV
  │
  └────────► Write Right WAV

Every 10 minutes

Close Files
      │
      ▼
Measure Max RMS
      │
      ▼
Rename Files

segment_20260702_103000_Left_L(-12.4dB).wav
segment_20260702_103000_Right_R(-9.8dB).wav
```

---

# Configuration

Example JSON

```json
{
    "device": "hw:1,0",
    "prefix": "HW1",
    "left": "StudioA",
    "right": "StudioB",
    "path": "/mnt/sda1/data1",

    "stream0": "rtsp://127.0.0.1:8554/left",
    "stream1": "rtsp://127.0.0.1:8554/right"
}
```

## Parameters

| Name | Description |
|------|-------------|
| device | ALSA capture device |
| prefix | Prefix of output filename |
| left | Left channel name |
| right | Right channel name |
| path | Output directory |
| stream0 | Left RTSP destination |
| stream1 | Right RTSP destination |

---

# Output Files

Example

```text
20260702_103000_StudioA_L(-12.3dB).wav
20260702_103000_StudioB_R(-10.7dB).wav
```

---

# RTSP Streams

Two independent RTSP streams are published.

```text
Left Channel
rtsp://server:8554/left

Right Channel
rtsp://server:8554/right
```

Codec

- Opus
- 48 kHz
- Mono

---

# Automatic Segmentation

A new recording segment is automatically created every **10 minutes**.

```
00
10
20
30
40
50
```

You can also manually create a new segment by pressing:

```
Enter
```

---

# Console Output

```
Recording started.

Current Position: 00:03:15

RMS: [-15.2, -13.7]

[SEGMENT CLOSED]
L=-12.4 dB
R=-10.8 dB

[NEW SEGMENT]
```

---

# Dependencies

Python

- Python 3

Python packages

```
numpy
PyGObject
```

Ubuntu packages

```bash
sudo apt install \
    python3-gi \
    python3-gst-1.0 \
    gir1.2-gstreamer-1.0 \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-libav
```

---

# Running

Using the default configuration

```bash
python3 segment_recorder_dm_rtsp.py
```

Using a custom configuration

```bash
python3 segment_recorder_dm_rtsp.py alsa_dm1.json
```

Example

```bash
python3 segment_recorder_dm_rtsp.py alsa_dm2.json
```

---

# Typical Use Cases

- Broadcast audio logging
- Government agency recording
- Simultaneous archive + RTSP monitoring
- Audio confidence monitoring
- Continuous recording systems

---

# License

MIT License
