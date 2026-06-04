"""Generate evil_model.pkl for G5 demo only — NOT used in production."""
import pickle
from pathlib import Path

class Evil:
    def __reduce__(self):
        import os
        return (os.system, ("echo G5_DEMO_PICKLE_DETECTED",))

out = Path(__file__).parent / "evil_model.pkl"
with out.open("wb") as f:
    pickle.dump(Evil(), f)
print("wrote", out)
