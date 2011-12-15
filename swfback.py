
# glue
from shared import pika, config, get_backend_queue, get_job_status, uuid
import json
import traceback
import os.path as path
import os
from time import time

# the interesting bits
import swf.movie, swf.consts, swf.tag, swf.sound
import Image

def output_image(img, outf):
    if hasattr(img, 'bitmapAlphaData'):
        img.bitmapAlphaData.seek(0)
        img.bitmapData.seek(0)
        opaque = Image.open(img.bitmapData)
        alpha = Image.fromstring('L', opaque.size, img.bitmapAlphaData.read())
        opaque.putalpha(alpha)
        opaque.save(outf)
    else:
        Image.open(img.bitmapData).save(outf)

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
        if swf.sound.supported_stream(stream):
            filename = 'soundstream-%d%s' % (i, swf.consts.AudioCodec.FileExtensions[stream[0].soundFormat])
            with open(path.join(outdir, filename), 'wb') as sf:
                swf.sound.write_stream_to_file(stream, sf)
            sounds.append(dict(status = 'extracted',
                               id = i,
                               filename = filename))
        else:
            sounds.append(dict(status = 'skipped',
                               id = i,
                               kind = swf.consts.AudioCodec.tostring(stream[0].soundFormat)))
    
    # sounds
    for i, sound in enumerate(m.all_tags_of_type(swf.tag.TagDefineSound)):
        if swf.sound.supported_tag(sound):
            filename = 'sound-%d%s' % (i, swf.consts.AudioCodec.FileExtensions[sound.soundFormat])
            with open(path.join(outdir, filename), 'wb') as sf:
                swf.sound.write_sound_to_file(sound, sf)
            sounds.append(dict(status = 'extracted',
                               id = i,
                               filename = filename))
        else:
            sounds.append(dict(status = 'skipped',
                               id = i,
                               kind = swf.consts.AudioCodec.tostring(sound.soundFormat)))
    
    # export images
    images = []
    
    for i, image in enumerate(m.all_tags_of_type((swf.tag.TagDefineBits, swf.tag.TagDefineBitsLossless))):
        filename = 'image-%d%s' % (i, swf.consts.BitmapType.FileExtensions[image.bitmapType])
        with open(path.join(outdir, filename), 'wb') as sf:
            output_image(image, sf)
        images.append(dict(status = 'extracted',
                           id = i,
                           filename = filename))
    
    print 'done'
    return dict(filesize = path.getsize(input),
                parse_time = parse_time,
                sounds = sounds,
                images = images,
                )

def emit_meta(dir, obj):
    with open(path.join(dir, config.metafn), 'w') as f:
        print >>f, json.dumps(obj)

def emit_exception(dir):
    with open(path.join(dir, config.errorfn), 'w') as f:
        traceback.print_exc(file = f)

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