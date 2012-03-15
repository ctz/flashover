import config
import glob
import json
import web
import os
import os.path as path
from fnmatch import fnmatch
from uuid import uuid4 as generate_uuid
from uuid import UUID as uuid
    
def get_job_status(job):
    job = str(job)
    existing = path.join(config.outputdir, job)
    if path.isdir(existing):
        return 'ready', existing
    
    outstanding = path.join(config.inputdir, job)
    if path.isdir(outstanding):
        return 'awaiting', outstanding
    
    return 'unknown', None

def get_meta(job):
    try:
        with open(path.join(config.outputdir, str(job), config.metafn), 'r') as f:
            return json.loads(f.read())
    except IOError:
        raise web.NotFound()

def get_file_for_job(job, fn):
    return open(path.join(config.outputdir, str(job), str(fn)), 'rb')

def is_flash_file(content):
    magic = content[0:3]
    return magic in ('FWS', 'CWS')
