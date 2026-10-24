"""SiteScope robot diagrams (10-12) and the master overview (01), drawn from the
wizard-and-assistant branch (robot_agent.py, mission_demo.py, robot_missions.py,
robot_schedules.py, robot_pairings.py, robot_maps.py, MAP_WAYPOINT_HOME_POSE_WORKFLOW.md)."""
import sys
from bpmngen import Diagram

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"


def d10():
    d = Diagram("10", "10 · Robot onboarding, map and capture points (one-time setup)")
    d.lane("own", "Project owner / Admin (web app)", 2)
    d.lane("be", "SiteScope backend", 2)
    d.lane("ag", "Robot agent (Jetson Orin NX)", 1)
    d.lane("ros", "Robot control panel / ROS 2", 1)

    # Pairing
    d.start("s", "New robot to add", "own", 0)
    d.task("acct", "Create robot service account (Admin › Robot pairing)", "own", 1, kind="user")
    d.task("tok", "Create pairing token and choose the default project", "own", 2, kind="user")
    d.task("grant", "Give robot Editor role on the project; store one-time token with expiry", "be", 3, kind="service")
    d.task("claim", "Claim the token once on the robot (robot_agent.py --claim-pairing-token)", "ag", 4, kind="manual")
    d.xor("valid", "Token valid and unused?", "be", 5, label_pos="above")
    d.end("rej", "Claim rejected (unknown, revoked, expired or already claimed)", "be", 5, row=1, kind="error")
    d.task("creds", "Mark token claimed; return robot credentials and server URL", "be", 6, kind="service")
    d.task("cfg", "Write robot_agent_config.json; start the sitescope-agent service", "ag", 7, kind="service")
    d.task("hb", "Log in; heartbeat with camera / LiDAR availability", "ag", 8, kind="service")
    d.task("online", "Show robot online on the Robots page", "be", 9, kind="service")
    d.chain("s", "acct", "tok", "grant", "claim", "valid")
    d.flow("valid", "rej", "No", route="v")
    d.flow("valid", "creds", "Yes")
    d.chain("creds", "cfg", "hb", "online")

    # Map
    d.xor("how", "How will the map be provided?", "own", 10, label_pos="above")
    d.task("upl", "Upload existing map files (.yaml + .pgm / .png)", "own", 11, kind="user")
    d.task("park", "Park robot at its home pose; press Start mapping", "own", 11, row=1, kind="user")
    d.task("qstart", "Queue map_start command", "be", 12, row=1, kind="service")
    d.task("slam", "Check sensors, stop navigation, start SLAM, stream live map", "ros", 13, kind="service")
    d.task("drive", "Drive the site with the handheld controller; bring robot back home", "own", 14, row=1, kind="manual")
    d.task("save", "Name the map; press Save (enabled when back within 30 cm / 15°)", "own", 15, row=1, kind="user")
    d.task("qsave", "Queue map_save command", "be", 16, row=1, kind="service")
    d.task("saved", "Save map and home pose; switch localization to the new map; stop SLAM", "ros", 17, kind="service")
    d.task("upmap", "Upload the map to the project", "ag", 18, kind="service")
    d.task("store", "Store new map version; retire capture points placed on the old map", "be", 19, row=1, kind="service")
    d.flow("online", "how", route="hvh")
    d.flow("how", "upl", "Upload")
    d.flow("how", "park", "Record", route="vh")
    d.flow("park", "qstart", route="hvh")
    d.flow("qstart", "slam", route="hvh")
    d.flow("slam", "drive", route="hvh")
    d.chain("drive", "save")
    d.flow("save", "qsave", route="hvh")
    d.flow("qsave", "saved", route="hvh")
    d.flow("saved", "upmap", route="hvh")
    d.flow("upmap", "store", route="hvh")
    d.flow("upl", "store", route="hv")

    # Capture points
    d.task("pts", "Place capture points: map position, facing direction, room", "own", 20, kind="user")
    d.task("savepts", "Save capture points in the map frame (x, y, yaw)", "be", 21, kind="service")
    d.end("ready", "Robot ready for missions", "be", 22)
    d.flow("store", "pts", route="hvh")
    d.flow("pts", "savepts", route="hvh")
    d.flow("savepts", "ready")
    d.note("Robot accounts are non-admin service users. Missions can only upload to projects where the robot is Owner or Editor.",
           "own", 3, row=0, attach="tok", w=250, dx=40, dy=-10)
    d.note("“Switch back to the previous map” restores the old map, home pose and its capture points.",
           "be", 19.4, row=0, attach="store", w=230, dx=20, dy=-12)
    d.note("The agent claims commands by polling, the same way it claims missions.", "ag", 12.2, row=0, w=230, dy=-12)
    return d


