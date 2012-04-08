from swf.stream import SWFStream
from swf.consts import MPEGLayer, MPEGVersion

DEBUG = 0

def MPEGBitrate(version, value):
    """
    Returns bitrate in thousands of bits per second.
    """
    if version == MPEGVersion.MPEG1:
        bitrates = [ 0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, None ]
    else:
        bitrates = [ 0, 8, 16, 24,32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, None ]
    assert len(bitrates) == 16
    rv = bitrates[value]
    if rv:
        rv *= 1000
    return rv

def MPEGSampleRate(version, value):
    """
    Returns sample rate in samples per second.
    """
    if version == MPEGVersion.MPEG1:
        return [ 44100, 48000, 32000, None ][value]
    elif version == MPEGVersion.MPEG2:
        return [ 22500, 24000, 16000, None ][value]
    elif version == MPEGVersion.MPEG2_5:
        return [ 11025, 12000, 8000, None ][value]

def SamplesPerFrame(version, layer):
    if version == MPEGVersion.MPEG1:
        return {
            0: 0,
            MPEGLayer.Layer1: 384,
            MPEGLayer.Layer2: 1152,
            MPEGLayer.Layer3: 1152
            }[layer]
    else:
        return {
            0: 0,
            MPEGLayer.Layer1: 384,
            MPEGLayer.Layer2: 1152,
            MPEGLayer.Layer3: 576
            }[layer]

def sync_ok(a, b, c):
    a = ord(a)
    b = ord(b)
    c = ord(c)
    return (a == 0xff and                     # sync a
            b & 0b11100000 == 0b11100000 and  # sync b
            b & 0b00011000 != 0b00001000 and  # illegal version
            b & 0b00000110 != 0b00000000 and  # illegal layer
            c & 0b11110000 != 0b11110000 and  # illegal bitrate
            c & 0b00001100 != 0b00001100)     # illegal samplerate
           
        
def frame_sync(st):
    while True:
        # scan for frame sync
        if DEBUG: print 'frame_sync', st.tell()
        
        # take 3 sync bytes
        start = st.tell()
        sync = st.read(3)
        
        # but only skip over one
        st.seek(start + 1)
        
        if len(sync) != 3:
            if DEBUG: print 'eof at', start
            return False
        
        if sync_ok(sync[0], sync[1], sync[2]):
            return True
        
        if DEBUG: print '... failed at', st.tell()

def get_hdr(st):
    while True:
        if not frame_sync(st):
            return None
            
        # - start with 0 bit alignment after first sync byte
        assert 0b111 == st.readUB(3)
        version = st.readUB(2)
        layer = st.readUB(2)
        have_crc = st.readUB(1) == 0
        # - byte alignment
        bitrateidx = st.readUB(4)
        samplerateidx = st.readUB(2)
        have_pad = st.readUB(1)
        private = st.readUB(1)
        # - byte alignment
        mode = st.readUB(2)
        is_mono = mode == 0b11
        modeext = st.readUB(2)
        copy = st.readUB(1)
        original = st.readUB(1)
        emphasis = st.readUB(2)
        
        bitrate = MPEGBitrate(version, bitrateidx)
        samplerate = MPEGSampleRate(version, samplerateidx)
        samples_in_frame = SamplesPerFrame(version, layer)
        
        if DEBUG:
            print 'starting at', st.tell() - 4
            print 'frame:', MPEGVersion.tostring(version), MPEGLayer.tostring(layer)
            print '      ', 'crc?', have_crc, 'pad?', have_pad, 'private bit', private
            print '      ', 'bitrate', bitrate, 'samplerate', samplerate
            print '      ', 'mode', mode, modeext, 'flags', copy, original, emphasis
            print 'ending at', st.tell()
        
        if bitrate is None or samplerate is None or samples_in_frame is None or have_crc:
            continue
        
        # work out frame length to skip over payload
        if layer == MPEGLayer.Layer1:
            frame_length = (12 * bitrate) / samplerate
            frame_length += have_pad
            frame_length *= 4
        else:
            frame_length = (samples_in_frame * bitrate) / samplerate
            frame_length /= 8
            frame_length += have_pad
        
        if frame_length == 0:
            # 'free' mode. skip header and try to resync
            frame_length = 4
         
        if DEBUG: print 'length:', frame_length
        st.seek(st.tell() + frame_length - 4)
        
        return dict(
            time = samples_in_frame / float(samplerate),
            bitrate = bitrate,
            samplerate = samplerate,
            channels = [2, 1][is_mono],
            version = MPEGVersion.tostring(version),
            layer = MPEGLayer.tostring(layer)
            )

def what(fn):
    with open(fn, 'rb') as f:
        st = SWFStream(f)
        first_hdr = None
        vbr = False
        totaltime = 0
        for hdr in iter(lambda: get_hdr(st), None):
            if DEBUG: print hdr
            if first_hdr is None:
                first_hdr = hdr
            if first_hdr['bitrate'] != hdr['bitrate']:
                vbr = True
            totaltime += hdr['time']
        
        if first_hdr is None:
            return None
        
        rc = dict(first_hdr)
        rc['time'] = totaltime
        rc['bitrate'] /= 1000.0
        rc['samplerate'] /= 1000.0
        rc['vbr'] = vbr
        return rc

if __name__ == '__main__':
    import glob
    
    def check(fn, secs):
        print '** file:', fn
        w = what(fn)
        if w['time'] < secs:
            print 'measured time is too short: wanted', secs, 'measured', w['time']
        return w
    
    for g in glob.glob('mp3hdrtest/mpeg/*.mp*'):
        print '** file:', g
        print what(g)
    print what('mp3hdrtest/thing.mp3')
    print what('mp3hdrtest/thing2.mp3')
    print check('mp3hdrtest/sound-0.mp3', 7)
    print check('mp3hdrtest/sound-1.mp3', 4)
    print check('mp3hdrtest/sound-2.mp3', 119)
    print check('mp3hdrtest/sound-3.mp3', 112)
    print check('mp3hdrtest/sound-4.mp3', 137)
    print check('mp3hdrtest/sound-5.mp3', 35)
    print check('mp3hdrtest/sound-6.mp3', 82)