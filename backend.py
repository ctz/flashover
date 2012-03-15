
# glue
from shared import config, get_job_status, uuid
from db import db
import json
import traceback
import os.path as path
import os
import sys

import swfback

def emit_meta(dir, obj):
    with open(path.join(dir, config.metafn), 'w') as f:
        print >>f, json.dumps(obj)

def emit_exception(dir):
    with open(path.join(dir, config.errorfn), 'w') as f:
        traceback.print_exc(file = f)
        traceback.print_exc(file = sys.stderr)

def process_one(job):
    job = uuid(job)
    print 'We have job', job
    status, location = get_job_status(job)

    if status != 'awaiting':
        print 'rejected: already processed'
        return dict()

    outdir = path.join(config.outputdir, str(job))
    try:
        meta = swfback.process_file(path.join(location, config.inputfn), location)
    except Exception, e:
        emit_meta(location, dict(error = 'failed to process swf. error logged.'))
        emit_exception(location)
        meta = dict()
    else:
        emit_meta(location, dict(status = 'success', meta = meta))
    os.rename(location, outdir)
    return meta

if __name__ == '__main__':
    while True:
        try:
            txn, job = db.get_queue_head()
            meta = process_one(job)
            db.finish_job(job, meta, swfback.produce_stats(meta))
        except:
            txn.rollback()
            raise
        else:
            txn.commit()
        