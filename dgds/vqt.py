def do_vqt_decode2(state, x, y, w, h):
    if not h or not w:
        return

    if w == 1 and h == 1:
        state['dstPtr'][state['rowStarts'][y] + x] = _get_vqt_bits(state, 8)
        return

    losize = (w & 0xff) * (h & 0xff)
    bitcount1 = 8
    if losize < 256:
        bitcount1 = 0
        b = losize - 1
        while b:
            bitcount1 += 1
            b >>= 1

    firstval = _get_vqt_bits(state, bitcount1)

    bitcount2 = 0
    bval = firstval
    while firstval:
        bitcount2 += 1
        firstval >>= 1

    bval += 1

    if losize * 8 <= losize * bitcount2 + bval * 8:
        for xx in range(x, x + w):
            for yy in range(y, y + h):
                state['dstPtr'][state['rowStarts'][yy] + xx] = _get_vqt_bits(state, 8)
        return

    if bval == 1:
        val = _get_vqt_bits(state, 8)
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                state['dstPtr'][state['rowStarts'][yy] + xx] = val
        return

    tmpbuf = bytearray(255)
    ptmpbuf = 0
    for _ in range(bval):
        tmpbuf[ptmpbuf] = _get_vqt_bits(state, 8)
        ptmpbuf += 1

    for xx in range(x, x + w):
        for yy in range(y, y + h):
            state['dstPtr'][state['rowStarts'][yy] + xx] = tmpbuf[_get_vqt_bits(state, bitcount2)]


def _get_vqt_bits(state, nbits):
    assert nbits <= 8
    offset = state['offset']
    index = offset >> 3
    shift = offset & 7
    state['offset'] += nbits
    assert state['offset'] <= 0xFFFFFFFF and index <= 0xFFFFFFFF and shift <= 0xFFFFFFFF
    return (int.from_bytes(state['srcPtr'][index:index+2], 'little') >> shift) & (0xff00 >> (16 - nbits))


def do_vqt_decode(state, x, y, w, h):
    if not w and not h:
        return

    mask = _get_vqt_bits(state, 4)

    # Top left quadrant
    if mask & 8:
        do_vqt_decode(state, x, y, w // 2, h // 2)
    else:
        do_vqt_decode2(state, x, y, w // 2, h // 2)

    # Top right quadrant
    if mask & 4:
        do_vqt_decode(state, x + (w // 2), y, (w + 1) // 2, h // 2)
    else:
        do_vqt_decode2(state, x + (w // 2), y, (w + 1) // 2, h // 2)

    # Bottom left quadrant
    if mask & 2:
        do_vqt_decode(state, x, y + (h // 2), w // 2, (h + 1) // 2)
    else:
        do_vqt_decode2(state, x, y + (h // 2), w // 2, (h + 1) // 2)

    # Bottom right quadrant
    if mask & 1:
        do_vqt_decode(state, x + (w // 2), y + (h // 2), (w + 1) // 2, (h + 1) // 2)
    else:
        do_vqt_decode2(state, x + (w // 2), y + (h // 2), (w + 1) // 2, (h + 1) // 2)


def load_vqt(data, offset, width, height):
    tw = width
    th = height
    assert th != 0
    if th > 200:
        raise ValueError("Max VQT height supported is 200px")
    state = {
        'dstPtr': bytearray(width * height),
        'offset': offset,
        'rowStarts': [tw * i for i in range(th)],
    }
    nbytes = len(data)
    buf = bytearray(nbytes + 8)
    buf[:nbytes] = data
    state['srcPtr'] = buf
    do_vqt_decode(state, 0, 0, tw, th)
    return state['offset'], bytes(state['dstPtr'])
