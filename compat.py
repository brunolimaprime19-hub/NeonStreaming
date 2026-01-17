import logging
import aiortc.codecs.h264
import aiortc.codecs.vpx
import aiortc.contrib.media
import av.audio.resampler
import aiortc.codecs.opus
import av
import fractions
import time
import sys

logger = logging.getLogger("NeonCompat")

IS_WINDOWS = sys.platform == "win32"

# --- COMPATIBILITY MONKEYPATCH FOR PYAV 13.x ---
# --- GLOBAL CONFIG FOR COMPAT ---
ENCODER_CONFIG = {
    "name": "libx264",
    "preset": "ultrafast",
    "tune": "zerolatency",
    "bitrate": 5000000,
    "net_limit": 500000000 # 500 Mbps default (Safety net)
}

class CodecProxy:
    def __init__(self, obj):
        object.__setattr__(self, "_obj", obj)
    def __getattr__(self, name):
        if name == "open":
            return self.patched_open
        return getattr(self._obj, name)
    
    def patched_open(self, *args, **kwargs):
        """Inject strict CBR options just before the codec is opened."""
        try:
            target_bps = ENCODER_CONFIG["bitrate"]
            actual_codec = self._obj.codec.name.lower()
            
            if "vaapi" in actual_codec:
                ull = ENCODER_CONFIG.get("ultra_low_latency", False)
                bad_conn = ENCODER_CONFIG.get("bad_connection_mode", False)
                
                # Dynamic adjustment for bad connection
                vaapi_quality = "4" if not bad_conn else "7" # 7 is faster/lower quality
                vaapi_async = "4" if not bad_conn else "1" # Lower async might reduce burstiness
                
                self._obj.options.update({
                    "async_depth": vaapi_async,
                    "b": str(target_bps),
                    "maxrate": str(target_bps),
                    "bufsize": str(int(target_bps/8)), # Optimized for 720p60 streaming
                    "rc_mode": "CBR",
                    "filler_data": "1",
                    "quality": vaapi_quality,
                    "g": "30" # Reduced GOP for lower latency (0.5s @ 60fps)
                })
            elif "nvenc" in actual_codec:
                self._obj.options.update({
                    "preset": "p1", # Fastest for NVENC
                    "tune": "ull", # Ultra low latency
                    "rc": "cbr",
                    "forced-idr": "1",
                    "delay": "0",
                    "zerolatency": "1",
                    "usage": "lowlatency",
                    "b": str(target_bps),
                    "maxrate": str(target_bps),
                    "bufsize": str(int(target_bps/10)),
                    "g": "30"
                })
            elif "amf" in actual_codec:
                self._obj.options.update({
                    "usage": "low_latency",
                    "quality": "speed",
                    "rc": "cbr",
                    "b": str(target_bps),
                    "maxrate": str(target_bps),
                    "g": "30"
                })
            elif "qsv" in actual_codec:
                self._obj.options.update({
                    "preset": "veryfast",
                    "tune": "zerolatency",
                    "b": str(target_bps),
                    "maxrate": str(target_bps),
                    "g": "30",
                    "async_depth": "1"
                })
            elif "x264" in actual_codec:
                self._obj.options.update({
                    "preset": "ultrafast",
                    "tune": "zerolatency",
                    "x264-params": f"nal-hrd=cbr:force-cfr=1:vbv-maxrate={int(target_bps/1000)}:vbv-bufsize={int(target_bps/10000)}:scenecut=0:bframes=0:ref=1:mbtree=0:keyint=30",
                    "threads": "auto",
                    "profile": "baseline"
                })
            elif "vpx" in actual_codec or "vp8" in actual_codec or "vp9" in actual_codec:
                self._obj.options.update({
                    "deadline": "realtime",
                    "cpu-used": "8",
                    "minrate": str(int(target_bps)),
                    "maxrate": str(int(target_bps)),
                    "rc_end_usage": "cbr",
                    "buf-sz": "1000",
                    "buf-initial-sz": "500",
                    "buf-optimal-sz": "600",
                    "undershoot-pct": "0",
                    "overshoot-pct": "0",
                    "static-thresh": "0",
                    "threads": "4"
                })
            logger.info(f"[NeonCompat] Proxy: Options injected for {actual_codec} at {target_bps/1000:.0f}kbps")
        except Exception as e:
            logger.warning(f"[NeonCompat] Proxy open fail: {e}")
            
        return self._obj.open(*args, **kwargs)

    def __setattr__(self, name, value):
        # PROTECT BITRATE: If trying to set bit_rate, force it to our ENCODER_CONFIG value
        if name in ["bit_rate", "rc_max_rate", "rc_min_rate", "max_rate", "min_rate"]:
            value = ENCODER_CONFIG["bitrate"]
        if name == "rc_buffer_size":
            value = int(ENCODER_CONFIG["bitrate"] / 2)
        
        try:
            if hasattr(self._obj, name):
                setattr(self._obj, name, value)
        except Exception:
            pass

