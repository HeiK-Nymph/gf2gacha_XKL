# -*- coding: utf-8 -*-
r"""采集 addon：只拦截散爆/米大师相关域名，其余流量一律透传（不影响电脑正常上网）。
输出：本文件同目录 flows\NNN_req|res_<host>.json  （含账号凭证，分析完请删除）
用法：启动脚本见同目录 start_capture.ps1
"""
import json, os, re, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "flows")
LOG = os.path.join(HERE, "hosts.txt")
WATCH = re.compile(r"sunborn|mica|passport|tersafe|turing|midas", re.I)
os.makedirs(OUT, exist_ok=True)

def log(msg):
    line = time.strftime("%H:%M:%S ") + str(msg)
    print(line, flush=True)
    try:
        open(LOG, "a", encoding="utf-8").write(line + "\n")
    except Exception:
        pass

_seq = [0]
_seen = set()

def _save(rec, host, tag):
    _seq[0] += 1
    name = "%03d_%s_%s.json" % (_seq[0], tag, re.sub(r"[^A-Za-z0-9._-]", "_", host)[:60])
    try:
        open(os.path.join(OUT, name), "w", encoding="utf-8").write(
            json.dumps(rec, ensure_ascii=False, indent=2))
        return name
    except Exception as e:
        log("[SAVE-ERR] %s" % e)
        return "?"

class Cap:
    def tls_clienthello(self, data):
        try:
            sni = data.client_hello.sni or "(no-sni)"
        except Exception:
            sni = "(err)"
        if sni not in _seen:
            _seen.add(sni)
            log("[SNI] " + sni)
        if not WATCH.search(sni):
            data.ignore_connection = True

    def request(self, flow):
        try:
            host = flow.request.pretty_host
            if host not in _seen:
                _seen.add(host)
                log("[HOST] " + host)
            if not WATCH.search(host):
                return
            rec = {"phase": "request", "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "url": flow.request.pretty_url, "method": flow.request.method,
                   "headers": dict(flow.request.headers),
                   "form": dict(flow.request.urlencoded_form or {}),
                   "raw_body": (flow.request.get_text(strict=False) or "")[:8000]}
            log("[REQ] %s %s -> %s" % (flow.request.method, flow.request.pretty_url[:160],
                                       _save(rec, host, "req")))
        except Exception as e:
            log("[REQ-ERR] %s" % e)

    def response(self, flow):
        try:
            host = flow.request.pretty_host
            if not WATCH.search(host):
                return
            rec = {"phase": "response", "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "url": flow.request.pretty_url, "status": flow.response.status_code,
                   "headers": dict(flow.response.headers),
                   "raw_body": (flow.response.get_text(strict=False) or "")[:8000]}
            log("[RES] %s <- %s" % (flow.request.pretty_url[:160], _save(rec, host, "res")))
        except Exception as e:
            log("[RES-ERR] %s" % e)

addons = [Cap()]
