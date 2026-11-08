"""mitmproxy addon: persist completed home recommendation responses live."""

import json
import re
from pathlib import Path

from mitmproxy import ctx, http

FEED_PATH = re.compile(r"^/api/sns/v\d+/homefeed(?:/categories)?$")


class HomeFeed:
    def load(self, loader):
        loader.add_option("homefeed_output", str, "", "Home recommendation JSONL path")

    def response(self, flow: http.HTTPFlow):
        request = flow.request
        if not request.host.endswith(".xiaohongshu.com") or not FEED_PATH.fullmatch(request.path.split("?", 1)[0]):
            return
        try:
            body = flow.response.json()
        except ValueError:
            body = None
        record = {
            "method": request.method,
            "url": request.pretty_url,
            "status": flow.response.status_code,
            "body": body,
        }
        if ctx.options.homefeed_output:
            with Path(ctx.options.homefeed_output).open("a", encoding="utf-8") as out:
                out.write(json.dumps(record, ensure_ascii=True) + "\n")


addons = [HomeFeed()]