def d11():
    d = Diagram("11", "11 · Scheduled inspection: from recurring schedule to mission")
    d.lane("own", "Project owner / Editor (Schedules tab or voice assistant)", 1)
    d.lane("be", "SiteScope backend: schedule dispatcher (every 15 s)", 3)
    d.lane("ag", "Robot agent", 1)
    d.start("s", "Inspection to repeat", "own", 0)
    d.task("create", "Create schedule: robot, ordered capture points, time + time zone, weekdays, photo / 3D scan, if busy: skip", "own", 1, kind="user", h=95)
    d.task("next", "Validate; compute next run in the schedule's time zone", "be", 2, kind="service")
    d.inter("due", "Next run time reached", "be", 3, kind="timer")
    d.xor("late", "More than 30 min late?", "be", 4)
    d.end("missed", "Occurrence missed", "be", 4, row=1)
    d.xor("ok", "Robot still Editor and capture points on the current map?", "be", 5)
    d.task("dis", "Disable schedule and record the reason", "be", 6, row=2, kind="service")
    d.end("inv", "Schedule invalid", "be", 7, row=2, kind="error")
    d.xor("busy", "Robot busy with another task?", "be", 6)
    d.end("skipb", "Skipped: robot busy", "be", 6, row=1)
    d.xor("pay", "Camera / LiDAR available on the robot?", "be", 7)
    d.end("skipp", "Skipped: payload unavailable", "be", 7, row=1)
    d.task("mk", "Create mission with one step per capture point (queued)", "be", 8, kind="service")
    d.xor("conn", "Auto-connect on and robot not connected?", "be", 9)
    d.task("qc", "Queue Connect robot command", "be", 10, row=1, kind="service")
    d.task("claim", "Agent poll: run Connect first, then claim the oldest queued mission", "ag", 11, kind="service")
    d.end("run", "Mission runs (diagram 12)", "ag", 12)
    d.chain("s", "create")
    d.flow("create", "next", route="hvh")
    d.chain("next", "due", "late")
    d.flow("late", "missed", "Yes", route="v")
    d.flow("late", "ok", "No")
    d.flow("ok", "dis", "No", route="vh")
    d.flow("dis", "inv")
    d.flow("ok", "busy", "Yes")
    d.flow("busy", "skipb", "Yes", route="v")
    d.flow("busy", "pay", "No")
    d.flow("pay", "skipp", "No", route="v")
    d.flow("pay", "mk", "Yes")
    d.flow("mk", "conn")
    d.flow("conn", "qc", "Yes", route="vh")
    d.flow("conn", "claim", "No", route="hv")
    d.flow("qc", "claim", route="hv")
    d.flow("claim", "run")
    d.note("Each occurrence creates at most one mission. After every occurrence the next run is computed, so the schedule keeps firing until it is disabled.",
           "be", 2.6, row=1, attach="due", w=270, dy=10)
    d.note("A one-off trip (“Run now” on the Route tab) creates the same queued mission directly, after the same robot, map and payload checks.",
           "own", 8.2, row=0, w=300, dy=-10)
    return d


