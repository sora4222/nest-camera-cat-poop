"""Built-in part implementations. Importing this package registers them all.

Add a new implementation as its own module here and import it below.
"""

from catpoop.parts import log_speaker, memory_event_log, onnx_detector, presence_off

__all__ = ["log_speaker", "memory_event_log", "onnx_detector", "presence_off"]
