"""Long-lived MRI segmentation worker.

The FastAPI process talks to this process over newline-delimited JSON so torch
and nnU-Net imports stay warm across cases.
"""

import argparse
import contextlib
import io
import json
import sys
import traceback
from pathlib import Path

from segmentation_worker import run


def _emit(payload: dict) -> None:
    sys.__stdout__.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.__stdout__.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    arguments = parser.parse_args()

    _emit({"type": "ready"})
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line == "__quit__":
            _emit({"type": "bye"})
            return

        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            request = json.loads(line)
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = run(
                    arguments.model_dir,
                    Path(request["case_dir"]),
                    request["case_id"],
                )
            _emit({
                "type": "result",
                "ok": True,
                "result": result,
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
            })
        except Exception as error:
            _emit({
                "type": "result",
                "ok": False,
                "error": str(error),
                "traceback": traceback.format_exc(),
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
            })


if __name__ == "__main__":
    main()
