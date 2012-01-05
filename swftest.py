import swfback
import glob
import os, sys
import pprint
path = os.path

def mustdir(d):
    if not path.isdir(d):
        os.makedirs(d)

if __name__ == '__main__':
    mustdir('testout')
    o = open('test.txt', 'w')
    sys.stdout = o
    for f in glob.glob('../corpus/*.swf'):
        if 'subscribe' not in f: continue
        print 'file', f
        out = path.join('testout', path.basename(f))
        mustdir(out)
        meta = swfback.process_file(f, out)
        pprint.pprint(meta, stream = o)