"""Tiny BPMN 2.0 writer with grid layout, for diagrams that open in bpmn.io / Camunda Modeler.

Nodes are placed on a (col, row) grid inside horizontal lanes of one pool; sequence flows are
routed orthogonally. The output is plain BPMN 2.0 XML with full DI, so every diagram stays editable.
"""
from __future__ import annotations

from xml.sax.saxutils import escape

CW = 175          # column width
LEFT = 130        # x of column 0 centre, measured from pool left (after the lane header)
RH = 125          # row height inside a lane
PAD = 35          # lane top/bottom padding
POOL_X, POOL_Y = 20, 20
HEADER = 30       # pool header width
LANE_HEADER = 30
SIZES = {"task": (150, 90), "gateway": (50, 50), "event": (36, 36)}

TASK_TAG = {"task": "task", "user": "userTask", "service": "serviceTask", "script": "scriptTask",
            "send": "sendTask", "receive": "receiveTask", "manual": "manualTask", "sub": "subProcess",
            "call": "callActivity", "rule": "businessRuleTask"}


def _x(s: str) -> str:
    return escape(s, {'"': "&quot;"})


class Node:
    def __init__(self, nid, name, cat, tag, lane, col, row, extra="", label_pos="below", w=None, h=None):
        self.id, self.name, self.cat, self.tag = nid, name, cat, tag
        self.lane, self.col, self.row, self.extra, self.label_pos = lane, col, row, extra, label_pos
        self.w, self.h = (w or SIZES[cat][0]), (h or SIZES[cat][1])
        self.cx = self.cy = 0.0

    @property
    def l(self): return self.cx - self.w / 2
    @property
    def r(self): return self.cx + self.w / 2
    @property
    def t(self): return self.cy - self.h / 2
    @property
    def b(self): return self.cy + self.h / 2