def d12():
    d = Diagram("12", "12 · Mission execution: navigate, capture, upload, return home")
    d.lane("op", "Operator (web app)", 1)
    d.lane("be", "SiteScope backend", 2)
    d.lane("ag", "Robot agent (Jetson Orin NX)", 2)
    d.lane("ros", "ROS 2 / Nav2", 1)
    d.lane("cam", "Insta360 X4 / Livox MID-360", 1)

    d.start("s", "Mission claimed", "ag", 0)
    d.task("run", "Post status running; emit “Task started”", "ag", 1, kind="service")
    d.xor("hc", "Nav2 and localization healthy?", "ag", 2)
    d.end("unsafe", "Task failed: navigation not safe", "ag", 2, row=1, kind="error")
    d.task("pose", "Use saved home pose as the return target", "ag", 3, kind="service")
    d.xor("m", "", "ag", 4)
    d.xor("more", "Another capture point?", "ag", 5, label_pos="below")
    d.task("nav", "NavigateToPose to the capture point (x, y, yaw)", "ros", 6, kind="service")
    d.xor("arr", "Arrived?", "ag", 7, row=1, label_pos="left")
    d.task("cap", "Capture 360° photo and / or 10 s LiDAR scan", "cam", 8, kind="service")
    d.task("fail", "Record failed step", "ag", 8, row=1, kind="service")
    d.xor("cont", "Continue on failure?", "ag", 9, row=1, label_pos="above")
    d.task("q", "Score image quality; in retry mode retake up to 3× and keep the best", "ag", 9, kind="service")
    d.task("ing", "Robot upload: store with project, room, date, mission, waypoint, sensor and pose; thumbnail, AI description, LAZ → Potree", "be", 10, kind="service", h=110, w=175)
    d.task("ok", "Mark step succeeded", "ag", 11, kind="service")
    d.task("home", "Return to home pose (Nav2)", "ag", 12, kind="service")
    d.task("fin", "Post final status and step results", "ag", 13, kind="service")
    d.task("close", "Close mission and steps; robot idle; log activity", "be", 14, kind="service")
    d.end("done", "Evidence available in SiteScope", "be", 15)

    d.start("cx", "Operator wants to stop", "op", 10, kind="conditional")
    d.task("press", "Press Cancel (or Stop during the return)", "op", 11, kind="user")
    d.task("req", "Mark cancel requested; agent's monitor cancels the active goal", "be", 12, row=1, kind="service")

    d.chain("s", "run", "hc")
    d.flow("hc", "unsafe", "No", route="v")
    d.flow("hc", "pose", "Yes")
    d.chain("pose", "m", "more")
    d.flow("more", "nav", "Yes", route="vh", label_at=(8, 80))
    d.flow("nav", "arr", route="hvh")
    d.flow("arr", "cap", "Yes", route="vh", label_at=(8, 60))
    d.flow("arr", "fail", "No")
    d.flow("fail", "cont")
    d.flow("cap", "q")
    d.flow("q", "ing")
    d.flow("ing", "ok")
    d.flow("ok", "m", route="over")
    d.flow("cont", "m", "Yes", route="under", label_at=(-45, 38))
    d.flow("cont", "home", "No", route="hv")
    d.flow("more", "home", "No", route="over", label_at=(30, -62))
    d.chain("cx", "press")
    d.flow("press", "req", route="hvh")
    d.flow("req", "home", route="v")
    d.flow("home", "fin")
    d.flow("fin", "close", route="hvh")
    d.flow("close", "done")
    # loop channels inside the agent lane's top padding
    for f in d.flows:
        if (f["src"], f["tgt"]) == ("ok", "m"):
            f["via_y"] = "AG_TOP+10"
        if (f["src"], f["tgt"]) == ("more", "home"):
            f["via_y"] = "AG_TOP+26"
        if (f["src"], f["tgt"]) == ("cont", "m"):
            f["via_y"] = "AG_BOTTOM-8"
    d.note("Every stage posts progress events (Going to…, Capturing…, Uploading…) shown live on the Progress tab and live map.",
           "be", 2.2, row=0, w=300, dy=-5)
    d.note("If the robot stops reporting for 2 min during a cancellation, a watchdog marks it failed: the return was not confirmed.",
           "be", 13.5, row=1, attach="req", w=250, dx=20, dy=10)
    return d


