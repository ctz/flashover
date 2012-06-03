
# glue
from shared import config
import os.path as path
import os, sys
from cStringIO import StringIO
from time import time

# the interesting bits
import swf.movie, swf.consts, swf.tag, swf.sound
import Image
import sndhdr
import mp3hdr
import swfmeta

# whether to write a huge log.txt in output directory
WRITE_LOG = False

def output_with_alpha(img, outf):
    if hasattr(img, 'bitmapAlphaData'):
        img.bitmapAlphaData.seek(0)
        img.bitmapData.seek(0)
        opaque = Image.open(img.bitmapData)
        alpha = Image.fromstring('L', opaque.size, img.bitmapAlphaData.read())
        opaque.putalpha(alpha)
        opaque.save(outf, 'PNG')
        return 'Re-attached alpha channel and converted to PNG', swf.consts.BitmapType.PNG
    else:
        im = Image.open(img.bitmapData)
        im.save(outf, im.format)
        return 'Direct', img.bitmapType

def output_image(img, jpeg_table, outf):
    if isinstance(img, swf.tag.TagDefineBitsJPEG2):
        return output_with_alpha(img, outf)
    elif isinstance(img, swf.tag.TagDefineBits):
        s = StringIO()
        assert jpeg_table is not None
        if jpeg_table:
            jpeg_table.jpegTables.seek(0)
            s.write(jpeg_table.jpegTables.read())
            action = 'Direct with re-attached JPEG tables'
        else:
            action = 'Direct'
        img.bitmapData.seek(0)
        s.write(img.bitmapData.read())
        s.seek(0)
        im = Image.open(s)
        im.save(outf, im.format)
        return action, img.bitmapType
    else:
        return output_with_alpha(img, outf)

def debug(f, timeline, indent = 0):
    for i, x in enumerate(timeline.tags):
        print >>f, '    ' * indent, i, x
        print >>f, '    ' * indent, '  ', vars(x)
        if hasattr(x, 'tags'):
            debug(f, x, indent + 1)
            
def produce_stats(meta):
    r = dict()
    for kind in 'images binaries sounds shapes'.split():
        r['c_' + kind] = len(meta.get(kind, []))
        r['sz_' + kind] = sum(x.get('filesize', 0) for id, x in meta.get(kind, []))
    r['sz_input'] = meta.get('filesize', 0)
    r['cputime'] = meta.get('parse_time', 0.0)
    return r

def get_image_meta(imf):
    im = Image.open(imf)
    return dict(img_mode = im.mode, img_dims = im.size, img_info = im.info, img_format = im.format)

def get_sound_meta(snf):
    hdr = sndhdr.what(snf)
    if hdr:
        tt, rate, chans, frames, bits_per_samp = hdr
        return dict(snd_type = tt, snd_rate = rate, snd_chans = chans, snd_frames = frames, snd_bits = bits_per_samp)
    
    hdr = mp3hdr.what(snf)
    if hdr:
        return hdr
    
    return dict()

def is_7bit_ascii(bin):
    for x in bin:
        if ord(x) & 0x80:
            return False
    return True

prefixes = {
    'CWS':      ('Flash movie (compressed)', 'application/x-shockwave-flash'),
    'FWS':      ('Flash movie (uncompressed)', 'application/x-shockwave-flash'),
    '\x89PNG':  ('PNG', 'image/png'),
    '\xff\xd8': ('JPEG', 'image/jpeg'),
}

def get_binary_meta(bb):
    # try for 7-bit ascii
    if is_7bit_ascii(bb):
        return dict(type = '7-bit ASCII', mimetype = 'text/plain')
    
    for pfx in prefixes:
        if bb.startswith(pfx):
            t, mt = prefixes[pfx]
            return dict(type = t, mimetype = mt)

    return dict(type = 'Unknown', mimetype = 'application/octet-stream')

def emit_stream(streams, stream, outdir):
    if streams:
        i = max(streams.keys()) + 1 # streams are unnumbered
    else:
        i = 0xffff
    try:
        if swf.sound.supported(stream):
            filename = 'soundstream-%d%s' % (i, swf.consts.AudioCodec.FileExtensions[stream[0].soundFormat])
            with open(path.join(outdir, filename), 'wb') as sf:
                swf.sound.write_stream_to_file(stream, sf)
            streams[i] = dict(status = 'extracted',
                              id = i,
                              kind = 'soundstream',
                              filesize = path.getsize(path.join(outdir, filename)),
                              mimetype = swf.consts.AudioCodec.MimeTypes[stream[0].soundFormat],
                              codec = swf.consts.AudioCodec.tostring(stream[0].soundFormat),
                              filename = filename,
                              **get_sound_meta(path.join(outdir, filename)))
        elif swf.sound.junk(stream):
            pass # discard junk
        else:
            streams[i] = dict(status = 'skipped',
                              id = i,
                              kind = 'soundstream',
                              reason = swf.sound.reason_unsupported(stream),
                              codec = swf.consts.AudioCodec.tostring(stream[0].soundFormat))
    except Exception:
        print 'stream', i, 'extraction failed:'
        sys.excepthook(*sys.exc_info())

