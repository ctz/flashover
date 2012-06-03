from db import db
import shared
import sys
import shutil
import os.path as path
import time

def submit(filename):
    job, jobdir = shared.setup_job()
    shutil.copy(filename, path.join(jobdir, shared.config.inputfn))
    db.queue_job(job)
    return job

def await(job):
    while True:
        print 'awaiting job', job, '...'
        status, dir = shared.get_job_status(job)
        if status != 'awaiting':
            print 'finished with status', status
            return status
        time.sleep(3)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print 'usage: %s <alias> <filename>' % (sys.argv[0])
        exit(1)
    
    _, alias, filename = sys.argv
    print 'processing', filename, '...'
    job = submit(filename)
    assert 'ready' == await(job)
    db.expire_alias(alias)
    db.set_alias(alias, job)
    db.never_expire(job)
    print 'done.'
    