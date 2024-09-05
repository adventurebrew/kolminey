class BitBuffer:
    def __init__(self, data, pos=0):
        self.advsize = 2
        self.bitbuf = 0
        self.bitpos = 0
        self.buf = data
        self.pos = pos

    def clear_buf(self, bits):
        self.bitbuf = self.bitbuf >> bits
        self.bitpos -= bits

    def get_bytes(self, length):
        destination_array = bytearray(length)
        if self.bitpos >= 0x10:
            self.bitpos -= 0x10
            self.bitbuf &= ((1 << self.bitpos) - 1)
            self.pos -= 2
        destination_array[:length] = self.buf[self.pos:self.pos+length]
        self.pos += length
        return destination_array

    def normalize_buf(self, bits):
        while bits > self.bitpos:
            num = 0
            if (self.pos + 1) == len(self.buf):
                num = self.buf[-1]
            elif self.pos < len(self.buf):
                num = int.from_bytes(self.buf[self.pos:self.pos+2], 'little')
            self.pos += 2
            self.bitbuf |= (num << self.bitpos)
            self.bitpos += 0x10

    def peek_bits(self, bits):
        self.normalize_buf(bits)
        return (self.bitbuf & ((1 << bits) - 1))

    def read_bits(self, bits):
        num = self.peek_bits(bits)
        self.clear_buf(bits)
        return num

    def write_bits(self, value, bits):
        self.bitbuf |= ((value & ((1 << (bits & 0x1f)) - 1)) << (self.bitpos & 0x1f))
        self.bitpos += bits
        while self.bitpos >= 0x10:
            num = self.bitbuf & 0xffff
            self.bitpos -= 0x10
            self.bitbuf = self.bitbuf >> 0x10
            self.buf[self.pos:self.pos+2] = num.to_bytes(2, 'little')
            self.pos += self.advsize
            self.advsize = 2

    def write_bytes(self, data):
        if self.bitpos == 0:
            self.buf[self.pos:self.pos+len(data)] = data
            self.pos += len(data)
        else:
            self.buf[self.pos + self.advsize:self.pos + self.advsize + len(data)] = data
            self.advsize += len(data)

    def write_end(self):
        if self.bitpos > 0:
            self.write_bits(0, 0x10 - self.bitpos)

    @property
    def position(self):
        return self.pos

def gen_crc(crc):
    for _ in range(8):
        if crc & 1:
            crc = (crc >> 1) ^ 0xA001
        else:
            crc >>= 1
    assert crc & 0xFFFF == crc, crc
    return crc

crctable = [gen_crc(i) for i in range(0x100)]

def calc_crc16(data):
    crc = 0
    for byte in data:
        crc = (crc >> 8) ^ crctable[(crc ^ byte) & 0xFF]
    return crc

class Huff:
    def __init__(self, ln, code, value):
        self.ln = ln
        self.code = code
        self.value = value


def input_value(bf, table):
    index = 0
    while table[index].code != bf.peek_bits(table[index].ln):
        index += 1
    bf.read_bits(table[index].ln)
    value = table[index].value
    if value >= 2:
        value -= 1
        value = bf.read_bits(value) | (1 << value)
    return value


def make_huff_table(bf):
    numCodes = bf.read_bits(5)
    if numCodes == 0:
        raise Exception("Bad RNC Format at Huff table")
    huffLength = [bf.read_bits(4) for _ in range(numCodes)] + [0] * (0x10 - numCodes)
    table_idx = 0
    lst = []
    for bitLength in range(1, 0x11):
        for k, length in enumerate(huffLength):
            if length == bitLength:
                b = table_idx >> (0x10 - bitLength)
                code = sum(((b >> m) & 1) << (bitLength - m - 1) for m in range(bitLength))
                table_idx += 1 << (0x10 - bitLength)
                lst.append(Huff(bitLength, code, k & 0xff))
    return lst

