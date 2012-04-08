import swfback
import glob
import os, sys, shutil
import pprint
import json
path = os.path

def mustdir(d):
    if path.isdir(d):
        shutil.rmtree(d)
    if not path.isdir(d):
        os.makedirs(d)

if __name__ == '__main__':
    mustdir('testout')
    #sys.stdout = o
    for f in glob.glob('../corpus/*.swf'):
        print 'file', f
        out = path.join('testout', path.basename(f))
        mustdir(out)
        meta = swfback.process_file(f, out)
        
        o = open(path.join(out, 'meta.json'), 'w')
        json.dump(meta, o)
        o.close()