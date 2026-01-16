import argparse
import os
import asyncio
import time
import json
import logging
import uuid
import signal
if os.name != "nt":
    import resource
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
import sys

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# Import local modules
import compat # Apply monkeypatches
from capture_system import MediaCaptureSystem
from input_manager import InputManager
from game_library import GameLibrary

def set_ram_limit(megabytes):
    """Enforces a RAM limit in MB using Virtual Address Space limits as a broad safety net."""
    if os.name == "nt":
        logger.info("RAM Guard: Safety limits (RLIMIT_AS) not supported on Windows. Proactive monitoring active.")
        return
    limit_as = int(megabytes * 1024 * 1024 * 4.0) 
    
    try:
        resource.setrlimit(resource.RLIMIT_AS, (limit_as, limit_as))
        logger.info("RAM Guard: Safety limits set (Vir: %d MB). Proactive monitoring active.", limit_as/1024/1024)
    except Exception as e:
        logger.warning(f"Não foi possível definir limites de RAM: {e}")

def get_memory_info():
    """Returns (RSS, VMS) in MB."""
    try:
        with open('/proc/self/status') as f:
            vms, rss = 0, 0
            for line in f:
                if line.startswith('VmSize:'): vms = int(line.split()[1]) / 1024
                if line.startswith('VmRSS:'): rss = int(line.split()[1]) / 1024
            return rss, vms
    except: return 0.0, 0.0

async def monitor_memory(target_mb):
    """Periodically logs memory usage and takes action if exceeding target."""
    import gc
    while True:
        rss, vms = get_memory_info()
        status = "✅ OK" if rss < target_mb else "⚠️ ALTO"
        
        if rss > target_mb * 0.5:
            gc.collect() 
            rss, _ = get_memory_info()

        logger.info(f"[📊 MONITOR RAM] Usando: {rss:.1f} MB (Limit: {target_mb} MB) | Status: {status}")
        
        if rss > target_mb:
            if not hasattr(monitor_memory, "_last_mem_warn") or time.time() - monitor_memory._last_mem_warn > 10:
                logger.warning(f"⚠️ Alerta: RAM ({rss:.1f}MB) acima do alvo ({target_mb}MB)")
                monitor_memory._last_mem_warn = time.time()
                
            if rss > target_mb * 1.3: # Even lower threshold
                logger.error("🚨 Memória Crítica! Forçando GC.")
                gc.collect()
                if rss > target_mb * 1.5:
                    from server import pcs
                    for pc in list(pcs):
                        asyncio.create_task(pc.close())
            
        await asyncio.sleep(2) # Monitor every 2s

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NeonServer")

ROOT = get_resource_path(".")
pcs = set()
input_mgr = InputManager()
game_library = GameLibrary()

@web.middleware
async def request_logger(request, handler):
    try:
        response = await handler(request)
        return response
    except Exception as e:
        logger.error("Error in handler %s: %s", request.path, e)
        raise

async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pc_id = str(uuid.uuid4())[:8]
    pcs.add(pc)

    logger.info("[%s] Connection started", pc_id)

    @pc.on("datachannel")
    def on_datachannel(channel):
        @channel.on("message")
        def on_message(message):
            try:
                data = json.loads(message)
                if data.get("type") == "STATS":
                    # Log client-side latency and quality stats
                    audio = data.get("audio", {})
                    # logger.info(...) # Reduce stats noise
                else:
                    logger.info(f"[INPUT DEBUG] Recv: {data}")
                    input_mgr.handle_input(data)
            except Exception as e:
                logger.error(f"Input Error: {e}")

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info("[%s] Connection state is %s", pc_id, pc.connectionState)
        if pc.connectionState in ["failed", "closed"]:
            if hasattr(pc, "_capture_sys"):
                pc._capture_sys.cleanup()
            await pc.close()
            pcs.discard(pc)
            logger.info("[%s] Connection closed", pc_id)

    # Performance monitoring task
    async def monitor_pc():
        while pc.connectionState not in ['closed', 'failed']:
            try:
                await asyncio.sleep(5)
                for sender in pc.getSenders():
                    if sender.track:
                        stats = await sender.getStats()
                        for stat in stats.values():
                            if stat.type == 'outbound-rtp':
                                logger.info("[%s] RTP Stats (%s): Packets Sent: %d, Bytes: %d", 
                                            pc_id, sender.track.kind, stat.packetsSent, stat.bytesSent)
            except Exception as e:
                logger.error("[%s] Stats error: %s", pc_id, e)
                break

    asyncio.create_task(monitor_pc())

    # Initialize Capture System (Audio + Video Together)
    capture_sys = MediaCaptureSystem(pc_id, args)
    await capture_sys.setup_tracks(pc)
    
    logger.info("[%s] Sistema de Captura AV Assíncrono Pronto", pc_id)
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    logger.info("[%s] Local SDP: %s", pc_id, pc.localDescription.sdp)

    return web.Response(
        content_type="application/json",
        text=json.dumps({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}),
    )

