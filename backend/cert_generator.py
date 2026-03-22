"""
证书生成器 - 为每个用户动态生成唯一的CA证书
"""
from pathlib import Path
import uuid
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import subprocess
import platform


def ensure_ca_certificate():
    """确保证书存在，不存在则返回需要生成的标志"""
    cert_dir = Path(__file__).parent.parent / "certs"
    cert_dir.mkdir(exist_ok=True)
    ca_pem = cert_dir / "mitmproxy-ca.pem"
    return cert_dir, not ca_pem.exists()


def generate_user_ca_certificate():
    """
    为当前用户生成独一无二的 CA 证书
    证书名称为: gf2gacha_XKL
    """
    print("[CERT] 首次运行，生成用户专属证书...")
    
    # 生成用户唯一标识
    user_id = str(uuid.uuid4())[:8].upper()
    
    # 生成RSA私钥
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    # 构建证书主体
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"CN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Beijing"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"Beijing"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"GF2Gacha_XKL"),
        x509.NameAttribute(NameOID.COMMON_NAME, f"gf2gacha_XKL_CA_{user_id}"),
    ])
    
    # 证书有效期：10年
    valid_from = datetime.utcnow()
    valid_to = valid_from + timedelta(days=3650)
    
    # 生成证书序列号（使用UUID的一部分）
    serial_number = int(uuid.uuid4().hex[:16], 16)
    
    # 构建X509证书
    cert = x509.CertificateBuilder()
    cert = cert.subject_name(subject)
    cert = cert.issuer_name(issuer)
    cert = cert.public_key(private_key.public_key())
    cert = cert.serial_number(serial_number)
    cert = cert.not_valid_before(valid_from)
    cert = cert.not_valid_after(valid_to)
    cert = cert.add_extension(
        x509.KeyUsage(
            digital_signature=False,
            content_commitment=False,
            key_encipherment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=True,
            crl_sign=True,
            encipher_only=False,
            decipher_only=False
        ),
        critical=True
    )
    cert = cert.add_extension(
        x509.BasicConstraints(ca=True, path_length=None),
        critical=True
    )
    cert = cert.add_extension(
        x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
        critical=False
    )
    
    # 自签名证书
    cert = cert.sign(private_key, hashes.SHA256(), default_backend())
    
    # 保存证书和私钥
    cert_dir = Path(__file__).parent.parent / "certs"
    cert_dir.mkdir(exist_ok=True)
    
    # 保存为 mitmproxy-ca.pem 格式（私钥 + 证书）
    ca_pem_path = cert_dir / "mitmproxy-ca.pem"
    with open(ca_pem_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
        )
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    # 保存证书为 PEM 格式（仅证书）
    ca_cert_pem_path = cert_dir / "mitmproxy-ca-cert.pem"
    with open(ca_cert_pem_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    # 保存证书为 CER 格式（Windows）
    ca_cert_cer_path = cert_dir / "mitmproxy-ca-cert.cer"
    with open(ca_cert_cer_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.DER))
    
    # 保存为 PKCS12 格式（Windows）
    ca_cert_p12_path = cert_dir / "mitmproxy-ca-cert.p12"
    p12 = serialization.pkcs12.serialize_key_and_certificates(
        name=b"gf2gacha_XKL_CA",
        key=private_key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(ca_cert_p12_path, "wb") as f:
        f.write(p12)
    
    print(f"[CERT] 证书生成完成！证书目录: {cert_dir}")
    print(f"[CERT] 证书唯一ID: {user_id}")
    
    return cert_dir


def install_certificate_windows(cert_path):
    """
    在Windows上自动安装证书到受信任的根证书颁发机构
    
    Args:
        cert_path: 证书文件路径 (.cer 或 .pem)
    """
    print(f"[CERT] 正在安装证书到系统受信任根证书颁发机构...")
    
    try:
        # 使用 certutil 安装证书
        result = subprocess.run([
            "certutil", "-addstore", "-user", "Root", str(cert_path)
        ], capture_output=True, text=True, check=True)
        
        if result.returncode == 0:
            print("[CERT] 证书安装成功！")
            return True
        else:
            print(f"[CERT] 证书安装失败: {result.stderr}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"[CERT] 证书安装出错: {e}")
        print(f"[CERT] 错误输出: {e.stderr}")
        return False
    except FileNotFoundError:
        print("[CERT] 错误: 找不到 certutil 命令，请确保在Windows系统上运行")
        return False


def uninstall_certificate_windows(cert_name):
    """
    在Windows上卸载指定名称的证书
    
    Args:
        cert_name: 证书名称（Common Name）
    """
    print(f"[CERT] 正在卸载证书: {cert_name}")
    
    try:
        # 查找并删除证书
        result = subprocess.run([
            "certutil", "-user", "-delstore", "Root", cert_name
        ], capture_output=True, text=True)
        
        if result.returncode == 0 or "成功" in result.stdout:
            print(f"[CERT] 证书 '{cert_name}' 卸载成功！")
            return True
        else:
            print(f"[CERT] 证书可能不存在或卸载失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"[CERT] 卸载证书出错: {e}")
        return False


def check_certificate_installed_windows(cert_name):
    """
    检查指定名称的证书是否已安装
    
    Args:
        cert_name: 证书名称（Common Name）
        
    Returns:
        bool: 是否已安装
    """
    try:
        result = subprocess.run([
            "certutil", "-user", "-store", "Root", cert_name
        ], capture_output=True, text=True)
        
        return result.returncode == 0 and cert_name in result.stdout
        
    except Exception as e:
        print(f"[CERT] 检查证书状态时出错: {e}")
        return False


def get_certificate_info(cert_path):
    """
    读取证书信息
    
    Args:
        cert_path: 证书文件路径
        
    Returns:
        dict: 证书信息
    """
    try:
        with open(cert_path, "rb") as f:
            cert_data = f.read()
        
        # 尝试解析为PEM格式
        try:
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
        except:
            # 尝试解析为DER格式
            cert = x509.load_der_x509_certificate(cert_data, default_backend())
        
        # 提取证书信息
        subject = cert.subject
        cn = None
        for attr in subject:
            if attr.oid == NameOID.COMMON_NAME:
                cn = attr.value
                break
        
        return {
            "common_name": cn,
            "serial_number": cert.serial_number,
            "valid_from": cert.not_valid_before_utc,
            "valid_to": cert.not_valid_after_utc,
            "issuer": cert.issuer.rfc4514_string()
        }
        
    except Exception as e:
        print(f"[CERT] 读取证书信息失败: {e}")
        return None


if __name__ == "__main__":
    # 测试证书生成
    print("=" * 50)
    print("测试证书生成器")
    print("=" * 50)
    
    # 检查并生成证书
    cert_dir, need_generate = ensure_ca_certificate()
    
    if need_generate:
        cert_dir = generate_user_ca_certificate()
    else:
        print(f"[CERT] 证书已存在，跳过生成")
    
    # 显示证书信息
    cert_path = cert_dir / "mitmproxy-ca-cert.cer"
    info = get_certificate_info(cert_path)
    
    if info:
        print(f"\n[CERT] 证书信息:")
        print(f"  名称: {info['common_name']}")
        print(f"  序列号: {info['serial_number']}")
        print(f"  有效期: {info['valid_from']} 至 {info['valid_to']}")
    
    # 如果是Windows，尝试安装
    if platform.system() == "Windows":
        print(f"\n[CERT] 检测到Windows系统，尝试安装证书...")
        install_certificate_windows(cert_dir / "mitmproxy-ca-cert.cer")
