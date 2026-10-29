#!/usr/bin/env python3
"""Big on-screen alert for the operator (readable from across the room).

Used by the autonomous build when it is stuck and must wait for a human.
    python3 tools/alert.py "PORUKA" [--close-after SECONDS]
Also sends a normal desktop notification and appends to docs/ALERTS.log.
"""
import argparse, datetime, os, subprocess, tkinter as tk

ap = argparse.ArgumentParser()
ap.add_argument("message")
ap.add_argument("--close-after", type=int, default=0)
a = ap.parse_args()

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(root_dir, "docs", "ALERTS.log"), "a", encoding="utf-8") as f:
    f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}  {a.message}\n")
try:
    subprocess.run(["notify-send", "-u", "critical", "PSE Riemann", a.message], timeout=5)
except Exception:
    pass

w = tk.Tk()
w.title("PSE Riemann — treba te")
w.configure(bg="#12151d")
w.attributes("-topmost", True)
sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
w.geometry(f"{int(sw*.9)}x{int(sh*.8)}+{int(sw*.05)}+{int(sh*.1)}")
tk.Label(w, text="PSE RIEMANN", fg="#ffc257", bg="#12151d", font=("DejaVu Sans", 48, "bold")).pack(pady=(30, 10))
tk.Label(w, text=a.message, fg="#e9ecf3", bg="#12151d", wraplength=int(sw*.85),
         font=("DejaVu Sans", 56, "bold"), justify="center").pack(expand=True)
tk.Button(w, text="U redu", font=("DejaVu Sans", 28), command=w.destroy,
          bg="#ffc257", fg="#3a2a06").pack(pady=30)
if a.close_after:
    w.after(a.close_after * 1000, w.destroy)
w.mainloop()
