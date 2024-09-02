import io
import pathlib
import archive
from iff import decompress_chunk, read_chunks

optable = {
    0x0000: 'FINISH',
    0x0020: 'SAVE_BACKGROUND',
    0x0070: 'FREE_PALETTE',
    0x0080: 'FREE_SHAPE',
    0x0090: 'FREE_FONT',
    0x00B0: 'NOTHING?',
    0x00C0: 'FREE_GETPUT',
    0x0110: 'PURGE',
    0x0220: 'STOP_CURRENT_MUSIC',
    0x0400: 'RESET_PALETTE',
    0x0ff0: 'REFRESH',
    0x1020: 'SET_DELAY {0}',
    0x1030: 'SET_BRUSH {0}',
    0x1050: 'SELECT_BMP {0}',
    0x1060: 'SELECT_PAL {0}',
    0x1070: 'SELECT_FONT {0}',
    0x1090: 'SELECT_SONG {0}',
    0x10a0: 'SET_SCENE? {0}',
    0x1100: 'SET_SCENE {0}',
    0x1110: 'SET_SCENE {0}',
    0x1120: 'SET_GETPUT_NUM {0}',
    0x1200: 'GOTO {0}',
    0x1300: 'PLAY_SFX {0}',
    0x1310: 'STOP_SFX {0}',
    0x2000: 'SET_COLORS fgcol={0}, bgcol={1}',
    0x2020: 'SET_RANDOM_SLEEP min={0}, max={1}',
    0x2300: 'PALETTE_CONFIGURE_BLOCK_SWAP num={0}, start={1}, end={2}',
    0x2400: 'PALETTE_DO_BLOCK_SWAPS {0}, {1}',
    0x3000: 'GOSUB {0}, {1}, {2}',
    0x4000: 'SET_CLIP_WINDOW {0}, {1}, {2}, {3}',
    0x4110: 'FADE_OUT colorno={0}, ncolors={1}, targetcol={2}, speed={3}',
    0x4120: 'FADE_IN colorno={0}, ncolors={1}, targetcol={2}, speed={3}',
    0x4200: 'STORE_AREA {0}, {1}, {2}, {3}',
    0x4210: 'SAVE_GETPUT_REGION {0}, {1}, {2}, {3}',
    0xA000: 'DRAW_PIXEL {0}, {1}',
    0xA010: 'DRAW_WIPE {0}, {1}, {2}, {3}',
    0xA020: 'DRAW_WIPE {0}, {1}, {2}, {3}',
    0xA030: 'DRAW_WIPE {0}, {1}, {2}, {3}',
    0xA040: 'DRAW_WIPE {0}, {1}, {2}, {3}',
    0xA050: 'DRAW_WIPE {0}, {1}, {2}, {3}',
    0xA060: 'DRAW_WIPE {0}, {1}, {2}, {3}',
    0xA070: 'DRAW_WIPE {0}, {1}, {2}, {3}',
    0xA080: 'DRAW_WIPE {0}, {1}, {2}, {3}',
    0xA090: 'DRAW_WIPE {0}, {1}, {2}, {3}',
    0xA0A0: 'DRAW_LINE {0}, {1}, {2}, {3}',
    0xA100: 'DRAW_FILLED_RECT {0}, {1}, {2}, {3}',
    0xA110: 'DRAW_EMPTY_RECT {0}, {1}, {2}, {3}',
    0xA200: 'DRAW_STRING {0}, {1}, {2}, {3}',
    0xA210: 'DRAW_STRING {0}, {1}, {2}, {3}',
    0xA220: 'DRAW_STRING {0}, {1}, {2}, {3}',
    0xA230: 'DRAW_STRING {0}, {1}, {2}, {3}',
    0xA240: 'DRAW_STRING {0}, {1}, {2}, {3}',
    0xA250: 'DRAW_STRING {0}, {1}, {2}, {3}',
    0xA260: 'DRAW_STRING {0}, {1}, {2}, {3}',
    0xA270: 'DRAW_STRING {0}, {1}, {2}, {3}',
    0xA280: 'DRAW_STRING {0}, {1}, {2}, {3}',
    0xA290: 'DRAW_STRING {0}, {1}, {2}, {3}',
    0xA300: 'DRAW_DIALOG_FOR_STRINGS {0}, {1}, {2}, {3}',
    0xA500: 'DRAW_SPRITE {0}, {1}',
    0xA510: 'DRAW_SPRITE_FLIP_V {0}, {1}',
    0xA520: 'DRAW_SPRITE_FLIP_H {0}, {1}',
    0xA530: 'DRAW_SPRITE_FLIP_HV {0}, {1}, {2}, {3}',
    0xA600: 'DRAW_GETPUT {0}',
    0xB000: 'CREDIT_SCROLL_INIT',
    0xB010: 'CREDIT_SCROLL {0}, {1}, {2}',
    0xC020: 'LOAD_SAMPLE {0}',
    0xC030: 'SELECT_SAMPLE {0}',
    0xC050: 'PLAY_SAMPLE {0}',
    0xF010: 'LOAD_SCR {text}',
    0xF020: 'LOAD_BMP {text}',
    0xF040: 'LOAD_FONT {text}',
    0xF050: 'LOAD_PAL {text}',
    0xF060: 'LOAD_SONG {text}',
    0xF100: 'SET_STRING {text}',
    0xF110: 'SET_STRING {text}',
    0xF120: 'SET_STRING {text}',
    0xF130: 'SET_STRING {text}',
    0xF140: 'SET_STRING {text}',
    0xF150: 'SET_STRING {text}',
    0xF160: 'SET_STRING {text}',
    0xF170: 'SET_STRING {text}',
    0xF180: 'SET_STRING {text}',
    0xF190: 'SET_STRING {text}',

    0x0010: 'UNKNOWN',
    0x0230: 'RESET_CURRENT_MUSIC',
    0x1040: 'SET_GLOBAL',
    0x10B0: 'NULL_OP',
    0x2010: 'SET_FRAME',
    0xA400: 'DRAW_FILLED_CIRCLE',
    0xA420: 'DRAW_EMPTY_CIRCLE',
    0xB600: 'DRAW_SCREEN',
    0xC040: 'DESELECT_SAMPLE',
    0xC060: 'STOP_SAMPLE',
    0xC0E0: 'FADE_SONG',
}

