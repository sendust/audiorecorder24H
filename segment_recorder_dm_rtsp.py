#!/usr/bin/python3

#   seamless, segmented audio recorder (mono L/R save)
#   by sendust (modified for per-channel RMS rename)
#   2025/9/23   functions to single class module
#   2025/10/2   json for config, record max_rms
#   2025/10/13  rename wave file name with max rms dB
#   2025/10/26 mono 2 stream (L/R) + RMS filename version
#   2025/11/04  rtsp streaming with mediamtx, change wav rate 44100 -> 48000
#

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject, GLib

import threading
import queue, json, os, sys
import wave
import time
import numpy as np
from datetime import datetime


class JsonConfig:
    def __init__(self, default_file="default.json"):
        # public dict property
        self.data: dict = {}

        # determine file path (use sys.argv[1] if provided, else default.json)
        if len(sys.argv) > 1:
            filepath = sys.argv[1]
        else:
            filepath = default_file

        # load JSON file if it exists
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            raise FileNotFoundError(f"JSON file not found: {filepath}")



class segment_recorder:
    """A GStreamer-based stereo recorder that saves two mono WAV files (L/R) with RMS dB in filename."""
    def __init__(self, cfg):
        Gst.init(None)
        self.audio_queue = queue.Queue()
        self.write_queue = queue.Queue()
        self.max_rms_L = -10000
        self.max_rms_R = -10000
        self.current_wave_file = {}
        self.current_wave_filename = {}
        self.wave_file_lock = threading.Lock()
        self.running = True
        self.timekeeper_prev = "00"
        self.cfg = cfg
        self.hasconsole = sys.stdout.isatty()


    def display_timestamp_progress(self, pipeline):
        position = pipeline.query_position(Gst.Format.TIME)[1]
        position_in_seconds = position / Gst.SECOND
        if self.hasconsole:
            L_short = split_filepath(self.current_wave_filename.get('L')).get("full_filename")
            R_short = split_filepath(self.current_wave_filename.get('R')).get("full_filename")
            print(f"Current Position: {seconds_to_hms(position_in_seconds)} seconds -- {L_short} >< {R_short}")
        return True

    # ------------------------------------------------------
    # WAV / filename handling
    # ------------------------------------------------------
    def create_wave_file(self, filename):
        wf = wave.open(filename, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        return wf

    def get_new_filename(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = self.cfg.get("prefix", "segment")
        path_full = os.path.join(self.cfg.get("path", "."), f"{prefix}_{timestamp}.wav")
        return path_full

    def rename_with_rms(self, left_fn, right_fn):
        """Close files and rename both with RMS dB value."""
        def rename_with_value(filename, label, rms_val):
            base, ext = os.path.splitext(filename)
            newname = f"{base}_{label}({rms_val:.1f}dB){ext}"
            try:
                os.rename(filename, newname)
                return newname
            except Exception as e:
                print(f"Rename failed: {e}")
                return filename

        renamed_L = rename_with_value(left_fn, "L", self.max_rms_L)
        renamed_R = rename_with_value(right_fn, "R", self.max_rms_R)
        print(f"[SEGMENT CLOSED] L={self.max_rms_L:.1f} dB, R={self.max_rms_R:.1f} dB")
        return renamed_L, renamed_R

    def new_segment(self):
        """Close current segment (rename with RMS) and open new L/R mono files."""
        with self.wave_file_lock:
            # close and rename previous
            if self.current_wave_file:
                left_fn = self.current_wave_file["L"]._file.name
                right_fn = self.current_wave_file["R"]._file.name
                for wf in self.current_wave_file.values():
                    wf.close()
                self.rename_with_rms(left_fn, right_fn)

            # create new segment
            base = self.get_new_filename()
            base_noext, ext = os.path.splitext(base)
            
            ch1 = self.cfg.get("left", "L")
            ch2 = self.cfg.get("right", "R")
            
            left_fn = f"{base_noext}_{ch1}{ext}"
            right_fn = f"{base_noext}_{ch2}{ext}"
            
            os.makedirs(os.path.dirname(left_fn), exist_ok=True)
            os.makedirs(os.path.dirname(right_fn), exist_ok=True)

            self.current_wave_file = {
                "L": self.create_wave_file(left_fn),
                "R": self.create_wave_file(right_fn)
            }
            self.current_wave_filename["L"] = left_fn
            self.current_wave_filename["R"] = right_fn
            self.max_rms_L = -10000
            self.max_rms_R = -10000
            print(f"[NEW SEGMENT] {left_fn}, {right_fn}")

    # ------------------------------------------------------
    # GStreamer callbacks
    # ------------------------------------------------------
    def appsink_callback(self, sink, data):
        sample = sink.emit("pull-sample")
        if sample:
            buffer = sample.get_buffer()
            success, map_info = buffer.map(Gst.MapFlags.READ)
            if success:
                audio_data = map_info.data
                try:
                    data_b = audio_data.tobytes()
                    self.audio_queue.put(data_b)
                except:
                    self.audio_queue.put(audio_data)
                buffer.unmap(map_info)
            return Gst.FlowReturn.OK
        return Gst.FlowReturn.ERROR

    def on_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.ELEMENT:
            struct = message.get_structure()
            if struct and struct.get_name() == "level":
                rms = [f"{x:.2f}" for x in struct.get_value("rms")]
                peak = [f"{x:.2f}" for x in struct.get_value("peak")]
                decay = [f"{x:.2f}" for x in struct.get_value("decay")]
                if self.hasconsole:
                    print(f"RMS: {rms}, Peak: {peak}, Decay: {decay}", end="\r")
                self.max_rms_L= max(self.max_rms_L, float(rms[0]))
                self.max_rms_R= max(self.max_rms_R, float(rms[1]))
        elif t == Gst.MessageType.EOS:
            print("End of stream")
            self.running = False
            self.mainloop.quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err}, {debug}")
            self.mainloop.quit()

    # ------------------------------------------------------
    # Thread workers
    # ------------------------------------------------------
    def collector_thread_func(self):
        while self.running:
            time.sleep(1)
            chunk = bytearray()
            while not self.audio_queue.empty():
                chunk.extend(self.audio_queue.get())
            if chunk:
                self.write_queue.put(chunk)

    def writer_thread_func(self):
        """Split stereo (L/R) PCM and write to mono files."""
        while self.running or not self.write_queue.empty():
            try:
                data = self.write_queue.get(timeout=0.5)
                samples = np.frombuffer(data, dtype=np.int16)
                left = samples[0::2]
                right = samples[1::2]
                with self.wave_file_lock:
                    if self.current_wave_file:
                        self.current_wave_file["L"].writeframes(left.tobytes())
                        self.current_wave_file["R"].writeframes(right.tobytes())
            except queue.Empty:
                continue

    def segment_listener(self):
        while self.running:
            input()
            self.new_segment()

    # ------------------------------------------------------
    # Timer for auto segment rotation
    # ------------------------------------------------------
    def timekeeper(self):
        timekeeper_now = datetime.now().strftime("%M")
        if self.timekeeper_prev.endswith("9") and timekeeper_now.endswith("0"):
            self.new_segment()
        self.timekeeper_prev = timekeeper_now
        return True

    # ------------------------------------------------------
    # Main loop
    # ------------------------------------------------------


    def loop(self):
        
        pipeline_desc = (
        "alsasrc name=src ! "
        "tee name=t t. ! "
        "queue ! audioconvert ! audioresample ! " 
        "audio/x-raw,format=S16LE,channels=2,rate=48000 ! "
        "level interval=100000000 ! "
        "appsink name=sink emit-signals=true max-buffers=100 drop=true "
        "t. ! queue ! audioconvert ! deinterleave name=d "
        "d.src_0 ! queue ! audioconvert ! audioresample ! opusenc ! rtspclientsink name=stream0  "
        "d.src_1 ! queue ! audioconvert ! audioresample ! opusenc ! rtspclientsink name=stream1 "
        )

        pipeline = Gst.parse_launch(pipeline_desc)
        appsink = pipeline.get_by_name("sink")
        appsink.connect("new-sample", self.appsink_callback, None)
        
        if self.cfg.get("device", None):
            src = pipeline.get_by_name("src")
            src.set_property("device", self.cfg.get("device"))
            print(f'pulse source = {self.cfg.get("device")}')

        url0 = pipeline.get_by_name("stream0")
        url0.set_property("location", self.cfg.get("stream0", "left"))
        print(f'set stream0 = {self.cfg.get("stream0", "left")}')

        url1 = pipeline.get_by_name("stream1")
        url1.set_property("location", self.cfg.get("stream1", "right"))
        print(f'set stream1 = {self.cfg.get("stream1", "right")}')
        
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

        # GStreamer 파이프라인 시작
        pipeline.set_state(Gst.State.PLAYING)

        # 초기 세그먼트 시작
        self.new_segment()

        # 쓰레드 시작
        collector_thread = threading.Thread(target=self.collector_thread_func, daemon=True)
        writer_thread = threading.Thread(target=self.writer_thread_func, daemon=True)
        if self.hasconsole:
            threading.Thread(target=self.segment_listener, daemon=True).start()

        collector_thread.start()
        writer_thread.start()

        #GLib.timeout_add(100, lambda: True) # return false to STOP
        GLib.timeout_add(100, self.timekeeper) # return false to STOP
        GLib.timeout_add_seconds(1, self.display_timestamp_progress, pipeline)
        if self.hasconsole:
            print("Recording started. Press Enter to start new segment. Ctrl+C to stop.")
        else:
            print("Recording started..")

        self.mainloop = GLib.MainLoop()

        try:
            self.mainloop.run()

        except KeyboardInterrupt:
            print("Stopping...")
        
        finally:
            self.mainloop.quit()

            # 종료
            self.running = False
            collector_thread.join()
            writer_thread.join()

            pipeline.set_state(Gst.State.NULL)

            with self.wave_file_lock:
                for wf in self.current_wave_file.values():
                    wf.close()

            print("Done.")


def seconds_to_hms(seconds: float) -> str:
    """Convert float seconds to hh:mm:ss format (rounded to nearest second)"""
    total_seconds = int(round(seconds))
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02}:{m:02}:{s:02}"


def split_filepath(filepath):
    dirname, basename = os.path.split(filepath)
    name_only, extension = os.path.splitext(basename)
    return {
    "directory_path": dirname,
    "full_filename": basename,
    "filename_only": name_only,
    "extension": extension
    }

if __name__ == "__main__":
    config = JsonConfig()
    sr = segment_recorder(config.data)
    sr.loop()
