import asyncio
import os
import subprocess
import time
import fractions
import av
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestWindows")

class MockArgs:
    def __init__(self):
        self.resolution = "1280x720"
        self.audio_gpu = False

async def test_capture():
    if os.name != "nt":
        print("This test is intended for Windows only.")
        return

    from capture_system import WindowsVideoTrack, WindowsAudioTrack
    
    args = MockArgs()
    video = WindowsVideoTrack("test_pc", args)
    audio = WindowsAudioTrack(args)
    
    print("Testing Video Track (DDA/GDI)...")
    try:
        frame = await asyncio.wait_for(video.recv(), timeout=5.0)
        print(f"✓ Video Frame Received: {frame.width}x{frame.height} {frame.format.name}")
    except Exception as e:
        print(f"✗ Video Capture Failed: {e}")
        
    print("Testing Audio Track (WASAPI)...")
    try:
        frame = await asyncio.wait_for(audio.recv(), timeout=5.0)
        print(f"✓ Audio Frame Received: {frame.samples} samples, {frame.sample_rate}Hz")
    except Exception as e:
        print(f"✗ Audio Capture Failed: {e}")
        
    video.stop()
    audio.stop()

if __name__ == "__main__":
    asyncio.run(test_capture())