def decompile_tt3(content):
    ln = len(content)

    with io.BytesIO(content) as stream:

        code = 0
        while code != 0x0ff0 and stream.tell() < ln:
            next = stream.read(2)
            code = int.from_bytes(next, 'little')
            op = code & 0xFFF0
            count = code & 0x000F
            ivals = []
            sval = bytearray()
            strval = ''

            if count > 8 and count != 0x0F:
                raise ValueError(count)

            if count == 0x0F:
                while True:
                    ch0, ch1 = stream.read(2)
                    if ch0:
                        sval.append(ch0)
                    if ch1:
                        sval.append(ch1)
                    if ch0 == 0 or ch1 == 0:
                        break
                strval = sval.decode('ascii')

            else:
                ivals = [int.from_bytes(stream.read(2), 'little') for _ in range(count)]

            # print(f'OP: 0x{op:04X}', ivals, strval)
            print(optable[op].format(*ivals, text=strval))


num_args = {
    0x1080: 1,
    0x1090: 1,
    0x1380: 1,
    0x1390: 1,
    0x13A0: 1,
    0x13A1: 1,
    0x13B0: 1,
    0x13B1: 1,
    0x13C0: 1,
    0x13C1: 1,
    0x3020: 1,
    0xF010: 1,
    0xF200: 1,
    0xF210: 1,
    0x1010: 2,
    0x1020: 2,
    0x1030: 2,
    0x1040: 2,
    0x1050: 2,
    0x1060: 2,
    0x1070: 2,
    0x1310: 2,
    0x1320: 2,
    0x1330: 2,
    0x1340: 2,
    0x1350: 2,
    0x1360: 2,
    0x1370: 2,
    0x2010: 3,
    0x2015: 3,
    0x2020: 3,
    0x4000: 3,
    0x4010: 3,
    0x2000: 4,
    0x2005: 4,
}

LOGIC_OPS = {
    0x1010, 0x1020, 0x1030, 0x1040, 0x1050, 0x1060, 0x1070, 0x1080, 0x1090, 
    0x1310, 0x1320, 0x1330, 0x1340, 0x1350, 0x1360, 0x1370, 0x1380, 0x1390,
    0x3010,
}

END_OPS = {
    0x1500, 0x1510, 0x1520,
    0x30FF,
}

BOOL_OPS = {0x1420, 0x1430}

def find_used_sequences_for_segment(stream, ln, segno):
    start = stream.tell()
    opcode = 0
    segno2 = int.from_bytes(stream.read(2), 'little')
    assert segno == segno2, (segno, segno2)
    while opcode != 0xFFFF and stream.tell() < ln:
        opcode = int.from_bytes(stream.read(2), 'little')
        args = [int.from_bytes(stream.read(2), 'little') for _ in range(num_args.get(opcode, 0))]
        print(f'SEGMENT - OP: 0x{opcode:04X}', args)

    return stream.tell() - start



