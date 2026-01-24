import mitmproxy.http
from datetime import datetime
import json
from pathlib import Path

_event_handler = None

COMMUNICATION_FILE = Path(__file__).parent.parent.parent / "json" / "latest_request.json"





def set_event_handler(handler):
    global _event_handler
    _event_handler = handler

class getGF2Req:
    def __init__(self):
        self.target_domain = "gf2-gacha-record.sunborngame.com"
        self.request_data = None

    

    def request(self, flow: mitmproxy.http.HTTPFlow):
        url = flow.request.url
        if self.target_domain in url:
            headers_dict = {k: v for k, v in flow.request.headers.items()}
            body_dict = dict(flow.request.urlencoded_form)
            params_dict = dict(flow.request.query)
            self.request_data = {
                "headers": headers_dict,
                "body": body_dict,
                "params": params_dict
            }
            print(self.request_data)
            # 保存请求数据到文件
            try:
                with open(COMMUNICATION_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.request_data, f, ensure_ascii=False, indent=4)
                    print(f"[OK] 保存请求数据成功: {COMMUNICATION_FILE}")
                    return True
            except Exception as e:
                print(f"[ERROR] 保存请求数据失败: {e}")
                return False
            
            

            if _event_handler and hasattr(_event_handler, "on_request"):
                try:
                    
                    _event_handler.on_request(self.request_data)
                except Exception as e:
                    print(f"[ERROR] 处理请求失败: {e}")
            
            

addons = [
    getGF2Req()
]