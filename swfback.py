
# glue
from shared import pika, config, get_backend_queue, get_job_status, uuid
import json
import traceback
import os.path as path
import os
import sys
from cStringIO import StringIO
from time import time

# the interesting bits
import swf.movie, swf.consts, swf.tag, swf.sound
import Image

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
        if hasattr(x, 'tags'):
            debug(f, x, indent + 1)
            
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
    for i, stream in enumerate(m.collect_sound_streams()):
        if swf.sound.supported(stream):
            filename = 'soundstream-%d%s' % (i, swf.consts.AudioCodec.FileExtensions[stream[0].soundFormat])
            with open(path.join(outdir, filename), 'wb') as sf:
                swf.sound.write_stream_to_file(stream, sf)
            sounds.append(dict(status = 'extracted',
                               id = i,
                               kind = 'soundstream',
                               filesize = path.getsize(path.join(outdir, filename)),
                               mimetype = swf.consts.AudioCodec.MimeTypes[stream[0].soundFormat],
                               filename = filename))
        elif swf.sound.junk(stream):
            pass # discard junk
        else:
            sounds.append(dict(status = 'skipped',
                               id = i,
                               kind = 'soundstream',
                               reason = swf.sound.reason_unsupported(stream),
                               codec = swf.consts.AudioCodec.tostring(stream[0].soundFormat)))
    
    # sounds
    for i, sound in enumerate(m.all_tags_of_type(swf.tag.TagDefineSound)):
        if swf.sound.supported(sound):
            filename = 'sound-%d%s' % (i, swf.consts.AudioCodec.FileExtensions[sound.soundFormat])
            with open(path.join(outdir, filename), 'wb') as sf:
                swf.sound.write_sound_to_file(sound, sf)
            sounds.append(dict(status = 'extracted',
                               id = i,
                               kind = 'sound',
                               filesize = path.getsize(path.join(outdir, filename)),
                               mimetype = swf.consts.AudioCodec.MimeTypes[sound.soundFormat],
                               filename = filename))
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
    
    for i, image in enumerate(m.all_tags_of_type((swf.tag.TagDefineBitsLossless, swf.tag.TagDefineBits))):
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
                           filename = real_filename))

    # export shapes
    shapes = []
    for i, shape in enumerate(m.all_tags_of_type(swf.tag.TagDefineShape)):
        filename = 'shape-%d.svg' % (i,)
        with open(path.join(outdir, filename), 'wb') as sf:
            exporter = swf.export.SingleShapeSVGExporter()
            svg = exporter.export_single_shape(shape)
            svg.seek(0)
            sf.write(svg.read())
        shapes.append(dict(status = 'converted',
                           id = i,
                           filesize = path.getsize(path.join(outdir, filename)),
                           filename = filename))
                 
    # export binaries
    binaries = []
    for i, bin in enumerate(m.all_tags_of_type(swf.tag.TagDefineBinaryData)):
        filename = 'binary-%d.dat' % (i, )
        with open(path.join(outdir, filename), 'wb') as sf:
            sf.write(bin.data)
        binaries.append(dict(status = 'extracted',
                             id = i,
                             filesize = path.getsize(path.join(outdir, filename)),
                             filename = filename))
    
    # try svg
    svg = m.export()
    with open(path.join(outdir, 'svg.svg'), 'w') as sf:
        svg.seek(0)
        sf.write(svg.read())
        
    with open(path.join(outdir, 'log.txt'), 'w') as sf:
        debug(sf, m)
    
    print 'done'
    return dict(filesize = path.getsize(input),
                parse_time = parse_time,
                sounds = sounds,
                images = images,
                binaries = binaries,
                shapes = shapes,
                svg = 'svg.svg',
                log = 'log.txt',
                input = config.inputfn,
                )

def emit_meta(dir, obj):
    with open(path.join(dir, config.metafn), 'w') as f:
        print >>f, json.dumps(obj)

def emit_exception(dir):
    with open(path.join(dir, config.errorfn), 'w') as f:
        traceback.print_exc(file = f)
        traceback.print_exc(file = sys.stderr)

def process_one(chan, method, properties, body):
    job = uuid(body)
    print 'We have job', job
    status, location = get_job_status(job)

    if status['status'] != 'awaiting':
        print 'rejected: already processed'
        return

    outdir = path.join(config.outputdir, str(job))
    try:
        meta = process_file(path.join(location, config.inputfn), location)
    except Exception, e:
        emit_meta(location, dict(error = 'failed to process swf. error logged.'))
        emit_exception(location)
    else:
        emit_meta(location, dict(status = 'success', meta = meta))
    os.rename(location, outdir)

if __name__ == '__main__':
    chan, _, _ = get_backend_queue()
    chan.basic_consume(process_one,
                       queue = config.backend_queue,
                       no_ack = True)
    print 'Now running...'
    chan.start_consuming()