def d01():
    d = Diagram("01", "01 · SiteScope: construction site documentation platform (overview)")
    d.lane("g", "Guest (not logged in)", 1)
    d.lane("u", "Logged-in user (all roles)", 5)
    d.lane("o", "Project owner", 3)
    d.lane("r", "Robot (Go2-W) and agent", 1)
    d.lane("sys", "System (automatic)", 2)
    d.lane("a", "Administrator", 1)

    d.start("gs", "Visitor arrives", "g", 0)
    d.task("gauth", "Register, log in or reset password → 02", "g", 1)
    d.end("ge", "Logged in", "g", 2)
    d.chain("gs", "gauth", "ge")

    d.start("us", "Session starts", "u", 0, row=2)
    d.xor("um", "", "u", 0.8, row=2)
    d.xor("uw", "What would you like to do?", "u", 1.5, row=2, label_pos="below")
    items = [("up", "Upload photos, 360°, video, PDFs, point clouds → 04"),
             ("br", "Browse, search, view and compare media → 06"),
             ("an", "Pin annotations on images → 08"),
             ("rep", "Write and publish a PDF field report → 09"),
             ("me", "Review own uploads, drafts, reports and activity")]
    d.xor("uj", "", "u", 3.6, row=2)
    d.xor("again", "Something else?", "u", 4.4, row=2, label_pos="below")
    d.end("ue", "Session ends", "u", 5.2, row=2)
    d.chain("us", "um", "uw")
    for i, (nid, name) in enumerate(items):
        d.task(nid, name, "u", 2.55, row=i)
        d.flow("uw", nid, route="vh" if i != 2 else "h")
        d.flow(nid, "uj", route="hv" if i != 2 else "h")
    d.flow("uj", "again")
    d.flow("again", "ue", "No")
    d.flow("again", "um", "Yes", route="over", via_y="U_TOP+8")

    d.start("os", "New project or site", "o", 0, row=1)
    d.xor("ow", "", "o", 1, row=1)
    d.task("op", "Create project: details, rooms, floor plan, room pins; invite members → 03", "o", 2, kind="user")
    d.task("orb", "Pair a robot, record the map, place capture points → 10", "o", 2, row=1, kind="user")
    d.task("osc", "Schedule recurring inspections (Schedules tab or voice assistant) → 11, 13", "o", 2, row=2, kind="user")
    d.xor("oj", "", "o", 3, row=1)
    d.end("oe", "Project ready", "o", 4, row=1)
    d.chain("os", "ow")
    d.flow("ow", "op", route="vh"); d.flow("ow", "orb"); d.flow("ow", "osc", route="vh")
    d.flow("op", "oj", route="hv"); d.flow("orb", "oj"); d.flow("osc", "oj", route="hv")
    d.flow("oj", "oe")

    d.start("rs", "Scheduled run is due", "r", 0, kind="timer")
    d.task("rm", "Navigate to each capture point, capture, upload, return home → 12", "r", 1, kind="service")
    d.end("re", "Evidence stored with provenance", "r", 2)
    d.chain("rs", "rm", "re")

    d.start("s1", "Point cloud uploaded", "sys", 0, kind="message")
    d.task("pc", "Convert LAZ / LAS to Potree 3D viewer → 05", "sys", 1, kind="service")
    d.end("s1e", "3D viewer ready", "sys", 2)
    d.start("s2", "Image uploaded", "sys", 0, row=1, kind="message")
    d.task("ai", "Generate AI description: scene, quality, safety → 07", "sys", 1, row=1, kind="service")
    d.end("s2e", "Description available", "sys", 2, row=1)
    d.chain("s1", "pc", "s1e"); d.chain("s2", "ai", "s2e")

    d.start("as", "Admin logs in", "a", 0)
    d.task("adm", "Manage users, robot accounts, projects and roles", "a", 1, kind="user")
    d.end("ae", "Done", "a", 2)
    d.chain("as", "adm", "ae")
    d.note("Robot captures enter through the same upload pipeline as people's uploads, so AI analysis and point cloud conversion start automatically.",
           "r", 3.1, row=0, attach="re", w=300, dy=-12)
    d.note("The first registered user becomes the global administrator.", "a", 3.1, w=260, attach="adm", dy=-5)
    return d


