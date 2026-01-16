
import av
import os

try:
    # Mimic the call in server.py
    # MediaPlayer(input_device, format="x11grab", options=options)
    # -> av.open(file, format=format, options=options)
    
    # We need a valid X11 display. 
    # This might fail in this headless environment if it can't connect to X server,
    # but we are checking if it rejects the OPTIONS first.
    
    options = {
        "framerate": "30",
        "video_size": "640x480",
        "vcodec": "h264_vaapi",  # The suspect
        "vaapi_device": "/dev/dri/renderD128" # The suspect
    }
    
    print("Attempting av.open with invalid options for x11grab...")
    # This will likely fail to connect to X11 too, but pay attention to the error.
    # If the error is "Unrecognized option 'vcodec'", then my hypothesis is confirmed.
    
    # Note: We need to use 'x11grab' which assumes Linux/X11.
    # If there is no X server, it will error with "cannot open display".
    # But av.open parses options before opening.
    
    container = av.open(":0.0", format="x11grab", options=options)
    print("Success (unexpected)")
except Exception as e:
    print(f"Caught expected error: {e}")
