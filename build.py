import subprocess
import os
import sys

def install_pyinstaller():
    try:
        import PyInstaller
        print("PyInstaller already installed.")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def build():
    install_pyinstaller()
    
    entry_point = "server_gui.py"
    output_name = "NeonStreamServer"
    
    # Path separator for --add-data differs between Windows (;) and Linux (:)
    # PyInstaller uses the OS-specific path separator for this argument.
    sep = os.pathsep
    
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name", output_name,
        f"--add-data=static{sep}static",
        "--hidden-import=av",
        "--hidden-import=aiortc",
        "--hidden-import=numpy",
        "--hidden-import=aiohttp",
        "--collect-all=aiortc",
        "--collect-all=av",
        "--noconsole" # Hide terminal for GUI
    ]
    
    if os.name == "nt":
        cmd += ["--hidden-import=vgamepad", "--hidden-import=psutil"]
    
    cmd.append(entry_point)
    
    print(f"Building {output_name} for {os.name}...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        subprocess.check_call(cmd)
        print(f"\nBuild successful! The executable can be found in the 'dist' folder.")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build()
