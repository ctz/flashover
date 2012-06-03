import web
import json
import os
import os.path as path
from traceback import format_exc
from shared import config, uuid, get_job_status, get_meta, get_file_for_job, is_flash_file, setup_job
from db import db
import urlparse
import formatting
import svgthumb
import Image
from StringIO import StringIO

job_re = '([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
id_re = '(\d+)'
sz_re = '(\d+)'
alias_re = '([^/]+)'
action_re = '([^/]+)'
remainder_re = '(.*)'

urls = (
    # top-level
    '/(home)?', 'front',
    '/about', 'about',
    '/api', 'api',
    '/stats', 'stats',
    '/tour', 'tour',
    
    # submission
    '/file-upload-json', 'file_upload_json',
    '/file-upload', 'file_upload_html',
    '/bookmarklet-target', 'start_fetch',
    '/file-fetch', 'start_fetch',
    
    # usage flow
    '/await/' + job_re, 'await',
    '/status/' + job_re, 'job_status',
    '/alias/' + alias_re + '/' + action_re + '/?' + remainder_re, 'job_dealias',
    '/results/' + job_re, 'job_intro',
    '/results-json/' + job_re, 'job_intro_json',
    
    # fetching assets
    '/image-svg/' + job_re + '/' + id_re, 'svg_raw',
    '/image-thumb-svg/' + job_re + '/' + id_re + '/' + sz_re, 'svg_thumb',
    
    '/image-raw/' + job_re + '/' + id_re, 'image_raw',
    '/image-thumb/' + job_re + '/' + id_re + '/' + sz_re, 'image_thumb',
    
    '/bin-raw/' + job_re + '/' + id_re, 'bin_raw',
    '/sound-raw/' + job_re + '/' + id_re, 'sound_raw',
    '/input-file/' + job_re, 'input_file_raw',
    
    # web frontend
    '/shapes/' + job_re, 'job_shapes',
    '/shape/' + job_re + '/' + id_re, 'shape_details',
    
    '/images/' + job_re, 'job_images',
    '/image/' + job_re + '/' + id_re, 'image_details',
    
    '/sounds/' + job_re, 'job_sounds',
    '/binaries/' + job_re, 'job_binaries',
    '/metadata/' + job_re, 'job_metadata',
    '/timeline/' + job_re, 'job_timeline',
    
    # debug
    '/log/' + job_re, 'log_raw',
    '/svg/' + job_re, 'svg_full_raw',
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
    
    def process(self, *args, **kwargs):
        raise NotImplementedError()

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

class tour(base_html):
    def process(self):
        return render.tour()

class stats(base_html):
    def process(self):
        return render.stats(stats24hr = db.get_stats_24hr(),
                            stats2hr = db.get_stats_2hr(),
                            statsall = db.get_stats())

def correct_url(s):
    try:
        url = urlparse.urlparse(s, 'http', allow_fragments = False)
        if url.scheme != 'http':
            return None
        if '.' not in url.netloc:
            return None
        return urlparse.urlunparse(url)
    except Exception, e:
        return None

class start_fetch(base_html):
    def process(self):
        w = web.input(url = None)
        if w.url is None:
            raise web.NotAcceptable('We need a URL parameter')
        url = correct_url(w.url)
        if url is None:
            raise web.NotAcceptable('URL parameter is invalid')
        job, _ = setup_job()
        db.queue_job(job, fetchurl = w.url)
        raise web.seeother('/await/' + str(job))

class file_upload_base(object):
    methods = set(['POST'])
    
    def process(self):
        w = web.input(file = {})
        
        value = w.file.file.read()
        
        if not is_flash_file(value):
            import hashlib
            return False, "Not a flash file.  Flash files must start with FWS or CWS. File size was %d bytes (hash %s)." % (len(value), hashlib.md5(value).hexdigest())
        
        job, jobdir = setup_job()
        with open(path.join(jobdir, config.inputfn), 'wb') as f:
            f.write(value)
        
        db.queue_job(job)
        return True, str(job)

class file_upload_json(file_upload_base, base_json):
    def process(self):
        worked, res = file_upload_base.process(self)
        if worked:
            return json(dict(job = str(res)))
        else:
            return json(dict(error = res))

class file_upload_html(file_upload_base, base_html):
    def process(self):
        worked, res = file_upload_base.process(self)
        if worked:
            return render.await(res)
        else:
            raise ValueError, res

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

class job_dealias(base_html):
    def process(self, alias, which, extra = ''):
        job = db.dealias(alias)
        if job is None:
            raise web.NotFound()
        raise web.seeother('/%s/%s%s' % (which, job, extra))

class job_intro_json(base_json):
    def process(self, job):
        web.header('Content-Type', 'text/json')
        job = str(uuid(job))
        return json(get_meta(job))

class job_base(base_html):
    WHERE = None
    
    def process(self, job):
        job = uuid(job)
        meta = get_meta(job)
        if 'error' in meta:
            return render.failed(meta['error'], str(job))
        else:
            stats = db.get_completed(job)
            sidebar = part_render.part_sidebar(current = self.WHERE, job = job, meta = meta['meta'], stats = stats)
            args = self.get_template_args(job, meta)
            return getattr(render, self.WHERE)(sidebar = sidebar, job = job, **args)
    
    def get_template_args(self, job, meta):
        return dict(meta = meta['meta'])

class job_item_base(base_html):
    WHERE = None
    
    def process(self, job, id):
        job = uuid(job)
        id = int(id)
        meta = get_meta(job)
        stats = db.get_completed(job)
        if 'error' in meta:
            return render.failed(meta['error'], str(job))
        itemmeta = self.get_template_args(job, meta, id)
        sidebar = part_render.part_sidebar(current = self.WHERE, job = job, meta = meta['meta'], stats = stats)
        return getattr(render, self.WHERE + '_details')(sidebar = sidebar, job = job, **itemmeta)
    
    def get_template_args(self, job, meta, id):
        items_of_type = dict(meta['meta'][self.WHERE])
        return dict(meta = items_of_type[id])
            
class job_intro(job_base):
    WHERE = 'results'
    
class job_shapes(job_base):
    WHERE = 'shapes'
    
class job_images(job_base):
    WHERE = 'images'
    
class job_sounds(job_base):
    WHERE = 'sounds'
    
class job_binaries(job_base):
    WHERE = 'binaries'

class job_metadata(job_base):
    WHERE = 'metadata'
    def get_template_args(self, job, meta):
        return dict(metadata = meta['meta']['metadata'])

class job_timeline(job_base):
    WHERE = 'timeline'
    def get_template_args(self, job, meta):
        return dict(timeline = meta['meta']['timeline'])

class image_details(job_item_base):
    WHERE = 'images'

class shape_details(job_item_base):
    WHERE = 'shapes'

class image_thumb(base_image):
    def process(self, job, id, px):
        web.header('Content-Type', 'application/octet-stream')
        job = uuid(job)
        meta = get_meta(job)['meta']
        img = dict(meta['images'])[int(id)]
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
    shp = dict(meta['shapes'])[int(id)]
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
        return serve_binary(job, lambda meta: dict(meta['images'])[int(id)]['filename'])

class bin_raw(base_image):
    def process(self, job, id):
        return serve_binary(job, lambda meta: dict(meta['binaries'])[int(id)]['filename'],
                            mimetype = lambda meta: dict(meta['binaries'])[int(id)]['mimetype'])
        
class sound_raw(base_image):
    def process(self, job, id):
        return serve_binary(job, lambda meta: dict(meta['sounds'])[int(id)]['filename'],
                            mimetype = lambda meta: dict(meta['sounds'])[int(id)]['mimetype'])

class svg_full_raw(base_image):
    def process(self, job):
        return serve_binary(job, lambda meta: meta['svg'], mimetype = 'image/svg+xml')

class svg_raw(base_image):
    def process(self, job, id):
        return serve_binary(job, lambda meta: dict(meta['shapes'])[int(id)]['filename'], mimetype = 'image/svg+xml')

class log_raw(base_image):
    def process(self, job):
        return serve_binary(job, lambda meta: meta['log'], mimetype = 'text/plain')

class input_file_raw(base_image):
    def process(self, job):
        return serve_binary(job, lambda meta: config.inputfn, mimetype = 'application/x-shockwave-flash')
    
if __name__ == '__main__':
    if os.name == 'nt':
        app.run()
    else:
        app.wsgifunc()