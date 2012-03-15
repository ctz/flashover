import web
from config import db_db, db_user, db_pass
import time

class dba(object):
    QUEUE_ORDERING = 'priority DESC, timestamp ASC'
    
    def __init__(self):
        self.conn = web.database(dbn = 'mysql', db = db_db, user = db_user, pw = db_pass)
        
    def get_queue_head(self):
        while True:
            results = self.conn.select('incoming', order = dba.QUEUE_ORDERING, limit = 1)
            if len(results):
                return self.conn.transaction(), results[0]['guid']
            time.sleep(2)
            
    def queue_position(self, job):
        jobs = self.conn.select('incoming', order = dba.QUEUE_ORDERING)
        jobs = list(jobs)
        found = [x for x in jobs if x.guid == job]
        if len(found):
            return dict(position = jobs.index(found[0]) + 1, queue = len(jobs))
        else:
            return dict(position = len(jobs), queue = len(jobs))
            
    def queue_job(self, job, uid = 0, priority = 100):
        self.conn.insert('incoming',
                         guid = str(job),
                         timestamp = time.time(),
                         priority = priority,
                         user = uid)
    
    def finish_job(self, job, meta, stats):
        vars = dict(guid = str(job))
        found = self.conn.select('incoming', where = 'guid = $guid', vars = vars)
        if len(found) == 0:
            return
        found = found[0]
        self.conn.delete('incoming', where = 'guid = $guid', vars = vars)
        self.conn.insert('completed',
                         guid = found['guid'],
                         cleaned = 0,
                         user = found['user'],
                         timestamp = int(time.time()),
                         waittime = int(time.time() - found['timestamp']),
                         **stats)
    
    def get_completed(self, job):
        return self.conn.select('completed', where = 'guid = $job', vars = dict(job = str(job)), limit = 1)[0]

    def get_stats(self, cutoff = 0):
        cols = """
        COALESCE(SUM(c_images), 0) as c_images,
        COALESCE(SUM(c_binaries), 0) as c_binaries,
        COALESCE(SUM(c_sounds), 0) as c_sounds,
        COALESCE(SUM(c_shapes), 0) as c_shapes,
        
        COALESCE(SUM(sz_images), 0) as sz_images,
        COALESCE(SUM(sz_binaries), 0) as sz_binaries,
        COALESCE(SUM(sz_sounds), 0) as sz_sounds,
        COALESCE(SUM(sz_shapes), 0) as sz_shapes,
        
        COALESCE(SUM(sz_input), 0) as sz_input,
        COALESCE(SUM(cputime), 0) as cputime,
        COALESCE(SUM(waittime), 0) as waittime,
        COUNT(*) as count
        """
    
        rows = self.conn.select('completed',
                                what = cols,
                                where = 'timestamp > $cutoff',
                                vars = locals())
        return rows[0]

    def get_stats_24hr(self):
        return self.get_stats(cutoff = time.time() - (24 * 60 * 60))

    def get_stats_2hr(self):
        return self.get_stats(cutoff = time.time() - (2 * 60 * 60))
        
db = dba()