def _resolve_via(d):
    """Replace symbolic via_y values (lane-relative) with absolute coordinates."""
    d._layout()
    for f in d.flows:
        v = f.get("via_y")
        if isinstance(v, str):
            name, off = v.replace("-", "+-").split("+", 1)
            lane = {"AG": "ag", "U": "u"}[name.split("_")[0]]
            top, h = d.lane_box[lane]
            base = top if name.endswith("TOP") else top + h
            f["via_y"] = base + float(off)


if __name__ == "__main__":
    import os
    os.makedirs(OUT, exist_ok=True)
    names = {"01": "01-master-overview", "10": "10-robot-setup-and-mapping",
             "11": "11-schedule-to-mission", "12": "12-mission-execution"}
    for fn in (d01, d10, d11, d12):
        dg = fn()
        _resolve_via(dg)
        print(dg.write(os.path.join(OUT, names[dg.id] + ".bpmn")))


def d12s():
    """Slide-sized summary of diagram 12 (same flow, fewer details)."""
    d = Diagram("12s", "SiteScope mission loop (summary of diagram 12)")
    d.lane("ag", "Robot agent (Go2-W)", 2)
    d.lane("hw", "Nav2 / Insta360 X4 / LiDAR", 1)
    d.lane("be", "SiteScope backend", 1)
    d.start("s", "Mission claimed", "ag", 0)
    d.xor("hc", "Navigation healthy?", "ag", 1)
    d.end("bad", "Task failed", "ag", 1, row=1, kind="error", label_pos="right")
    d.xor("m", "", "ag", 2)
    d.xor("more", "Next capture point?", "ag", 3, label_pos="above")
    d.task("nav", "Navigate to capture point (x, y, yaw)", "hw", 4, kind="service")
    d.task("cap", "Capture 360° photo / LiDAR scan", "hw", 5, kind="service")
    d.task("q", "Quality check; retake if needed", "ag", 6, row=1, kind="service")
    d.task("up", "Store with provenance; thumbnail, AI description", "be", 7, kind="service")
    d.task("home", "Return to home pose", "ag", 8, kind="service")
    d.task("fin", "Close mission; post results", "be", 9, kind="service")
    d.end("e", "Evidence available", "be", 10)
    d.chain("s", "hc")
    d.flow("hc", "bad", "No", route="v")
    d.flow("hc", "m", "Yes")
    d.flow("m", "more")
    d.flow("more", "nav", "Yes", route="vh", label_at=(8, 60))
    d.flow("nav", "cap")
    d.flow("cap", "q", route="hvh")
    d.flow("q", "up", route="hvh")
    d.flow("up", "m", route="right_up", via_x=0, via_y=0)
    d.flow("more", "home", "No", route="h", label_at=(60, -22))
    d.flow("home", "fin", route="hvh")
    d.flow("fin", "e")
    return d


def _fix12s(d):
    d._layout()
    up, m = d.nodes["up"], d.nodes["m"]
    for f in d.flows:
        if (f["src"], f["tgt"]) == ("up", "m"):
            f["route"] = "under"
            f["via_y"] = up.b + 22
    d.lane_box  # noqa


if __name__ == "__main__":
    dg = d12s(); _fix12s(dg)
    print(dg.write(os.path.join(OUT, "12s-mission-loop-summary.bpmn")))
