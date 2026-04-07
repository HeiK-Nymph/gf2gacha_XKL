"""
独立更新器
功能：从R2下载更新包，解压覆盖，启动新版本主程序
"""
import sys
import os
import io
import subprocess
import shutil
import zipfile
import time
import warnings
from pathlib import Path
import json
import requests

# ===================== 关闭所有警告，提升性能 =====================
warnings.filterwarnings('ignore')
requests.packages.urllib3.disable_warnings()
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)


# 全局 Session（复用连接，优化性能）
GLOBAL_SESSION = requests.Session()
GLOBAL_SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
})
# 优化连接池配置
adapter = requests.adapters.HTTPAdapter(
    pool_connections=20,      # 增大连接池
    pool_maxsize=20,          # 增大最大连接数
    max_retries=3,            # 自动重试
    pool_block=False          # 不阻塞
)
GLOBAL_SESSION.mount('http://', adapter)
GLOBAL_SESSION.mount('https://', adapter)

# 简化头部（部分请求用）
BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}


def get_base_path():
    """获取基础路径（_internal 目录）"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent


def get_app_root_path():
    """获取应用根目录（gf2gacha_XKL.exe 所在目录）"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent.parent
    else:
        return Path(__file__).parent


def verify_environment():
    """
    验证当前环境是否正确
    返回: (是否有效, 本地版本, 错误信息)
    """
    base_path = get_base_path()
    version_file = base_path / "version.json"
    
    # 检查 version.json 是否存在
    if not version_file.exists():
        return False, None, f"找不到版本文件: {version_file}"
    
    # 检查 version.json 是否有效
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        local_version = data.get("current_version")
        if not local_version:
            return False, None, "version.json 中缺少 current_version 字段"
        
        # 检查是否有必要的标识字段（确保这是正确的应用）
        app_name = data.get("app_name", "")
        if not app_name:
            # 如果没有 app_name，至少检查是否有 version_url
            if not data.get("version_url"):
                return False, None, "version.json 格式不正确，可能是错误的文件"
        
        return True, local_version, None
        
    except json.JSONDecodeError:
        return False, None, "version.json 格式错误，无法解析"
    except Exception as e:
        return False, None, f"读取 version.json 失败: {e}"


