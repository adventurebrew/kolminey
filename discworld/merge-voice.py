
import struct
import wave

smpFile = open('ENGLISH-NEW.SMP', 'wb')
idxFile = open('ENGLISH.IDX', 'rb')
nidxFile = open('ENGLISH-NEW.IDX', 'wb')

count = 0
idxFile.seek(0, 2)
size = idxFile.tell()
size = size / 4
idxCount = size
idxFile.seek(0, 0)
written = 4
smpFile.write('\x2e\xa1\x08\x00')
while idxCount > 0:
    position = struct.unpack('<I', idxFile.read(4))[0]
    if position == 0:
        nidxFile.write(struct.pack('<I', 0))
        # written += 4
    else:
        with open('VOICES/sample-{}.wav'.format(size - idxCount), 'rb') as wavFile:
            nidxFile.write(struct.pack('<I', written))
            data = wavFile.read().split('data')
            length = struct.unpack('<I', data[1][:4])[0]
            # smpFile.write(struct.pack('<I', length))
            smpFile.write(data[1])
            written += length + 4
    idxCount -= 1

smpFile.close()
idxFile.close()
nidxFile.close()
