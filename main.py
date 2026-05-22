import webview
import webbrowser
import threading
import asyncio
import sys
import os
import json
from pathlib import Path
import requests

# 添加backend路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

class GachaApp:
    def __init__(self):
        self.window = None
        self.proxy_thread = None
        self.proxy_running = False  # 新增：代理运行标志
        # 新增：版本管理
        self.version = self._load_version()
        # 从本地 version.json 读取远程版本检查地址（R2）
        self.version_url = self.version.get("version_url", "https://r2.gf2gacha-xkl.uk/version.json")
        # 先设置为空数据，延迟加载（后台线程）
        self.ssr_data = {
            "version": "loading",
            "SSR_character": {},
            "SSR_weapon": {},
            "SSR_permanent": {}
        }
        self.ssr_loading = True  # 标记正在加载

        # 启动时清理旧的更新器
        self._cleanup_old_updater()
        
    def get_gacha(self):
        from backend.api.getGacha import get_gacha_data_all
        from backend.proxy import close_proxy
        import requests

        # 检查 latest_request.json 是否为空
        json_path = Path(__file__).parent / "json" / "latest_request.json"
        if not json_path.exists() or json_path.stat().st_size == 0:
            
            return {
                "status": "error",
                "msg": "获取抽卡记录失败",
            }

        # 读取 Authorization
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                latest_request = json.load(f)
            authorization = latest_request.get("headers", {}).get("Authorization", "")
            
            if not authorization:
                print("[ERROR] 未找到Authorization字段")
                return {
                    "status": "error",
                    "msg": "获取抽卡记录失败",
                }
        except Exception as e:
            print(f"[ERROR] 读取Authorization失败: {e}")
            return {
                "status": "error",
                "msg": "获取抽卡记录失败",
            }

        self.enable_system_proxy()

        # 获取用户uid
        uid = None
        try:
            account_url = "https://gf2-zoneinfo.sunborngame.com/account/info"
            account_headers = {
                "Host": "gf2-zoneinfo.sunborngame.com",
                "User-Agent": "UnityPlayer/2019.4.40f1 (UnityWebRequest/1.0, libcurl/7.80.0-DEV)",
                "Accept": "*/*",
                "Accept-Encoding": "deflate, gzip",
                "Authorization": authorization,
                "Content-Type": "application/json",
                "X-Unity-Version": "2019.4.40f1"
            }
            
            response = requests.post(account_url, headers=account_headers, json={}, verify=False)
            
            if response.status_code == 200:
                account_data = response.json()
                if account_data.get("code") == 0:
                    uid = account_data.get("data", {}).get("uid")
                    print(f"[INFO] 获取到用户UID: {uid}")
                else:
                    print(f"[ERROR] 获取UID失败: {account_data.get('msg')}")
            else:
                print(f"[ERROR] 请求失败，状态码: {response.status_code}")
        except Exception as e:
            print(f"[ERROR] 获取UID失败: {e}")

        gacha = get_gacha_data_all()

        if gacha is not None:
            print("=" * 50)
            print(gacha)
            
            # 将uid和gacha数据一起返回
            return {
                "status": "success",
                "msg": "获取抽卡记录成功",
                "data": {
                    "uid": uid,
                    "gacha": gacha
                }
            }
        else:
            # 只要有一个池子获取失败，就返回错误，而不是返回空数据
            return {
                "status": "error",
                "msg": "获取抽卡记录失败：请检查token是否过期或网络连接",
            }
        
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
                    return {
                        "status": "success",
                        "msg": "证书已安装，无需重复安装",
                        "cert_name": cert_name
                    }
                
                # 自动安装证书
                success = install_certificate_windows(cert_path)
                if success:
                    return {
                        "status": "success",
                        "msg": "证书安装成功！",
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
            
            # 卸载 gf2gacha_XKL 证书
            success = uninstall_certificate_windows(cert_name)
            
            if success:
                return {
                    "status": "success",
                    "msg": "证书卸载成功！",
                }
            else:
                return {
                    "status": "error",
                    "msg": "证书卸载失败",
                }
                
        except Exception as e:
            print(f"[ERROR] 卸载证书失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "msg": f"卸载证书失败: {str(e)}",
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

    def _load_ssr_data(self):
        """启动时加载SSR数据：优先从本地游戏数据(protobuf)解析，降级到远程/本地json"""
        print("[SSR] 开始加载SSR角色数据...")

        # 优先：从本地游戏数据解析（protobuf）
        try:
            from backend.ssr_parser import load_ssr_from_local
            local_result = load_ssr_from_local()
            if local_result is not None:
                print(f"[SSR] ★★★ 从本地游戏数据解析成功！版本: {local_result.get('version')} ★★★")
                return local_result
        except Exception as e:
            print(f"[SSR] 本地protobuf解析失败: {e}")

        # 降级1: 读取本地 ssr.json
        try:
            local_ssr_path = Path(__file__).parent / "json" / "ssr.json"
            if local_ssr_path.exists():
                with open(local_ssr_path, "r", encoding="utf-8") as f:
                    local_data = json.load(f)
                print(f"[SSR] 使用本地ssr.json，版本: {local_data.get('version', 'unknown')}")
                return local_data
        except Exception as e:
            print(f"[SSR] 读取本地ssr.json失败: {e}")

        # 返回空数据结构
        print("[SSR] 无法获取SSR数据，返回空结构")
        return {
            "version": "none",
            "SSR_character": {},
            "SSR_weapon": {},
            "SSR_permanent": {}
        }

    def load_ssr_data(self):
        """前端调用加载SSR数据：优先从本地游戏数据(protobuf)解析"""
        print("[SSR] 前端请求加载SSR数据...")

        # 优先：从本地游戏数据解析（protobuf）
        try:
            from backend.ssr_parser import load_ssr_from_local
            local_result = load_ssr_from_local()
            if local_result is not None:
                self.ssr_data = dict(local_result)
                self.ssr_data['_fromRemote'] = False
                print(f"[SSR] ★★★ 从本地游戏数据解析成功！版本: {self.ssr_data.get('version')} ★★★")
                return {
                    "status": "success",
                    "source": "local-proto",
                    "data": self.ssr_data
                }
        except Exception as e:
            print(f"[SSR] 本地protobuf解析失败: {e}")

        # 降级1: 读取本地 ssr.json
        try:
            local_ssr_path = Path(__file__).parent / "json" / "ssr.json"
            if local_ssr_path.exists():
                with open(local_ssr_path, "r", encoding="utf-8") as f:
                    self.ssr_data = json.load(f)
                self.ssr_data['_fromRemote'] = False
                print(f"[SSR] 使用本地ssr.json，版本: {self.ssr_data.get('version', 'unknown')}")
                return {
                    "status": "success",
                    "source": "local-json",
                    "data": self.ssr_data
                }
        except Exception as e:
            print(f"[SSR] 读取本地ssr.json失败: {e}")

        # 全部失败
        print("[SSR] 所有数据源都不可用")
        self.ssr_data = {
            "version": "none",
            "SSR_character": {},
            "SSR_weapon": {},
            "SSR_permanent": {},
            "_fromRemote": False
        }
        return {
            "status": "error",
            "source": "none",
            "data": self.ssr_data
        }

    def get_ssr_data(self):
        """供前端调用获取SSR数据（仅返回当前数据）"""
        return {
            "status": "success",
            "data": self.ssr_data
        }

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
        except Exception as e:
            print(f"[WARNING] 清理旧更新器失败: {e}")
    
    def check_update(self):
        """检查更新"""
        print("=" * 50)
        print("[UPDATE] 开始检查更新...")
        print(f"[UPDATE] 版本检查URL: {self.version_url}")

        # 暂时关闭系统代理以检查更新
        from backend.proxy import close_proxy
        print("[UPDATE] 暂时关闭系统代理...")
        close_proxy()

        try:
            # 从 GitHub 获取最新版本
            print("[UPDATE] 正在请求 r2...")
            response = requests.get(self.version_url, timeout=5)
            print(f"[UPDATE] HTTP状态码: {response.status_code}")

            remote_data = response.json()
            print(f"[UPDATE] 远程数据: {remote_data}")

            remote_version = remote_data.get("current_version", "1.0.0")
            print(f"[UPDATE] remote_version: {remote_version}")

            local_version = self.version.get("current_version", "1.0.0")
            print(f"[UPDATE] local_version: {local_version}")

            # 比较版本号
            remote_list = [int(x) for x in remote_version.split(".")]
            local_list = [int(x) for x in local_version.split(".")]

            if remote_list > local_list:
                print("[UPDATE] 发现新版本！")
                # 发现新版本，不恢复代理
                return {
                    "status": "success",
                    "has_update": True,
                    "latest_version": remote_version,
                    "message": f"发现新版本 v{remote_version}"
                }
            else:
                print("[UPDATE] 当前已是最新版本")
                # 已是最新版本，恢复代理
                print("[UPDATE] 恢复系统代理...")
                self.enable_system_proxy()
                return {
                    "status": "success",
                    "has_update": False,
                    "message": "当前已是最新版本"
                }
        except requests.exceptions.ProxyError as e:
            print(f"[UPDATE] 代理错误: {e}")
            # 检查出错，恢复代理
            print("[UPDATE] 恢复系统代理...")
            self.enable_system_proxy()
            return {
                "status": "error",
                "has_update": False,
                "message": "网络连接失败，请检查代理设置"
            }
        except requests.exceptions.Timeout as e:
            print(f"[UPDATE] 请求超时: {e}")
            # 检查出错，恢复代理
            print("[UPDATE] 恢复系统代理...")
            self.enable_system_proxy()
            return {
                "status": "error",
                "has_update": False,
                "message": "连接超时，请稍后重试"
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[UPDATE] 连接错误: {e}")
            # 检查出错，恢复代理
            print("[UPDATE] 恢复系统代理...")
            self.enable_system_proxy()
            return {
                "status": "error",
                "has_update": False,
                "message": "网络连接失败，请检查网络"
            }
        except Exception as e:
            print(f"[UPDATE] 未知错误: {e}")
            import traceback
            traceback.print_exc()
            # 检查出错，恢复代理
            print("[UPDATE] 恢复系统代理...")
            self.enable_system_proxy()
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
            
            # 确定 updater.exe 的路径
            if getattr(sys, 'frozen', False):
                # 打包后的环境
                base_path = Path(sys.executable).parent / "_internal"
            else:
                # 开发环境
                base_path = Path(__file__).parent
            
            updater_path = base_path / "updater.exe"
            
            if not updater_path.exists():
                print(f"[ERROR] 更新器不存在: {updater_path}")
                return {
                    "status": "error",
                    "message": "更新器文件不存在"
                }
            
            print(f"[UPDATE] 更新器路径: {updater_path}")
            
            # 启动更新器（独立进程）
            subprocess.Popen(
                [str(updater_path)],
                cwd=str(base_path),
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
            
            print("[UPDATE] 更新器已启动，主程序即将退出...")
            
            # 关闭代理
            from backend.proxy import close_proxy
            close_proxy()
            
            # 关闭主程序
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

    def copy_image_to_clipboard(self, _unused=None):
        """通过 evaluate_js 从前端获取截图数据并写入系统剪贴板（Python后端预下载图片+8秒延迟）"""
        try:
            import os
            import subprocess
            import base64
            import tempfile
            import time
            import requests as req_lib

            # ============================================================
            # 步骤1：Python 后端获取容器内所有图片 URL，逐个下载为 base64
            #        Python requests 不受浏览器同源策略限制！
            # ============================================================
            print("[DEBUG] 步骤1：获取图片列表...")

            # 1a. 从前端获取所有图片的 src 和索引
            img_list = self.window.evaluate_js("""
                (function() {
                    var el = document.querySelector('.screenshot-container');
                    if (!el) return null;
                    var imgs = el.querySelectorAll('img');
                    var list = [];
                    Array.prototype.forEach.call(imgs, function(img, idx) {
                        list.push({index: idx, src: img.src || ''});
                    });
                    return {total: list.length, images: list};
                })()
            """)
            
            if not img_list:
                return {"status": "error", "message": "无法获取图片列表或容器不存在"}

            print(f"  找到 {img_list['total']} 张图片")

            # 1b. Python 端按路径去重 + 并发下载图片（绕过浏览器 CORS）
            #     相同 URL 只下载一次，多张相同图片复用同一 base64 数据
            from concurrent.futures import ThreadPoolExecutor, as_completed

            # 先收集所有唯一 URL（去重）
            unique_srcs = set()
            for img_info in img_list['images']:
                src = img_info['src']
                if not src or src.startswith('data:'):
                    continue
                unique_srcs.add(src)

            src_to_datauri = {}  # { src: data_uri }

            def _download_one(src_url):
                """下载单张图片并返回 (src, data_uri) 或 (src, None)"""
                try:
                    resp = req_lib.get(src_url, timeout=15, verify=False)
                    if resp.status_code == 200 and resp.content:
                        b64 = base64.b64encode(resp.content).decode('ascii')
                        content_type = resp.headers.get('Content-Type', 'image/png')
                        if 'image' not in content_type:
                            content_type = 'image/png'
                        return (src_url, f"data:{content_type};base64,{b64}", len(resp.content))
                    return (src_url, None, 0)
                except Exception as e:
                    return (src_url, None, str(e))

            # 并发下载所有唯一图片
            if not unique_srcs:
                print("  所有图片已是 data URI，无需重新下载")
            else:
                MAX_WORKERS = min(len(unique_srcs), 8)  # 最多8个并发线程
                print(f"  并发下载 {len(unique_srcs)} 个唯一URL (并发数={MAX_WORKERS})...")
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    future_map = {executor.submit(_download_one, src): src for src in unique_srcs}
                    for future in as_completed(future_map):
                        src_url, data_uri, info = future.result()
                        if data_uri:
                            src_to_datauri[src_url] = data_uri
                            print(f"  OK: {src_url[:50]}... ({info} bytes)")
                        else:
                            print(f"  FAIL: {src_url[:50]}... ({info})")

            print(f"  下载完成: {len(src_to_datauri)}/{len(unique_srcs)} 成功 / 共{img_list['total']}张图片")

            # 1c. 将下载好的 base64 数据注入到前端 DOM 中（按 src 匹配复用）
            print("[DEBUG] 步骤2：注入 base64 图片到 DOM...")
            if src_to_datauri:
                # 构造 JS：将每个 img.src 替换为对应的 data URI（相同路径复用同一数据）
                js_map = json.dumps(src_to_datauri)
                self.window.evaluate_js(f"""
                    (function() {{
                        var map = {js_map};
                        var el = document.querySelector('.screenshot-container');
                        if (!el) return;
                        var imgs = el.querySelectorAll('img');
                        var injectCount = 0;
                        Array.prototype.forEach.call(imgs, function(img) {{
                            if (img.src && map[img.src]) {{
                                img.src = map[img.src];
                                injectCount++;
                            }}
                        }});
                        window.__screenshot_injected = injectCount;
                    }})()
                """)

                # 验证注入是否成功
                injected = self.window.evaluate_js("window.__screenshot_injected")
                print(f"  注入结果: {injected} 张图片已替换")

            # ============================================================
            # 步骤3：直接执行 html2canvas 截图（所有图片已是 data URI，无跨域）
            #        后端已确保资源下载完成，无需额外等待
            # ============================================================
            print("[DEBUG] 步骤3：执行 html2canvas 截图...")
            self.window.evaluate_js("""
                (function() {
                    window.__screenshot_result = null;
                    window.__screenshot_error = null;

                    var el = document.querySelector('.screenshot-container');
                    if (!el) { window.__screenshot_error = '容器不存在'; return; }
                    var h2c = window.html2canvas;
                    if (!h2c) { window.__screenshot_error = 'html2canvas未加载'; return; }

                    // 最终检查：统计 data URI 比例
                    var imgs = el.querySelectorAll('img');
                    var dataCount = 0;
                    Array.prototype.forEach.call(imgs, function(img) {
                        if (img.src && img.src.startsWith('data:')) dataCount++;
                    });
                    console.log('[Screenshot] 截图前检查: dataURI=' + dataCount + '/' + imgs.length);

                    h2c(el, {
                        scale: 2,
                        useCORS: true,
                        allowTaint: true,
                        backgroundColor: '#ffffff',
                        width: el.scrollWidth,
                        height: el.scrollHeight,
                        logging: false
                    }).then(function(canvas) {
                        console.log('[Screenshot] canvas: ' + canvas.width + 'x' + canvas.height);
                        return new Promise(function(resolve, reject) {
                            canvas.toBlob(function(blob) {
                                if (!blob) { reject('toBlob failed'); return; }
                                var reader = new FileReader();
                                reader.onload = function() { resolve(reader.result); };
                                reader.readAsDataURL(blob);
                            }, 'image/png');
                        });
                    }).then(function(dataUrl) {
                        console.log('[Screenshot] 完成, 长度:' + dataUrl.length);
                        window.__screenshot_result = dataUrl;
                    }).catch(function(e) {
                        console.error('[Screenshot] 错误:', e);
                        window.__screenshot_error = e.message || String(e);
                    });
                })()
            """)

            # 步骤5：轮询等待截图完成
            print("[DEBUG] 等待截图完成...")
            for i in range(60):  # 最多等 30 秒
                time.sleep(0.5)
                result = self.window.evaluate_js("window.__screenshot_result")
                error = self.window.evaluate_js("window.__screenshot_error")
                if result and isinstance(result, str) and result.startswith('data:'):
                    break
                if error and isinstance(error, str):
                    return {"status": "error", "message": f"截图失败: {error}"}
            else:
                # 超时，检查最终状态
                result = self.window.evaluate_js("window.__screenshot_result")
                error = self.window.evaluate_js("window.__screenshot_error")
                if error:
                    return {"status": "error", "message": f"截图超时/失败: {error}"}
                return {"status": "error", "message": f"截图超时 (result={result})"}

            data_url = result
            print(f"[DEBUG] 截图数据长度: {len(data_url)}")

            if not data_url or not isinstance(data_url, str):
                return {"status": "error", "message": f"获取截图失败: {data_url}"}

            if data_url.startswith('ERROR:'):
                return {"status": "error", "message": data_url}

            if ',' not in data_url:
                return {"status": "error", "message": f"数据格式异常 (len={len(data_url)})"}

            b64_data = data_url.split(',', 1)[1]
            image_bytes = base64.b64decode(b64_data)
            print(f"[DEBUG] 截图数据大小: {len(image_bytes)} bytes")

            # 验证 PNG 签名
            png_sig = bytes([0x89, 0x50, 0x4E, 0x47])
            if image_bytes[:4] != png_sig:
                return {"status": "error", "message": f"非PNG格式 (hex: {image_bytes[:4].hex()})"}

            # 写入临时文件
            fd, file_path = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(image_bytes)

            # PowerShell 写入剪贴板
            ps_cmd = (
                'Add-Type -AssemblyName System.Windows.Forms; '
                'Add-Type -AssemblyName System.Drawing; '
                f'$img = [System.Drawing.Image]::FromFile("{file_path}"); '
                '[System.Windows.Forms.Clipboard]::SetImage($img); '
                '$img.Dispose()'
            )
            result = subprocess.run(
                ['powershell', '-Command', ps_cmd],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                return {"status": "error", "message": f"PowerShell失败: {result.stderr.strip()}"}

            # 清理临时文件
            try:
                os.unlink(file_path)
            except:
                pass

            return {"status": "success", "message": "已复制到剪贴板"}

        except Exception as e:
            print(f"[ERROR] 复制图片到剪贴板失败: {e}")
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
        
    def enable_system_proxy(self):
        """开启系统代理(不启动mitmproxy)"""
        from backend.proxy import set_proxy, actual_port

        # 使用 mitmproxy 实际监听的端口
        port = actual_port if actual_port is not None else 8080

        try:
            set_proxy('127.0.0.1', port)
            print(f"[OK] 开启系统代理成功，端口: {port}")
        except Exception as e:
            print(f"[ERROR] 开启系统代理失败: {e}")
    
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
        """在子线程中启动mitmproxy"""
        if self.proxy_running:
            print("[ERROR] 代理已运行")
            return

        from backend.proxy import run_proxy
        from backend.addons.addons import set_event_handler
        
        def run():
            # 设置事件处理器
            set_event_handler(self)

            # 启动mitmproxy（在后台线程）
            print("[INFO] 启动mitmproxy代理...")
            try:
                self.proxy_running = True
                asyncio.run(run_proxy(8080))
            except Exception as e:
                print(f"[ERROR] 代理启动失败: {e}")
            finally:
                self.proxy_running = False
        
        self.proxy_thread = threading.Thread(target=run, daemon=True)
        self.proxy_thread.start()
    
    def on_closed(self):
        """窗口关闭时的处理"""
        from backend.proxy import close_proxy
        close_proxy()
        self.proxy_running = False
        
        # 清除 latest_request.json 内容
        try:
            json_path = Path(__file__).parent / "json" / "latest_request.json"
            if json_path.exists():
                json_path.write_text("", encoding="utf-8")
                print("[INFO] 已清除 latest_request.json")
        except Exception as e:
            print(f"[WARNING] 清除 latest_request.json 失败: {e}")
        
        print("[INFO] 应用关闭")

    
    
    def test_api(self, message):
        """测试API - 供前端调用"""
        print(f"[INFO] 收到前端消息: {message}")
        return {"status": "success", "reply": f"Python收到: {message}"}
    
    def run(self):
        """启动应用"""
        print("=" * 50)
        print("少女前线抽卡记录工具")
        print(f"[INFO] 当前版本: v{self.version.get('current_version', '1.0.0')}")
        print("=" * 50)
        
        # 首次运行时检查并生成证书
        self._check_and_generate_certificate()
        
        # 加载前端URL
        url = self.load_frontend()
        if not url:
            return
        
        # 创建窗口
        self.window = webview.create_window(
            title="少前2抽卡记录工具_XKL",
            url=url,
            width=1200,
            height=800,
            js_api=self,  # 将整个对象暴露给JS
            confirm_close=False,  # 询问是否关闭
            resizable=False
        )
        
        # 注册关闭事件
        self.window.events.closed += self.on_closed

        # 前端会主动请求SSR数据，后端不再自动加载

        # 启动mitmproxy（在后台线程）
        self.start_proxy()
        
        # 启动Webview GUI（主线程）
        print("[OK] 启动GUI界面...")
        print("[INFO] 按 Ctrl+C 停止应用")
        webview.start()
    
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

def check_single_instance():
    """检查程序是否已在运行"""
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
    # 检查单实例
    if not check_single_instance():
        print("[ERROR] 程序已在运行，请勿重复打开！")
        import ctypes
        import time
        # 显示错误提示
        ctypes.windll.user32.MessageBoxW(0, "程序已在运行，请勿重复打开！", "错误", 0)
        sys.exit(1)

    app = GachaApp()
    app.run()