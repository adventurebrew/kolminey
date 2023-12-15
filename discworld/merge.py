import struct
size = 0
with open('ENGLISH-NEW.TXT', 'wb') as pFile:
    for filenum in range(107):
        pFile.write('\x01\x00\x34\x33')
        with open('DIALOGUE\ENGLISH-PART{:04}.TXT'.format(filenum), 'rb') as cFile:
            lines = cFile.readlines()
            with open('DIALOGUE\TEMP.TXT', 'wb') as tempFile:
                count = 0
                writeLines = []
                for line in lines:
                    line = line.rstrip()
                    if line == '===ENDLINE===':
                        writeLine = '\n'.join(writeLines[::-1])
                        tempFile.write(chr(len(writeLine)))
                        writeLine = writeLine[::-1]
                        tempFile.write(writeLine)
                        writeLines = []
                        count += 1
                    else:
                        writeLines.append(line)
                size += tempFile.tell() + 8
            pFile.write(struct.pack('<I', size))
            print hex(size)
            with open('DIALOGUE\TEMP.TXT', 'rb') as tempFile:
                pFile.write(tempFile.read())
    pFile.write('\x01\x00\x34\x33')
    pFile.write('\0\0\0\0\0\0')

