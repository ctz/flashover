import web

def base_reduce(value, base, suffixes):
    i = 0
    while value > base and i < len(suffixes):
        i += 1
        value /= base
    return '%2.f%s' % (value, suffixes[i])

def filesize(fs):
    return base_reduce(fs, 1024.0, [' bytes'] + 'KB MB GB TB'.split())

def duration(secs):
    return base_reduce(secs * 1e9, 1000, 'ns us ms s'.split())

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

exports = dict(
    filesize = filesize,
    duration = duration,
    overview = overview,
    urlquote = web.urlquote,
    plural = plural
)
