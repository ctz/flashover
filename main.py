import web
import json
import os
import os.path as path
from traceback import format_exc
from shared import config, uuid, generate_uuid, get_job_status, get_meta, get_file_for_job, is_flash_file
from db import db
import formatting
import svgthumb
import Image
from StringIO import StringIO

job = '([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
id = '(\d+)'
sz = '(\d+)'

urls = (
    '/(home)?', 'front',
    '/about', 'about',
    '/api', 'api',
    '/stats', 'stats',
    '/await/' + job, 'await',
    '/status/' + job, 'job_status',
    '/results/' + job, 'job_intro',
    '/file-upload', 'file_upload',
    '/image/' + job + '/' + id, 'image_details',
    '/shape/' + job + '/' + id, 'shape_details',
    '/image-thumb/' + job + '/' + id + '/' + sz, 'image_thumb',
    '/image-thumb-svg/' + job + '/' + id + '/' + sz, 'svg_thumb',
    '/image-svg/' + job + '/' + id, 'svg_raw',
    '/image-raw/' + job + '/' + id, 'image_raw',
    '/bin-raw/' + job + '/' + id, 'bin_raw',
    '/sound-raw/' + job + '/' + id, 'sound_raw',
    '/input-file/' + job, 'input_file_raw',
    '/shapes/' + job, 'job_shapes',
    '/images/' + job, 'job_images',
    '/sounds/' + job, 'job_sounds',
    '/binaries/' + job, 'job_binaries',
    '/log/' + job, 'log_raw',
    '/svg/' + job, 'svg_full_raw',
)
app = web.application(urls, globals())

render = web.template.render(config.templates, base = 'base', globals = formatting.exports)
part_render = web.template.render(config.templates, globals = formatting.exports)
json = json.dumps
web.config.debug = True

class base_page(object):
    """
    Basic content-type-non-specific error handling.
    """
    methods = set(['GET'])

    def GET(self, *args, **kwargs):
        if 'GET' not in self.methods:
            raise web.NoMethod('GET not supported here')
        try:
            return self.process(*args, **kwargs)
        except Exception, e:
            if web.config.debug:
                raise
            else:
                return self.error(e)

    def POST(self, *args, **kwargs):
        if 'POST' not in self.methods:
            raise web.NoMethod('POST not supported here')
        try:
            return self.process(*args, **kwargs)
        except Exception, e:
            return self.error(e)

class base_html(base_page):
    """
    Base for pages wanting HTML error handling.
    """
    @staticmethod
    def error(err):
        return render.error(error = err, trace = format_exc(err))

class base_image(base_page):
    """
    Base for pages wanting image error handling.
    """
    @staticmethod
    def error(err):
        web.header('Content-Type', 'image/png')
        web.header('X-Error-Message', str(err))
        for i, l in enumerate(format_exc(err).splitlines()):
            web.header('X-Traceback-%d' % i, l)
            
        with open('static/error.png', 'rb') as f:
            return f.read()

class base_json(base_page):
    """
    Base for pages wanting JSON error handling.
    """
    @staticmethod
    def error(err):
        web.header('Content-Type', 'text/json')
        return json(dict(error = str(err)))

class front(base_html):
    def process(self, *args, **kwargs):
        return render.front()

class about(base_html):
    def process(self):
        return render.about()

class api(base_html):
    def process(self):
        return render.api()

class stats(base_html):
    def process(self):
        return render.stats(stats24hr = db.get_stats_24hr(),
                            stats2hr = db.get_stats_2hr(),
                            statsall = db.get_stats())

class file_upload(base_json):
    methods = set(['POST'])
    
    def process(self):
        w = web.input(file = {})
        
        if not is_flash_file(w.file.value):
            return json(dict(error = "Not a flash file.  Flash files must start with FWS or CWS.",
                             size = len(w.file.value)))
        
        job = generate_uuid()        
        jobdir = path.join(config.inputdir, str(job))
        os.mkdir(jobdir, 0700)
        with open(path.join(jobdir, config.inputfn), 'wb') as f:
            f.write(w.file.value)
        
        db.queue_job(job)
        return json(dict(job = str(job)))

class await(base_html):
    def process(self, job):
        job = str(uuid(job))
        return render.await(job)

