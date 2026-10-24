"""Vector redraw of Fig. 2 of the SiteScope IROS 2026 workshop paper (schedule-to-report workflow)."""
import os, sys
from bpmngen import Diagram

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"


def fig2():
    d = Diagram("P2", "SiteScope schedule-to-report workflow (paper Fig. 2)")
    d.lane("man", "Manual workflow", 1)
    d.lane("plat", "User / SiteScope platform", 1)
    d.lane("rob", "Robot system", 1)
    d.start("ms", "Start", "man", 0)
    d.task("sm1", "S-M1: Define route", "man", 1, kind="manual")
    d.task("m1", "M1: Prepare camera", "man", 2.3, kind="manual")
    d.task("m2", "M2: Capture and upload evidence", "man", 3.3, kind="manual")
    d.start("ps", "Start", "plat", 0)
    d.task("sr", "S-R1–S-R5: Configure robotic workflow", "plat", 1, kind="user")
    d.task("r1", "R1: Start robot", "plat", 2.3, kind="manual")
    d.inter("occ", "Scheduled occurrence", "plat", 3.05, kind="timer")
    d.task("mk", "Create mission", "plat", 3.8, kind="service")
    d.task("r2", "R2: Claim mission, navigate, capture, upload, return to H", "rob", 3.8, kind="service")
    d.xor("ev", "Evidence available", "plat", 5.25, label_pos="left")
    d.task("ing", "Ingest and store with provenance", "plat", 6.1, kind="service")
    d.task("rev", "Review and annotate", "plat", 7.1, kind="user")
    d.task("gen", "Generate PDF", "plat", 8.0, kind="service")
    d.task("pub", "Verify and publish", "plat", 8.9, kind="user")
    d.end("end", "End", "plat", 9.8)
    d.chain("ms", "sm1", "m1", "m2")
    d.flow("m2", "ev", route="hv")
    d.chain("ps", "sr", "r1", "occ", "mk")
    d.flow("mk", "r2", route="v")
    d.flow("r2", "ev", route="hv")
    d.chain("ev", "ing", "rev", "gen", "pub", "end")
    d.group("ONE-TIME SETUP", 0, 1, "man", "rob")
    d.group("RECURRING EXECUTION", 2.3, 3.8, "man", "rob")
    d.group("COMMON SITESCOPE WORKFLOW", 4.88, 9.8, "man", "rob")
    d.group("C1: Review and report publication", 7.1, 8.9, "plat", "plat", inset=18)
    return d


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print(fig2().write(os.path.join(OUT, "00-paper-schedule-to-report.bpmn")))
