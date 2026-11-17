"""Pin every figure listed in a paper's figures.json on the figpack cloud.

Uploaded figures expire after 24 hours unless pinned. Each entry of figures.json needs a
"url", a "name" (at most 100 characters) and a "description" (10 to 300 characters).
Needs FIGPACK_API_KEY. Run after uploading:

    .venv/bin/python tools/pin_figures.py papers/<paper key>/figures.json
"""

import json
import os
import sys

import requests

API = os.getenv("FIGPACK_API_BASE_URL", "https://figpack-api.figpack.org")


def main(path):
    key = os.environ["FIGPACK_API_KEY"]
    figures = json.load(open(path))
    for name, f in figures.items():
        # the API stores the URL as the upload returned it; try that form, then without index.html
        for url in (f["url"], f["url"].removesuffix("/index.html")):
            r = requests.post(f"{API}/pin", headers={"x-api-key": key}, timeout=60, json={
                "figureUrl": url,
                "pinInfo": {"name": f["name"], "figureDescription": f["description"]},
            })
            if r.status_code != 404:
                break
        ok = r.ok and r.json().get("success")
        print(f"{name}: {'pinned' if ok else 'FAILED ' + r.text[:200]}")
        if not ok:
            sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1])