def get_local_version():
    """获取本地版本（已废弃，使用 verify_environment）"""
    version_file = get_base_path() / "version.json"
    if version_file.exists():
        with open(version_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("current_version")
    return None


def http_get(url, timeout=30):
    """HTTP GET 请求（使用Session复用）"""
    return GLOBAL_SESSION.get(url, timeout=timeout, verify=False)


def check_update():
    """检查更新"""
    print("=" * 50)
    
    # 首先验证环境
    is_valid, local_version, error_msg = verify_environment()
    
    if not is_valid:
        print("[UPDATER] 错误：环境验证失败！")
        print(f"[UPDATER] 原因: {error_msg}")
        print("[UPDATER] 请确保 updater.exe 位于正确的安装目录中。")
        print("[UPDATER] 如果您是手动运行 updater.exe，请改为运行主程序 gf2gacha_XKL.exe")
        print("=" * 50)
        return {
            "has_update": False,
            "error": f"环境验证失败: {error_msg}",
            "invalid_environment": True
        }
    
    # 读取本地配置
    local_version_file = get_base_path() / "version.json"
    with open(local_version_file, "r", encoding="utf-8") as f:
        local_data = json.load(f)
    
    version_url = local_data.get("version_url", "https://r2.gf2gacha-xkl.uk/version.json")
    
    print("[UPDATER] 开始检查更新...")
    print(f"[UPDATER] 当前目录: {get_base_path()}")
    print(f"[UPDATER] 版本检查URL: {version_url}")
    
    try:
        response = http_get(version_url, timeout=15)
        remote_data = response.json()
        
        remote_version = remote_data.get("current_version", "0.0.0")
        
        print(f"[UPDATER] 本地版本: {local_version}")
        print(f"[UPDATER] 远程版本: {remote_version}")
        
        remote_list = [int(x) for x in remote_version.split(".")]
        local_list = [int(x) for x in local_version.split(".")]
        
        if remote_list > local_list:
            print(f"[UPDATER] 发现新版本: v{remote_version}")
            # 优先使用远程的 download_url，否则使用本地的
            remote_download_url = remote_data.get("download_url", "")
            local_download_url = local_data.get("download_url", "https://r2.gf2gacha-xkl.uk/gf2gacha_XKL.zip")
            download_url = remote_download_url if remote_download_url else local_download_url
            
            return {
                "has_update": True,
                "local_version": local_version,
                "remote_version": remote_version,
                "download_url": download_url,
                "update_info": remote_data.get("update_info", "")
            }
        else:
            print("[UPDATER] 当前已是最新版本")
            return {
                "has_update": False,
                "local_version": local_version,
                "remote_version": remote_version
            }
            
    except Exception as e:
        print(f"[UPDATER] 检查更新失败: {e}")
        return {
            "has_update": False,
            "error": str(e)
        }


# ===================== 16线程内存下载 =====================
import threading


class ThreadState:
    """线程下载状态"""
    def __init__(self, thread_id, start_byte, end_byte):
        self.thread_id = thread_id
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.current_pos = start_byte
        self.buffer = io.BytesIO()
        self.lock = threading.Lock()
        self.completed = False
        self.error = None
        self.start_time = time.time()  # 线程启动时间（用于预热期判断）


def download_chunk_to_memory(url, thread_state, progress_dict):
    """下载一个分片到内存缓冲区"""
    start_byte = thread_state.start_byte
    end_byte = thread_state.end_byte
    
    try:
        headers = {'Range': f'bytes={start_byte}-{end_byte}'}
        
        with requests.get(
            url,
            headers=headers,
            stream=True,
            timeout=120,
            verify=False,
            allow_redirects=True
        ) as response:
            response.raise_for_status()
            
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if chunk:
                    with thread_state.lock:
                        thread_state.buffer.write(chunk)
                        thread_state.current_pos += len(chunk)
                        progress_dict[thread_state.thread_id] = thread_state.current_pos - start_byte
                    
                    if thread_state.current_pos >= end_byte:
                        with thread_state.lock:
                            thread_state.completed = True
                        break
    except Exception as e:
        with thread_state.lock:
            thread_state.error = str(e)


def download_file_parallel(url, dest_path, num_threads=16):
    """16线程内存下载"""
    print(f"[UPDATER] 开始下载: {url}")
    print(f"[UPDATER] 16线程内存下载")
    
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 获取文件大小
    try:
        head_resp = GLOBAL_SESSION.head(url, timeout=30, verify=False, allow_redirects=True)
        total_size = int(head_resp.headers.get('Content-Length', 0))
        accept_ranges = head_resp.headers.get('Accept-Ranges', '').lower() == 'bytes'
        
        if total_size == 0:
            print("[UPDATER] 错误：无法获取文件大小")
            return False
        
        if not accept_ranges:
            print("[UPDATER] 错误：服务器不支持 Range 请求")
            return False
            
    except Exception as e:
        print(f"[UPDATER] 获取文件信息失败: {e}")
        return False
    
    print(f"[UPDATER] 文件大小: {total_size/1024/1024:.1f} MB")
    print(f"[UPDATER] 启动 {num_threads} 个下载线程...")
    
    # 计算每个线程的范围
    chunk_size = total_size // num_threads
    thread_states = []
    for i in range(num_threads):
        start = i * chunk_size
        end = total_size - 1 if i == num_threads - 1 else start + chunk_size - 1
        thread_states.append(ThreadState(i, start, end))
    
    # 共享进度字典
    progress_dict = {i: 0 for i in range(num_threads)}
    
    # 启动线程
    threads = []
    start_time = time.time()
    last_print_time = 0
    last_check_time = start_time
    last_total = 0
    
    for ts in thread_states:
        t = threading.Thread(
            target=download_chunk_to_memory,
            args=(url, ts, progress_dict)
        )
        t.daemon = True
        t.start()
        threads.append(t)
    
    # 等待完成（带低速检测和重启）
    while any(t.is_alive() for t in threads):
        current_time = time.time()
        
        # 低速检测（每6秒检查一次）
        if current_time - last_check_time >= 6.0:
            total_downloaded = sum(progress_dict.values())
            downloaded_since_last = total_downloaded - last_total
            time_since_last = current_time - last_check_time
            speed_bytes = downloaded_since_last / time_since_last if time_since_last > 0 else 0
            speed_mb = speed_bytes / 1024 / 1024
            
            # 速度为0时重启卡住的线程（排除预热期8秒内的线程）
            if speed_mb == 0 and total_downloaded < total_size:
                print(f"\n[UPDATER] 速度过低 ({speed_mb:.2f} MB/s)，重启卡住线程...")
                for i, (ts, t) in enumerate(zip(thread_states, threads)):
                    # 排除预热期（8秒）内的线程
                    if current_time - ts.start_time < 8.0:
                        continue
                    if not ts.completed and not t.is_alive():
                        # 重启该线程，重置启动时间
                        ts.buffer = io.BytesIO()
                        ts.current_pos = ts.start_byte
                        ts.completed = False
                        ts.error = None
                        ts.start_time = time.time()  # 重置预热时间
                        t = threading.Thread(
                            target=download_chunk_to_memory,
                            args=(url, ts, progress_dict)
                        )
                        t.daemon = True
                        t.start()
                        threads[i] = t
            
            last_total = total_downloaded
            last_check_time = current_time
        
        # 进度显示
        if current_time - last_print_time >= 0.5:
            total_downloaded = sum(progress_dict.values())
            percent = total_downloaded / total_size * 100 if total_size > 0 else 0
            elapsed = current_time - start_time
            instant_speed = total_downloaded / elapsed / 1024 / 1024 if elapsed > 0 else 0
            completed = sum(1 for ts in thread_states if ts.completed)
            
            print(f"\r[UPDATER] {percent:.1f}% | {total_downloaded/1024/1024:.1f}MB | {instant_speed:.1f} MB/s | 完成: {completed}/{num_threads}", end="")
            last_print_time = current_time
        
        time.sleep(0.1)
    
    # 等待所有线程结束
    for t in threads:
        t.join()
    
    # 检查错误
    errors = [ts.error for ts in thread_states if ts.error]
    if errors:
        print(f"\n[UPDATER] 下载出错: {errors[0]}")
        return False
    
    # 验证分片
    for ts in thread_states:
        expected_size = ts.end_byte - ts.start_byte + 1
        actual_size = ts.current_pos - ts.start_byte
        if actual_size != expected_size:
            print(f"\n[UPDATER] 错误：分片 {ts.thread_id} 大小不匹配 ({actual_size}/{expected_size})")
            return False
    
    # 合并数据
    print("\n[UPDATER] 合并数据...")
    final_data = b''.join(ts.buffer.getvalue() for ts in thread_states)
    
    if len(final_data) != total_size:
        print(f"[UPDATER] 错误：大小不匹配 ({len(final_data)}/{total_size})")
        return False
    
    # 写入文件
    if dest_path.exists():
        dest_path.unlink()
    
    with open(dest_path, 'wb') as f:
        f.write(final_data)
    
    actual_size = dest_path.stat().st_size
    if actual_size != total_size:
        print(f"[UPDATER] 错误：文件大小不匹配 ({actual_size}/{total_size})")
        dest_path.unlink()
        return False
    
    elapsed = time.time() - start_time
    avg_speed = total_size / elapsed / 1024 / 1024 if elapsed > 0 else 0
    print(f"[UPDATER] 下载完成! {total_size/1024/1024:.1f} MB | 平均速度: {avg_speed:.1f} MB/s")
    print(f"[UPDATER] 文件保存成功: {dest_path.name}")
    return True


def download_file(url, dest_path):
    """单线程下载"""
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"[UPDATER] 开始下载: {url}")
    
    try:
        with GLOBAL_SESSION.get(url, stream=True, timeout=300, verify=False) as r:
            r.raise_for_status()
            total = int(r.headers.get('Content-Length', 0))
            dl = 0
            t0 = time.time()
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(256 * 1024):
                    if chunk:
                        f.write(chunk)
                        dl += len(chunk)
                        if total:
                            print(f"\r[UPDATER] {dl*100/total:.1f}% | {dl/1024/1024:.1f}MB", end="")
            print(f"\n[UPDATER] 完成 {dl/1024/1024:.1f}MB")
            return True
    except Exception as e:
        print(f"\n[UPDATER] 下载失败: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False


def download_with_urllib(url, dest_path):
    """urllib 备用下载（已废弃，保留兼容）"""
    return download_file(url, dest_path)


def perform_update(download_url):
    """执行更新操作"""
    base_path = get_base_path()
    app_root = get_app_root_path()
    
    print("=" * 50)
    print("[UPDATER] 开始执行更新...")
    
    temp_dir = app_root / "update_temp"
    temp_dir.mkdir(exist_ok=True)
    zip_path = temp_dir / "update.zip"
    
    if not download_file(download_url, zip_path):
        print("[UPDATER] 下载失败，更新终止")
        cleanup_temp(temp_dir)
        return False
    
    print("[UPDATER] 开始解压...")
    extract_dir = temp_dir / "extracted"
    extract_dir.mkdir(exist_ok=True)
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        print("[UPDATER] 解压完成!")
    except Exception as e:
        print(f"[UPDATER] 解压失败: {e}")
        cleanup_temp(temp_dir)
        return False
    
    source_dir = extract_dir
    if (extract_dir / "gf2gacha_XKL").exists():
        source_dir = extract_dir / "gf2gacha_XKL"
    elif (extract_dir / "dist" / "gf2gacha_XKL").exists():
        source_dir = extract_dir / "dist" / "gf2gacha_XKL"
    
    current_updater = base_path / "updater.exe"
    old_updater = base_path / "updater_old.exe"
    
    if current_updater.exists():
        try:
            if old_updater.exists():
                old_updater.unlink()
            current_updater.rename(old_updater)
        except Exception as e:
            pass
    
    preserve_items = {"records", "certs", "updater_old.exe"}
    
    # 1. 备份数据文件夹到根目录
    backup_records = app_root / "records_backup_temp"
    backup_certs = app_root / "certs_backup_temp"
    
    # 如果备份已存在，先删除（防止残留）
    if backup_records.exists():
        shutil.rmtree(backup_records)
    if backup_certs.exists():
        shutil.rmtree(backup_certs)
    
    # 执行备份
    records_src = base_path / "records"
    certs_src = base_path / "certs"
    
    if records_src.exists():
        shutil.copytree(records_src, backup_records)
    if certs_src.exists():
        shutil.copytree(certs_src, backup_certs)
    
    # 2. 处理根目录（不包含 _internal）
    for item in source_dir.iterdir():
        if item.name in preserve_items or item.name == "_internal":
            continue
        dest = app_root / item.name
        try:
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        except Exception as e:
            if "拒绝访问" in str(e) or "WinError 5" in str(e):
                pass  # 跳过正在使用的文件，不显示错误
            else:
                print(f"[UPDATER] 处理根目录文件失败: {item.name}, {e}")
    
    # 3. 处理 _internal 目录内部（不删除整个 _internal）
    source_internal = source_dir / "_internal"
    if source_internal.exists():
        for item in source_internal.iterdir():
            if item.name in preserve_items:
                continue
            dest = base_path / item.name
            try:
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
            except Exception as e:
                if "拒绝访问" in str(e) or "WinError 5" in str(e):
                    pass  # 跳过正在使用的文件，不显示错误
                else:
                    print(f"[UPDATER] 处理 _internal 文件失败: {item.name}, {e}")
    
    # 4. 恢复备份的数据文件夹
    if backup_records.exists():
        if records_src.exists():
            shutil.rmtree(records_src)
        shutil.move(str(backup_records), str(records_src))
    if backup_certs.exists():
        if certs_src.exists():
            shutil.rmtree(certs_src)
        shutil.move(str(backup_certs), str(certs_src))
    
    cleanup_temp(temp_dir)
    print("[UPDATER] 更新完成!")
    return True


def cleanup_temp(temp_dir):
    try:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    except:
        pass


def launch_main_app():
    app_root = get_app_root_path()
    main_exe = app_root / "gf2gacha_XKL.exe"
    if main_exe.exists():
        try:
            time.sleep(1)
            subprocess.Popen(
                [str(main_exe)],
                cwd=str(app_root),
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
            return True
        except:
            return False
    return False


def main():
    print("=" * 50)
    print("GF2抽卡工具 - 独立更新器")
    print("=" * 50)
    
    result = check_update()
    
    # 检查是否是无效环境
    if result.get("invalid_environment"):
        print("\n" + "=" * 50)
        print("[UPDATER] 更新器终止运行")
        print("=" * 50)
        print("\n按回车键退出...")
        input()
        return
    
    if result.get("has_update"):
        download_url = result.get("download_url", "")
        if perform_update(download_url):
            launch_main_app()
    
    print("\n按回车键退出...")
    input()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[UPDATER] 发生致命错误: {e}")
        import traceback
        traceback.print_exc()
        print("\n按回车键退出...")
        input()
        import sys
        sys.exit(1)