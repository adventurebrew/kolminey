
import struct
import wave

smpFile = open('ENGLISH.SMP', 'rb')
idxFile = open('ENGLISH.IDX', 'rb')

count = 0
idxFile.seek(0, 2)
size = idxFile.tell()
size = size / 4
idxCount = size
idxFile.seek(0, 0)
while idxCount > 0:
    position = struct.unpack('<I', idxFile.read(4))[0]
    if position != 0:
        smpFile.seek(position, 0)
        sampleSize = struct.unpack('<I', smpFile.read(4))[0]
        wavFile = wave.open('VOICES/sample-{}.wav'.format(size - idxCount), 'wb')
        wavFile.setnchannels(1)
        wavFile.setsampwidth(1)
        wavFile.setframerate(22050)
        wavFile.writeframes(smpFile.read(sampleSize))
        wavFile.close()
    idxCount -= 1

smpFile.close()
idxFile.close()
