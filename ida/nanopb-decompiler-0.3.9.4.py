import enum
import sys
import importlib

module_name = "common_0_3_x"

# for dev, reload module
if module_name in sys.modules:
    importlib.reload(sys.modules[module_name])
    print("reload")
else:
    __import__(module_name)
    print("import")

from common_0_3_x import *

class ScalarType(enum.IntEnum):
    BOOL = 0x00
    INT = 0x01
    UINT = 0x02
    SINT = 0x03
    FIXED32 = 0x04
    FIXED64 = 0x05
    BYTES = 0x06
    STRING = 0x07
    SUBMESSAGE = 0x08
    EXTENSION = 0x09
    FIXED_LENGTH_BYTES = 0x0a

run_decompiler(ScalarType)
