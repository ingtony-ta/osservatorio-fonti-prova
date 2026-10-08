"""Esegue in sequenza le prove elencate in prove/richiesta.json, con analizza.py in modalità prova."""
import json
import os
import subprocess
import sys
from pathlib import Path

r = json.loads(Path("prove/richiesta.json").read_text(encoding="utf-8"))
esiti = []
for p in r["prove"]:
    env = dict(os.environ, PROVA=p["nome"], MODELLO=p["modello"], ADVISOR=p.get("advisor", ""), EFFORT=p.get("effort", ""),
               MAX_RICERCHE=str(r.get("max_ricerche", 30)), TETTO_DOLLARI=str(r.get("tetto_dollari", 5)),
               RACCOLTA=r["raccolta"], ISTRUZIONI=r["istruzioni"])
    print(f"=== Prova {p['nome']}", flush=True)
    esiti.append(subprocess.run([sys.executable, "analizza.py"], env=env).returncode)
print("Esiti:", esiti)
sys.exit(0 if all(e == 0 for e in esiti) else 1)