def emit_sound(sounds, sound, outdir):
    try:
        i = sound.soundId
        if swf.sound.supported(sound):
            filename = 'sound-%d%s' % (i, swf.consts.AudioCodec.FileExtensions[sound.soundFormat])
            with open(path.join(outdir, filename), 'wb') as sf:
                swf.sound.write_sound_to_file(sound, sf)
            sounds[i] = dict(status = 'extracted',
                             id = i,
                             kind = 'sound',
                             filesize = path.getsize(path.join(outdir, filename)),
                             mimetype = swf.consts.AudioCodec.MimeTypes[sound.soundFormat],
                             codec = swf.consts.AudioCodec.tostring(sound.soundFormat),
                             filename = filename,
                             **get_sound_meta(path.join(outdir, filename)))
        elif swf.sound.junk(sound):
            pass # discard junk
        else:
            sounds[i] = dict(status = 'skipped',
                             id = i,
                             kind = 'sound',
                             reason = swf.sound.reason_unsupported(sound),
                             codec = swf.consts.AudioCodec.tostring(sound.soundFormat))
    except Exception:
        print 'sound', i, 'extraction failed:'
        sys.excepthook(*sys.exc_info())

def emit_image(images, image, jpeg_table, outdir):
    try:
        i = image.characterId
    
        # output to temp file, because type can change during writing
        tmp_filename = 'image-%d.tmp' % (i)
        with open(path.join(outdir, tmp_filename), 'wb') as sf:
            action, resulting_type = output_image(image, jpeg_table, sf)
        
        # now move into place
        real_filename = 'image-%d%s' % (i, swf.consts.BitmapType.FileExtensions[resulting_type])
        os.rename(path.join(outdir, tmp_filename), path.join(outdir, real_filename))
        
        images[i] = dict(status = 'extracted',
                         id = i,
                         extract = action,
                         filesize = path.getsize(path.join(outdir, real_filename)),
                         original_type = swf.consts.BitmapType.tostring(image.bitmapType),
                         effective_type = swf.consts.BitmapType.tostring(resulting_type),
                         filename = real_filename,
                         **get_image_meta(path.join(outdir, real_filename)))
    except Exception:
        print 'image', i, 'extraction failed:'
        sys.excepthook(*sys.exc_info())

def emit_shape(shapes, shape, movie, outdir):
    try:
        i = shape.characterId
        filename = 'shape-%d.svg' % (i,)
        with open(path.join(outdir, filename), 'wb') as sf:
            exporter = swf.export.SingleShapeSVGExporter()
            svg = exporter.export_single_shape(shape, movie)
            svg.seek(0)
            sf.write(svg.read())
        shapes[i] = dict(status = 'converted',
                         id = i,
                         filesize = path.getsize(path.join(outdir, filename)),
                         filename = filename)
    except Exception:
        print 'shape', i, 'extraction failed:'
        sys.excepthook(*sys.exc_info())

def emit_binary(binaries, binary, outdir):
    try:
        i = binary.characterId
        filename = 'binary-%d.dat' % (i, )
        with open(path.join(outdir, filename), 'wb') as sf:
            sf.write(binary.data)
        binaries[i] = dict(status = 'extracted',
                           id = i,
                           filesize = path.getsize(path.join(outdir, filename)),
                           filename = filename,
                           **get_binary_meta(binary.data))
    except Exception:
        print 'binary', i, 'extraction failed:'
        sys.excepthook(*sys.exc_info())

def process_file(input, outdir):
    print 'we have candidate', input

    # open it
    start = time()
    with open(input, 'rb') as f:
        m = swf.movie.SWF(f)
    parse_time = time() - start
    
    if WRITE_LOG:
        with open(path.join(outdir, 'log.txt'), 'w') as sf:
            debug(sf, m)
  
    # export sounds
    sounds = {}
    
    # sounds
    for sound in m.all_tags_of_type(swf.tag.TagDefineSound):
        emit_sound(sounds, sound, outdir)
    
    # streams (after, as we add to the number space)
    for stream in m.collect_sound_streams():
        emit_stream(sounds, stream, outdir)
    
    # export images
    images = {}
    
    jpeg_table = None
    for jpeg_table in m.all_tags_of_type(swf.tag.TagJPEGTables):
        pass
    
    for image in m.all_tags_of_type((swf.tag.TagDefineBitsLossless, swf.tag.TagDefineBits)):
        emit_image(images, image, jpeg_table, outdir)

    # export shapes
    shapes = {}
    for shape in m.all_tags_of_type(swf.tag.TagDefineShape):
        emit_shape(shapes, shape, m, outdir)
                 
    # export binaries
    binaries = {}
    for bb in m.all_tags_of_type(swf.tag.TagDefineBinaryData):
        emit_binary(binaries, bb, outdir)
    
    print 'done'
    return dict(filesize = path.getsize(input),
                parse_time = parse_time,
                sounds = sounds.items(),
                images = images.items(),
                binaries = binaries.items(),
                shapes = shapes.items(),
                metadata = swfmeta.extract_metadata(m),
                )
