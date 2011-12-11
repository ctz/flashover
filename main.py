import web
import json
import os
import os.path as path
from shared import pika, config, get_backend_queue, uuid, generate_uuid, get_job_status

urls = (
  '/(home)?', 'front',
  '/about', 'about',
  '/await/([0-9a-f-]+)', 'await',
  '/status/([0-9a-f-]+)', 'job_status',
  '/intro/([0-9a-f-]+)', 'job_intro',
  '/file-upload', 'file_upload',
)
app = web.application(urls, globals())

render = web.template.render(config.templates, base = 'base')
json = json.dumps

class front(object):
  def GET(self, *args, **kwargs):
    return render.front()

class about(object):
  def GET(self):
    return render.about()

def is_flash_file(content):
  magic = content[0:3]
  return magic in ('FWS', 'CWS')

def queue_backend(chan, job):
  chan.basic_publish(exchange = '',
                     routing_key = config.backend_queue,
                     body = str(job),
                     properties = pika.BasicProperties(content_type = 'text/plain',
                                                       delivery_mode = 2))

class file_upload(object):
  def POST(self):
    w = web.input(file = {})
    #web.header('Content-Type', 'text/json')
    
    if not is_flash_file(w.file.value):
        return json(dict(error = "Not a flash file.  Flash files must start with FWS or CWS.",
                         size = len(w.file.value)))
    
    job = generate_uuid()
    chan, count, _ = get_backend_queue()
    
    jobdir = path.join(config.inputdir, '%08d--%s' % (count, job))
    os.mkdir(jobdir, 0700)
    f = open(path.join(jobdir, config.inputfn), 'w')
    f.write(w.file.value)
    f.close()
    
    queue_backend(chan, job)
    return json(dict(job = str(job)))

class await(object):
  def GET(self, job):
    job = str(uuid(job))
    return render.await(job)

class job_status(object):
  def GET(self, job):
    #web.header('Content-Type', 'text/json')
    job = str(uuid(job))
    status, _ = get_job_status(job)
    return json(status)

class job_intro(object):
  def GET(self, job):
    #web.header('Content-Type', 'text/json')
    job = uuid(job)
    status, location = get_job_status(job)
    return json(dict(status = status, location = location))

if __name__ == '__main__':
  app.run()