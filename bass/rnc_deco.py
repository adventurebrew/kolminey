# Implementation based on: https://github.com/scummvm/scummvm/blob/9e7849a30ce1f26e7a70f176b89a8415bd687d14/common/compression/rnc_deco.cpp

NOT_PACKED = 0
PACKED_CRC =-1
UNPACKED_CRC = -2

HEADER_LEN = 18
MIN_LENGTH = 2


def READ_BE_UINT32(data):
    return int.from_bytes(data[:4], byteorder='big', signed=False)

def READ_BE_UINT16(data):
    return int.from_bytes(data[:2], byteorder='big', signed=False)

def READ_LE_UINT16(data):
    return int.from_bytes(data[:2], byteorder='little', signed=False)


class RncDecoder:

    def __init__(self):
        self._bitBuffl = 0
        self._bitBuffh = 0
        self._bitCount = 0
        self._srcPtr = None
        self._dstPtr = None
        self._inputByteLeft = 0

        self._crcTable = bytearray(0x200)
        self._rawTable = [0] * 64
        self._posTable = [0] * 64
        self._lenTable = [0] * 64

        self.initCrc()

    def initCrc(self):
        tmp1 = 0
        tmp2 = 0

        for tmp2 in range(256):
            tmp1 = tmp2
            for cnt in range(8, 0, -1):
                if tmp1 % 2:
                    tmp1 >>= 1
                    tmp1 ^= 0x0a001
                else:
                    tmp1 >>= 1
            self._crcTable[2*tmp2:2*tmp2 + 2] = tmp1.to_bytes(2, byteorder='little', signed=False)

    def crcBlock(self, block, size):
        crc = 0
        crcTable8 = self._crcTable
        tmp = 0

        for i in range(size):
            tmp = block[i]
            crc ^= tmp
            tmp = (crc >> 8) & 0x00FF
            crc &= 0x00FF
            crc = READ_LE_UINT16(crcTable8[crc << 1:])
            crc ^= tmp

        return crc

    def inputBits(self, amount):
        newBitBuffh = self._bitBuffh
        newBitBuffl = self._bitBuffl
        newBitCount = self._bitCount
        remBits = 0
        returnVal = ((1 << amount) - 1) & newBitBuffl
        newBitCount -= amount

        if newBitCount < 0:
            newBitCount += amount
            remBits = (newBitBuffh << (16 - newBitCount))
            remBits &= 0xFFFF
            newBitBuffh >>= newBitCount
            newBitBuffl >>= newBitCount
            newBitBuffl |= remBits
            self._srcPtr += 2

            self._inputByteLeft -= 2
            if self._inputByteLeft <= 0:
                newBitBuffh = 0
            elif self._inputByteLeft == 1:
                newBitBuffh = self._input[self._srcPtr]
            else:
                newBitBuffh = READ_LE_UINT16(self._input[self._srcPtr:])

            amount -= newBitCount
            amount &= 0x00FF
            newBitCount = 16 - amount

        remBits = (newBitBuffh << (16 - amount))
        remBits &= 0xFFFF
        self._bitBuffh = newBitBuffh >> amount
        self._bitBuffl = (newBitBuffl >> amount) | remBits
        self._bitCount = newBitCount & 0x00FF

        return returnVal

    def makeHufftable(self, table):
        bitLength = 0
        i = 0
        j = 0
        numCodes = self.inputBits(5)

        if not numCodes:
            return

        huffLength = [0] * 16
        for i in range(numCodes):
            huffLength[i] = self.inputBits(4) & 0x00FF

        huffCode = 0

        table_idx = 0
        for bitLength in range(1, 17):
            for i in range(numCodes):
                if huffLength[i] == bitLength:
                    table[table_idx] = (1 << bitLength) - 1
                    assert table[table_idx] & 0xFFFF == table[table_idx]
                    table_idx += 1

                    b = huffCode >> (16 - bitLength)
                    a = 0

                    for j in range(bitLength):
                        a |= ((b >> j) & 1) << (bitLength - j - 1)
                        a &= 0xFFFF
                    table[table_idx] = a
                    table_idx += 1

                    table[table_idx + 0x1e] = (huffLength[i] << 8) | (i & 0x00FF)
                    huffCode += 1 << (16 - bitLength)
                    huffCode &= 0xFFFF

    def inputValue(self, table):
        valOne = 0
        valTwo = 0
        value = self._bitBuffl

        table_idx = 0
        while True:
            valTwo = table[table_idx] & value
            table_idx += 1
            valOne = table[table_idx]
            table_idx += 1

            if valOne == valTwo:
                break

        value = table[table_idx + 0x1e]
        self.inputBits((value >> 8) & 0x00FF)
        value &= 0x00FF

        if value >= 2:
            value -= 1
            valOne = self.inputBits(value & 0x00FF)
            valOne |= (1 << value)
            valOne &= 0xFFFF
            value = valOne

        return value

    def unpackM1(self, input, inputSize, output):
        outputLow = output
        outputHigh = None
        inputHigh = None

        inputptr = 0
        unpackLen = 0
        packLen = 0
        counts = 0
        crcUnpacked = 0
        crcPacked = 0

        self._inputByteLeft = inputSize
        self._bitBuffl = 0
        self._bitBuffh = 0
        self._bitCount = 0

        self._input = input
        self._output = output

        # Check for "RNC "
        if input[0:4] != b'RNC\x01':
            print(input[0:4])
            return NOT_PACKED

        inputptr += 4

        # Read unpacked/packed file length
        unpackLen = READ_BE_UINT32(input[inputptr:])
        inputptr += 4
        packLen = READ_BE_UINT32(input[inputptr:])
        inputptr += 4

        blocks = input[inputptr + 5]

        # Read CRCs
        crcUnpacked = READ_BE_UINT16(input[inputptr:])
        inputptr += 2
        crcPacked = READ_BE_UINT16(input[inputptr:])
        inputptr += 2
        inputptr = inputptr + HEADER_LEN - 16

        print(crcPacked, crcUnpacked)
        if self.crcBlock(input[inputptr:], packLen) != crcPacked:
            return PACKED_CRC

        inputptr = HEADER_LEN
        self._srcPtr = inputptr

        inputHigh = packLen + HEADER_LEN
        outputLow = 0
        outputHigh = input[16] + unpackLen + outputLow

        if not (inputHigh <= outputLow or outputHigh <= inputHigh):
            self._srcPtr = inputHigh
            self._dstPtr = outputHigh
            output[self._dstPtr-packLen:self._dstPtr] = input[self._srcPtr-packLen:self._srcPtr]
            self._srcPtr = self._dstPtr - packLen
            self._input = self._output

        self._inputByteLeft -= HEADER_LEN

        self._dstPtr = 0
        self._bitCount = 0

        self._bitBuffl = READ_LE_UINT16(self._input[self._srcPtr:])
        self.inputBits(2)

        assert blocks > 0, blocks
        for _ in range(blocks):
            self.makeHufftable(self._rawTable)
            self.makeHufftable(self._posTable)
            self.makeHufftable(self._lenTable)

            counts = self.inputBits(16)
            counts &= 0xFFFF

            assert counts > 0, counts

            while True:
                inputLength = self.inputValue(self._rawTable)
                inputOffset = 0

                if inputLength:
                    if self._inputByteLeft < inputLength or inputLength > 0xff000000:
                        return NOT_PACKED
                    self._output[self._dstPtr:self._dstPtr+inputLength] = self._input[self._srcPtr:self._srcPtr+inputLength]
                    self._dstPtr += inputLength
                    self._srcPtr += inputLength
                    self._inputByteLeft -= inputLength
                    a = 0
                    if self._inputByteLeft <= 0:
                        a = 0
                    elif self._inputByteLeft == 1:
                        a = self._input[self._srcPtr]
                    else:
                        a = READ_LE_UINT16(self._input[self._srcPtr:])

                    b = 0
                    if self._inputByteLeft <= 2:
                        b = 0
                    elif self._inputByteLeft == 3:
                        b = self._input[self._srcPtr + 2]
                    else:
                        b = READ_LE_UINT16(self._input[self._srcPtr + 2:])

                    self._bitBuffl &= ((1 << self._bitCount) - 1)
                    self._bitBuffl |= (a << self._bitCount)
                    self._bitBuffl &= 0xFFFF
                    self._bitBuffh = (a >> (16 - self._bitCount)) | (b << self._bitCount)

                if counts > 1:
                    inputOffset = self.inputValue(self._posTable) + 1
                    inputLength = self.inputValue(self._lenTable) + MIN_LENGTH

                    tmpPtr = self._dstPtr - inputOffset
                    while inputLength > 0:
                        self._output[self._dstPtr] = self._output[tmpPtr]
                        self._dstPtr += 1
                        tmpPtr += 1
                        inputLength -= 1

                counts -= 1
                counts &= 0xFFFF
                # print('COUNTS', counts)
                if counts == 0:
                    break

        if self.crcBlock(output, unpackLen) != crcUnpacked:
            return UNPACKED_CRC

        return unpackLen
