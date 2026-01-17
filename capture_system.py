import logging
import asyncio
import os
import time
import fractions
import subprocess
import threading
import av
import numpy as np
from aiortc.mediastreams import MediaStreamTrack

logger = logging.getLogger("NeonCapture")

IS_WINDOWS = os.name == "nt"

class BaseCaptureTrack(MediaStreamTrack):
    """
    Base simplificada para captura via FFmpeg com Pipes.
    """
    def __init__(self):
        super().__init__()
        self.process = None
        self._running = False
        self._latest_frame = None
        self._lock = threading.Lock()
        self._ev = asyncio.Event()
        self.frame_count = 0
        self._buf_idx = 0
        
        # Performance Tracking
        self._last_fps_check = time.time()
        self._frame_counter = 0
        self._fps_history = []
        self._last_log_time = time.time()

    def _start_ffmpeg(self, cmd, env=None):
        self.stop() 
        self._running = True
        
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        logger.info(f"[{self.kind.upper()}] Iniciando FFmpeg (MAX PERF)...")
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, 
            env=full_env,
            bufsize=10**7 
        )
        
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        
        self._err_thread = threading.Thread(target=self._error_loop, daemon=True)
        self._err_thread.start()

    def _error_loop(self):
        while self._running and self.process and self.process.stderr:
            try:
                line = self.process.stderr.readline()
                if not line: break
                line_str = line.decode().strip()
                if "error" in line_str.lower():
                    logger.error(f"[FFmpeg {self.kind}] {line_str}")
                # Filter out warnings to clean logs unless critical
                elif "dropped" in line_str.lower():
                    logger.warning(f"[FFmpeg {self.kind}] {line_str}")
            except: break

    def _read_loop(self):
        if hasattr(self, "is_encoded") and self.is_encoded:
            self._read_loop_encoded()
        else:
            self._read_loop_raw()

    def _read_loop_encoded(self):
        """Robust OBS-style reading using PyAV's demuxer on the pipe."""
        container = None
        try:
            # We use Annex-B for H.264 and Matroska for Opus to ensure flushable packets
            fmt = "h264" if self.kind == "video" else "matroska"
            container = av.open(self.process.stdout, format=fmt)
            
            # Identify the stream
            stream = None
            if self.kind == "video":
                stream = container.streams.video[0]
            else:
                stream = container.streams.audio[0]

            for packet in container.demux(stream):
                if not packet.data: continue
                
                with self._lock:
                    packet_bytes = bytes(packet)
                    if self.kind == "video":
                        self._latest_frame = packet_bytes
                    else:
                        if not hasattr(self, "_queue"): self._queue = []
                        self._queue.append(packet_bytes)
                        if len(self._queue) > 50: self._queue.pop(0)
                    self._frame_counter += 1
                
                self._ev.set()
                
                # Performance Tracking
                now = time.time()
                if now - self._last_fps_check >= 1.0:
                    fps = self._frame_counter / (now - self._last_fps_check)
                    self._fps_history.append(fps)
                    if len(self._fps_history) > 60: self._fps_history.pop(0)
                    self._frame_counter = 0
                    self._last_fps_check = now
                
                if now - self._last_log_time >= 10.0:
                    avg_fps = sum(self._fps_history) / len(self._fps_history) if self._fps_history else 0
                    logger.info(f"[PERF] Capture {self.kind} (ENCODED): {avg_fps:.1f} FPS")
                    self._last_log_time = now

        except Exception as e:
            if self._running:
                logger.error(f"Error in encoded read loop {self.kind}: {e}")
        finally:
            if container: container.close()
            self.stop()

    def _read_loop_raw(self):
        """Standard raw pipe reading."""
        while self._running and self.process:
            try:
                current_buf = None
                if self.kind == "video":
                    if self._buffers is None: break
                    current_buf = self._buffers[self._buf_idx]
                else: 
                    current_buf = bytearray(self.frame_size)
                
                mv = memoryview(current_buf)
                total_read = 0
                while total_read < self.frame_size:
                    n = self.process.stdout.readinto(mv[total_read:])
                    if not n: break
                    total_read += n
                
                if total_read < self.frame_size: break
                
                with self._lock:
                    if self.kind == "video":
                        self._latest_frame = current_buf
                        self._buf_idx = 1 - self._buf_idx
                    else:
                        if not hasattr(self, "_queue"): self._queue = []
                        self._queue.append(bytes(current_buf))
                        if len(self._queue) > 15: self._queue.pop(0)
                    self._frame_counter += 1
                self._ev.set()

                now = time.time()
                if now - self._last_fps_check >= 1.0:
                    fps = self._frame_counter / (now - self._last_fps_check)
                    self._fps_history.append(fps)
                    if len(self._fps_history) > 60: self._fps_history.pop(0)
                    self._frame_counter = 0
                    self._last_fps_check = now
                
                if now - self._last_log_time >= 10.0:
                    avg_fps = sum(self._fps_history) / len(self._fps_history) if self._fps_history else 0
                    logger.info(f"[PERF] Capture {self.kind} (RAW): {avg_fps:.1f} FPS")
                    self._last_log_time = now

            except Exception as e:
                logger.error(f"Error in raw read loop {self.kind}: {e}")
                break
        self.stop()

    async def recv(self):
        self._check_process()
        while self._running:
            data = None
            with self._lock:
                if self.kind == "video":
                    data = self._latest_frame
                    self._latest_frame = None
                else:
                    if hasattr(self, "_queue") and self._queue:
                        data = self._queue.pop(0)
            
            if data:
                return self._create_frame(data)
            
            self._ev.clear()
            try:
                await asyncio.wait_for(self._ev.wait(), timeout=0.1)
            except asyncio.TimeoutError:
                self._check_process()
                if not self._running: break
                continue
        raise Exception(f"Track {self.kind} stopped")

    def _create_frame(self, data):
        try:
            if self.kind == "video":
                if hasattr(self, "is_encoded") and self.is_encoded:
                    # Video Passthrough
                    frame = av.VideoFrame(16, 16, "yuv420p")
                    frame._encoded_payload = [data]
                else:
                    # Raw Video mode
                    frame = av.VideoFrame(self.width, self.height, "yuv420p")
                    y_size = self.width * self.height
                    u_size = (self.width // 2) * (self.height // 2)
                    y_plane = np.frombuffer(data, dtype=np.uint8, count=y_size, offset=0).reshape((self.height, self.width))
                    u_plane = np.frombuffer(data, dtype=np.uint8, count=u_size, offset=y_size).reshape((self.height // 2, self.width // 2))
                    v_plane = np.frombuffer(data, dtype=np.uint8, count=u_size, offset=y_size + u_size).reshape((self.height // 2, self.width // 2))
                    frame.planes[0].update(y_plane)
                    frame.planes[1].update(u_plane)
                    frame.planes[2].update(v_plane)
            else:
                if hasattr(self, "is_encoded") and self.is_encoded:
                    # Audio Passthrough
                    frame = av.AudioFrame(format="s16", layout="stereo", samples=960)
                    frame.sample_rate = 48000
                    # Return payload as list of bytes
                    frame._encoded_payload = [data]
                else:
                    # Raw Audio mode
                    frame = av.AudioFrame(format="s16", layout="5.1", samples=480)
                    frame.sample_rate = 48000
                    frame.planes[0].update(data)

            pts, tb = self._get_pts()
            frame.pts = pts
            frame.time_base = tb
            return frame
        except Exception as e:
            logger.error(f"Erro ao criar frame {self.kind}: {e}")
            raise e

    def _check_process(self):
        if self.process is None or self.process.poll() is not None:
            self._start_capture()

    def stop(self):
        self._running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=0.2)
            except:
                try: self.process.kill()
                except: pass
            self.process = None

    def _get_pts(self):
        # Override me
        pass

    def _start_capture(self):
        # Override me
        pass
        
    def __del__(self):
        self.stop()

class EncodedAudioTrack(BaseCaptureTrack):
    kind = "audio"
    def __init__(self, args, device="default"):
        super().__init__()
        self.args = args
        self.device = device
        if self.device == "default":
            self.device = self._find_best_audio_source()
        self.is_encoded = True
        self.frame_size = 0 
        self._queue = []
    
    def _find_best_audio_source(self):
        try:
            sink_cmd = ["pactl", "get-default-sink"]
            default_sink = subprocess.check_output(sink_cmd).decode().strip()
            if default_sink:
                monitor = f"{default_sink}.monitor"
                sources = subprocess.check_output(["pactl", "list", "sources", "short"]).decode()
                if monitor in sources:
                    logger.info(f"[AUDIO] Usando monitor automático: {monitor}")
                    return monitor
            
            res = subprocess.check_output(["pactl", "list", "sources", "short"]).decode()
            for line in res.splitlines():
                name = line.split()[1]
                if ".monitor" in name:
                    return name
        except: pass
        return "default"

    def _get_pts(self):
        pts = self.frame_count * 960
        tb = fractions.Fraction(1, 48000)
        self.frame_count += 1
        return pts, tb

    def _start_capture(self):
        # OBS-Style: Direct Opus encoding in Matroska for robust piping
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
            "-f", "pulse", "-i", self.device,
            "-ac", "2", "-ar", "48000",
            "-c:a", "libopus", "-b:a", f"{getattr(self.args, 'audio_bitrate', 128)}k",
            "-vbr", "on", "-compression_level", "10", "-frame_duration", "20",
            "-application", "lowdelay",
            "-f", "matroska", "-cluster_size_limit", "2", "-cluster_time_limit", "10", "-"
        ]
        
        latency = "10"
        if getattr(self.args, 'audio_gpu', False) or getattr(self.args, 'ultra_low_latency', False):
             latency = "1"
             
        logger.info(f"[AUDIO OBS-STYLE] CMD: {' '.join(cmd)}")
        self._start_ffmpeg(cmd, env={"PULSE_LATENCY_MSEC": latency})

class WindowsAudioTrack(BaseCaptureTrack):
    kind = "audio"
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.channels = 2 # WASAPI loopback usually stereo
        self.frame_size = 480 * self.channels * 2 
        self._queue = []

    def _get_pts(self):
        pts = self.frame_count * 480
        tb = fractions.Fraction(1, 48000)
        self.frame_count += 1
        return pts, tb

    def _start_capture(self):
        # We use WASAPI loopback to capture system audio on Windows
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
            "-f", "wasapi", "-i", "default",
            "-ac", str(self.channels), "-ar", "48000",
            "-c:a", "pcm_s16le", "-f", "s16le", "-"
        ]
        self._start_ffmpeg(cmd)

class EncodedVideoTrack(BaseCaptureTrack):
    kind = "video"
    def __init__(self, pc_id, args):
        self.args = args
        self.width, self.height = map(int, args.resolution.split('x'))
        self.fps = 60
        self.is_encoded = True
        self._buffers = None
        super().__init__()
        
    def _get_pts(self):
        pts = self.frame_count
        tb = fractions.Fraction(1, self.fps)
        self.frame_count += 1
        return pts, tb

    def _start_capture(self):
        input_str = ":0.0+0,0"
        src_w, src_h = "1920", "1080"
        
        try:
             if self.args.region and "," in self.args.region:
                  r = self.args.region.split(',')
                  src_w, src_h = r[2], r[3]
                  input_str = f":0.0+{r[0]},{r[1]}"
        except: pass

        # OBS-Style Encoder Selection & Tuning
        encoder = "libx264"
        enc_opts = ["-preset", "ultrafast", "-tune", "zerolatency"]
        
        # Determine target encoder
        req_enc = getattr(self.args, 'encoder', 'auto').lower()
        
        if req_enc in ["vaapi", "gpu", "auto"] and os.path.exists("/dev/dri/renderD128"):
            encoder = "h264_vaapi"
            enc_opts = [
                "-vaapi_device", "/dev/dri/renderD128", 
                "-vf", f"format=nv12,hwupload,scale_vaapi={self.width}:{self.height}",
                "-rc_mode", "CBR",
                "-filler_data", "1",
                "-qp", "24" # Default quality point for VAAPI CBR
            ]
            if req_enc == "vaapi": logger.info("[VIDEO] Force VAAPI (AMD/Intel)")
            
        elif req_enc in ["nvenc", "gpu"]:
            encoder = "h264_nvenc"
            enc_opts = [
                "-preset", "p1", 
                "-tune", "ull", 
                "-zerolatency", "1", 
                "-delay", "0",
                "-rc", "cbr",
                "-vf", f"scale={self.width}:{self.height},format=yuv420p"
            ]
            logger.info("[VIDEO] Using NVENC (Nvidia)")
        else:
            # CPU or fallback
            enc_opts += ["-vf", f"scale={self.width}:{self.height},format=yuv420p"]
            logger.info("[VIDEO] Using Software/CPU (libx264)")

        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
            "-f", "x11grab", "-framerate", "60", "-draw_mouse", "0",
            "-video_size", f"{src_w}x{src_h}", "-i", input_str,
            "-c:v", encoder
        ] + enc_opts + [
            "-b:v", f"{self.args.bitrate}k",
            "-maxrate", f"{self.args.bitrate}k",
            "-bufsize", f"{self.args.bitrate//10}k",
            "-g", "60", "-f", "h264", "-"
        ]
        
        logger.info(f"[VIDEO OBS-STYLE] CMD: {' '.join(cmd)}")
        self._start_ffmpeg(cmd)

class WindowsVideoTrack(BaseCaptureTrack):
    kind = "video"
    def __init__(self, pc_id, args):
        self.args = args
        self.width, self.height = map(int, args.resolution.split('x'))
        self.fps = 60
        self.frame_size = int(self.width * self.height * 1.5)
        self._buffers = [bytearray(self.frame_size), bytearray(self.frame_size)]
        super().__init__()

    def _get_pts(self):
        pts = self.frame_count
        tb = fractions.Fraction(1, self.fps)
        self.frame_count += 1
        return pts, tb

    def _start_capture(self):
        # Prefer ddagrab (Desktop Duplication API) for performance, fallback to gdigrab
        backend = "ddagrab" # Could be made configurable
        
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
            "-f", backend,
            "-framerate", "60",
            "-i", "desktop",
            "-vf", f"scale={self.width}:{self.height},format=yuv420p",
            "-c:v", "rawvideo", "-f", "rawvideo", "-"
        ]
        
        logger.info(f"[VIDEO WINDOWS] Backend: {backend} | CMD: {' '.join(cmd)}")
        self._start_ffmpeg(cmd)

class MediaCaptureSystem:
    def __init__(self, pc_id, args):
        self.pc_id = pc_id
        self.args = args
        if IS_WINDOWS:
            self.video_track = WindowsVideoTrack(pc_id, args)
            self.audio_track = WindowsAudioTrack(args)
        else:
            self.video_track = EncodedVideoTrack(pc_id, args)
            self.audio_track = EncodedAudioTrack(args)
    
    def get_video_track(self): return self.video_track
    def get_audio_track(self): return self.audio_track
    
    async def setup_tracks(self, pc):
        pc.addTrack(self.video_track)
        pc.addTrack(self.audio_track)

    def stop(self):
        self.video_track.stop()
        self.audio_track.stop()