def decompress(data: bytes) -> bytes:

    header, packed = data[:0x12], data[0x12:]

    if header[:4] != b'RNC\x01':
        return b''

    unpacked_size = int.from_bytes(header[0x4:0x8], 'big')
    packed_size = int.from_bytes(header[0x8:0xC], 'big')
    crc_unpacked = int.from_bytes(header[0xC:0xE], 'big')
    crc_packed = int.from_bytes(header[0xE:0x10], 'big')

    _leeway = header[0x10]
    blocks = header[0x11]

    assert len(packed) == packed_size, (len(packed), packed_size)

    if calc_crc16(packed) != crc_packed:
        raise Exception("Bad CRC at packed")

    output = bytearray(unpacked_size)

    bf = BitBuffer(packed)
    index = 0
    bf.read_bits(2)

    for _ in range(blocks):
        raw_table = make_huff_table(bf)
        pos_table = make_huff_table(bf)
        len_table = make_huff_table(bf)
        counts = bf.read_bits(0x10)

        while counts > 0:
            inputLength = input_value(bf, raw_table)
            if inputLength > 0:
                output[index:index+inputLength] = bf.get_bytes(inputLength)
                index += inputLength
            if counts > 1:
                inputOffset = input_value(bf, pos_table) + 1
                inputLength = input_value(bf, len_table) + 2
                for _ in range(inputLength):
                    output[index] = output[index - inputOffset]
                    index += 1
            counts -= 1

    assert len(output) == unpacked_size, (len(output), unpacked_size)

    if calc_crc16(output) != crc_unpacked:
        raise Exception("Bad CRC at unpacked")

    return bytes(output)