def patch_encoder_class(cls):
    orig_init = cls.__init__
    def patched_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        if hasattr(self, "codec"):
            if ENCODER_CONFIG["name"] == "h264_vaapi":
                try:
                    new_codec = av.Codec(ENCODER_CONFIG["name"], "w")
                    new_ctx = av.CodecContext.create(new_codec)
                    self.codec = new_ctx
                    logger.info("[NeonCompat] Forced H264 VAAPI")
                except Exception as e:
                    logger.warning("[NeonCompat] VAAPI Fail: %s", e)
            
            # Lock Bitrate and Options (Enforce CBR for strict bandwidth control)
            try:
                target_bps = ENCODER_CONFIG["bitrate"]
                
                # Safely set RC parameters if available
                if hasattr(self.codec, "bit_rate"):
                    self.codec.bit_rate = target_bps
                
                for attr in ["rc_max_rate", "rc_min_rate", "max_rate", "min_rate"]:
                    try:
                        if hasattr(self.codec, attr):
                            setattr(self.codec, attr, target_bps)
                    except (AttributeError, Exception):
                        pass
                
                try:
                    if hasattr(self.codec, "rc_buffer_size"):
                        self.codec.rc_buffer_size = int(target_bps / 2)
                except (AttributeError, Exception):
                    pass
                
                try:
                    self.codec.time_base = fractions.Fraction(1, 1000)
                except: pass
                
                if self.codec is not None:
                    # Se já for um proxy, ele cuidará do 'open' e do bitrate interno
                    if not isinstance(self.codec, CodecProxy):
                        self.codec = CodecProxy(self.codec)
                    
                    target_bps = ENCODER_CONFIG["bitrate"]
                    # Forçar bitrate nominal via proxy
                    self.codec.bit_rate = target_bps
                
                logger.info(f"[NeonCompat] Enforced CBR via Proxy: {ENCODER_CONFIG['bitrate']/1000:.0f} kbps")
            except Exception as e:
                logger.warning(f"[NeonCompat] Failed to set CBR params: {e}")

    cls.__init__ = patched_init

    # Intercept any runtime bitrate changes
    orig_encode = cls.encode
    def patched_encode(self, frame, force_keyframe=False):
        # --- PASSTHROUGH OPTIMIZATION ---
        if hasattr(frame, "_encoded_payload"):
            return frame._encoded_payload
            
        if hasattr(self, "codec"):
            requested_bitrate = ENCODER_CONFIG["bitrate"]
            limit = ENCODER_CONFIG["net_limit"]
            
            # Clamp bitrate to Net Limit
            if requested_bitrate > limit:
                if frame.time < 5: 
                    logger.warning(f"[NeonCompat] Security Limit Enforced! Requested {requested_bitrate/1e6:.1f}Mbps capped to {limit/1e6:.1f}Mbps")
                requested_bitrate = limit
            
            # Force target bitrate ONLY if it changed to avoid heavy per-frame overhead
            if not hasattr(self, "_last_applied_bitrate") or self._last_applied_bitrate != requested_bitrate:
                try: 
                    logger.info(f"[NeonCompat] Dinamic Bitrate: {requested_bitrate/1000:.0f} kbps")
                    self.codec.bit_rate = int(requested_bitrate)
                    
                    for attr in ["rc_max_rate", "rc_min_rate", "max_rate", "min_rate"]:
                        if hasattr(self.codec, attr):
                            setattr(self.codec, attr, int(requested_bitrate))
                        self.codec.rc_buffer_size = int(requested_bitrate / 4)
                    
                    # Force options again if possible (some encoders allow this)
                    if hasattr(self.codec, "options"):
                       actual_codec = self.codec.codec.name.lower() if self.codec.codec else ""
                       if "x264" in actual_codec:
                           self.codec.options["x264-params"] = f"nal-hrd=cbr:force-cfr=1:vbv-maxrate={int(requested_bitrate/1000)}:vbv-bufsize={int(requested_bitrate/120000)}:scenecut=0:bframes=0:ref=1:mbtree=0"
                       elif "vpx" in actual_codec or "vp8" in actual_codec:
                           self.codec.options.update({"minrate": str(int(requested_bitrate)), "maxrate": str(int(requested_bitrate))})
                    
                    self._last_applied_bitrate = requested_bitrate
                except Exception as e:
                    pass
        return orig_encode(self, frame, force_keyframe)
    cls.encode = patched_encode

    orig_setattr = cls.__setattr__
    def patched_setattr(self, name, value):
        if name == "codec" and value is not None and not isinstance(value, CodecProxy):
            value = CodecProxy(value)
        orig_setattr(self, name, value)
    cls.__setattr__ = patched_setattr