def parse_ads(content):
    with io.BytesIO(content) as stream:
        segno = 0
        currlabel = segno
        ast = {currlabel: []}
        while stream.tell() < len(content):
            opcode = int.from_bytes(stream.read(2), 'little')
            args = [int.from_bytes(stream.read(2), 'little') for _ in range(num_args.get(opcode, 0))]
            ast[currlabel].append((opcode, args))
            if opcode == 0xFFFF:
                _segno2 = int.from_bytes(stream.read(2), 'little')
                segno += 1
                assert segno not in ast, segno
                currlabel = segno
                ast[currlabel] = []

    return ast


ast_ops = {
    0x0001: 'init',
    0x0003: 'unknown',
    0x0005: 'init',
    0x1010: 'WHILE runtype {0}, {1}',
    0x1020: 'WHILE not runtype {0}, {1}',
    0x1030: 'WHILE NOT_PLAYED {0}, {1}',
    0x1040: 'WHILE PLAYED {0}, {1}',
    0x1050: 'WHILE FINISHED {0}, {1}',
    0x1060: 'WHILE NOT_RUNNING {0}, {1}',
    0x1070: 'WHILE RUNNING {0}, {1}',
    0x1080: 'WHILE count? {0}',
    0x1090: 'WHILE ?? {0}',
    0x1310: 'IF runtype 5 {0}, {1}',
    0x1320: 'IF not runtype 5 {0}, {1}',
    0x1330: 'IF NOT_PLAYED {0}, {1}',
    0x1340: 'IF PLAYED {0}, {1}',
    0x1350: 'IF FINISHED {0}, {1}',
    0x1360: 'IF NOT_RUNNING {0}, {1}',
    0x1370: 'IF RUNNING {0}, {1}',
    0x1380: 'IF DETAIL LEVEL <= {0}',
    0x1390: 'IF DETAIL LEVEL >= {0}',
    0x1500: 'ELSE / Skip to end-if',
    0x1510: 'END IF',
    0x1520: 'END WHILE',
    0x2000: 'ADD sequence {0}, {1}, {2}, {3}',
    0x2005: 'ADD sequence {0}, {1}, {2}, {3}',
    0x2010: 'STOP SCENE {0}, {1}, {2}',
    0x2015: 'SET RUNFLAG 5 {0}, {1}, {2}',
    0x2020: 'RESET SEQ {0}, {1}, {2}',
    0x3020: 'RANDOM_NOOP {0}',
    0x3010: 'RANDOM_START',
    0x30FF: 'RANDOM_END',
    0x4000: 'MOVE SEQ TO BACK {0}, {1}',
    0x4010: 'MOVE SEQ TO FRONT {0}, {1}',
    0xF000: 'SET STATE 2',
    0xF010: 'FADE_OUT {0}',
    0xF200: 'RUN_SCRIPT {0}',
    0xF210: 'RUN_SCRIPT {0}',
    0xFFFF: 'END',
    0x1420: 'AND',
    0x1430: 'OR',
    0xFF10: 'UNKNOWN',
    0xFFF0: 'END_IF',
}



def decompile_ads(ast):
    for seg, seq in ast.items():
        if not seq:
            continue
        print(f'{seg}:')
        ident = 1
        for opcode, args in seq:
            if opcode in END_OPS | BOOL_OPS:
                ident -= 1
            print('\t' * ident + ast_ops[opcode].format(*args))
            if opcode in LOGIC_OPS:
                ident += 1
    print()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('fname', help='Path to the game resource map')
    args = parser.parse_args()

    fname = pathlib.Path(args.fname)

    with archive.open(fname) as f:
        # for palfile in f.glob('*.TTM'):
        #     print(palfile.name)
        #     chunks = list(read_chunks(palfile.read_bytes()))

        #     for chunk in chunks:
        #         content = chunk.content
        #         if chunk.tag == b'TT3:':
        #             content = decompress_chunk(content)

        #             decompile_tt3(content)

        for palfile in f.glob('*.ADS'):
            print(palfile.name)
            chunks = list(read_chunks(palfile.read_bytes()))
            for chunk in chunks:
                content = chunk.content
                if chunk.tag == b'ADS:':
                    subchunks = list(read_chunks(content))
                    for subchunk in subchunks:
                        content = subchunk.content
                        if subchunk.tag == b'TAG:':
                            # tags = read_tags(subchunk.content)
                            print(subchunk.content)
                        elif subchunk.tag == b'RES:':
                            pass
                        elif subchunk.tag == b'SCR:':
                            content = decompress_chunk(content)
                            ast = parse_ads(content)
                            decompile_ads(ast)