class RNCCompressor:

    def bit_len(self, value):
        num = 0
        while value != 0:
            value >>= 1
            num += 1
            num &= 0xffff
        return num

    @classmethod
    def compress(cls, data: bytes) -> bytes:
        return cls().do_compress(data)

    def do_compress(self, unpacked: bytes) -> bytes:
        output = bytearray(len(unpacked))
        output[:4] = b'RNC\x01'
        output[4:8] = len(unpacked).to_bytes(4, 'big')
        output[12:14] = calc_crc16(unpacked).to_bytes(2, 'big')
        self.bf = BitBuffer(output, 0x12)
        self.bf.write_bits(0, 2)
        self.ibuf = unpacked
        self.ipos = 0

        num = 0
        while self.ipos < len(self.ibuf):
            block = self.make_block()
            self.write_block(block)
            num = (num + 1) & 0xFF

        self.bf.write_end()
        output = output[:self.bf.pos]
        output[8:12] = (len(output) - 0x12).to_bytes(4, 'big')
        output[14:16] = calc_crc16(output[0x12:]).to_bytes(2, 'big')
        output[0x10] = 0
        output[0x11] = num
        return bytes(output)

    def emit_pair(self, ofs, length):
        tupl = self.get_tuple(self.tup, self.tid)
        tupl['ofs'] = ofs
        tupl['len'] = length
        self.tup[self.tid] = tupl
        self.tid += 1
        self.cpos += length
        self.get_tuple(self.tup, self.tid)

    def emit_raw(self, length):
        tupl = self.get_tuple(self.tup, self.tid)
        tupl['rawdata'] += self.ibuf[self.cpos:self.cpos+length]
        self.tup[self.tid] = tupl
        self.cpos += length

    def find_sequence(self, pos, length, maxpos):
        if pos == 0:
            return length, 0
        num = pos - 0x7fff
        if num < 0:
            num = 0
        num2 = 2
        num3 = 0
        num4 = 1
        num5 = 0
        while pos - num4 >= num and num2 < 0x1000:
            num5 = 0
            index = pos
            num7 = index - num4
            while index < maxpos and self.ibuf[index] == self.ibuf[num7] and num5 < 0x1000:
                index += 1
                num7 += 1
                num5 += 1
            if num5 > num2:
                num2 = num5
                num3 = num4
            num4 += 1
        return num2, num3

    def get_tuple(self, tup, tid):
        while len(tup) - 1 < tid:
            item = {'rawdata': bytearray(), 'ofs': 0, 'len': 0}
            tup.append(item)
        return tup[tid]

    def isbetter(self, length, no, l, o):
        if length < l:
            return False
        return (length > l and (no - 0x800) < o) or (length > (l + 1) and (no - 0x1000) < o) or length > (l + 2)

    def make_block(self):
        self.tup = []
        self.tid = 0
        self.cpos = self.ipos
        no = 0
        length = 0
        ln = 0
        l = 0
        o = 0
        maxpos = self.ipos + 0x3000
        if maxpos > len(self.ibuf):
            maxpos = len(self.ibuf)
        while self.cpos < maxpos and self.tid < 0xfff:
            if maxpos - self.cpos < 3:
                self.emit_raw(maxpos - self.cpos)
            else:
                length, no = self.find_sequence(self.cpos + ln, length, maxpos)
                if ln > 0:
                    if no > 0 and self.isbetter(length, no, l, o):
                        self.emit_raw(ln)
                        ln = 1
                        o = no
                        l = length
                    elif self.cpos + 1 >= self.ipos + 0x3000:
                        maxpos = self.cpos
                    else:
                        self.emit_pair(o, l)
                        ln = o = l = 0
                    continue
                if length > 2:
                    ln = 1
                    l = length
                    o = no
                else:
                    self.emit_raw(1)
        self.ipos = self.cpos
        return self.tup

    def make_huff_table(self, freq):
        nodeArray = [None] * 0x20
        lst = []
        index = 0
        for i in range(0x10):
            if freq[i] > 0:
                nodeArray[index] = {'freq': freq[i], 'parent': -1, 'lchild': -1, 'rchild': i}
                index += 1
        num3 = index
        if num3 == 1:
            num3 = 2
        while num3 > 1:
            num4 = 0x7ffffffe
            num5 = 0x7fffffff
            num6 = 0
            num7 = 0
            for num8 in range(index):
                if nodeArray[num8]['parent'] == -1:
                    if num4 > nodeArray[num8]['freq']:
                        num5 = num4
                        num7 = num6
                        num4 = nodeArray[num8]['freq']
                        num6 = num8
                    elif num5 > nodeArray[num8]['freq']:
                        num5 = nodeArray[num8]['freq']
                        num7 = num8
            nodeArray[index] = {'freq': num4 + num5, 'parent': -1, 'lchild': num6, 'rchild': num7}
            nodeArray[num6]['parent'] = nodeArray[num7]['parent'] = index
            index += 1
            num3 -= 1
        num9 = 0
        for j in range(0x10):
            lst.append(Huff(0, 0, 0))
        for k in range(index):
            if nodeArray[k]['lchild'] == -1:
                num12 = 0
                num3 = k
                while nodeArray[num3]['parent'] != -1:
                    num12 += 1
                    num3 = nodeArray[num3]['parent']
                huff = lst[nodeArray[k]['rchild']]
                huff.value = nodeArray[k]['rchild'] & 0xffff
                huff.ln = num12 & 0xff
                lst[nodeArray[k]['rchild']] = huff
                if num9 < num12:
                    num9 = num12
        num13 = 0
        for m in range(1, num9 + 1):
            for index in range(0x10):
                if lst[index].ln == m:
                    num15 = (num13 >> (0x10 - m)) & 0xffff
                    num16 = 0
                    for num17 in range(m):
                        num16 |= ((num15 >> num17) & 1) << (m - num17 - 1)
                        num16 &= 0xffff
                    huff2 = lst[index]
                    huff2.code = num16
                    lst[index] = huff2
                    num13 += 1 << (0x10 - m)
                    num13 &= 0xffff
        n = len(lst) - 1
        while lst[n].ln == 0 and len(lst) > 1:
            lst.pop(n)
            n -= 1
        return lst

    def write_block(self, block):
        freq = [0] * 0x10
        for item in block:
            freq[self.bit_len(len(item['rawdata']))] += 1
        table = self.make_huff_table(freq)
        self.write_huff(table)
        freq = [0] * 0x10
        for item in block[:-1]:
            freq[self.bit_len(item['ofs'] - 1)] += 1
        huff_array2 = self.make_huff_table(freq)
        self.write_huff(huff_array2)
        freq = [0] * 0x10
        for item in block[:-1]:
            freq[self.bit_len(item['len'] - 2)] += 1
        huff_array3 = self.make_huff_table(freq)
        self.write_huff(huff_array3)
        self.bf.write_bits(len(block), 0x10)
        for num7 in range(len(block)):
            self.write_huff_value(table, len(block[num7]['rawdata']))
            if len(block[num7]['rawdata']) > 0:
                self.bf.write_bytes(block[num7]['rawdata'])
            if num7 < len(block) - 1:
                self.write_huff_value(huff_array2, block[num7]['ofs'] - 1)
                self.write_huff_value(huff_array3, block[num7]['len'] - 2)

    def write_huff(self, table):
        self.bf.write_bits(len(table), 5)
        for item in table:
            self.bf.write_bits(item.ln, 4)

    def write_huff_value(self, table, value):
        index = self.bit_len(value)
        self.bf.write_bits(table[index].code, table[index].ln)
        if index > 1:
            self.bf.write_bits(value, index - 1)
