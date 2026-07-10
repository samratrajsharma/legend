#!/usr/bin/env python3
"""Create a tiny git repo with history so you can try KnowIT's Track tab.

    python scripts/make_demo_history.py [dest_dir]
Then point KnowIT (sidebar) at the printed folder and open Track.
"""
import os
import subprocess
import sys


def main(dest="_demo_history"):
    dest = os.path.abspath(dest)
    os.makedirs(dest, exist_ok=True)

    def run(args):
        subprocess.run(args, cwd=dest, check=True)

    def write(rel, content):
        p = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        with open(p, "w") as fh:
            fh.write(content)

    def commit(msg):
        run(["git", "add", "-A"])
        run(["git", "commit", "-qm", msg])

    run(["git", "init", "-q"])
    run(["git", "config", "user.email", "demo@knowit"])
    run(["git", "config", "user.name", "KnowIT Demo"])

    write("model.py", "from data import load\n\n\nclass Net:\n    def forward(self, x):\n        return x\n")
    write("data.py", "def load(path):\n    return open(path).read()\n")
    commit("c1: initial Net + data loader")

    write("model.py", "from losses import focal\n\n\nclass Net:\n    def forward(self, x):\n"
                      "        if x:\n            return focal(x)\n        return x\n\n"
                      "    def extra(self):\n        return 1\n")
    write("losses.py", "def focal(x):\n    return x * 2\n")
    os.remove(os.path.join(dest, "data.py"))
    commit("c2: add focal loss, branch in forward, drop data.py")

    write("api.py", "from model import Net\n\n\ndef serve():\n    return Net().forward(1)\n\n"
                    "if __name__ == '__main__':\n    serve()\n")
    commit("c3: add api entry point")

    print("Demo git repo created at:", dest)
    print("Point KnowIT at it (sidebar) and open the Track tab.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "_demo_history")
