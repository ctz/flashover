import swfback
import glob
import os, sys, shutil
import pprint
path = os.path

def mustdir(d):
    if path.isdir(d):
        shutil.rmtree(d)
    if not path.isdir(d):
        os.makedirs(d)

if __name__ == '__main__':
    mustdir('testout')
    o = open('test.txt', 'w')
    #sys.stdout = o
    for f in glob.glob('../corpus/*.swf'):
        if 'apollo' not in f: continue
        print 'file', f
        out = path.join('testout', path.basename(f))
        mustdir(out)
        meta = swfback.process_file(f, out)
        pprint.pprint(meta, stream = o)