class Diagram:
    def __init__(self, did: str, pool_name: str):
        self.id, self.pool = did, pool_name
        self.lanes: list[tuple[str, str, int]] = []
        self.nodes: dict[str, Node] = {}
        self.flows: list[dict] = []
        self.notes: list[dict] = []
        self._n = 0

    # ---- building -------------------------------------------------------------------------
    def lane(self, lid, name, rows=1):
        self.lanes.append((lid, name, rows))

    def _add(self, node):
        assert node.id not in self.nodes, node.id
        self.nodes[node.id] = node
        return node.id

    def task(self, nid, name, lane, col, row=0, kind="task", w=None, h=None):
        return self._add(Node(nid, name, "task", TASK_TAG[kind], lane, col, row, w=w, h=h))

    def xor(self, nid, name, lane, col, row=0, label_pos="above"):
        return self._add(Node(nid, name, "gateway", "exclusiveGateway", lane, col, row, label_pos=label_pos))

    def par(self, nid, name, lane, col, row=0, label_pos="above"):
        return self._add(Node(nid, name, "gateway", "parallelGateway", lane, col, row, label_pos=label_pos))

    def start(self, nid, name, lane, col, row=0, kind=None, label_pos="below"):
        return self._add(Node(nid, name, "event", "startEvent", lane, col, row, extra=kind or "",
                              label_pos=label_pos))

    def end(self, nid, name, lane, col, row=0, kind=None, label_pos="below"):
        return self._add(Node(nid, name, "event", "endEvent", lane, col, row, extra=kind or "",
                              label_pos=label_pos))

    def inter(self, nid, name, lane, col, row=0, kind="timer", catch=True, label_pos="below"):
        tag = "intermediateCatchEvent" if catch else "intermediateThrowEvent"
        return self._add(Node(nid, name, "event", tag, lane, col, row, extra=kind, label_pos=label_pos))

    def flow(self, src, tgt, label=None, route=None, label_dx=6, label_dy=-20, via_y=None, via_x=None,
             label_at=None):
        """label_at=(dx, dy) pins the label's top-left relative to the source centre."""
        self.flows.append(dict(src=src, tgt=tgt, label=label, route=route, ldx=label_dx, ldy=label_dy,
                               via_y=via_y, via_x=via_x, lat=label_at))

    def chain(self, *ids, **kw):
        for a, b in zip(ids, ids[1:]):
            self.flow(a, b, **kw)

    def note(self, text, lane, col, row=0, attach=None, w=260, h=None, dx=0, dy=0):
        self.notes.append(dict(text=text, lane=lane, col=col, row=row, attach=attach, w=w, h=h, dx=dx, dy=dy))

    # ---- layout ---------------------------------------------------------------------------
    def _layout(self):
        y = POOL_Y
        self.lane_box = {}
        for lid, name, rows in self.lanes:
            h = rows * RH + 2 * PAD
            self.lane_box[lid] = (y, h)
            y += h
        self.pool_h = y - POOL_Y
        for n in self.nodes.values():
            ly, _ = self.lane_box[n.lane]
            n.cx = POOL_X + HEADER + LANE_HEADER + LEFT + n.col * CW
            n.cy = ly + PAD + n.row * RH + RH / 2
        right = max(n.r for n in self.nodes.values())
        for nt in self.notes:
            ly, _ = self.lane_box[nt["lane"]]
            nt["x"] = POOL_X + HEADER + LANE_HEADER + LEFT + nt["col"] * CW - 70 + nt["dx"]
            nt["y"] = ly + PAD + nt["row"] * RH + 15 + nt["dy"]
            lines = max(1, sum(len(p) // max(1, int(nt["w"] / 6.6)) + 1 for p in nt["text"].split("\n")))
            nt["h"] = nt["h"] or 14 * lines + 12
            right = max(right, nt["x"] + nt["w"])
        self.pool_w = right - POOL_X + 60

    def _route(self, f):
        s, t = self.nodes[f["src"]], self.nodes[f["tgt"]]
        r = f["route"]
        sx, sy, tx, ty = s.cx, s.cy, t.cx, t.cy
        same_row = abs(sy - ty) < 1
        if r is None:
            if same_row and tx > sx:
                r = "h"
            elif same_row:
                r = "under"
            elif abs(tx - sx) < 1:
                r = "v"
            elif tx > sx:
                r = "vh" if s.cat == "gateway" else ("hv" if t.cat == "gateway" else "hvh")
            else:
                r = "vh_back"
        if r == "h":
            return [(s.r, sy), (t.l, ty)]
        if r == "v":
            return [(sx, s.b), (tx, t.t)] if ty > sy else [(sx, s.t), (tx, t.b)]
        if r == "vh":
            return [(sx, s.b if ty > sy else s.t), (sx, ty), (t.l, ty)]
        if r == "hv":
            return [(s.r, sy), (tx, sy), (tx, t.t if ty > sy else t.b)]
        if r == "hvh":
            mx = f["via_x"] if f["via_x"] is not None else (s.r + t.l) / 2
            return [(s.r, sy), (mx, sy), (mx, ty), (t.l, ty)]
        if r == "vh_back":   # leave top/bottom, run horizontally into the target's right side
            return [(sx, s.b if ty > sy else s.t), (sx, ty), (t.r, ty)]
        if r in ("under", "over"):   # loop back below/above the row
            sign = 1 if r == "under" else -1
            yy = f["via_y"] if f["via_y"] is not None else (max(s.b, t.b) + 28 if sign > 0 else min(s.t, t.t) - 28)
            return [(sx, s.b if sign > 0 else s.t), (sx, yy), (tx, yy), (tx, t.b if sign > 0 else t.t)]
        if r == "down_left":   # down from source then left/right into the target's top
            return [(sx, s.b), (sx, f["via_y"]), (tx, f["via_y"]), (tx, t.t)]
        if r == "up_into":     # leave right, go to target column, enter from below
            return [(s.r, sy), (tx, sy), (tx, t.b)]
        if r == "right_up":    # leave right, rise/fall at via_x, enter target bottom/top
            mx = f["via_x"]
            return [(s.r, sy), (mx, sy), (mx, f["via_y"]), (tx, f["via_y"]), (tx, t.b if ty < f["via_y"] else t.t)]
        raise ValueError(r)

    # ---- output ---------------------------------------------------------------------------
    def xml(self) -> str:
        self._layout()
        P, out, di = f"Process_{self.id}", [], []
        out.append('<?xml version="1.0" encoding="UTF-8"?>')
        out.append('<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
                   'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
                   'xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
                   'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" '
                   f'id="Defs_{self.id}" targetNamespace="https://sitescope.smart-crg.com/bpmn" '
                   'exporter="SiteScope BPMN generator" exporterVersion="1.0">')
        out.append(f'<bpmn:collaboration id="Collab_{self.id}"><bpmn:participant id="Pool_{self.id}" '
                   f'name="{_x(self.pool)}" processRef="{P}"/>')
        out.append('</bpmn:collaboration>')
        out.append(f'<bpmn:process id="{P}" isExecutable="false">')
        out.append(f'<bpmn:laneSet id="LaneSet_{self.id}">')
        for lid, name, _ in self.lanes:
            refs = "".join(f"<bpmn:flowNodeRef>{n.id}</bpmn:flowNodeRef>" for n in self.nodes.values() if n.lane == lid)
            out.append(f'<bpmn:lane id="Lane_{lid}" name="{_x(name)}">{refs}</bpmn:lane>')
        out.append('</bpmn:laneSet>')
        inc = {n: [] for n in self.nodes}
        outg = {n: [] for n in self.nodes}
        for i, f in enumerate(self.flows):
            f["id"] = f"Flow_{i + 1}"
            outg[f["src"]].append(f["id"]); inc[f["tgt"]].append(f["id"])
        for n in self.nodes.values():
            body = "".join(f"<bpmn:incoming>{x}</bpmn:incoming>" for x in inc[n.id])
            body += "".join(f"<bpmn:outgoing>{x}</bpmn:outgoing>" for x in outg[n.id])
            if n.extra == "timer":
                body += f'<bpmn:timerEventDefinition id="TED_{n.id}"/>'
            elif n.extra == "message":
                body += f'<bpmn:messageEventDefinition id="MED_{n.id}"/>'
            elif n.extra == "error":
                body += f'<bpmn:errorEventDefinition id="EED_{n.id}"/>'
            elif n.extra == "terminate":
                body += f'<bpmn:terminateEventDefinition id="TerED_{n.id}"/>'
            elif n.extra == "signal":
                body += f'<bpmn:signalEventDefinition id="SED_{n.id}"/>'
            elif n.extra == "conditional":
                body += f'<bpmn:conditionalEventDefinition id="CED_{n.id}"><bpmn:condition xsi:type="bpmn:tFormalExpression" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/></bpmn:conditionalEventDefinition>'
            out.append(f'<bpmn:{n.tag} id="{n.id}" name="{_x(n.name)}">{body}</bpmn:{n.tag}>')
        for f in self.flows:
            name = f' name="{_x(f["label"])}"' if f["label"] else ""
            out.append(f'<bpmn:sequenceFlow id="{f["id"]}"{name} sourceRef="{f["src"]}" targetRef="{f["tgt"]}"/>')
        for i, nt in enumerate(self.notes):
            nt["id"] = f"Note_{i + 1}"
            out.append(f'<bpmn:textAnnotation id="{nt["id"]}"><bpmn:text>{_x(nt["text"])}</bpmn:text></bpmn:textAnnotation>')
            if nt["attach"]:
                out.append(f'<bpmn:association id="Assoc_{i + 1}" sourceRef="{nt["attach"]}" targetRef="{nt["id"]}"/>')
        out.append('</bpmn:process>')

        # ---- DI ----
        di.append(f'<bpmndi:BPMNDiagram id="Diagram_{self.id}"><bpmndi:BPMNPlane id="Plane_{self.id}" bpmnElement="Collab_{self.id}">')
        di.append(f'<bpmndi:BPMNShape id="Pool_{self.id}_di" bpmnElement="Pool_{self.id}" isHorizontal="true">'
                  f'<dc:Bounds x="{POOL_X}" y="{POOL_Y}" width="{self.pool_w:.0f}" height="{self.pool_h:.0f}"/></bpmndi:BPMNShape>')
        for lid, _, _ in self.lanes:
            ly, lh = self.lane_box[lid]
            di.append(f'<bpmndi:BPMNShape id="Lane_{lid}_di" bpmnElement="Lane_{lid}" isHorizontal="true">'
                      f'<dc:Bounds x="{POOL_X + HEADER}" y="{ly:.0f}" width="{self.pool_w - HEADER:.0f}" height="{lh:.0f}"/></bpmndi:BPMNShape>')
        for n in self.nodes.values():
            label = ""
            if n.cat != "task" and n.name:
                lw = 120
                lines = max(1, len(n.name) // 19 + 1)
                lh = 14 * lines
                ly = n.b + 6 if n.label_pos == "below" else n.t - lh - 6
                lx = n.cx - lw / 2
                if n.label_pos == "right":
                    lx, ly = n.r + 8, n.cy - lh / 2 - 12
                elif n.label_pos == "left":
                    lx, ly = n.l - lw - 8, n.cy - lh / 2 - 12
                label = f'<bpmndi:BPMNLabel><dc:Bounds x="{lx:.0f}" y="{ly:.0f}" width="{lw}" height="{lh}"/></bpmndi:BPMNLabel>'
            marker = ' isMarkerVisible="true"' if n.tag == "exclusiveGateway" else ""
            expanded = ' isExpanded="false"' if n.tag == "subProcess" else ""
            di.append(f'<bpmndi:BPMNShape id="{n.id}_di" bpmnElement="{n.id}"{marker}{expanded}>'
                      f'<dc:Bounds x="{n.l:.0f}" y="{n.t:.0f}" width="{n.w}" height="{n.h}"/>{label}</bpmndi:BPMNShape>')
        for f in self.flows:
            pts = self._route(f)
            wps = "".join(f'<di:waypoint x="{x:.0f}" y="{y:.0f}"/>' for x, y in pts)
            label = ""
            if f["label"]:
                (x0, y0), (x1, y1) = pts[0], pts[1]
                lx, ly = (x0 + x1) / 2 + f["ldx"], (y0 + y1) / 2 + f["ldy"]
                if abs(x0 - x1) < 1:   # vertical first segment: label to the right of it
                    lx, ly = x0 + 6 + f["ldx"] - 6, (y0 + y1) / 2 - 7 + f["ldy"] + 20
                if f.get("lat"):
                    sn = self.nodes[f["src"]]
                    lx, ly = sn.cx + f["lat"][0], sn.cy + f["lat"][1]
                lw = max(30, min(150, 6.4 * len(f["label"])))
                lh = 14 * (1 + int(6.4 * len(f["label"]) // 150))
                label = f'<bpmndi:BPMNLabel><dc:Bounds x="{lx:.0f}" y="{ly:.0f}" width="{lw:.0f}" height="{lh}"/></bpmndi:BPMNLabel>'
            di.append(f'<bpmndi:BPMNEdge id="{f["id"]}_di" bpmnElement="{f["id"]}">{wps}{label}</bpmndi:BPMNEdge>')
        for i, nt in enumerate(self.notes):
            di.append(f'<bpmndi:BPMNShape id="{nt["id"]}_di" bpmnElement="{nt["id"]}">'
                      f'<dc:Bounds x="{nt["x"]:.0f}" y="{nt["y"]:.0f}" width="{nt["w"]}" height="{nt["h"]:.0f}"/></bpmndi:BPMNShape>')
            if nt["attach"]:
                a = self.nodes[nt["attach"]]
                ax = min(max(a.cx, nt["x"]), nt["x"] + nt["w"])
                ay = nt["y"] if nt["y"] > a.cy else nt["y"] + nt["h"]
                sy = a.b if nt["y"] > a.cy else a.t
                di.append(f'<bpmndi:BPMNEdge id="Assoc_{i + 1}_di" bpmnElement="Assoc_{i + 1}">'
                          f'<di:waypoint x="{a.cx:.0f}" y="{sy:.0f}"/><di:waypoint x="{ax:.0f}" y="{ay:.0f}"/></bpmndi:BPMNEdge>')
        di.append('</bpmndi:BPMNPlane></bpmndi:BPMNDiagram>')
        return "\n".join(out + di + ["</bpmn:definitions>"])

    def write(self, path):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.xml())
        return path
