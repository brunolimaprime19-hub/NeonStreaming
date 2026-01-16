
import inspect
from aiortc.codecs.opus import OpusEncoder
import sys

print("Source of OpusEncoder.encode:")
try:
    print(inspect.getsource(OpusEncoder.encode))
except Exception as e:
    print(f"Could not get source: {e}")

print("\nMethod resolution order:")
print(OpusEncoder.mro())

