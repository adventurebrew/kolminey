import struct

def signed(num):
    return struct.unpack('<h', struct.pack('<H', num))[0]

def high_bits(value, numbits):
    mask = ((1 << numbits) - 1) << (8 - numbits)
    return value & mask

def low_bits(value, numbits):
    mask = ((1 << numbits) - 1)
    return value & mask

def decompress(data, size):
    dict_size = 4096
    dict_data = [0 for _ in range(dict_size)]
    output = []
    dict_off = 1
    out_off = 0

    offset = 0
    bit_shift = 0

    while True:
        value = data[offset]
        bitmask = (0x80 >> bit_shift) % 256

        use_raw_byte = value & bitmask
        if bit_shift == 8:
            bit_shift = 0
            offset += 1
        if not use_raw_byte:
            bits_from_first = 8 - bit_shift
            bits_from_last = 16 - 8 - bits_from_first

            byte1 = low_bits(data[offset], bits_from_first) % 256
            byte2 = data[offset + 1]
            byte3 = high_bits(data[offset + 2], bits_from_last) % 256

            lookup = ((byte1 << (8 + bits_from_last)) % 256) | ((byte2 << bits_from_last) % 256) | byte3

            lookup_offset = (lookup >> 4) & 0xFFF

            if lookup_offset == 0:
                break

            lookup_run_length = (lookup & 0xF) + 2

            for j in range(lookup_run_length):
                output.append(dict_data[(lookup_offset + j) % dict_size])
                dict_data[dict_off] = dict_data[(lookup_offset + j) % dict_size]
                dict_off += 1
                dict_off %= dict_size

            offset += 2
        else:
            bits_from_first = 8 - bit_shift
            bits_from_last = 8 - bits_from_first

            value = low_bits(data[offset], bits_from_first) << bits_from_last
            value |= high_bits(data[offset + 1], bits_from_last)

            offset += 1

            output.append(value)
            dict_data[dict_off] = value
            dict_off += 1
            dict_off %= dict_size
        print(out_off, offset)
    print(out_off, output[:60])
    return output


# TODO: implement lzss compression
def compress(data, size):
    pass