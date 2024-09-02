import io


MAX_TABLE = 0x4000

class LZWDecoder:

    def get_code(self, total_bits, stream):
        bit_masks = [0x00, 0x01, 0x03, 0x07, 0x0f, 0x1f, 0x3f, 0x7f, 0xff]
        num_bits = total_bits
        result = 0

        while num_bits > 0:

            more = stream.read(1)
            if not more:
                return 0xFFFFFFFF
            stream.seek(-1, io.SEEK_CUR)

            if self._bitssize == 0:
                self._bitssize = 8
                self._bitsdata = ord(stream.read(1))

            useBits = num_bits
            if useBits > 8:
                useBits = 8
            if useBits > self._bitssize:
                useBits = self._bitssize

            result |= (self._bitsdata & bit_masks[useBits]) << (total_bits - num_bits)
            num_bits -= useBits
            self._bitssize -= useBits
            self._bitsdata >>= useBits

        return result

    def reset(self):
        self.code_table = [[0] for _ in range(MAX_TABLE)]
        self.code_table[:256] = [[x] for x in range(256)]

        self._table_size = 0x101
        self._table_max = 0x200
        self._table_full = False

        self._code_size = 9
        self._cache_bits = 0


    def decompress(self, data, size):
        out = bytearray()
        
        self._bitsdata = 0
        self._bitssize = 0
        self.reset()

        code_cur = []
        self._cache_bits = 0

        with io.BytesIO(data) as stream:
            while len(out) < size:
                code = self.get_code(self._code_size, stream)
                if code == 0xFFFFFFFF:
                    out += bytes(size - len(out))
                    break
                # print(list(data[:20]))
                # print('CODE', code)

                self._cache_bits += self._code_size
                if self._cache_bits >= self._code_size * 8:
                    self._cache_bits -= self._code_size * 8

                if code == 0x100:
                    if self._cache_bits > 0:
                        self.get_code(self._code_size * 8 - self._cache_bits, stream)
                        self.reset()
                        # code_cur = []
                        continue

                if code >= self._table_size and not self._table_full:
                    code_cur.append(code_cur[0])
                    out += bytes(code_cur)
                else:
                    out += bytes(self.code_table[code])
                    code_cur.append(self.code_table[code][0])

                if len(code_cur) < 2:
                    continue

                if not self._table_full:
                    if self._table_size == self._table_max and self._code_size == 12:
                        self._table_full = True
                        last_code = self._table_size
                    else:
                        last_code = self._table_size
                        self._table_size += 1
                        self._cache_bits = 0

                    if self._table_size == self._table_max and self._code_size < 12:
                        self._code_size += 1
                        self._table_max *= 2

                    self.code_table[last_code] = bytes(code_cur)

                code_cur = bytearray(self.code_table[code])

            return out
