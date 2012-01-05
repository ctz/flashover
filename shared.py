import config
import pika
import glob
import json
import os.path as path
from uuid import uuid4 as generate_uuid
from uuid import UUID as uuid

def get_backend_queue():
  conn = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
  chan = conn.channel()
  x = chan.queue_declare(queue = config.backend_queue,
                         durable = True,
                         exclusive = False,
                         auto_delete = False)
  return chan, x.method.message_count, x.method.consumer_count

def get_job_status(job):
  job = str(job)
  existing = path.join(config.outputdir, job)
  if path.isdir(existing):
    return dict(status = 'ready'), existing
  outstanding = glob.glob(path.join(config.inputdir, '*--*'))
  found = [x for x in outstanding if x.endswith(job)]
  if len(found):
    outstanding.sort()
    item = found[0]
    return dict(status = 'awaiting', position = outstanding.index(item) + 1, queue = len(outstanding)), item
  else:
    return dict(status = 'unknown'), None

def get_meta(job):
  with open(path.join(config.outputdir, str(job), config.metafn), 'r') as f:
    return json.loads(f.read())

def get_file_for_job(job, fn):
  return open(path.join(config.outputdir, str(job), str(fn)), 'rb')