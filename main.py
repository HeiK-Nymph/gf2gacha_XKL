import os
import sys

# 看门狗由本程序以独立进程重新拉起。这里必须在导入 webview / mitmproxy 之前
# 处理，保证即使 GUI 依赖损坏，主进程退出后也能恢复 Windows 代理设置。
if len(sys.argv) >= 2 and sys.argv[1] == "--proxy-watchdog":
    try:
        if len(sys.argv) != 6:
            raise SystemExit(2)
        from backend.proxy_watchdog import run_watchdog
        raise SystemExit(run_watchdog(
            int(sys.argv[2]),
            sys.argv[3],
            sys.argv[4],
            sys.argv[5],
        ))
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(2)

import webview
import webbrowser
import threading
import asyncio
import json
import shutil
import subprocess
import time
from types import SimpleNamespace
from datetime import datetime
from pathlib import Path
import requests

from backend.announcement import AnnouncementService

# 添加backend路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

_log_path = None


def _app_root() -> Path:
    """安装根目录（frozen: exe 所在目录；开发环境: 仓库目录）"""
    override = os.environ.get("GF2XKL_APP_ROOT", "").strip()
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        return Path(__file__).parent.parent
    return Path(__file__).parent


def _update_state_path() -> Path:
    """更新状态文件（与 updater.py 共用同一个约定路径）

    GF2XKL_APP_ROOT 只用于本地演练：把"安装目录"指向临时目录。
    """
    override = os.environ.get("GF2XKL_APP_ROOT", "").strip()
    if override:
        return Path(override) / "_internal" / "logs" / "update_state.json"
    return Path(__file__).parent / "logs" / "update_state.json"


