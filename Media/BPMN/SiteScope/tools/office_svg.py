"""Make an SVG safe for PowerPoint: inline <use> references and draw arrowhead markers as plain geometry.

usage: python3 office_svg.py in.svg out.svg
"""
import math, re, sys
from lxml import etree

SVG = "http://www.w3.org/2000/svg"
NUM = re.compile(r"-?\d+(?:\.\d+)?")


def end_points(d, at_end=True):
    pts = [float(n) for n in NUM.findall(d)]
    pts = list(zip(pts[0::2], pts[1::2]))
    if not at_end:
        pts = pts[::-1]
    a, b = pts[-2], pts[-1]
    return b, math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def stroke_width(style):
    m = re.search(r"stroke-width:\s*([\d.]+)", style or "")
    return float(m.group(1)) if m else 1.0


def inline_uses(root):
    """Replace every <use> with a copy of what it references (Office ignores some <use> forms)."""
    XL = "{http://www.w3.org/1999/xlink}href"
    USE = "{%s}use" % SVG
    ids = {e.get("id"): e for e in root.iter() if isinstance(e.tag, str) and e.get("id")}

    def resolved(el, seen=()):
        """Deep copy of el with its own <use> elements expanded."""
        out = etree.fromstring(etree.tostring(el))
        out.tail = None
        for e in out.iter():
            if isinstance(e.tag, str):
                e.attrib.pop("id", None)
        if out.tag == USE:   # a reference to another reference
            wrap = etree.Element("{%s}g" % SVG); wrap.append(out); out = wrap
        for u in list(out.iter(USE)):
            expand(u, seen)
        return out

    def expand(u, seen=()):
        key = (u.get(XL) or u.get("href") or "#")[1:]
        ref = ids.get(key)
        if ref is None or key in seen:   # dangling reference: browsers draw nothing for it
            u.getparent().remove(u)
            return
        g = etree.Element("{%s}g" % SVG)
        tf = (u.get("transform") or "") + " translate(%s,%s)" % (u.get("x", "0"), u.get("y", "0"))
        g.set("transform", tf.strip())
        for k, v in u.attrib.items():
            if k not in (XL, "href", "transform", "x", "y", "width", "height"):
                g.set(k, v)
        body = resolved(ref, seen + (key,))
        if etree.QName(body).localname == "symbol":
            g.extend(list(body))
        else:
            g.append(body)
        g.tail = u.tail
        u.getparent().replace(u, g)

    defs = set(root.iter("{%s}defs" % SVG))
    for u in list(root.iter(USE)):
        if not any(a in defs for a in u.iterancestors()):
            expand(u)
    for d in list(root.iter("{%s}defs" % SVG)):
        if not any(etree.QName(e).localname in ("marker", "clipPath", "linearGradient", "radialGradient", "pattern")
                   for e in d.iter() if isinstance(e.tag, str)):
            d.getparent().remove(d)


def flatten(src, dst):
    tree = etree.parse(src)
    root = tree.getroot()
    if root.get("viewBox") is None and root.get("width") and root.get("height"):
        root.set("viewBox", "0 0 %s %s" % (root.get("width"), root.get("height")))
    inline_uses(root)
    markers = {m.get("id"): m for m in root.iter("{%s}marker" % SVG)}
    for el in list(root.iter("{%s}path" % SVG, "{%s}polyline" % SVG)):
        style = el.get("style", "")
        for prop, at_end in (("marker-end", True), ("marker-start", False)):
            m = re.search(prop + r":\s*url\('?#([^')]+)'?\)", style)
            if not m or m.group(1) not in markers:
                continue
            mk = markers[m.group(1)]
            d = el.get("d") or " ".join(el.get("points", "").split())
            (x, y), ang = end_points(d, at_end)
            if not at_end and mk.get("orient") == "auto":
                ang += 180   # start markers point back along the path for orient="auto"
            vb = [float(v) for v in mk.get("viewBox", "0 0 10 10").split()]
            scale = float(mk.get("markerWidth", 3)) / vb[2]
            if mk.get("markerUnits", "strokeWidth") == "strokeWidth":
                scale *= stroke_width(style)
            if mk.get("orient") not in ("auto", "auto-start-reverse"):
                ang = float(mk.get("orient", 0))
            g = etree.Element("{%s}g" % SVG, transform="translate(%g,%g) rotate(%g) scale(%g) translate(%g,%g)" % (
                x, y, ang, scale, -float(mk.get("refX", 0)), -float(mk.get("refY", 0))))
            for child in mk:
                g.append(etree.fromstring(etree.tostring(child)))
            el.addnext(g)
            style = re.sub(prop + r":[^;]*;?", "", style)
        el.set("style", style)
    for el in list(root.iter()):
        if "djs-outline" in (el.get("class") or "").split():
            el.getparent().remove(el)
    for mk in markers.values():
        mk.getparent().remove(mk)
    tree.write(dst, xml_declaration=True, encoding="utf-8")


if __name__ == "__main__":
    flatten(sys.argv[1], sys.argv[2])
