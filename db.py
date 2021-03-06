import web
from config import db_db, db_user, db_pass
import time

JOB_LIFETIME = 2

def now():
    return int(time.time())
def hours_ago(n):
    return now() - (n * 60 * 60)
def hours_hence(n):
    return hours_ago(-n)
def years_hence(n):
    return hours_hence(365 * 24 * n)

class dba(object):
    QUEUE_ORDERING = 'priority DESC, timestamp ASC'
    
    def __init__(self):
        self.conn = web.database(dbn = 'mysql', db = db_db, user = db_user, pw = db_pass)
        
    def get_queue_head(self):
        results = self.conn.select('incoming', order = dba.QUEUE_ORDERING, limit = 1)
        if len(results):
            r = results[0]
            return self.conn.transaction(), r['guid'], r['fetchurl']
        else:
            return None, None, None
            
    def queue_position(self, job):
        jobs = self.conn.select('incoming', order = dba.QUEUE_ORDERING)
        jobs = list(jobs)
        found = [x for x in jobs if x.guid == job]
        if len(found):
            return dict(position = jobs.index(found[0]) + 1, queue = len(jobs))
        else:
            return dict(position = len(jobs), queue = len(jobs))
            
    def queue_job(self, job, uid = 0, priority = 100, fetchurl = None):
        self.conn.insert('incoming',
                         guid = str(job),
                         timestamp = now(),
                         priority = priority,
                         user = uid,
                         fetchurl = fetchurl)
    
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
                         timestamp = now(),
                         expires = hours_hence(JOB_LIFETIME),
                         waittime = int(now() - found['timestamp']),
                         alias = '',
                         **stats)
    
    def get_completed(self, job):
        rows = self.conn.select('completed', where = 'guid = $job', vars = dict(job = str(job)), limit = 1)
        if len(rows):
            return rows[0]
        else:
            raise ValueError('completed table missing completed job row')

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
        return self.get_stats(cutoff = hours_ago(24))

    def get_stats_2hr(self):
        return self.get_stats(cutoff = hours_ago(2))
    
    def get_cleanable(self):
        rows = self.conn.select('completed', where = 'cleaned = 0 and expires < $cutoff', what = 'guid', vars = dict(cutoff = now()))
        return [j['guid'] for j in rows]
        
    def set_cleaned(self, job):
        self.conn.update('completed', where = 'guid = $guid', cleaned = 1, vars = dict(guid = str(job)))
    
    def dealias(self, alias):
        rows = self.conn.select('completed', where = 'alias = $alias', what = 'guid', vars = dict(alias = alias))
        rows = list(rows)
        if len(rows):
            return rows[0]['guid']
        else:
            return None
    
    def expire_alias(self, alias):
        assert len(alias) != 0
        self.conn.update('completed', where = 'alias = $alias', expires = now(), alias = '', vars = dict(alias = alias))
    
    def set_alias(self, alias, job):
        self.conn.update('completed', where = 'guid = $guid', alias = alias, vars = dict(guid = str(job)))
        
    def never_expire(self, job):
        self.conn.update('completed', where = 'guid = $guid', expires = years_hence(10), vars = dict(guid = str(job)))
    
db = dba()
