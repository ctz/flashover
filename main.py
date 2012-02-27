import web
import json
import os
import os.path as path
from traceback import format_exc
from shared import config, get_backend_queue, uuid, generate_uuid, get_job_status, get_meta, get_file_for_job, is_flash_file, queue_backend
import formatting
import svgthumb
import Image
from StringIO import StringIO

urls = (
    '/(home)?', 'front',
    '/about', 'about',
    '/await/([0-9a-f-]+)', 'await',
    '/status/([0-9a-f-]+)', 'job_status',
    '/results/([0-9a-f-]+)', 'job_intro',
    '/file-upload', 'file_upload',
    '/image/([0-9a-f-]+)/(\d+)', 'image_details',
    '/image-thumb/([0-9a-f-]+)/(\d+)/(\d+)', 'image_thumb',
    '/image-thumb-svg/([0-9a-f-]+)/(\d+)/(\d+)', 'svg_thumb',
    '/image-svg/([0-9a-f-]+)/(\d+)/(\d+)', 'svg_raw',
    '/image-raw/([0-9a-f-]+)/(\d+)', 'image_raw',
    '/bin-raw/([0-9a-f-]+)/(\d+)', 'bin_raw',
    '/sound-raw/([0-9a-f-]+)/(\d+)', 'sound_raw',
    '/input-file/([0-9a-f-]+)', 'input_file_raw',
    '/log/([0-9a-f-]+)', 'log_raw',
    '/svg/([0-9a-f-]+)', 'svg_full_raw',
)
app = web.application(urls, globals())

render = web.template.render(config.templates, base = 'base', globals = formatting.exports)
json = json.dumps
debug = True

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
            if debug:
                raise e
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

class file_upload(base_json):
    methods = set(['POST'])
    
    def process(self):
        w = web.input(file = {})
        
        if not is_flash_file(w.file.value):
            return json(dict(error = "Not a flash file.  Flash files must start with FWS or CWS.",
                             size = len(w.file.value)))
        
        job = generate_uuid()
        chan, count, _ = get_backend_queue()
        
        jobdir = path.join(config.inputdir, '%08d--%s' % (count, job))
        os.mkdir(jobdir, 0700)
        with open(path.join(jobdir, config.inputfn), 'wb') as f:
            f.write(w.file.value)
        
        queue_backend(chan, job)
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
        return json(status)

class job_intro(base_html):
    def process(self, job):
        job = uuid(job)
        status, location = get_job_status(job)
        meta = get_meta(job)
        if 'error' in meta:
            return render.failed(meta['error'])
        else:
            return render.intro(job = job, status = status, meta = meta['meta'])

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
    
class svg_thumb(object):
  def GET(self, job, id, px):
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
        return f.read()

class image_raw(object):
    def GET(self, job, id):
        return serve_binary(job, lambda meta: meta['images'][int(id)]['filename'])

class bin_raw(object):
    def GET(self, job, id):
        return serve_binary(job, lambda meta: meta['binaries'][int(id)]['filename'])
        
class sound_raw(object):
    def GET(self, job, id):
        return serve_binary(job, lambda meta: meta['sounds'][int(id)]['filename'],
                            mimetype = lambda meta: meta['sounds'][int(id)]['mimetype'])

class svg_full_raw(object):
    def GET(self, job):
        return serve_binary(job, lambda meta: meta['svg'], mimetype = 'image/svg+xml')

class svg_raw(object):
    def GET(self, job, id):
        return serve_binary(job, lambda meta: meta['shapes'][int(id)]['filename'], mimetype = 'image/svg+xml')

class log_raw(object):
    def GET(self, job):
        return serve_binary(job, lambda meta: meta['log'], mimetype = 'text/plain')

class input_file_raw(object):
    def GET(self, job):
        return serve_binary(job, lambda meta: meta['input'], mimetype = 'application/x-shockwave-flash')
        
class image_details(object):
    def GET(self, job, id):
        job = uuid(job)
        id = int(id)
        meta = get_meta(job)['meta']
        imgmeta = meta['images'][id]
        with get_file_for_job(job, imgmeta['filename']) as f:
            im = Image.open(f)
            imgdata = dict(dims = im.size, mode = im.mode, format = im.format)
        return render.imageinfo(job = job, meta = imgmeta, img = imgdata)
    
if __name__ == '__main__':
  app.run()