class job_status(base_json):
    def process(self, job):
        web.header('Content-Type', 'text/json')
        job = str(uuid(job))
        status, _ = get_job_status(job)
        
        if status == 'awaiting':
            return json(dict(status = status, **db.queue_position(job)))
        else:
            return json(dict(status = status))

class job_base(base_html):
    def process(self, job):
        job = uuid(job)
        status, location = get_job_status(job)
        meta = get_meta(job)
        stats = db.get_completed(job)
        if 'error' in meta:
            return render.failed(meta['error'], str(job))
        else:
            sidebar = part_render.part_sidebar(current = self.WHERE, job = job, status = status, meta = meta['meta'], stats = stats)
            return getattr(render, self.WHERE)(sidebar = sidebar, job = job, status = status, meta = meta['meta'], stats = stats)

class job_item_base(base_html):
    def process(self, job, id):
        job = uuid(job)
        id = int(id)
        status, location = get_job_status(job)
        meta = get_meta(job)
        stats = db.get_completed(job)
        if 'error' in meta:
            return render.failed(meta['error'], str(job))
        itemmeta = meta['meta'][self.WHERE][id]
        sidebar = part_render.part_sidebar(current = self.WHERE, job = job, status = status, meta = meta['meta'], stats = stats)
        return getattr(render, self.WHERE + '_details')(sidebar = sidebar, job = job, meta = itemmeta)
            
class job_intro(job_base):
    WHERE = 'intro'
    
class job_shapes(job_base):
    WHERE = 'shapes'
    
class job_images(job_base):
    WHERE = 'images'
    
class job_sounds(job_base):
    WHERE = 'sounds'
    
class job_binaries(job_base):
    WHERE = 'binaries'

class image_details(job_item_base):
    WHERE = 'images'

class shape_details(job_item_base):
    WHERE = 'shapes'

class image_thumb(base_image):
    def process(self, job, id, px):
        web.header('Content-Type', 'application/octet-stream')
        job = uuid(job)
        meta = get_meta(job)['meta']
        img = meta['images'][int(id)]
        with get_file_for_job(job, img['filename']) as f:
            im = Image.open(f)
            im.load()
        im.thumbnail([int(px)] * 2, Image.ANTIALIAS)
        s = StringIO()
        im.save(s, 'PNG')
        return s.getvalue()
    
class svg_thumb(base_image):
  def process(self, job, id, px):
    job = uuid(job)
    meta = get_meta(job)['meta']
    shp = meta['shapes'][int(id)]
    with get_file_for_job(job, shp['filename']) as f:
      web.header('Content-Type', 'image/svg+xml')
      return svgthumb.svg_thumb(f, int(px))

def serve_binary(job, chooser, mimetype = 'application/octet-stream'):
    job = uuid(job)
    meta = get_meta(job)['meta']
    name = chooser(meta)
    
    if callable(mimetype):
        web.header('Content-Type', mimetype(meta))
    else:
        web.header('Content-Type', mimetype)
    web.header('Content-Disposition', 'inline; filename=' + name)
    with get_file_for_job(job, name) as f:
        f.seek(0, os.SEEK_END)
        web.header('Content-Length', str(f.tell()))
        f.seek(0)
        return f.read()

class image_raw(base_image):
    def process(self, job, id):
        return serve_binary(job, lambda meta: meta['images'][int(id)]['filename'])

class bin_raw(base_image):
    def process(self, job, id):
        return serve_binary(job, lambda meta: meta['binaries'][int(id)]['filename'])
        
class sound_raw(base_image):
    def process(self, job, id):
        return serve_binary(job, lambda meta: meta['sounds'][int(id)]['filename'],
                            mimetype = lambda meta: meta['sounds'][int(id)]['mimetype'])

class svg_full_raw(base_image):
    def process(self, job):
        return serve_binary(job, lambda meta: meta['svg'], mimetype = 'image/svg+xml')

class svg_raw(base_image):
    def process(self, job, id):
        return serve_binary(job, lambda meta: meta['shapes'][int(id)]['filename'], mimetype = 'image/svg+xml')

class log_raw(base_image):
    def process(self, job):
        return serve_binary(job, lambda meta: meta['log'], mimetype = 'text/plain')

class input_file_raw(base_image):
    def process(self, job):
        return serve_binary(job, lambda meta: meta['input'], mimetype = 'application/x-shockwave-flash')

    
if __name__ == '__main__':
  app.run()