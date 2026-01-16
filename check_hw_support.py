
import av
import os

print("Checking available codecs...")
try:
    codec = av.Codec('h264_vaapi', 'w')
    print(f"Codec h264_vaapi found: {codec.name}")
except Exception as e:
    print(f"Codec h264_vaapi lookup failed: {e}")

print("\nChecking VAAPI Device Access...")
try:
    # PyAV doesn't easily let us open device context directly without a stream usually
    # But we can try to open a dummy encoder
    ctx = av.Codec('h264_vaapi', 'w').create()
    # We need to open a device context... strict PyAV usually requires more setup
    # checking /dev/dri
    if os.path.exists("/dev/dri/renderD128"):
        print("/dev/dri/renderD128 exists.")
    else:
        print("/dev/dri/renderD128 MISSING.")
        
except Exception as e:
    print(f"Initialization failed: {e}")

print("\nChecking NVENC...")
try:
    codec = av.Codec('h264_nvenc', 'w')
    print(f"Codec h264_nvenc found: {codec.name}")
    ctx = av.Codec('h264_nvenc', 'w').create()
    print("NVENC Context Created (Dry Run)")
except Exception as e:
    print(f"NVENC check failed: {e}")
