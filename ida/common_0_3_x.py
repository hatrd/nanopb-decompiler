import enum
import typing
import struct

import ida_bytes
import ida_kernwin
import ida_segment

from common import *

class Decompiler030(Decompiler):

    def __init__(self, field_size : int, is_64bit : int, stype : enum.IntEnum):
        super().__init__(field_size)
        self.stype = stype

        if field_size == 8:
            size_fmt = "B"
            self.ida_get_field_bits = ida_bytes.get_byte
        elif field_size == 16:
            size_fmt = "H"
            self.ida_get_field_bits = ida_bytes.get_16bit
        else:
            size_fmt = "I"
            self.ida_get_field_bits = ida_bytes.get_32bit

        if is_64bit:
            ptr_fmt = "Q"  # 64-bit pointer
        else:
            ptr_fmt = "I"  # 32-bit pointer
        
        # Format follows struct definition
        # I: unsigned int (4 bytes)
        # B: unsigned char (1 byte)
        # xxx: 3 padding bytes
        # I: unsigned int data_offset (4 bytes)
        # i: signed int size_offset (4 bytes)
        # I: unsigned int data_size (4 bytes)
        # I: unsigned int array_size (4 bytes)
        # ptr_fmt: pointer (4 or 8 bytes)
        self.pb_field_fmt = f"<IBxxxIiII{ptr_fmt}"
        self.pb_field_size = struct.calcsize(self.pb_field_fmt)
        
        print(f"Structure size: {self.pb_field_size} bytes")
    
    def parse_message(self, ea : int):
        fields = []
        print(f"Parsing message at address: 0x{ea:X}")

        while True:
            data = ida_bytes.get_bytes(ea, self.pb_field_size)
            
            # fmt: <IBxxxIiII{ptr_fmt}>
            # corresponds to: tag, type, (padding), data_offset, size_offset, data_size, array_size, ptr
            tag, field_type_raw, data_offset, size_offset, data_size, array_size, extra = struct.unpack(self.pb_field_fmt, data)
            
            # Debug output
            print(f"Raw data: addr=0x{ea:X}, tag={tag}, type=0x{field_type_raw:02X}, data_offset={data_offset}, size_offset={size_offset}, data_size={data_size}, array_size={array_size}, ptr=0x{extra:X}")
            
            if tag == 0:
                # indicates the end of the array
                print("Found tag=0, ending parse")
                break
            
            # Extract type, repeat rule and allocation type from type field
            field_type = self.stype(field_type_raw & 0b1111)
            repeat_rule = RepeatRule((field_type_raw >> 4) & 0b11)
            allocation_type = AllocationType((field_type_raw >> 6) & 0b11)
            
            print(f"Parsed: type={field_type.name}, repeat_rule={repeat_rule.name}, allocation_type={allocation_type.name}")

            if extra == 0:
                extra = None
            else:
                if field_type == self.stype.FIXED32:
                    extra = ida_bytes.get_32bit(extra)
                elif field_type == self.stype.FIXED64:
                    extra = ida_bytes.get_64bit(extra)
                elif field_type in (self.stype.INT, self.stype.UINT, self.stype.SINT):
                    if data_size == 1:
                        extra = ida_bytes.get_byte(extra)
                        sign_mask = (1 << 7)
                    elif data_size == 2:
                        extra = ida_bytes.get_16bit(extra)
                        sign_mask = (1 << 15)
                    elif data_size == 4:
                        extra = ida_bytes.get_32bit(extra)
                        sign_mask = (1 << 31)
                    else:
                        extra = ida_bytes.get_64bit(extra)
                        sign_mask = (1 << 63)
                    if field_type != self.stype.UINT:
                        if extra & sign_mask:
                            extra = -1 * (((~extra) & (sign_mask - 1)) + 1)
                elif field_type == self.stype.FIXED_LENGTH_BYTES:
                    extra = ida_bytes.get_bytes(extra, data_size)
                elif field_type == self.stype.BYTES:
                    tmp = self.ida_get_field_bits(extra)
                    extra = ida_bytes.get_bytes(extra + self.field_size_bytes, tmp)
                elif field_type == self.stype.STRING:
                    s = ""
                    while len(s) < data_size:
                        tmp = ida_bytes.get_byte(extra)
                        if tmp == 0x00:
                            break
                        s += chr(tmp)
                        extra += 1
                    extra = s
                        
            field = FieldInfo(
                tag,
                field_type,
                repeat_rule,
                allocation_type,
                data_offset, size_offset, data_size, array_size, extra)
            
            print(field)

            fields.append(field)
            ea += self.pb_field_size
        
        return fields

    def group_fields(self, fields: list[FieldInfo]) -> list[FieldInfo | list[FieldInfo]]:
        result = []
        oneof_fields = typing.OrderedDict[int,list[FieldInfo]]()
        last_offset = None

        for field in fields:
            if field.repeat_rules == RepeatRule.ONEOF:
                offset = field.data_offset
                if offset == self.max_value:
                    if last_offset == None:
                        raise DecompileError("Missing the starting field for a oneof group...")
                    offset = last_offset

                oneof = oneof_fields.get(offset, None)
                if oneof == None:
                    oneof = []
                    oneof_fields[offset] = oneof
                    result.append(oneof)
                
                oneof.append(field)
                last_offset = offset
            else:
                result.append(field)
        
        return result

def run_decompiler(stype):
    ea = ida_kernwin.get_screen_ea()
    seg = ida_segment.getseg(ea)
    if seg != None:
        field_size = ida_kernwin.ask_long(8, "Field Size (8, 16, 32)")
        if field_size in (8, 16, 32):
            decompiler = Decompiler030(field_size, seg.is_64bit(), stype)
            decompiler.add_message(ea)
            print(decompiler.to_proto())
        else:
            print("Invalid field size:", field_size)
    else:
        print("Cursor not in a segment")