def _read_update_state() -> dict:
    try:
        with open(_update_state_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_update_state(**fields) -> dict:
    state = _read_update_state()
    state.update(fields)
    state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        path = _update_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception as e:
        print(f"[WARNING] 写更新状态失败: {e}")
    return state


def _version_tuple(text) -> tuple:
    """把 1.2.3 / 1.2.3-beta 这类版本号转成可比较的元组

    旧实现直接 int() 拆分，远端一旦出现 beta 后缀就抛异常、在界面上显示成
    "检查更新失败"，用户会以为断网。
    """
    parts = []
    for chunk in str(text or "").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _init_logging():
    """初始化日志：打包后的主程序没有控制台，logs/app.log 是唯一的排障手段"""
    global _log_path
    if _log_path is not None:
        return _log_path
    try:
        from backend.applog import setup_logging
        _log_path = setup_logging()
    except Exception as e:
        print(f"[WARNING] 初始化日志失败: {e}")
        _log_path = Path(__file__).parent / "logs" / "app.log"
    return _log_path

class GachaApp:
    def __init__(self):
        self.window = None
        self._window_maximized = False
        self.proxy_thread = None
        self.proxy_running = False  # 新增：代理运行标志
        self._proxy_lock = threading.Lock()    # 防止重复启动代理
        self._capture_lock = threading.Lock()
        self._closing = threading.Event()
        self._ssr_lock = threading.Lock()
        self._ssr_thread = None
        self._ssr_source = 'none'
        self._ssr_refresh_started = False
        self.last_capture = None               # mitmproxy 最近一次捕获（内存里的状态）
        self._pending_update = {}              # 最近一次"检查更新"的结果（供 start_update 写进状态文件）
        # 新增：版本管理
        self.version = self._load_version()
        # 从本地 version.json 读取远程版本检查地址（R2）
        self.version_url = self.version.get("version_url", "https://r2.gf2gacha-xkl.uk/version.json")
        self.announcement_center = AnnouncementService()
        # 先设置为空数据，延迟加载（后台线程）
        self.ssr_data = {
            "version": "loading",
            "SSR_character": {},
            "SSR_weapon": {},
            "SSR_permanent": {},
            "SR_character": {},
            "SR_weapon": {},
        }
        self.ssr_loading = True  # 标记正在加载

        # 启动时清理旧的更新器
        self._cleanup_old_updater()
        
    # ------------------------------------------------------------------
    # 抽卡记录
    # ------------------------------------------------------------------
    def get_gacha(self):
        """重放捕获到的抽卡请求，取回五个池子的记录

        失败一律带 code 字段，方便前端给出「怎么修」的提示：
            no_capture  还没抓到游戏请求（最常见：没在游戏里打开抽卡记录页面）
            no_auth     抓到的是同域名下的其它请求，不带 Authorization
            network / http / parse / api / pagination   重放阶段的具体失败原因
        """
        from backend import capture

        info = capture.describe_capture()
        print(f"[GACHA] 捕获状态: exists={info['exists']} size={info['size']} "
              f"replayable={info['replayable']} captured_at={info['captured_at']}")

        if not info["replayable"]:
            if not info["exists"] or not info["size"]:
                return {
                    "status": "error",
                    "code": "no_capture",
                    "msg": "还没有抓到游戏请求。" + capture.HINT_OPEN_GACHA_PAGE,
                    "capture": info,
                }
            if not info["has_authorization"]:
                return {
                    "status": "error",
                    "code": "no_auth",
                    "msg": "捕获到的请求里没有 Authorization（多半是同域名下的其它请求，不是抽卡记录）。"
                           + capture.HINT_OPEN_GACHA_PAGE,
                    "capture": info,
                }
            return {
                "status": "error",
                "code": "bad_capture",
                "msg": "捕获到的请求不完整（缺少请求体）。" + capture.HINT_OPEN_GACHA_PAGE,
                "capture": info,
            }

        # 依赖放在真正要发请求之前再 import：组件缺失时也能给出人话提示，
        # 而不是在用户刚点按钮时抛一个 ModuleNotFoundError
        try:
            from backend.api.getGacha import get_gacha_data_all_ex
        except Exception as e:
            print(f"[ERROR] 加载抽卡接口模块失败: {e}")
            return {
                "status": "error",
                "code": "module_missing",
                "msg": f"程序组件缺失，无法发起请求：{e}",
                "capture": info,
            }

        # 重放本身不走系统代理；顺手确保代理在跑，用户接着进游戏就能刷新一份新捕获
        proxy_status = self._ensure_proxy_for_capture()

        uid = self._fetch_uid()

        result = get_gacha_data_all_ex()
        if not result.get("ok"):
            error = result.get("error") or {}
            msg = self._describe_replay_error(error, info)
            print(f"[ERROR] 重放抽卡请求失败: {error}")
            return {
                "status": "error",
                "code": error.get("kind", "unknown"),
                "msg": msg,
                "detail": error,
                "capture": info,
                "proxy": proxy_status,
            }

        print("=" * 50)
        print(f"[OK] 抽卡记录获取成功，uid={uid}")
        return {
            "status": "success",
            "msg": "获取抽卡记录成功",
            "data": {
                "uid": uid,
                "gacha": result["data"],
            },
            "capture": info,
            "proxy": proxy_status,
        }

    def _describe_replay_error(self, error, info):
        """把结构化错误翻译成用户能照做的提示"""
        kind = error.get("kind")
        pool = error.get("pool")
        prefix = {
            "network": "网络请求失败",
            "http": "服务器返回异常状态码",
            "parse": "接口返回内容异常",
            "api": "接口返回错误",
            "pagination": "分页数据异常",
            "internal": "内部异常",
        }.get(kind, "获取抽卡记录失败")

        msg = f"{prefix}：{error.get('msg') or '无描述'}"
        if pool:
            msg = f"{pool}：{msg}"
        if error.get("page"):
            msg += f"（中断于第 {error['page']} 页，之前已成功 {error.get('ok_pages', 0)} 页）"

        hints = []
        if kind == "api":
            hints.append("Authorization 可能已过期，请在游戏里重新打开一次「招募 · 访问详情」页面，再点『更新记录』")
        elif kind == "http":
            hints.append("请先在游戏里重新打开「招募 · 访问详情」页面刷新 token；若仍失败，可能是接口有变动")
        elif kind == "network":
            hints.append("请检查网络；如果开了其它代理 / 加速器 / VPN，请先关掉")
        if info.get("age_text"):
            hints.append(f"当前这份请求捕获于 {info['age_text']}")

        return msg + ("（" + "；".join(hints) + "）" if hints else "")

    def _fetch_uid(self):
        """按捕获到的 Authorization 取一次 uid（失败不影响取记录）"""
        from backend import capture as capture_module

        data = capture_module.load_capture() or {}
        authorization = ""
        for key, value in (data.get("headers") or {}).items():
            if str(key).lower() == "authorization":
                authorization = str(value or "")
                break
        if not authorization:
            return None

        account_url = "https://gf2-zoneinfo.sunborngame.com/account/info"
        headers = {
            "Host": "gf2-zoneinfo.sunborngame.com",
            "User-Agent": "UnityPlayer/2019.4.40f1 (UnityWebRequest/1.0, libcurl/7.80.0-DEV)",
            "Accept": "*/*",
            "Accept-Encoding": "deflate, gzip",
            "Authorization": authorization,
            "Content-Type": "application/json",
            "X-Unity-Version": "2019.4.40f1",
        }
        try:
            with requests.Session() as session:
                session.trust_env = False
                response = session.post(account_url, headers=headers, json={}, timeout=10, verify=False)
            if response.status_code == 200:
                account_data = response.json()
                if account_data.get("code") == 0:
                    uid = account_data.get("data", {}).get("uid")
                    print(f"[INFO] 获取到用户UID: {uid}")
                    return uid
                print(f"[ERROR] 获取UID失败: {account_data.get('msg')}")
            else:
                print(f"[ERROR] 获取UID失败，状态码: {response.status_code}")
        except Exception as e:
            print(f"[ERROR] 获取UID失败: {e}")
        return None

    def _ensure_proxy_for_capture(self):
        """确保 mitmproxy 在跑（没在跑就拉起来），返回代理状态供界面提示"""
        from backend.proxy import get_proxy_status

        status = get_proxy_status()
        if status.get("ready"):
            if not status.get("system_proxy"):
                self.enable_system_proxy()
            return get_proxy_status()

        print("[WARN] mitmproxy 未就绪，尝试重新启动代理...")
        self.start_proxy()
        deadline = time.time() + 6.0
        while time.time() < deadline:
            status = get_proxy_status()
            if status.get("ready"):
                break
            time.sleep(0.2)

        self.enable_system_proxy()
        return get_proxy_status()

    def install_cert(self):
        """安装证书 - 首次运行自动生成用户专属证书并自动安装到系统"""
        try:
            from backend.cert_generator import (
                ensure_ca_certificate, 
                generate_user_ca_certificate,
                install_certificate_windows,
                check_certificate_installed_windows,
                get_certificate_info
            )
            import platform
            
            # 检查并生成证书（如果不存在）
            cert_dir, is_new = ensure_ca_certificate()
            if is_new:
                cert_dir = generate_user_ca_certificate()
            
            # 获取证书信息
            cert_path = cert_dir / "mitmproxy-ca-cert.cer"
            if not cert_path.exists():
                cert_path = cert_dir / "mitmproxy-ca-cert.pem"
            
            info = get_certificate_info(cert_path)
            if not info:
                return {
                    "status": "error",
                    "msg": "无法读取证书信息",
                }
            
            cert_name = info['common_name']
            
            # 检查是否已安装
            if platform.system() == "Windows":
                if check_certificate_installed_windows(cert_name):
                    self._enable_proxy_after_cert()
                    return {
                        "status": "success",
                        "msg": "证书已安装，正在启用仅针对游戏抽卡域名的定向代理",
                        "cert_name": cert_name
                    }
                
                # 自动安装证书
                success = install_certificate_windows(cert_path)
                if success:
                    self._enable_proxy_after_cert()
                    return {
                        "status": "success",
                        "msg": "证书安装成功！正在启用仅针对游戏抽卡域名的定向代理",
                        "cert_name": cert_name
                    }
                else:
                    return {
                        "status": "error",
                        "msg": "证书自动安装失败，请手动安装",
                    }
            else:
                # 非Windows系统，打开证书目录让用户手动安装
                import webbrowser
                webbrowser.open(str(cert_dir))
                return {
                    "status": "success",
                    "msg": "非Windows系统，请手动安装证书",
                    "cert_path": str(cert_dir)
                }
                
        except Exception as e:
            print(f"[ERROR] 安装证书失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "msg": f"证书安装失败: {str(e)}",
            }
    
    def uninstall_cert(self):
        """卸载证书 - 仅卸载 gf2gacha_XKL 证书"""
        was_proxy_active = False
        try:
            from backend.cert_generator import (
                uninstall_certificate_windows, 
                check_certificate_installed_windows,
                get_certificate_info
            )
            import platform
            
            if platform.system() != "Windows":
                return {
                    "status": "error",
                    "msg": "仅支持Windows系统卸载证书",
                }
            
            # 获取本工具的证书信息
            cert_dir = Path(__file__).parent / "certs"
            cert_path = cert_dir / "mitmproxy-ca-cert.cer"
            
            if not cert_path.exists():
                return {
                    "status": "error",
                    "msg": "证书文件不存在",
                }
            
            info = get_certificate_info(cert_path)
            if not info or not info['common_name']:
                return {
                    "status": "error",
                    "msg": "无法读取证书信息",
                }
            
            cert_name = info['common_name']
            
            # 检查是否已安装
            if not check_certificate_installed_windows(cert_name):
                return {
                    "status": "success",
                    "msg": "证书未安装，无需卸载",
                }
            
            # 证书卸载后若代理仍指向本工具，目标域名会因证书不受信任而失败。
            # 先恢复用户原来的代理设置；卸载失败时再按原状态恢复定向代理。
            from backend.proxy import close_proxy, get_proxy_status
            was_proxy_active = bool(get_proxy_status().get("system_proxy"))
            if was_proxy_active:
                close_proxy()

            success = uninstall_certificate_windows(cert_name)
            if success:
                return {
                    "status": "success",
                    "msg": "证书卸载成功！",
                }

            if was_proxy_active:
                self._enable_proxy_after_cert()
            return {
                "status": "error",
                "msg": "证书卸载失败",
            }
                
        except Exception as e:
            print(f"[ERROR] 卸载证书失败: {e}")
            import traceback
            traceback.print_exc()
            if was_proxy_active:
                self._enable_proxy_after_cert()
            return {
                "status": "error",
                "msg": f"证书卸载失败: {str(e)}",
            }
    
    def check_cert_status(self):
        """检查证书安装状态"""
        try:
            from backend.cert_generator import (
                check_certificate_installed_windows, 
                get_certificate_info
            )
            import platform
            
            cert_dir = Path(__file__).parent / "certs"
            cert_path = cert_dir / "mitmproxy-ca-cert.cer"
            
            if not cert_path.exists():
                return {
                    "status": "not_generated",
                    "msg": "证书尚未生成",
                    "installed": False
                }
            
            info = get_certificate_info(cert_path)
            if not info:
                return {
                    "status": "error",
                    "msg": "无法读取证书信息",
                    "installed": False
                }
            
            cert_name = info['common_name']
            
            if platform.system() == "Windows":
                installed = check_certificate_installed_windows(cert_name)
                return {
                    "status": "success",
                    "msg": "证书状态查询成功",
                    "installed": installed,
                    "cert_name": cert_name,
                    "valid_from": str(info['valid_from']),
                    "valid_to": str(info['valid_to'])
                }
            else:
                return {
                    "status": "success",
                    "msg": "非Windows系统，请手动检查",
                    "installed": False,
                    "cert_path": str(cert_path)
                }
                
        except Exception as e:
            print(f"[ERROR] 检查证书状态失败: {e}")
            return {
                "status": "error",
                "msg": f"检查证书状态失败: {str(e)}",
                "installed": False
            }
        
    def get_record_list(self):
        """获取所有已保存的记录列表"""
        try:
            print("[INFO] 正在获取记录列表...")
            records_dir = Path(__file__).parent / "records"
            print(f"[INFO] records目录路径: {records_dir}")

            # 如果目录不存在，自动创建
            if not records_dir.exists():
                print("[INFO] records目录不存在，自动创建...")
                records_dir.mkdir(exist_ok=True)
                print("[INFO] records目录创建成功")

            record_files = []
            for file in records_dir.glob("*.json"):
                record_id = file.stem  # 获取文件名（不含.json扩展名）
                record_files.append(record_id)
                print(f"[INFO] 找到记录: {record_id}")

            print(f"[INFO] 共找到 {len(record_files)} 条记录")
            return {
                "status": "success",
                "msg": "获取记录列表成功",
                "data": record_files
            }
        except Exception as e:
            print(f"[ERROR] 获取记录列表失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "msg": f"获取记录列表失败: {e}",
                "data": []
            }

    def import_record(self, record_id):
        try:
            records_dir = Path(__file__).parent / "records"
            input_file = records_dir / f"{record_id}.json"

            if not input_file.exists():
                return {
                    "status": "error",
                    "msg": f"记录文件 {record_id}.json 不存在",
                }

            with open(input_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(data)
            return {
                "status": "success",
                "msg": "导入抽卡记录成功",
                "data": data
            }
        except Exception as e:
            return {
                "status": "error",
                "msg": f"导入抽卡记录失败: {e}",
            }

    def export_record(self, record_id, gacha_data):
        try:
            if not gacha_data:
                return {
                    "status": "error",
                    "msg": "抽卡记录为空",
                }
            records_dir = Path(__file__).parent / "records"
            records_dir.mkdir(exist_ok=True)
            output_file = records_dir / f"{record_id}.json"
            if output_file.exists():
                # 读取现有文件
                with open(output_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                
                # 合并五个池子
                merged_data = {
                    "permanent_pool": self._merge_pool_data(
                        gacha_data.get("permanent_pool", []),
                        existing_data.get("permanent_pool", [])
                    ),
                    "character_pool": self._merge_pool_data(
                        gacha_data.get("character_pool", []),
                        existing_data.get("character_pool", [])
                    ),
                    "weapon_pool": self._merge_pool_data(
                        gacha_data.get("weapon_pool", []),
                        existing_data.get("weapon_pool", [])
                    ),
                    "custom_character_pool": self._merge_pool_data(
                        gacha_data.get("custom_character_pool", []),
                        existing_data.get("custom_character_pool", [])
                    ),
                    "custom_weapon_pool": self._merge_pool_data(
                        gacha_data.get("custom_weapon_pool", []),
                        existing_data.get("custom_weapon_pool", [])
                    )
                }
                gacha_data = merged_data
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(gacha_data, f, ensure_ascii=False, indent=2)
            return {
                "status": "success",
                "msg": "保存抽卡记录成功",
            }
        except Exception as e:
            return {
                "status": "error",
                "msg": "保存抽卡记录失败",
            }
    
    def _generate_fake_id(self, records):
        """
        为每条抽卡记录生成唯一fakeId。
        算法: fakeId = time * 100 + order
        其中order是同一秒(time)内连抽的序号(0~9)。
        参考 gf2gacha_Matcha 项目的 MergeRecord.go:addFakeId()
        """
        if not records:
            return records

        pre_timestamp = None
        order = -1

        for i, record in enumerate(records):
            timestamp = record.get("time", 0)

            if timestamp != pre_timestamp:
                # 时间戳变了 → 新的一抽，order重置为0
                order = 0
            else:
                # 同一秒内的连抽 → order递增
                order += 1
                if order > 9:
                    print(f"[警告] 存在时间戳相同但超过十连的数据: time={timestamp}")

            # fakeId = 时间戳 * 100 + 序号（两位数补零）
            fake_id = timestamp * 100 + order
            record["_fake_id"] = fake_id

            pre_timestamp = timestamp

        return records

    def _merge_pool_data(self, new_pages, old_pages):
        """
        合并池子数据，基于 fakeId 去重（参考 gf2gacha_Matcha 项目）。
        
        算法原理:
        1. 从API原始记录的 time 字段生成 fakeId = time * 100 + order
           (order为同一秒内连抽序号0~9)
        2. 将新旧记录按 fakeId 做 set 去重
        3. 按 fakeId 降序排列（最新在前）
        4. 重建页面结构
        
        优势:
        - 不依赖JSON序列化比对，不受字段顺序/精度影响
        - 不要求连续重叠，任意位置的重复都能检测到
        - 数学上保证唯一性（同一条记录无论获取多少次fakeId不变）
        """
        # === 步骤1: 扁平化记录列表 ===
        new_records = []
        for page in new_pages:
            for record in page.get("data", {}).get("list", []):
                new_records.append(record.copy())  # copy避免污染原始数据

        old_records = []
        for page in old_pages:
            for record in page.get("data", {}).get("list", []):
                old_records.append(record.copy())

        # === 步骤2: 为每条记录生成 fakeId ===
        self._generate_fake_id(new_records)
        self._generate_fake_id(old_records)

        # === 步骤3: 基于 fakeId 去重合并（新数据优先） ===
        seen_ids = set()
        all_records = []

        # 先遍历新记录
        for record in new_records:
            fid = record.get("_fake_id")
            if fid is not None and fid not in seen_ids:
                seen_ids.add(fid)
                # 移除内部标记字段再存入
                del record["_fake_id"]
                all_records.append(record)

        # 再遍历旧记录（补充新记录中没有的）
        for record in old_records:
            fid = record.get("_fake_id")
            if fid is not None and fid not in seen_ids:
                seen_ids.add(fid)
                del record["_fake_id"]
                all_records.append(record)

        # === 步骤4: 按 time 降序排序（最新在前） ===
        all_records.sort(key=lambda r: r.get("time", 0), reverse=True)

        # === 步骤5: 重建页面结构 ===
        return self._rebuild_pages(all_records)

    def _rebuild_pages(self, records):
        """将记录列表重建为页面结构"""
        if not records:
            return []

        pages = []
        current_list = []

        # 按原始页面大小重建（每页6条）
        for i, record in enumerate(records):
            current_list.append(record)
            if (i + 1) % 6 == 0 or i == len(records) - 1:
                page = {
                    "code": 0,
                    "message": "OK",
                    "data": {"list": current_list.copy(), "next": ""}
                }
                pages.append(page)
                current_list = []

        return pages
    
    def _load_version(self):
        """加载本地版本"""
        version_file = Path(__file__).parent / "version.json"
        if version_file.exists():
            with open(version_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"current_version": "1.0.0"}

    # R2 上的五星数据（开发者维护，比内置 json 新；本地游戏数据解析失败时用它兜底）
    SSR_REMOTE_URL = "https://r2.gf2gacha-xkl.uk/ssr.json"

    def _with_non_ssr(self, data):
        """给五星表补充四星物品映射，供统计视图计算原生物品品质。"""
        result = dict(data or {})
        try:
            path = Path(__file__).parent / "json" / "non_ssr.json"
            if path.exists():
                extra = json.loads(path.read_text(encoding="utf-8"))
                result["SR_character"] = extra.get("SR_character", {})
                result["SR_weapon"] = extra.get("SR_weapon", {})
                result["R_weapon"] = extra.get("R_weapon", {})
        except Exception as exc:
            print(f"[SSR] 读取非五星物品表失败: {exc}")
        result.setdefault("SR_character", {})
        result.setdefault("SR_weapon", {})
        return result
    def _load_ssr_data_impl(self):
        """按优先级加载五星数据，返回 (data, source)

        source 取值（前端据此显示不同提示）：
            local-proto  本地游戏数据（最准，跟着游戏版本走） -> 绿色「正在使用最新五星数据」
            remote       R2 远端数据（开发者维护的兜底）      -> 绿色「正在使用远端五星数据」
            local-json   随程序内置的 json（可能不是最新）    -> 黄色「正在使用本地五星数据(可能不是最新)」
            none         一个都拿不到
        """
        # 1. 本地游戏数据（protobuf）
        try:
            from backend.ssr_parser import load_ssr_from_local
            local_result = load_ssr_from_local()
            if local_result is not None:
                print(f"[SSR] ★★★ 使用本地游戏数据，版本: {local_result.get('version')} ★★★")
                return self._with_non_ssr(local_result), "local-proto"
        except Exception as e:
            print(f"[SSR] 本地protobuf解析失败: {e}")

        # 2. R2 远端（兜底）
        remote = self._fetch_remote_ssr()
        if remote is not None:
            print(f"[SSR] ★★★ 使用 R2 远端数据，版本: {remote.get('version')} ★★★")
            return self._with_non_ssr(remote), "remote"

        # 3. 内置 json（最后兜底）
        try:
            local_ssr_path = Path(__file__).parent / "json" / "ssr.json"
            if local_ssr_path.exists():
                with open(local_ssr_path, "r", encoding="utf-8") as f:
                    local_data = json.load(f)
                print(f"[SSR] 使用内置ssr.json（可能不是最新），版本: {local_data.get('version', 'unknown')}")
                return self._with_non_ssr(local_data), "local-json"
        except Exception as e:
            print(f"[SSR] 读取内置ssr.json失败: {e}")

        print("[SSR] 无法获取SSR数据，返回空结构")
        return self._with_non_ssr({
            "version": "none",
            "SSR_character": {},
            "SSR_weapon": {},
            "SSR_permanent": {},
        }), "none"

    def _fetch_remote_ssr(self, timeout=5):
        """从 R2 拉取 ssr.json（超时/断网/格式异常一律返回 None，不影响主流程）"""
        try:
            print(f"[SSR] 尝试从 R2 获取五星数据: {self.SSR_REMOTE_URL}")
            with requests.Session() as session:
                session.trust_env = False
                response = session.get(self.SSR_REMOTE_URL, timeout=timeout)
            if response.status_code != 200:
                print(f"[SSR] R2 返回 HTTP {response.status_code}，忽略")
                return None
            data = response.json()
            if not isinstance(data, dict) or not data.get("SSR_character"):
                print("[SSR] R2 数据格式异常，忽略")
                return None
            return data
        except Exception as e:
            print(f"[SSR] R2 获取失败: {e}")
            return None

    def _load_ssr_data(self):
        """启动时加载SSR数据（兼容旧接口：只返回数据）"""
        data, source = self._load_ssr_data_impl()
        print(f"[SSR] 数据来源: {source}")
        return data

    def load_ssr_data(self):
        """前端调用加载SSR数据：返回 {status, source, data}"""
        print("[SSR] 前端请求加载SSR数据...")
        data, source = self._load_ssr_data_impl()
        data = dict(data)
        data['_fromRemote'] = source in ("local-proto", "remote")
        self.ssr_data = data
        print(f"[SSR] 数据来源: {source}")
        if source == "none":
            return {"status": "error", "source": "none", "data": self.ssr_data}
        return {"status": "success", "source": source, "data": self.ssr_data}

    def get_ssr_data(self):
        """供前端调用获取SSR数据（仅返回当前数据）"""
        return {
            "status": "success",
            "data": self.ssr_data
        }

    def get_startup_ssr_data(self):
        """先返回内置表；慢解析和网络刷新只运行一个后台任务。"""
        with self._ssr_lock:
            if not self._ssr_refresh_started and not self._closing.is_set():
                self._ssr_refresh_started = True
                try:
                    path = Path(__file__).parent / 'json' / 'ssr.json'
                    data = self._with_non_ssr(json.loads(path.read_text(encoding='utf-8')))
                    if not isinstance(data, dict) or not data.get('SSR_character'):
                        raise ValueError('内置五星表无效')
                    self.ssr_data = data
                    self._ssr_source = 'local-json'
                except Exception as exc:
                    print(f'[STARTUP] 读取内置五星表失败: {exc}')

                def refresh():
                    started = time.monotonic()
                    try:
                        data, source = self._load_ssr_data_impl()
                        with self._ssr_lock:
                            if not self._closing.is_set() and source != 'none':
                                self.ssr_data = dict(data)
                                self._ssr_source = source
                    except Exception as exc:
                        print(f'[STARTUP] 五星表后台刷新失败: {exc}')
                    finally:
                        with self._ssr_lock:
                            self.ssr_loading = False
                        print(f'[STARTUP] 五星表刷新结束，耗时 {time.monotonic() - started:.2f}s')

                self._ssr_thread = threading.Thread(target=refresh, daemon=True, name='ssr-refresh')
                self._ssr_thread.start()
            return {
                'status': 'success' if self._ssr_source != 'none' else 'error',
                'source': self._ssr_source,
                'data': self.ssr_data,
                'refreshing': self.ssr_loading and not self._closing.is_set(),
            }

    # ------------------------------------------------------------------
    # 自绘标题栏窗口控制
    # ------------------------------------------------------------------
    def window_minimize(self):
        """最小化当前窗口。"""
        if self.window:
            self.window.minimize()
        return {"status": "success", "maximized": self._window_maximized}

    def window_toggle_maximize(self):
        """最大化 / 还原当前窗口。"""
        if not self.window:
            return {"status": "error", "message": "窗口尚未就绪"}
        if self._window_maximized:
            self.window.restore()
            self._window_maximized = False
        else:
            self.window.maximize()
            self._window_maximized = True
        return {"status": "success", "maximized": self._window_maximized}

    def window_close(self):
        """关闭当前窗口，on_closed 会统一恢复系统代理。"""
        if self.window:
            self.window.destroy()
        return {"status": "success"}

    def _create_js_api(self):
        """只暴露前端使用的方法，避免桥接反射进入原生窗口及线程。"""
        names = (
            'get_startup_ssr_data', 'get_ssr_data', 'load_ssr_data',
            'get_capture_status', 'get_record_list', 'get_version_info',
            'get_gacha', 'export_record', 'import_record',
            'install_cert', 'uninstall_cert', 'open_github', 'open_log_file',
            'prefetch_share_images', 'get_cached_images', 'copy_image_to_clipboard',
            'get_update_status', 'mark_update_ok', 'dismiss_update_status',
            'rollback_update', 'start_update',
            "get_announcement", 'mark_announcement_seen',
            'get_key_export_status', 'start_key_export', 'copy_key_to_clipboard',
            'get_community_status', 'bind_community', 'community_one_click',
            'window_minimize', 'window_toggle_maximize', 'window_close',
        )
        return SimpleNamespace(**{name: getattr(self, name) for name in names})

    pass

    def _cleanup_old_updater(self):
        """清理旧的更新器文件"""
        try:
            # 在打包后的环境中，updater_old.exe 在 _internal 目录
            if getattr(sys, 'frozen', False):
                base_path = Path(sys.executable).parent / "_internal"
            else:
                base_path = Path(__file__).parent
            
            old_updater = base_path / "updater_old.exe"
            if old_updater.exists():
                old_updater.unlink()
                print(f"[INFO] 已清理旧更新器: {old_updater}")
            # 新布局：更新器在安装根目录，残留的 updater_old.exe 也在那儿
            root_old = _app_root() / "updater_old.exe"
            if root_old.exists() and root_old != old_updater:
                root_old.unlink()
                print(f"[INFO] 已清理旧更新器: {root_old}")
            # 一次性迁移：老版本把 updater.exe 放在 _internal 里，新布局用它外面那份；
            # 里面那份留着也没用了（还占 12MB），根目录有新的就删掉
            root_updater = _app_root() / "updater.exe"
            internal_updater = base_path / "updater.exe"
            if root_updater.exists() and internal_updater.exists():
                internal_updater.unlink()
                print(f"[INFO] 已清理 _internal 里多余的更新器: {internal_updater}")
        except Exception as e:
            print(f"[WARNING] 清理旧更新器失败: {e}")
    
    def check_update(self):
        """检查更新（直连 R2，不修改系统代理）"""
        print("=" * 50)
        print("[UPDATE] 开始检查更新...")
        print(f"[UPDATE] 版本检查URL: {self.version_url}")

        try:
            print("[UPDATE] 正在请求 r2...")
            # 程序自身请求固定直连，不读取 Windows 注册表代理。
            with requests.Session() as session:
                session.trust_env = False
                response = session.get(self.version_url, timeout=8)
                response.raise_for_status()
                remote_data = response.json()
            print(f"[UPDATE] HTTP状态码: {response.status_code}")
            print(f"[UPDATE] 远程数据: {remote_data}")

            remote_version = remote_data.get("current_version", "1.0.0")
            print(f"[UPDATE] remote_version: {remote_version}")

            local_version = self.version.get("current_version", "1.0.0")
            print(f"[UPDATE] local_version: {local_version}")

            if _version_tuple(remote_version) > _version_tuple(local_version):
                print("[UPDATE] 发现新版本！")
                return {
                    "status": "success",
                    "has_update": True,
                    "latest_version": remote_version,
                    "download_url": remote_data.get("download_url", ""),
                    "sha256": remote_data.get("sha256", ""),
                    "size": remote_data.get("size", 0),
                    "notes": remote_data.get("update_info", ""),
                    "message": f"发现新版本 v{remote_version}"
                }

            print("[UPDATE] 当前已是最新版本")
            return {
                "status": "success",
                "has_update": False,
                "message": "当前已是最新版本"
            }
        except requests.exceptions.Timeout as e:
            print(f"[UPDATE] 请求超时: {e}")
            return {
                "status": "error",
                "has_update": False,
                "message": "连接超时，请稍后重试"
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[UPDATE] 连接错误: {e}")
            return {
                "status": "error",
                "has_update": False,
                "message": "网络连接失败，请检查网络"
            }
        except Exception as e:
            print(f"[UPDATE] 未知错误: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "has_update": False,
                "message": f"检查更新失败: {str(e)}"
            }

    def start_update(self):
        """启动更新器并关闭主程序"""
        print("=" * 50)
        print("[UPDATE] 准备启动更新器...")
        
        try:
            import subprocess
            
            # 更新器位置：新布局在安装根目录，老布局在 _internal 里（兼容）
            candidates = [_app_root() / "updater.exe", _app_root() / "_internal" / "updater.exe"]
            updater_path = next((path for path in candidates if path.exists()), None)
            if updater_path is None:
                print(f"[ERROR] 更新器不存在: {candidates}")
                return {
                    "status": "error",
                    "message": "更新器文件不存在"
                }

            # 把"要更新到什么版本、包在哪、sha256 是多少"先写进状态文件，
            # 更新器读它来干活（也方便下次启动时判断上次更新走到哪一步）
            info = self._pending_update or {}
            _write_update_state(
                phase="starting",
                **{
                    "from": self.version.get("current_version", ""),
                    "to": info.get("latest_version", ""),
                    "download_url": info.get("download_url", ""),
                    "sha256": info.get("sha256", ""),
                    "size": info.get("size", 0),
                    "error": "",
                },
            )
            print(f"[UPDATE] 更新意图已写入状态文件: {_update_state_path()}")
            print(f"[UPDATE] 更新器路径: {updater_path}")
            
            # 启动更新器（独立进程）
            subprocess.Popen(
                [str(updater_path)],
                cwd=str(_app_root()),
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
            
            print("[UPDATE] 更新器已启动，主程序即将退出...")
            
            # 关闭主程序；on_closed 会统一停止代理并恢复用户原来的系统代理。
            if self.window:
                self.window.destroy()
            
            return {
                "status": "success",
                "message": "更新器已启动"
            }
            
        except Exception as e:
            print(f"[ERROR] 启动更新器失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "message": f"启动更新器失败: {str(e)}"
            }

    
    def _is_newer(self, remote, local):
        """简单的版本号比较"""
        try:
            return [int(x) for x in remote.split(".")] > [int(x) for x in local.split(".")]
        except:
            return False
    
    def get_version_info(self):
        """获取版本信息"""
        print("=" * 50)
        print("[UPDATE] 开始获取版本信息...")
        try:
            # 检查更新
            update_result = self.check_update()
            local_version = self.version.get("current_version", "1.0.0")
            self._pending_update = update_result if update_result.get("has_update") else {}
            
            if update_result.get("status") != "success":
                return {
                    "status": "error",
                    "current_version": local_version,
                    "has_update": False,
                    "latest_version": "",
                    "message": update_result.get("message", "检查更新失败")
                }
            
            return {
                "status": "success",
                "current_version": local_version,
                "has_update": update_result.get("has_update", False),
                "latest_version": update_result.get("latest_version", ""),
                "sha256": update_result.get("sha256", ""),
                "size": update_result.get("size", 0),
                "notes": update_result.get("notes", ""),
                "message": update_result.get("message", "")
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"获取版本信息失败"
            }
    
    def create_temp_png_file(self):
        """创建临时 PNG 文件并返回路径"""
        import tempfile
        import os
        fd, path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        # 确保文件为空（用于后续写入）
        with open(path, 'wb') as f:
            pass
        print(f"[DEBUG] 创建临时文件: {path}")
        return path

    def write_chunk_to_file(self, file_path, offset, b64_chunk):
        """将 base64 编码的数据块写入文件指定偏移位置"""
        try:
            import base64
            chunk_bytes = base64.b64decode(b64_chunk)
            with open(file_path, 'r+b') as f:
                f.seek(offset)
                f.write(chunk_bytes)
            return {"status": "success", "written": len(chunk_bytes)}
        except Exception as e:
            print(f"[ERROR] 写入文件块失败 (offset={offset}): {e}")
            return {"status": "error", "message": str(e)}

    def prefetch_share_images(self, urls=None):
        """预热分享用的图标缓存（前端在数据加载完后调用，后台线程执行）

        分享真正慢的是「每张图标都要重新下载」，所以数据一到位就先把图标拉下来
        存进缓存，用户点「分享」时基本是纯本地操作。
        """
        try:
            from backend import icon_cache

            url_list = [u for u in (urls or []) if isinstance(u, str) and u.startswith("http")]
            url_list = list(dict.fromkeys(url_list))[:500]
            if not url_list:
                return {"status": "success", "msg": "没有需要预热的图标", "count": 0}

            def run():
                try:
                    icon_cache.prefetch(url_list, workers=8)
                except Exception as exc:
                    print(f"[分享] 图标预热失败: {exc}")

            threading.Thread(target=run, daemon=True).start()
            print(f"[分享] 已开始后台预热 {len(url_list)} 个图标")
            return {"status": "success", "msg": f"已开始预热 {len(url_list)} 个图标", "count": len(url_list)}
        except Exception as e:
            print(f"[ERROR] 预热图标失败: {e}")
            return {"status": "error", "msg": f"预热图标失败: {e}"}

    def get_cached_images(self, urls=None):
        """批量返回角色/武器图片 data URI；磁盘缓存命中时不访问网络。"""
        try:
            from backend import icon_cache
            url_list = [u for u in (urls or []) if isinstance(u, str) and u.startswith("http")]
            if not url_list:
                return {"status": "success", "images": {}, "count": 0}
            images = icon_cache.get_data_uris(url_list, workers=8)
            return {
                "status": "success",
                "images": images,
                "count": len(images),
                "missing": max(0, len(set(url_list)) - len(images)),
            }
        except Exception as exc:
            print(f"[ERROR] 读取图片缓存失败: {exc}")
            return {"status": "error", "message": str(exc), "images": {}}
    def copy_image_to_clipboard(self, _unused=None):
        """把分享图生成好并复制到剪贴板

        步骤：
            ① 收集离屏分享容器里的图标 -> 统一转成 data URI
               （走 backend/icon_cache：内存 + 磁盘缓存，预热过就几乎零耗时）
            ② 注入容器（html2canvas 只能画同源的 data URI）
            ③ html2canvas 出图
            ④ 写入系统剪贴板

        相对旧版的优化：
            * 图标不再每次重新下载（旧版分享一次要下载一百多张，实测每张 1.6s）；
            * 轮询只读一个小标志位，最后才取一次大 base64
              （旧版每 0.5 秒就把整张图通过 JS 桥拉一次）；
            * PowerShell 加 -NoProfile -NonInteractive，省掉几百毫秒启动开销；
            * 全程打点，日志里能直接看到每一步花了多久。
        """
        try:
            import base64
            import subprocess
            import tempfile
            import time

            from backend import icon_cache

            started = time.time()

            # ============================================================
            # 步骤1：收集图片并转成 data URI（带缓存）
            # ============================================================
            # 只收集「这次会被拍进去」的图片：未勾选的池子用 v-show 隐藏了
            # （display:none），它们的图标不必参与（预热时仍然会下载，不影响）
            img_list = self.window.evaluate_js("""
                (function() {
                    var el = document.querySelector('.screenshot-container');
                    if (!el) return null;
                    var imgs = el.querySelectorAll('img');
                    var list = [];
                    var skipped = 0;
                    Array.prototype.forEach.call(imgs, function(img, idx) {
                        if (!img.offsetParent) { skipped++; return; }
                        list.push({index: idx, src: img.src || ''});
                    });
                    return {total: list.length, skipped: skipped, images: list};
                })()
            """)

            if not img_list:
                return {"status": "error", "message": "无法获取图片列表或容器不存在"}

            unique_srcs = []
            for img_info in img_list["images"]:
                src = img_info.get("src") or ""
                if src and not src.startswith("data:") and src not in unique_srcs:
                    unique_srcs.append(src)

            cached_hits = sum(1 for src in unique_srcs if icon_cache.is_cached(src))
            print(
                f"[分享] 参与出图的图片 {img_list['total']} 张"
                f"（未勾选池子跳过 {img_list.get('skipped', 0)} 张）"
                f" / {len(unique_srcs)} 个唯一地址，其中缓存命中 {cached_hits} 个"
            )

            src_to_datauri = {}
            failed = []
            for src in unique_srcs:
                data_uri = icon_cache.get_data_uri(src)
                if data_uri:
                    src_to_datauri[src] = data_uri
                else:
                    failed.append(src)

            print(
                f"[分享] 图标就绪 {len(src_to_datauri)}/{len(unique_srcs)}"
                f"（缓存命中 {cached_hits}，新下载 {len(src_to_datauri) - cached_hits}），"
                f"用时 {time.time() - started:.2f}s"
            )

            if failed:
                # 触发组件的错误兜底，替换掉失败的远程图片，分享仍能保留完整记录。
                print(f"[分享] {len(failed)} 张图标未取到，使用文字占位")
                self.window.evaluate_js(f"""
                    (function() {{
                        var failed = {json.dumps(failed)};
                        document.querySelectorAll('.screenshot-container img').forEach(function(img) {{
                            if (failed.includes(img.src)) img.dispatchEvent(new Event('error'));
                        }});
                    }})()
                """)

            # ============================================================
            # 步骤2：注入 data URI
            # ============================================================
            if src_to_datauri:
                js_map = json.dumps(src_to_datauri)
                self.window.evaluate_js(f"""
                    (function() {{
                        var map = {js_map};
                        var el = document.querySelector('.screenshot-container');
                        if (!el) return;
                        var imgs = el.querySelectorAll('img');
                        var n = 0;
                        Array.prototype.forEach.call(imgs, function(img) {{
                            if (img.src && map[img.src]) {{ img.src = map[img.src]; n++; }}
                        }});
                        window.__screenshot_injected = n;
                    }})()
                """)

            # ============================================================
            # 步骤3：html2canvas 出图（完成时只置一个标志位）
            # ============================================================
            self.window.evaluate_js("""
                (function() {
                    window.__screenshot_ready = false;
                    window.__screenshot_result = null;
                    window.__screenshot_error = null;

                    var el = document.querySelector('.screenshot-container');
                    if (!el) { window.__screenshot_error = '容器不存在'; window.__screenshot_ready = true; return; }
                    var h2c = window.html2canvas;
                    if (!h2c) { window.__screenshot_error = 'html2canvas未加载'; window.__screenshot_ready = true; return; }

                    h2c(el, {
                        scale: 2,
                        useCORS: true,
                        allowTaint: false,
                        backgroundColor: '#ffffff',
                        width: el.scrollWidth,
                        height: el.scrollHeight,
                        logging: false
                    }).then(function(canvas) {
                        return new Promise(function(resolve, reject) {
                            canvas.toBlob(function(blob) {
                                if (!blob) { reject('toBlob failed'); return; }
                                var reader = new FileReader();
                                reader.onload = function() { resolve(reader.result); };
                                reader.readAsDataURL(blob);
                            }, 'image/png');
                        });
                    }).then(function(dataUrl) {
                        window.__screenshot_result = dataUrl;
                        window.__screenshot_ready = true;
                    }).catch(function(e) {
                        window.__screenshot_error = (e && e.message) ? e.message : String(e);
                        window.__screenshot_ready = true;
                    });
                })()
            """)

            # ============================================================
            # 步骤4：等完成标志（每 0.25s 只读一个布尔值，很便宜）
            # ============================================================
            ready = False
            for _ in range(160):  # 最多 40 秒
                time.sleep(0.25)
                if self.window.evaluate_js("window.__screenshot_ready === true"):
                    ready = True
                    break

            error = self.window.evaluate_js("window.__screenshot_error")
            if error:
                return {"status": "error", "message": f"截图失败: {error}"}
            if not ready:
                return {"status": "error", "message": "截图超时"}

            data_url = self.window.evaluate_js("window.__screenshot_result")
            if not data_url or not isinstance(data_url, str) or "," not in data_url:
                return {"status": "error", "message": f"获取截图失败 (result={str(data_url)[:60]})"}

            image_bytes = base64.b64decode(data_url.split(",", 1)[1])
            if image_bytes[:4] != bytes([0x89, 0x50, 0x4E, 0x47]):
                return {"status": "error", "message": f"非PNG格式 (hex: {image_bytes[:4].hex()})"}
            print(f"[分享] 截图完成 {len(image_bytes)} bytes，用时 {time.time() - started:.2f}s")

            # ============================================================
            # 步骤5：写剪贴板
            # ============================================================
            fd, file_path = tempfile.mkstemp(suffix=".png")
            with os.fdopen(fd, "wb") as fh:
                fh.write(image_bytes)

            ps_cmd = (
                'Add-Type -AssemblyName System.Windows.Forms; '
                'Add-Type -AssemblyName System.Drawing; '
                f'$img = [System.Drawing.Image]::FromFile("{file_path}"); '
                '[System.Windows.Forms.Clipboard]::SetImage($img); '
                '$img.Dispose()'
            )
            try:
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                    capture_output=True, text=True, timeout=20,
                )
                if result.returncode != 0:
                    return {"status": "error", "message": f"PowerShell失败: {result.stderr.strip()}"}
            finally:
                try:
                    os.unlink(file_path)
                except OSError:
                    pass

            print(f"[分享] 已复制到剪贴板，总用时 {time.time() - started:.2f}s")
            return {"status": "success", "message": "已复制到剪贴板"}

        except Exception as e:
            print(f"[ERROR] 复制图片失败: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": f"复制失败: {str(e)}"}

    def open_github(self):
        try:
            webbrowser.open("https://github.com/HeiK-Nymph/gf2gacha_XKL")
            return {
                "status": "success",
                "message": "已打开GitHub主页"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": "打开GitHub主页失败"
            }
        
    def _enable_proxy_after_cert(self):
        """证书刚安装/已确认后，后台启用定向代理，避免阻塞 UI 线程。"""
        try:
            threading.Thread(
                target=self.enable_system_proxy,
                daemon=True,
                name="proxy-after-cert",
            ).start()
        except Exception as exc:
            print(f"[WARN] 启动证书后代理任务失败: {exc}")

    def enable_system_proxy(self):
        """把系统代理指向本机 mitmproxy

        代理没就绪或证书未安装时绝不乱设；mitmproxy 只解密抽卡域名，
        其余流量原样透传，所以其它网站照常可用。
        """
        from backend.proxy import set_proxy, get_proxy_status

        if self._closing.is_set():
            return False
        status = get_proxy_status()
        port = status.get("port")
        if not status.get("ready") or not port:
            print(f"[WARN] mitmproxy 未就绪，跳过系统代理设置 (state={status})")
            return False
        try:
            if set_proxy('127.0.0.1', port) is False:
                return False
            print(f"[OK] 系统代理已启用: 127.0.0.1:{port}，仅游戏抽卡域名会被解密")
            return True
        except Exception as e:
            print(f"[ERROR] 开启系统代理失败: {e}")
            return False

    def load_frontend(self):
        """加载Vue前端"""
        # 获取前端构建目录
        frontend_dir = Path(__file__).parent / "frontend" / "dist"
        index_path = frontend_dir / "index.html"
        
        if not index_path.exists():
            print("[ERROR] 前端未构建，请先运行: npm run build")
            return None
            
        # 使用绝对路径
        url = f"file://{index_path.absolute()}"
        print(f"[INFO] 加载前端: {url}")
        return url
    
    def start_proxy(self):
        """在子线程中启动mitmproxy（幂等：重复调用不会起第二个实例）"""
        with self._proxy_lock:
            if self._closing.is_set():
                return False
            if self.proxy_thread is not None and self.proxy_thread.is_alive():
                print("[INFO] mitmproxy 已在运行，跳过重复启动")
                return False

            from backend.proxy import run_proxy
            from backend.addons.addons import set_event_handler

            def run():
                # 设置事件处理器：捕获到游戏请求时回调本对象的 on_request
                set_event_handler(self)

                print("[INFO] 启动mitmproxy代理...")
                try:
                    self.proxy_running = True
                    asyncio.run(run_proxy(8080, stop_event=self._closing))
                except Exception as e:
                    print(f"[ERROR] 代理启动失败: {e}")
                finally:
                    self.proxy_running = False

            self.proxy_thread = threading.Thread(target=run, daemon=True)
            self.proxy_thread.start()
            return True

    def _purge_expired_icon_cache(self, stage: str):
        """清理超过 24 小时的图片缓存；任何失败都不影响启动或退出。"""
        try:
            from backend import icon_cache
            stats = icon_cache.purge_expired()
            if stats.get('removed'):
                freed_kb = stats.get('freed_bytes', 0) / 1024
                print(
                    f"[icon-cache] {stage}清理完成: {stats['removed']} 个文件 / "
                    f"{freed_kb:.1f} KB / {stats.get('seconds', 0):.3f}s"
                )
            if stats.get('failed'):
                print(f"[icon-cache] {stage}清理有 {stats['failed']} 个文件失败，已跳过")
        except Exception as exc:
            print(f"[icon-cache] {stage}清理失败，已跳过: {exc}")

    def on_closed(self):
        """窗口关闭：恢复系统代理 + 清除捕获的请求

        捕获文件里有 Authorization，所以按「关掉软件就自动清除」的行为处理
        （界面上不再需要「清除捕获」按钮）。
        """
        self._closing.set()
        try:
            from backend.proxy import stop_proxy
            stop_proxy()
            if self.proxy_thread and self.proxy_thread is not threading.current_thread():
                self.proxy_thread.join(timeout=2)
                if self.proxy_thread.is_alive():
                    print('[SHUTDOWN] 代理清理超过2秒，不再等待后台线程')
        except Exception as exc:
            print(f'[SHUTDOWN] 代理清理失败: {exc}')
        self.proxy_running = False

        try:
            from backend import capture
            result = capture.clear_capture()
            info = capture.describe_capture()
            print(f"[INFO] 退出时已清除捕获: {result.get('status')} / size={info['size']}")
        except Exception as e:
            print(f"[WARNING] 清除捕获失败: {e}")

        self._purge_expired_icon_cache('退出时')

        print("[INFO] 应用关闭")

    def on_request(self, request_data):
        """mitmproxy 捕获到游戏请求时的回调（运行在代理线程里）"""
        try:
            if self._closing.is_set():
                return
            with self._capture_lock:
                self.last_capture = {
                    "at": datetime.now().strftime("%H:%M:%S"),
                    "url": request_data.get("url"),
                }
            print("[INFO] 已捕获游戏抽卡请求，现在可以点『更新记录』了")
        except Exception as e:
            print(f"[WARNING] 记录捕获状态失败: {e}")

    def get_capture_status(self):
        """给界面用的状态：代理是否就绪 + 最后一次捕获（前端定时轮询）"""
        from backend import capture
        from backend.proxy import get_proxy_status

        try:
            info = capture.describe_capture()
        except Exception as e:
            info = {"exists": False, "error": str(e)}
        try:
            proxy = get_proxy_status()
        except Exception as e:
            proxy = {"error": str(e)}
        with self._capture_lock:
            last_seen = self.last_capture

        return {
            "status": "success",
            "proxy": proxy,
            "proxy_running": self.proxy_running,
            "capture": info,
            "last_seen": last_seen,
            "hint": capture.HINT_OPEN_GACHA_PAGE,
            "log_path": str(_log_path) if _log_path else "",
        }

    # ---------------------------------------------------------------- 社区签到 / 任务 / 兑换

    def _community_error(self, exc):
        print(f"[ERROR] 社区操作失败: {type(exc).__name__}: {exc}")
        return {"status": "error", "msg": str(exc) or "社区操作失败"}

    def get_community_status(self):
        """社区快照（只读，不会在首次使用时偷偷换票）。

        * 令牌有效 → 直接返回；
        * 以前绑过但令牌过期 → 有游戏凭证就自动续期（无感）；
        * 从未绑定 → 返回未绑定，由「绑定社区」按钮显式触发。
        """
        from backend import community

        try:
            account = community.load_account()
            if community.token_valid(account):
                return {"status": "success", "data": community.snapshot(str(account.get("token") or ""))}

            if not account:
                return {
                    "status": "success",
                    "data": {
                        "ok": False,
                        "bound": False,
                        "message": "尚未绑定：先在游戏里打开「招募 · 访问详情」并点一次「更新记录」，再点「绑定社区」。",
                    },
                }

            if not community.game_token_from_capture():
                return {
                    "status": "success",
                    "data": {
                        "ok": False,
                        "bound": False,
                        "message": "社区令牌已过期，且没有新的游戏凭证：请在游戏里打开「招募 · 访问详情」，回到工具点「更新记录」后再绑定。",
                    },
                }

            account = community.bind()  # 仅「已过期」这一种情况自动续期
            return {"status": "success", "data": community.snapshot(str(account.get("token") or ""))}
        except community.CommunityError as exc:
            return {"status": "error", "code": exc.code, "msg": exc.message}
        except Exception as exc:
            return self._community_error(exc)

    def bind_community(self):
        """手动绑定：用当前捕获的游戏 access_token 换社区 JWT。"""
        from backend import community

        try:
            account = community.bind()
            return {"status": "success", "data": community.snapshot(str(account.get("token") or ""))}
        except community.CommunityError as exc:
            return {"status": "error", "code": exc.code, "msg": exc.message}
        except Exception as exc:
            return self._community_error(exc)

    def community_one_click(self):
        """按钮入口：签到 → 每日任务 → 兑换。"""
        from backend import community

        try:
            return {"status": "success", "data": community.one_click()}
        except community.CommunityError as exc:
            return {"status": "error", "code": exc.code, "msg": exc.message}
        except Exception as exc:
            return self._community_error(exc)

    # ---------------------------------------------------------------- 小程序导入钥匙

    def get_key_export_status(self):
        """给界面用：钥匙导出的无网络预览（捕获状态 / 渠道 / 凭证过期时间）"""
        from backend import key_export

        try:
            return key_export.get_key_export_status()
        except Exception as e:
            print(f"[ERROR] 读取钥匙导出状态失败: {type(e).__name__}")
            return {"ok": False, "error": {"kind": "internal", "msg": f"内部异常: {e}"}}

    def start_key_export(self, uid=None):
        """核验捕获的凭证；通过后暂存在后端内存，等用户点「复制」再写剪贴板"""
        from backend import key_export

        try:
            result = key_export.start_key_export(uid)
        except Exception as e:
            print(f"[ERROR] 钥匙导出核验异常: {type(e).__name__}")
            result = {"ok": False, "error": {"kind": "internal", "msg": f"内部异常: {e}"}}
        if not result.get("ok"):
            error = result.get("error") or {}
            return {
                "status": "error",
                "code": error.get("kind", "unknown"),
                "msg": self._describe_key_error(error),
            }
        return {
            "status": "success",
            "msg": "凭证核验通过",
            "data": {key: value for key, value in result.items() if key != "ok"},
        }

    def copy_key_to_clipboard(self):
        """把核验通过的钥匙写进剪贴板（不再发网络请求；钥匙不落盘、不进日志、不回传前端）"""
        from backend import key_export

        try:
            result = key_export.copy_key_to_clipboard()
        except Exception as e:
            print(f"[ERROR] 钥匙复制异常: {type(e).__name__}")
            result = {"ok": False, "error": {"kind": "internal", "msg": f"内部异常: {e}"}}
        if not result.get("ok"):
            error = result.get("error") or {}
            return {
                "status": "error",
                "code": error.get("kind", "unknown"),
                "msg": self._describe_key_error(error),
            }
        return {
            "status": "success",
            "msg": "钥匙已复制到剪贴板。打开微信小程序「夏克里助手」→ 抽卡分析 → 粘贴即可导入"
                   "（钥匙是短期凭证，导入完成后不要保存）",
        }

    def _describe_key_error(self, error):
        """把钥匙导出的结构化错误翻译成用户能照做的提示（口径对齐 _describe_replay_error）"""
        kind = error.get("kind")
        msg = error.get("msg") or "无描述"
        if kind == "token":
            return (f"凭证已过期或已失效（同账号在其他设备重新登录也会作废）：{msg}。"
                    "请在游戏里重新打开一次「招募 · 访问详情」页面后再导出")
        if kind == "network":
            return f"网络请求失败：{msg}。请检查网络；如果开了其它代理 / 加速器 / VPN，请先关掉"
        if kind == "http":
            return (f"官方接口异常：{msg}。请稍后重试；若持续失败，"
                    "请在游戏里重新打开「招募 · 访问详情」页面刷新凭证")
        if kind in ("parse", "api"):
            return f"官方接口返回异常：{msg}"
        if kind == "internal":
            return f"内部异常：{msg}"
        # no_capture / bad_capture / format / uid_required / uid_mismatch /
        # capture_changed / no_verified / clipboard 的 msg 在 key_export 里已是可照做的人话
        return msg

    def get_update_status(self):
        """给界面用：上次更新走到哪一步、要不要提示用户"""
        state = _read_update_state()
        phase = state.get("phase") or ""
        needs_attention = phase in (
            "starting", "downloading", "verified", "extracted", "switching",
            "switched", "failed", "rolled_back",
        )
        # 回滚备份还在 -> 可以一键回滚（新版已经被换掉了就没有了）
        can_rollback = (_app_root() / "_internal_old").exists() and phase not in ("rolled_back",)
        if needs_attention:
            print(f"[UPDATE] 上次更新未完成: phase={phase} error={state.get('error') or '无'}")
        return {
            "status": "success",
            "phase": phase,
            "needs_attention": needs_attention,
            "rolled_back": phase == "rolled_back",
            "can_rollback": can_rollback,
            "from": state.get("from") or "",
            "to": state.get("to") or "",
            "error": state.get("error") or "",
            "updated_at": state.get("updated_at") or "",
            "updater_log": str(Path(__file__).parent / "logs" / "updater.log"),
        }

    def rollback_update(self):
        """一键回滚：拉起 updater.exe --rollback，然后关掉自己（不然 _internal 改不了名）"""
        try:
            candidates = [_app_root() / "updater.exe", _app_root() / "_internal" / "updater.exe"]
            updater_path = next((path for path in candidates if path.exists()), None)
            if updater_path is None:
                return {"status": "error", "msg": "找不到更新器，无法回滚"}
            if not (_app_root() / "_internal_old").exists():
                return {"status": "error", "msg": "没有可用的回滚备份"}

            _write_update_state(phase="rollback_requested")
            subprocess.Popen(
                [str(updater_path), "--rollback", "--reason", "用户在界面上选择回滚"],
                cwd=str(_app_root()),
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            print("[UPDATE] 已启动回滚流程，主程序即将退出")
            # 与正常更新一致，由 on_closed 统一恢复代理，避免重复切换。
            if self.window:
                self.window.destroy()
            return {"status": "success", "msg": "正在回滚"}
        except Exception as e:
            print(f"[ERROR] 启动回滚失败: {e}")
            return {"status": "error", "msg": f"启动回滚失败: {e}"}

    def mark_update_ok(self):
        """主程序界面成功启动时调用：更新流程收尾（写 ok + 清理备份/临时文件）"""
        state = _read_update_state()
        if not state or state.get("phase") == "ok":
            return {"status": "success", "cleaned": []}

        app_root = _app_root()
        # 先落 ok：万一下面清理到一半崩了，也不会让用户下次启动看到"更新未完成"
        _write_update_state(phase="ok", error="")

        cleaned = []
        # 回滚备份：新版已经成功跑起来，可以删了（不占用户空间）
        for leftover in (app_root / "_internal_old", app_root / "_internal_broken",
                         app_root / "_update_tmp", app_root / "update_temp",
                         app_root / "records_backup_temp", app_root / "certs_backup_temp",
                         app_root / "updater_old.exe"):
            if leftover.exists():
                try:
                    if leftover.is_dir():
                        shutil.rmtree(leftover, ignore_errors=True)
                    else:
                        leftover.unlink()
                    cleaned.append(leftover.name)
                except Exception as e:
                    print(f"[WARNING] 清理 {leftover} 失败: {e}")

        if cleaned:
            print(f"[UPDATE] 更新流程收尾完成，已清理: {', '.join(cleaned)}")
        else:
            print("[UPDATE] 更新流程收尾完成（没有需要清理的残留）")
        return {"status": "success", "cleaned": cleaned}

    def dismiss_update_status(self):
        """用户点了"我知道了"：不要再重复提示同一次未完成的更新"""
        _write_update_state(phase="acknowledged")
        return {"status": "success"}

    def open_log_file(self, which="app"):
        """用系统默认程序直接打开日志文件（logs/app.log）

        界面上「日志」窗口里的「打开日志文件」按钮走这里：不再另开 HTML 窗口，
        就是让 Windows 用它默认的程序（通常是记事本）打开这个文件。
        """
        try:
            from backend import applog

            log_path = Path(applog.get_log_path() or (Path(__file__).parent / "logs" / "app.log"))
            if which == "updater":
                log_path = Path(__file__).parent / "logs" / "updater.log"
            if not log_path.exists():
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.touch(exist_ok=True)
            if os.name == "nt":
                os.startfile(str(log_path))  # noqa: S606 - 固定路径，非用户输入
            else:
                webbrowser.open(f"file://{log_path.absolute()}")
            print(f"[INFO] 已打开日志文件: {log_path}")
            return {"status": "success", "msg": "已打开日志文件", "path": str(log_path)}
        except Exception as e:
            print(f"[ERROR] 打开日志文件失败: {e}")
            return {"status": "error", "msg": f"打开日志文件失败: {e}"}

    def get_announcement(self, force=False):
        """读取最新公告；force=True 用于用户点「公告」时强制刷新。"""
        try:
            result = self.announcement_center.latest(force=bool(force))
            announcement = result.get('announcement') if isinstance(result, dict) else None
            if announcement:
                print(f"[ANNOUNCEMENT] 最新公告: {announcement.get('id')} unread={result.get('unread')} stale={result.get('stale')}")
            return result
        except Exception as exc:
            print(f"[ERROR] 获取公告失败: {exc}")
            return {"status": "error", "message": f"公告获取失败：{exc}"}

    def mark_announcement_seen(self, announcement_id):
        """记录本机最后看过的公告 ID，下次只对新公告显示「新」标记。"""
        try:
            return self.announcement_center.mark_seen(announcement_id)
        except Exception as exc:
            print(f"[ERROR] 保存公告已读状态失败: {exc}")
            return {"status": "error", "message": f"保存公告已读状态失败：{exc}"}

    def clear_capture(self):
        """清空捕获文件（里面有 Authorization，允许用户手动抹掉）"""
        from backend import capture
        return capture.clear_capture()

    def test_api(self, message):
        """测试API - 供前端调用"""
        print(f"[INFO] 收到前端消息: {message}")
        return {"status": "success", "reply": f"Python收到: {message}"}
    
    def run(self):
        """启动应用"""
        _init_logging()
        self._purge_expired_icon_cache('启动时')

        print("=" * 50)
        print("少女前线抽卡记录工具")
        print(f"[INFO] 当前版本: v{self.version.get('current_version', '1.0.0')}")
        print("=" * 50)

        # 启动时先把捕获状态写进日志，排障时一眼能看到「到底有没有抓到过」
        try:
            from backend import capture
            info = capture.describe_capture()
            print(f"[INFO] 捕获文件: {info['path']} (exists={info['exists']}, size={info['size']}, "
                  f"replayable={info['replayable']}, captured_at={info['captured_at']})")
        except Exception as e:
            print(f"[WARNING] 读取捕获状态失败: {e}")

        # 旧版本被强杀时可能留下指向已停止 mitmproxy 的全局代理。
        # 此时先关闭它，避免用户在打开新版之前一直无法上网。
        try:
            from backend.proxy_watchdog import repair_stale_local_proxy
            if repair_stale_local_proxy():
                print("[OK] 已清理旧版本遗留的失效本机代理")
        except Exception as exc:
            print(f"[WARN] 检查旧版本代理残留失败: {exc}")

        # 首次运行时检查并生成证书
        self._check_and_generate_certificate()
        
        # 加载前端URL
        url = self.load_frontend()
        if not url:
            return
        
        # 创建窗口
        self.window = webview.create_window(
            title="夏克里助手",
            url=url,
            width=1200,
            height=800,
            js_api=self._create_js_api(),
            confirm_close=False,
            frameless=True,
            easy_drag=False,
            resizable=True,
            shadow=True,
            background_color='#0B0D0F',
        )
        
        # 注册关闭事件
        self.window.events.closed += self.on_closed

        # 前端会主动请求SSR数据，后端不再自动加载

        # 启动mitmproxy（在后台线程）
        self.start_proxy()
        
        # 启动Webview GUI（主线程）
        print("[OK] 启动GUI界面...")
        print("[INFO] 按 Ctrl+C 停止应用")
        try:
            webview.start()
        finally:
            if not self._closing.is_set():
                self.on_closed()
    
    def _check_and_generate_certificate(self):
        """检查并生成证书（首次运行）"""
        try:
            from backend.cert_generator import ensure_ca_certificate, generate_user_ca_certificate
            
            print("[CERT] 检查证书状态...")
            cert_dir, is_new = ensure_ca_certificate()
            
            if is_new:
                print("[CERT] 首次运行，生成用户专属证书...")
                cert_dir = generate_user_ca_certificate()
                print(f"[CERT] 证书已生成并保存到: {cert_dir}")
            else:
                print("[CERT] 证书已存在，跳过生成")
                
        except Exception as e:
            print(f"[ERROR] 检查证书时出错: {e}")
            import traceback
            traceback.print_exc()

_single_instance_mutex = None


def check_single_instance():
    """检查程序是否已在运行

    优先用 Windows 命名互斥体：旧实现按「进程名」判断，复制一份 exe 再运行就
    绕过去了，改名运行又会误判。互斥体随进程结束自动释放，崩溃了也不会残留。

    两个坑：
      * 互斥体错误码必须用 ctypes.get_last_error() 读（配 use_last_error=True）。
        直接调 kernel32.GetLastError() 会被 ctypes 自己的内部调用覆盖，结果时对时错
        —— 会把「首次启动」误判成「已在运行」，用户就起不来了。
      * 同一进程里重复调用要直接返回 True（否则第二次调用会看到
        ERROR_ALREADY_EXISTS，把自己当成另一个实例）。
    """
    global _single_instance_mutex

    if _single_instance_mutex is not None:
        return True

    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            handle = kernel32.CreateMutexW(None, False, "gf2gacha_XKL_single_instance")
            last_error = ctypes.get_last_error()
            if handle:
                if last_error == 183:  # ERROR_ALREADY_EXISTS
                    kernel32.CloseHandle(handle)
                    return False
                _single_instance_mutex = handle  # 保持引用，进程存活期间不释放
                return True
            print(f"[WARNING] 创建互斥体失败(last_error={last_error})，回退到进程名检查")
        except Exception as e:
            print(f"[WARNING] 互斥体单实例检查失败，回退到进程名检查: {e}")

    try:
        import psutil
        current_pid = os.getpid()
        current_process = psutil.Process(current_pid)
        process_name = current_process.name()

        # 查找同名进程
        count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] == process_name:
                    count += 1
                    if count > 1:
                        return False
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return True
    except ImportError:
        print("[WARNING] 未安装 psutil，无法进行单实例检查")
        print("[INFO] 运行 pip install psutil 以启用单实例检查")
        return True
    except Exception as e:
        print(f"[WARNING] 单实例检查失败: {e}")
        return True

if __name__ == "__main__":
    _init_logging()

    # 检查单实例
    if not check_single_instance():
        print("[ERROR] 程序已在运行，请勿重复打开！")
        import ctypes
        # 显示错误提示
        ctypes.windll.user32.MessageBoxW(0, "程序已在运行，请勿重复打开！", "错误", 0)
        sys.exit(1)

    app = GachaApp()
    app.run()
