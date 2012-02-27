from xml.dom.minidom import parse

def svg_thumb(svg, dimension):
    svgdoc = parse(svg)
    dim = '%dpx' % dimension
    svgdoc.documentElement.attributes['width'] = dim
    svgdoc.documentElement.attributes['height'] = dim
    svgdoc.documentElement.attributes['preserveAspectRatio'] = 'xMinYMin meet'
    return svgdoc.toxml(encoding = 'UTF-8')