async def index(request):
    content = open(os.path.join(ROOT, "static/index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)

async def javascript(request):
    content = open(os.path.join(ROOT, "static/client.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)

async def css(request):
    content = open(os.path.join(ROOT, "static/index.css"), "r").read()
    return web.Response(content_type="text/css", text=content)

async def get_games(request):
    logger.info("API: Fetching game library...")
    games = await asyncio.to_thread(game_library.get_all_games)
    logger.info("API: Found %d games", len(games))
    return web.json_response({"games": games})

async def launch_game(request):
    try:
        data = await request.json()
        game_id = data.get("id")
        if game_id:
            logger.info("Launching game: %s", game_id)
            game_library.launch_game(game_id)
            return web.json_response({"status": "ok"})
        return web.json_response({"status": "error", "message": "No game ID"}, status=400)
    except Exception as e:
        logger.error("Launch error: %s", e)
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def favicon(request):
    return web.Response(status=204)

async def on_shutdown(app):
    logger.info("Server shutting down...")
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

def cleanup_orphan_processes():
    """Kills any leftover neon_video FFmpeg processes from previous runs."""
    try:
        if os.name != "nt":
            # pkill -f matches against full command line
            subprocess.run(["pkill", "-f", "ffmpeg.*neon_video"], check=False)
            logger.info("Orphan FFmpeg processes cleaned up.")
        else:
            # On Windows, we use taskkill
            subprocess.run(["taskkill", "/F", "/IM", "ffmpeg.exe", "/T"], check=False)
            logger.info("Orphan FFmpeg processes cleaned up (Windows).")
    except Exception as e:
        logger.warning(f"Failed to cleanup orphan processes: {e}")

def main():
    parser = argparse.ArgumentParser(description="Neon Stream Server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--resolution", default="1920x1080")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--bitrate", type=int, default=20000) # kbps
    parser.add_argument("--bitrate-auto", action="store_true")
    parser.add_argument("--encoder", default="auto")
    parser.add_argument("--codec", default="h264")
    parser.add_argument("--audio-bitrate", type=int, default=128)
    parser.add_argument("--region", default="full")
    # Ignored legacy args for compatibility with GUI
    parser.add_argument("--capture-backend", default="x11")
    parser.add_argument("--gop", default="60")
    parser.add_argument("--h264-profile", default="baseline")
    parser.add_argument("--bframes", default="0")
    parser.add_argument("--latency-preset", default="ultrafast")
    parser.add_argument("--buffer-video", default="0")
    parser.add_argument("--audio-latency", default="low")
    parser.add_argument("--buffer-audio", default="0")
    parser.add_argument("--monitor", default="primary")
    parser.add_argument("--process-priority", default="normal")
    parser.add_argument("--echo-cancel", action="store_true")
    parser.add_argument("--frame-drop", action="store_true")
    parser.add_argument("--capture-cursor", action="store_true")
    parser.add_argument("--dynamic-scale", action="store_true")
    parser.add_argument("--adaptive-bitrate", action="store_true")
    parser.add_argument("--adaptive-fps", action="store_true")
    parser.add_argument("--bad-connection-mode", action="store_true")
    parser.add_argument("--audio-gpu", action="store_true")
    parser.add_argument("--cpu-affinity", default="all")
    parser.add_argument("--net-limit", type=int, default=50) # Mbps
    parser.add_argument("--mem-limit", type=int, default=2000) # MB (2.0 GB)
    parser.add_argument("--ultra-low-latency", action="store_true")
    parser.add_argument("--debug", action="store_true")

    global args # Keep args global for access in other functions
    args = parser.parse_args()

    # --- CLEAN SLATE ---
    cleanup_orphan_processes()

    # --- ENFORCE RAM LIMIT ---
    set_ram_limit(args.mem_limit)

    # --- PROCESS OPTIMIZATIONS ---
    # Set priority (Linux only)
    try:
        priority = args.process_priority.lower()
        if os.name != "nt":
            if priority == "alta":
                os.nice(-10)
                logger.info("Process priority set to HIGH")
            elif priority == "tempo real":
                os.nice(-20)
                logger.info("Process priority set to REAL-TIME")
        else:
            import psutil
            p = psutil.Process(os.getpid())
            if priority == "alta":
                p.nice(psutil.HIGH_PRIORITY_CLASS)
                logger.info("Process priority set to HIGH (Windows)")
            elif priority == "tempo real":
                p.nice(psutil.REALTIME_PRIORITY_CLASS)
                logger.info("Process priority set to REAL-TIME (Windows)")
    except ImportError:
        logger.info("psutil not installed. Cannot set process priority on Windows.")
    except PermissionError:
        logger.info("Process priority could not be set (insufficient permissions)")
    except Exception as e:
        logger.warning("Could not set process priority: %s", e)

    # CPU Affinity
    if args.cpu_affinity and args.cpu_affinity.lower() != "all":
        try:
            cores = [int(c.strip()) for c in args.cpu_affinity.split(",")]
            if os.name != "nt":
                os.sched_setaffinity(0, cores)
            else:
                import psutil
                p = psutil.Process(os.getpid())
                p.cpu_affinity(cores)
            logger.info("CPU Affinity set to cores: %s", cores)
        except ImportError:
            logger.info("psutil not installed. Cannot set CPU affinity on Windows.")
        except Exception as e:
            logger.warning("Could not set CPU affinity: %s", e)

    # Apply settings to Compat layer
    import compat
    compat.ENCODER_CONFIG["bitrate"] = args.bitrate * 1000 # Convert kbps to bps
    compat.ENCODER_CONFIG["audio_bitrate"] = args.audio_bitrate * 1000 # kbps to bps
    compat.ENCODER_CONFIG["net_limit"] = args.net_limit * 1000 * 1000 # Mbps to bps
    compat.ENCODER_CONFIG["ultra_low_latency"] = args.ultra_low_latency
    compat.ENCODER_CONFIG["adaptive_bitrate"] = args.adaptive_bitrate
    compat.ENCODER_CONFIG["adaptive_fps"] = args.adaptive_fps
    compat.ENCODER_CONFIG["bad_connection_mode"] = args.bad_connection_mode
    
    if args.encoder == "vaapi":
        compat.ENCODER_CONFIG["name"] = "h264_vaapi"
    elif args.encoder == "nvenc":
        compat.ENCODER_CONFIG["name"] = "h264_nvenc"
    elif args.encoder == "amf":
        compat.ENCODER_CONFIG["name"] = "h264_amf"
    elif args.encoder == "qsv":
        compat.ENCODER_CONFIG["name"] = "h264_qsv"
    else:
        compat.ENCODER_CONFIG["name"] = "libx264"
        # Mapeia presets do GUI para presets reais do x264
        preset_map = {
            "ultra_baixa": "ultrafast",
            "baixa": "superfast",
            "balanceada": "veryfast"
        }
        compat.ENCODER_CONFIG["preset"] = preset_map.get(args.latency_preset.lower(), "ultrafast")
        compat.ENCODER_CONFIG["tune"] = "zerolatency"

    logger.info("Starting Neon Server on port %d...", args.port)
    logger.info("Quality Config: %s %s at %d kbps", args.encoder, args.codec, args.bitrate)

    app = web.Application()
    app.middlewares.append(request_logger)
    app.on_shutdown.append(on_shutdown)
    
    # Start memory monitoring
    async def start_monitors(app):
        asyncio.create_task(monitor_memory(args.mem_limit))
    app.on_startup.append(start_monitors)
    
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    app.router.add_get("/index.css", css)
    app.router.add_get("/api/games", get_games)
    app.router.add_get("/favicon.ico", favicon)
    app.router.add_post("/api/launch", launch_game)
    
    async def set_settings(request):
        try:
            data = await request.json()
            if "bitrate" in data:
                new_bitrate = int(data["bitrate"]) * 1000 # kbps to bps
                # Update global config which the encoder monkeypatch reads
                compat.ENCODER_CONFIG["bitrate"] = new_bitrate
                logger.info("Dynamic Bitrate Update: %d bps", new_bitrate)
                return web.json_response({"status": "ok", "bitrate": new_bitrate})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)
            
    app.router.add_post("/api/settings", set_settings)
    
    async def set_quality(request):
        try:
            data = await request.json()
            quality = data.get("quality", "1080p")
            # Atualizar args globalmente para novas conexões
            if quality == "720p":
                args.resolution = "1280x720"
                args.resolution = "1280x720"
                args.bitrate = 25000  # High quality 720p (25 Mbps) - Unlocked Network
            elif quality == "2k":
                args.resolution = "2560x1440"
                args.bitrate = 35000
            elif quality == "4k":
                args.resolution = "3840x2160"
                args.bitrate = 55000
            else:  # 1080p
                args.resolution = "1920x1080"
                args.bitrate = 20000
                
            # Sync to encoder config
            compat.ENCODER_CONFIG["bitrate"] = args.bitrate * 1000
            
            logger.info(f"Quality changed to: {quality} ({args.resolution} @ {args.bitrate} kbps)")
            return web.json_response({"status": "ok", "quality": quality, "resolution": args.resolution})
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)
    
    app.router.add_post("/api/quality", set_quality)
    app.router.add_post("/offer", offer)
    app.router.add_static("/static/", path=os.path.join(ROOT, "static"), name="static")

    web.run_app(app, port=args.port)

if __name__ == "__main__":
    main()
