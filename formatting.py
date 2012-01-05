
def base_reduce(value, base, suffixes):
    i = 0
    while value > base and i < len(suffixes):
        i += 1
        value /= base
    return '%2.f%s' % (value, suffixes[i])

def filesize(fs):
    return base_reduce(fs, 1024.0, 'bytes KB MB GB TB'.split())

def duration(secs):
    return base_reduce(secs * 1e9, 1000, 'ns us ms s'.split())

globals = dict(
    filesize = filesize,
    duration = duration
)
