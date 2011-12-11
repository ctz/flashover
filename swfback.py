import os.path as path
import json
import random
import time
import traceback
import os
from shared import pika, config, get_backend_queue, get_job_status, uuid

def emit(dir, obj):
  with open(path.join(dir, config.metafn), 'w') as f:
    print >>f, json.dumps(obj)

def emit_exception(dir):
  with open(path.join(dir, config.errorfn), 'w') as f:
    traceback.print_exc(file = f)

def process_file(input, outdir):
  print 'we have candidate', input
  time.sleep(random.randrange(4, 15))
  print 'done'
  return dict(filesize = path.getsize(input))

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
    emit(location, dict(error = 'failed to process swf. error logged.'))
    emit_exception(location)
  else:
    emit(location, dict(status = 'success', meta = meta))
  os.rename(location, outdir)

if __name__ == '__main__':
  chan, _, _ = get_backend_queue()
  chan.basic_consume(process_one,
                     queue = config.backend_queue,
                     no_ack = True)
  print 'Now running...'
  chan.start_consuming()