#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试证书生成、安装和卸载功能
"""
import sys
from pathlib import Path

# 添加backend路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from backend.cert_generator import (
    ensure_ca_certificate,
    generate_user_ca_certificate,
    install_certificate_windows,
    uninstall_certificate_windows,
    check_certificate_installed_windows,
    get_certificate_info
)

def test_cert_generation():
    """测试证书生成"""
    print("=" * 60)
    print("测试证书生成功能")
    print("=" * 60)
    
    cert_dir, is_new = ensure_ca_certificate()
    
    if is_new:
        print("[TEST] 检测到首次运行，生成新证书...")
        cert_dir = generate_user_ca_certificate()
    else:
        print("[TEST] 证书已存在，跳过生成")
    
    # 检查生成的文件
    files = ['mitmproxy-ca.pem', 'mitmproxy-ca-cert.pem', 
             'mitmproxy-ca-cert.cer', 'mitmproxy-ca-cert.p12']
    
    print(f"\n[TEST] 证书目录: {cert_dir}")
    for f in files:
        path = cert_dir / f
        exists = "✓" if path.exists() else "✗"
        print(f"  {exists} {f}")
    
    # 显示证书信息
    cert_path = cert_dir / "mitmproxy-ca-cert.cer"
    info = get_certificate_info(cert_path)
    
    if info:
        print(f"\n[TEST] 证书信息:")
        print(f"  名称: {info['common_name']}")
        print(f"  序列号: {info['serial_number']}")
        print(f"  有效期: {info['valid_from'].strftime('%Y-%m-%d')} 至 {info['valid_to'].strftime('%Y-%m-%d')}")
    
    return cert_dir

def test_cert_installation(cert_dir):
    """测试证书安装"""
    print("\n" + "=" * 60)
    print("测试证书安装功能")
    print("=" * 60)
    
    import platform
    if platform.system() != "Windows":
        print("[TEST] 非Windows系统，跳过安装测试")
        return
    
    cert_path = cert_dir / "mitmproxy-ca-cert.cer"
    info = get_certificate_info(cert_path)
    
    if not info:
        print("[TEST] 无法读取证书信息")
        return
    
    cert_name = info['common_name']
    
    # 检查是否已安装
    is_installed = check_certificate_installed_windows(cert_name)
    print(f"[TEST] 证书安装状态: {'已安装' if is_installed else '未安装'}")
    
    if not is_installed:
        print(f"[TEST] 正在安装证书: {cert_name}")
        success = install_certificate_windows(cert_path)
        print(f"[TEST] 安装结果: {'成功' if success else '失败'}")
        
        # 再次检查
        is_installed = check_certificate_installed_windows(cert_name)
        print(f"[TEST] 安装后状态: {'已安装' if is_installed else '未安装'}")
    
    return cert_name

def test_cert_uninstallation(cert_name):
    """测试证书卸载"""
    print("\n" + "=" * 60)
    print("测试证书卸载功能")
    print("=" * 60)
    
    import platform
    if platform.system() != "Windows":
        print("[TEST] 非Windows系统，跳过卸载测试")
        return
    
    is_installed = check_certificate_installed_windows(cert_name)
    print(f"[TEST] 证书安装状态: {'已安装' if is_installed else '未安装'}")
    
    if is_installed:
        print(f"[TEST] 正在卸载证书: {cert_name}")
        success = uninstall_certificate_windows(cert_name)
        print(f"[TEST] 卸载结果: {'成功' if success else '失败'}")
        
        # 再次检查
        is_installed = check_certificate_installed_windows(cert_name)
        print(f"[TEST] 卸载后状态: {'已安装' if is_installed else '未安装'}")
    else:
        print("[TEST] 证书未安装，无需卸载")

def main():
    """主测试流程"""
    print("GF2Gacha_XKL 证书功能测试")
    print("注意: 本测试需要管理员权限才能安装/卸载证书")
    
    # 测试1: 生成证书
    cert_dir = test_cert_generation()
    
    # 测试2: 安装证书
    cert_name = test_cert_installation(cert_dir)
    
    # 测试3: 卸载证书（可选）
    if cert_name:
        print("\n[TEST] 是否测试卸载功能? (y/n): ", end="")
        try:
            response = input().strip().lower()
            if response == 'y':
                test_cert_uninstallation(cert_name)
        except:
            print("\n[TEST] 跳过卸载测试")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
