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
        while self._running and self.process:
            try:
                current_buf = None
                if self.kind == "video":
                    if self._buffers is None: 
                        logger.error(f"[{self.kind.upper()}] Video buffers not initialized.")
                        break
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
                        
                        # FPS Tracking (Video only)
                        self._frame_counter += 1
                        now = time.time()
                        elapsed = now - self._last_fps_check
                        if elapsed >= 1.0:
                            fps = self._frame_counter / elapsed
                            self._fps_history.append(fps)
                            if len(self._fps_history) > 60: self._fps_history.pop(0)
                            
                            if fps < 30:
                                logger.warning(f"[PERF] FPS de Captura BAIXO: {fps:.1f} FPS (O alvo é 60)")
                            
                            self._frame_counter = 0
                            self._last_fps_check = now
                        
                        # Periodic Average Log (Every 10s)
                        if now - self._last_log_time >= 10.0:
                            avg_fps = sum(self._fps_history) / len(self._fps_history) if self._fps_history else 0
                            logger.info(f"[PERF] Status de Captura ({self.kind}): Média {avg_fps:.1f} FPS | Total: {self.frame_count} frames")
                            self._last_log_time = now
                    else:
                        if not hasattr(self, "_queue"): self._queue = []
                        self._queue.append(bytes(current_buf))
                        if len(self._queue) > 15: self._queue.pop(0)

                self._ev.set()
            except Exception as e:
                logger.error(f"Erro no loop de leitura {self.kind}: {e}")
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
                # Use from_bytes to correctly handle internal stride alignment (fix for 848x480)
                # Convert bytearray to bytes to avoid TypeError in some PyAV versions
                frame = av.VideoFrame.from_bytes(bytes(data), format="yuv420p", width=self.width, height=self.height)
            else:
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

class PulseAudioTrack(BaseCaptureTrack):
    kind = "audio"
    def __init__(self, args, device="default"):
        super().__init__()
        self.args = args
        self.device = device
        if self.device == "default":
            self.device = self._find_best_audio_source()
        self.channels = 6 
        self.frame_size = 480 * self.channels * 2 
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
        pts = self.frame_count * 480
        tb = fractions.Fraction(1, 48000)
        self.frame_count += 1
        return pts, tb

    def _start_capture(self):
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
            "-fflags", "nobuffer+flush_packets", "-flags", "low_delay",
            "-threads", "1",
            "-f", "pulse", 
            "-thread_queue_size", "512", 
            "-i", self.device,
            "-ac", str(self.channels), "-ar", "48000",
            "-probesize", "32k", "-analyzeduration", "0",
            "-af", "aresample=async=1,volume=1.2",
            "-c:a", "pcm_s16le", "-f", "s16le", "-"
        ]
        if getattr(self.args, 'audio_gpu', False):
             logger.info("[AUDIO] Modo GPU/Ultra-Low Latency Ativado (Requested by User)")
             latency = "1"
        else:
             latency = "10"

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

class RawVideoTrack(BaseCaptureTrack):
    kind = "video"
    def __init__(self, pc_id, args):
        self.args = args
        self.width, self.height = map(int, args.resolution.split('x'))
        self.fps = 60 # FORCE 60 FPS NO MATTER WHAT
        self.frame_size = int(self.width * self.height * 1.5)
        self._buffers = [bytearray(self.frame_size), bytearray(self.frame_size)]
        super().__init__()
        
    def _get_pts(self):
        pts = self.frame_count
        tb = fractions.Fraction(1, self.fps)
        self.frame_count += 1
        return pts, tb

    def _start_capture(self):
        # BALANCED_CAPTURE: Configuração focada em compatibilidade e estabilidade
        # Ideal para uso com Encoder de Software (CPU)
        
        input_str = ":0.0+0,0"
        src_w, src_h = "1920", "1080"
        
        try:
             if self.args.region and "," in self.args.region:
                  r = self.args.region.split(',')
                  src_w, src_h = r[2], r[3]
                  input_str = f":0.0+{r[0]},{r[1]}"
        except: pass

        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
            
            # --- INPUT OPTIONS ---
            "-f", "x11grab",
            "-rtbufsize", "64M", # Reduzido de 500M para poupar RAM
            "-framerate", "60", 
            # Threads Auto (sem -threads N)
            "-draw_mouse", "0",
            "-video_size", f"{src_w}x{src_h}",
            "-probesize", "10M", # Reduzido de 50M
            "-analyzeduration", "0",
            "-i", input_str,
            
            # --- FILTERING ---
            # Using simple scaling without aggressive threading force
            "-vf", f"scale={self.width}:{self.height}",
            
            # --- OUTPUT ---
            # Remover cfr forçado para evitar drift com encoder lento
            "-r", "60",
            
            "-c:v", "rawvideo", 
            "-pix_fmt", "yuv420p",
            "-f", "rawvideo", "-"
        ]
        
        logger.info(f"[VIDEO BALANCED] CMD: {' '.join(cmd)}")
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
            self.video_track = RawVideoTrack(pc_id, args)
            self.audio_track = PulseAudioTrack(args)
    
    def get_video_track(self): return self.video_track
    def get_audio_track(self): return self.audio_track
    
    async def setup_tracks(self, pc):
        pc.addTrack(self.video_track)
        pc.addTrack(self.audio_track)

    def stop(self):
        self.video_track.stop()
        self.audio_track.stop()
