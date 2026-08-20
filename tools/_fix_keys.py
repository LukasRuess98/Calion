from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tg = ROOT / "tools/tablegen_p1.py"
t = tg.read_text(encoding="utf-8")
for a, b in [("Wirtz.2021", "Wirtz2021_complexity"), ("Kotzur.2021", "Kotzur2021"),
             ("vanderHeijde.2019", "vanderHeijde2017"), ("Hering.2021", "Hering2021")]:
    n = t.count(a)
    t = t.replace(a, b)
    print(f"  {a} -> {b}  (x{n})")
tg.write_text(t, encoding="utf-8")
