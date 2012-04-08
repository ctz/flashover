import web
import time
import json

duration_units = (
  'ns',
  'us',
  'ms',
  's',
  ' mins',
  ' hrs',
  ' days'
)

def base_reduce(value, bases, suffixes):
    if not isinstance(bases, list):
        bases = [bases] * len(suffixes)
    i = 0
    while i < len(suffixes) and i < len(bases) and value > bases[i]:
        value /= bases[i]
        i += 1
    return '%2.f%s' % (value, suffixes[i])

def filesize(fs):
    return base_reduce(float(fs), 1024.0, [' bytes'] + 'KB MB GB TB'.split())

def duration(secs):
    if secs < 0:
        return duration(-secs) + ' ago'
    return base_reduce(float(secs) * 1e9, [1000, 1000, 1000, 60, 60, 24], duration_units)

def overview(items):
    count = len(items)
    size = sum(it['filesize'] for it in items)
    if count == 0:
        return ''
    else:
        return '%d totalling %s' % (count, filesize(size))

def plural(n, single, plural):
    if not isinstance(n, (int, long)):
        n = len(n)
    return [plural, single][n == 1]

def audio_desc(meta):
    if meta['type'] == 'MP3':
        inp = dict(meta)
        inp['stereo'] = ['mono', 'stereo'][meta['channels'] != 1]
        inp['bitrate'] = str(int(meta['bitrate'])) + 'kbps'
        if meta['vbr']:
            inp['bitrate'] += ' (VBR)'
        return "%(version)s %(layer)s %(samplerate)sKHz %(bitrate)s %(stereo)s" % inp
    else:
        return 'unknown'
    
exports = dict(
    filesize = filesize,
    duration = duration,
    overview = overview,
    urlquote = web.urlquote,
    plural = plural,
    time_now = time.time(),
    json = json.dumps,
    audio_desc = audio_desc,
)