if hasattr(aiortc.codecs.h264, "H264Encoder"):
    patch_encoder_class(aiortc.codecs.h264.H264Encoder)
if hasattr(aiortc.codecs.vpx, "Vp8Encoder"):
    patch_encoder_class(aiortc.codecs.vpx.Vp8Encoder)
if hasattr(aiortc.codecs.vpx, "Vp9Encoder"):
    patch_encoder_class(aiortc.codecs.vpx.Vp9Encoder)

# --- AUDIO RESAMPLER PATCH ---
orig_resampler = av.audio.resampler.AudioResampler

class SafeResampler(orig_resampler):
    def resample(self, frame):
        try:
            fmt_name = getattr(frame.format, 'name', '')
            layout_name = getattr(frame.layout, 'name', '')
            if (frame.sample_rate == 48000 and fmt_name == 's16' and layout_name in ['stereo', '2 channels', '5.1', '6 channels']):
                return [frame]
            return super().resample(frame)
        except Exception as e:
            if getattr(frame, 'sample_rate', 0) == 48000 and getattr(frame.format, 'name', '') == 's16':
                return [frame]
            return []

aiortc.contrib.media.av.AudioResampler = SafeResampler

# --- OPUS ENCODER PATCH ---
def patched_opus_encode(self, frame, force_keyframe=False):
    frames = []
    if (frame.sample_rate == 48000 and len(frame.layout.channels) in [2, 6] and frame.format.name == 's16'):
        frames = [frame]
    else:
        try:
            frames = self.resampler.resample(frame)
        except:
            try:
                if not hasattr(self, "_fallback_resampler"):
                     self._fallback_resampler = av.AudioResampler(format="s16", layout="stereo", rate=48000)
                frames = self._fallback_resampler.resample(frame)
            except:
                if len(frame.layout.channels) in [2, 6]: frames = [frame]
                else: return [], None

    packets = []
    try:
        for f in frames: packets += self.codec.encode(f)
    except: return [], None

    if self.first_packet_pts is None and packets:
        self.first_packet_pts = packets[0].pts

    if packets:
        timestamp = packets[0].pts
        if timestamp is not None and self.first_packet_pts is not None:
             timestamp = timestamp - self.first_packet_pts
        return [bytes(p) for p in packets], timestamp
    return [], None

def patched_opus_init(self, *args, **kwargs):
    orig_opus_init(self, *args, **kwargs)
    try:
        # Enforce audio bitrate from global config
        target_audio_bps = ENCODER_CONFIG.get("audio_bitrate", 128000)
        if hasattr(self, "codec") and self.codec:
            self.codec.bit_rate = target_audio_bps
            logger.info(f"[NeonCompat] Opus Bitrate set to: {target_audio_bps/1000:.0f} kbps")
    except Exception as e:
        logger.warning(f"[NeonCompat] Failed to set Opus bitrate: {e}")

orig_opus_init = aiortc.codecs.opus.OpusEncoder.__init__
aiortc.codecs.opus.OpusEncoder.__init__ = patched_opus_init
aiortc.codecs.opus.OpusEncoder.encode = patched_opus_encode
