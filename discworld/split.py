import os
import struct

filenum = 0
reverse = False
os.makedirs('DIALOGUE', exist_ok=True)
with open('ENGLISH.TXT', 'rb') as pFile, \
        open('DIALOGUE\ENGLISH-ALL.TXT'.format(filenum), 'w') as cFile: 
    while True:
        a = pFile.read(4)
        assert a[:2] == b'\x01\x00'
        assert a[2:] == b'43'
        nextOffset = struct.unpack('<I', pFile.read(4))[0]
        if nextOffset == 0:
            break
        while pFile.tell() < nextOffset:
            size, = struct.unpack('<I', pFile.read(1) + b'\x00\x00\x00')
            eline = pFile.read(size)
            print(eline)
            line = eline.decode('windows-1255').replace('\t', '\\t').replace('"', '`')
            if reverse:
                line = '\n'.join(line.split('\n')[::-1])[::-1]
            if line:
                print(filenum, f'"{line}"', sep='\t', file=cFile)
        filenum += 1
        '''
        with open('DIALOGUE\ENGLISH-PART{:04}.TXT'.format(filenum), 'w') as cFile:
            size = struct.unpack('<I', pFile.read(1) + '\x00\x00\x00')
            line = pFile.read(size[0])
            line = '\n'.join(line.split('\n')[::-1])
            cFile.write(line[::-1] + '\n===ENDLINE===\n')
        '''
