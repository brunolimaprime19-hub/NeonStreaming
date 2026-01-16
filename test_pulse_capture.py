#!/usr/bin/env python3
import asyncio
import logging
import time
import subprocess
import numpy as np
import av
from capture_system import PulseAudioTrack

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestAudio")

def get_audio_source():
    try:
        sources = subprocess.check_output(["pactl", "list", "short", "sources"], text=True)
        for line in sources.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                name = parts[1]
                if "hdmi" in name.lower() and "monitor" in name.lower():
                    print(f"DEBUG: Found HDMI Monitor Source: {name}")
                    return name
        
        res = subprocess.check_output(["pactl", "get-default-sink"], text=True).strip()
        print(f"DEBUG: Falling back to default sink monitor: {res}.monitor")
        return f"{res}.monitor"
    except Exception as e:
        print(f"DEBUG: Audio source detection failed: {e}")
        return "default"

async def test_track():
    device = get_audio_source()
    print(f"Testing PulseAudioTrack with device: {device}")
    track = PulseAudioTrack(device=device)
    
    print("Starting capture for 5 seconds...")
    start_time = time.time()
    frames_received = 0
    max_peak = 0
    
    try:
        while time.time() - start_time < 5:
            try:
                frame = await asyncio.wait_for(track.recv(), timeout=1.0)
                if frame:
                    frames_received += 1
                    # Extract data from the first plane
                    data = frame.planes[0].to_bytes() if hasattr(frame.planes[0], 'to_bytes') else bytes(frame.planes[0])
                    audio_np = np.frombuffer(data, dtype=np.int16)
                    peak = np.max(np.abs(audio_np)) if audio_np.size > 0 else 0
                    if peak > max_peak:
                        max_peak = peak
                    
                    if frames_received % 50 == 0:
                        print(f"Received {frames_received} frames... (PTS: {frame.pts}, Current Peak: {peak})")
                else:
                    print("Received empty frame")
            except asyncio.TimeoutError:
                print("Timeout waiting for audio frame!")
                break
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"Test finished. Total frames: {frames_received}")
        print(f"Maximum amplitude captured: {max_peak}")
        track.stop()
        
    if frames_received > 100:
        if max_peak > 100:
            print(f"✓ SUCCESS: Audio track is producing frames with sound (Max Peak: {max_peak}).")
        else:
            print(f"⚠ WARNING: Audio track is producing frames, but it's SILENT (Max Peak: {max_peak}).")
        return True
    else:
        print("✗ FAILURE: Not enough audio frames received.")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_track())
    import sys
    sys.exit(0 if success else 1)
