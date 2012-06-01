
# glue
from shared import config, get_job_status, uuid
from db import db
import json
import traceback
import os.path as path
import os
import shutil
import sys
import time
import optparse

import swfback
import urllib

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
        emit_meta(location, dict(error = 'Failed to process swf'))
        emit_exception(location)
        meta = dict()
    else:
        emit_meta(location, dict(status = 'success', meta = meta))
    os.rename(location, outdir)
    return meta

def process_fetch(job, fetchurl):
    outdir = path.join(config.outputdir, str(job))
    try:
        _, location = get_job_status(job)
        urllib.urlretrieve(fetchurl, path.join(location, config.inputfn))
        return True
    except Exception, e:
        emit_meta(location, dict(error = 'Failed to fetch swf'))
        emit_exception(location)
        os.rename(location, outdir)
        return False
    
def handle_queue_head(txn, job, fetchurl):
    if txn is None:
        return
    if fetchurl is not None:
        if not process_fetch(job, fetchurl):
            db.finish_job(job, dict(), swfback.produce_stats(dict()))
            return
    meta = process_one(job)
    db.finish_job(job, meta, swfback.produce_stats(meta))

def check_queue():
    txn = None
    try:
        txn, job, fetchurl = db.get_queue_head()
        handle_queue_head(txn, job, fetchurl)
    except:
        if txn:
            txn.rollback()
        raise
    else:
        if txn:
            txn.commit()

def clean(job):
    outdir = path.join(config.outputdir, str(job))
    if path.isdir(outdir):
        open(path.join(outdir, '.clean'), 'w').close()  # leave a marker in case it fails right now
        shutil.rmtree(outdir, ignore_errors = 1)

def check_clean():
    for job in db.get_cleanable():
        clean(job)
        db.set_cleaned(job)

if __name__ == '__main__':    
    op = optparse.OptionParser()
    op.add_option('-p', '--pidfile', help = 'write PID to PIDFILE', default = './flashover.pid')
    options, args = op.parse_args()
    
    try:
        with open(options.pidfile, 'w') as f:
            print >>f, os.getpid()
        while True:
            check_queue()
            check_clean()
            time.sleep(2)
    finally:
        try:
            os.unlink(options.pidfile)
        except:
            pass