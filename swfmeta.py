
from shared import config
import os.path as path
import os, sys
from cStringIO import StringIO
from time import time
import json

import swf.movie, swf.consts, swf.tag, swf.sound

# --- Metadata ---
def get_background_color(m):
    for t in m.all_tags_of_type(swf.tag.TagSetBackgroundColor):
        return dict(background_color = '%08x' % t.color)
    return dict()

def get_file_attrs(m):
    for t in m.all_tags_of_type(swf.tag.TagFileAttributes):
        return dict(
            attr_directblit = t.useDirectBlit,
            attr_usegpu = t.useGPU,
            attr_hasmeta = t.hasMetadata,
            attr_as3 = t.actionscript3,
            attr_network = t.useNetwork
        )
    return dict()
    
def get_xml_meta(m):
    return dict(
        xml_metadata = [t.xmlString for t in m.all_tags_of_type(swf.tag.TagMetadata)]
    )

def get_product_data(m):
    for t in m.all_tags_of_type(swf.tag.TagProductInfo):
        return dict(
            prod_product = swf.consts.ProductKind.tostring(t.product),
            prod_edition = swf.consts.ProductEdition.tostring(t.edition),
            prod_version = '%d.%d.%d' % (t.majorVersion, t.minorVersion, t.build),
            prod_compiletime = t.compileTime
        )
    return dict()

def get_script_limits(m):
    for t in m.all_tags_of_type(swf.tag.TagScriptLimits):
        return dict(
            lim_maxrecurse = t.maxRecursionDepth,
            lim_timeout = t.scriptTimeoutSeconds
        )
    return dict()
    
def get_debug_id(m):
    for t in m.all_tags_of_type(swf.tag.TagDebugID):
        return dict(
            dbg_guid = t.guid.encode('hex')
        )
    return dict()

def get_protect_data(m):
    for t in m.all_tags_of_type(swf.tag.TagProtect):
        if t.password is None:
            return dict(dbg_protected = True)
        else:
            return dict(
                dbg_protected = True,
                dbg_protect_password = t.password
            )
    return dict(dbg_protected = False)

def get_debugger_data(m):
    for t in m.all_tags_of_type((swf.tag.TagEnableDebugger, swf.tag.TagEnableDebugger2)):
        return dict(
            dbg_debuggable = True,
            dbg_debug_password = t.password
        )
    return dict(dbg_debuggable = False)

def extract_metadata(m):
    r = dict(
        swf_compressed = m.header.compressed,
        swf_version = m.header.version,
        swf_tags = len(m.tags)
    )
    r.update(get_background_color(m))
    r.update(get_file_attrs(m))
    r.update(get_xml_meta(m))
    r.update(get_product_data(m))
    r.update(get_script_limits(m))
    r.update(get_debug_id(m))
    r.update(get_protect_data(m))
    r.update(get_debugger_data(m))
    return r
    
# --- Scripts ---
def extract_as2(m):
    actions = []
    for t in m.all_tags_of_type((swf.tag.TagDoAction, swf.tag.TagDoInitAction)):
        actions.append(t.actions)
    return dict(as2_actions = actions)

def extract_as3(m):
    # TODO
    return dict()
        
def extract_scripts(m):
    r = dict()
    r.update(extract_as2(m))
    r.update(extract_as3(m))
    return r
    
# --- Timeline ---
def describe_actor(act):
    if isinstance(act, swf.tag.TagDefineSprite):
        return dict(type = 'sprite', id = act.characterId)
    if isinstance(act, (swf.tag.TagDefineButton, swf.tag.TagDefineButton2)):
        return dict(type = 'button', id = act.characterId)
    if isinstance(act, swf.tag.TagDefineShape):
        return dict(type = 'shape', id = act.characterId)
    if isinstance(act, swf.tag.TagDefineText):
        return dict(type = 'text', id = act.characterId)
    else:
        return dict(type = 'unknown', realtype = str(type(act)))

def extract_timeline(m):
    def character_displayed(now, id):
        for depth, (placement_tag, character_tag) in now.iteritems():
            if placement_tag.characterId == id:
                return True
        return False
        
    i = 1
    characters = m.build_dictionary()
    char_meta = dict([(k, describe_actor(v)) for k, v in characters.items()])
    displayed_now = {}
    frames = []
    
    for tag in m.all_tags_of_type((swf.tag.DisplayListTag, swf.tag.TagShowFrame), recurse_into_sprites = False):
        if isinstance(tag, swf.tag.TagPlaceObject):
            displayed_now[tag.depth] = tag
        
        if isinstance(tag, swf.tag.TagRemoveObject):
            del displayed_now[tag.depth]
        
        if isinstance(tag, swf.tag.TagShowFrame):
            print i, displayed_now.values()
            frame = [char_meta[id.characterId] for id in displayed_now.values() if id.characterId in char_meta]
            frames.append(frame)
            i += 1
        
    r = dict(nframes = i, frames = frames)
    return r

# --- Testing ---
def wrapper(file, hdlr):
    m = swf.movie.SWF(file)
    file.close()
    file = None
    return json.loads(json.dumps(hdlr(m)))

def wrapper_metadata(file): return wrapper(file, extract_metadata)
def wrapper_scripts(file): return wrapper(file, extract_scripts)
def wrapper_timeline(file): return wrapper(file, extract_timeline)

if __name__ == '__main__':
    import glob
    for fn in glob.glob('../corpus/*.swf'):
        with file(fn, 'rb') as f:
            print fn, wrapper(f, lambda m: (extract_metadata(m), extract_scripts(m)))