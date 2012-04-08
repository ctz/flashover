
# glue
from shared import config
import json
import os.path as path
import os
from cStringIO import StringIO
from time import time

# the interesting bits
import swf.movie, swf.consts, swf.tag, swf.sound
import Image
import sndhdr
import mp3hdr

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
        r['sz_' + kind] = sum(x['filesize'] for x in meta.get(kind, []))
    r['sz_input'] = meta.get('filesize', 0)
    r['cputime'] = meta.get('parse_time', 0.0)
    return r

def get_image_meta(imf):
    im = Image.open(imf)
    return dict(img_mode = im.mode, img_dims = im.size, img_info = im.info, img_format = im.format)

def get_sound_meta(snf):
    hdr = sndhdr.what(snf)
    if hdr:
        type, rate, chans, frames, bits_per_samp = hdr
        return dict(snd_type = type, snd_rate = rate, snd_chans = chans, snd_frames = frames, snd_bits = bits_per_samp)
    
    hdr = mp3hdr.what(snf)
    if hdr:
        return hdr
    
    return dict()
    
def process_file(input, outdir):
    print 'we have candidate', input

    # open it
    start = time()
    with open(input, 'rb') as f:
        m = swf.movie.SWF(f)
    parse_time = time() - start
  
    # export sounds
    sounds = []
    
    # streams
    for stream in m.collect_sound_streams():
        i = len(sounds)
        if swf.sound.supported(stream):
            filename = 'soundstream-%d%s' % (i, swf.consts.AudioCodec.FileExtensions[stream[0].soundFormat])
            with open(path.join(outdir, filename), 'wb') as sf:
                swf.sound.write_stream_to_file(stream, sf)
            sounds.append(dict(status = 'extracted',
                               id = i,
                               kind = 'soundstream',
                               filesize = path.getsize(path.join(outdir, filename)),
                               mimetype = swf.consts.AudioCodec.MimeTypes[stream[0].soundFormat],
                               type = swf.consts.AudioCodec.tostring(stream[0].soundFormat),
                               filename = filename,
                               **get_sound_meta(path.join(outdir, filename))))
        elif swf.sound.junk(stream):
            pass # discard junk
        else:
            sounds.append(dict(status = 'skipped',
                               id = i,
                               kind = 'soundstream',
                               reason = swf.sound.reason_unsupported(stream),
                               codec = swf.consts.AudioCodec.tostring(stream[0].soundFormat)))
    
    # sounds
    for sound in m.all_tags_of_type(swf.tag.TagDefineSound):
        i = len(sounds)
        if swf.sound.supported(sound):
            filename = 'sound-%d%s' % (i, swf.consts.AudioCodec.FileExtensions[sound.soundFormat])
            with open(path.join(outdir, filename), 'wb') as sf:
                swf.sound.write_sound_to_file(sound, sf)
            sounds.append(dict(status = 'extracted',
                               id = i,
                               kind = 'sound',
                               filesize = path.getsize(path.join(outdir, filename)),
                               mimetype = swf.consts.AudioCodec.MimeTypes[sound.soundFormat],
                               type = swf.consts.AudioCodec.tostring(sound.soundFormat),
                               filename = filename,
                               **get_sound_meta(path.join(outdir, filename))))
        elif swf.sound.junk(stream):
            pass # discard junk
        else:
            sounds.append(dict(status = 'skipped',
                               id = i,
                               kind = 'sound',
                               reason = swf.sound.reason_unsupported(sound),
                               codec = swf.consts.AudioCodec.tostring(sound.soundFormat)))
    
    # export images
    images = []
    
    jpeg_table = None
    for jpeg_table in m.all_tags_of_type(swf.tag.TagJPEGTables):
        pass
    
    for image in m.all_tags_of_type((swf.tag.TagDefineBitsLossless, swf.tag.TagDefineBits)):
        i = len(images)
        
        # output to temp file, because type can change during writing
        tmp_filename = 'image-%d.tmp' % (i)
        with open(path.join(outdir, tmp_filename), 'wb') as sf:
            action, resulting_type = output_image(image, jpeg_table, sf)
        
        # now move into place
        real_filename = 'image-%d%s' % (i, swf.consts.BitmapType.FileExtensions[resulting_type])
        os.rename(path.join(outdir, tmp_filename), path.join(outdir, real_filename))
        
        images.append(dict(status = 'extracted',
                           id = i,
                           extract = action,
                           filesize = path.getsize(path.join(outdir, real_filename)),
                           original_type = swf.consts.BitmapType.tostring(image.bitmapType),
                           effective_type = swf.consts.BitmapType.tostring(resulting_type),
                           filename = real_filename,
                           **get_image_meta(path.join(outdir, real_filename))))

    # export shapes
    shapes = []
    for shape in m.all_tags_of_type(swf.tag.TagDefineShape):
        i = len(shapes)
        
        filename = 'shape-%d.svg' % (i,)
        with open(path.join(outdir, filename), 'wb') as sf:
            exporter = swf.export.SingleShapeSVGExporter()
            svg = exporter.export_single_shape(shape, m)
            svg.seek(0)
            sf.write(svg.read())
        shapes.append(dict(status = 'converted',
                           id = i,
                           filesize = path.getsize(path.join(outdir, filename)),
                           filename = filename))
                 
    # export binaries
    binaries = []
    for bin in m.all_tags_of_type(swf.tag.TagDefineBinaryData):
        i = len(binaries)
        filename = 'binary-%d.dat' % (i, )
        with open(path.join(outdir, filename), 'wb') as sf:
            sf.write(bin.data)
        binaries.append(dict(status = 'extracted',
                             id = i,
                             filesize = path.getsize(path.join(outdir, filename)),
                             filename = filename))
        
    with open(path.join(outdir, 'log.txt'), 'w') as sf:
        debug(sf, m)
    
    print 'done'
    return dict(filesize = path.getsize(input),
                parse_time = parse_time,
                sounds = sounds,
                images = images,
                binaries = binaries,
                shapes = shapes,
                log = 'log.txt',
                input = config.inputfn,
                )
