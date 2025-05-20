"""
===============================================================================
文件名称: auto_update_ssh.py
文件功能: 自动化测试脚本，用于通过 Web 界面上传、删除软件版本，并通过串口校验 MD5 值。
作者: [zxf]
创建日期: 2025年5月12日
版本: 1.2
===============================================================================

功能描述:
1. 通过 Web 页面上传软件版本，后台校验上传的版本 MD5 值是否和上传前一致。
2. 使用 Selenium 自动化操作 Web 页面，完成上传和删除软件版本的操作。
3. 使用 SSH 连接目标设备，通过挂载 /boot 目录校验版本 MD5 值。

依赖:
- Python 3.13 及以上
- Selenium
- ChromeDriver (需与 Chrome 浏览器版本匹配)

注意事项:
1. 确保目标设备和测试环境的网络连接正常。
2. 确保 ChromeDriver 已正确安装并配置在脚本所在目录。
3. 配置文件 (config.json) 必须存在，并包含必要的参数。

配置文件示例 (config.json):
{
    "server_ip": "192.168.1.1",
    "user_name": "admin",
    "user_pwd": "password",
    "test_file": "test.bin",
    "detail_print": true,
    "terminate_on_md5_mismatch": false,
    "loop_check_count": 5
}

===============================================================================
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
import traceback

from auto_ssh import SSHClientWrapper
from auto_web import Web

# 固定的全局变量
MOUNT_DIR = "/boot"  # 挂载目录
MD5SUM_CMD = "md5sum"  # MD5 校验命令
UPLOAD_TIMEOUT = 500  # 文件上传超时时间（秒）
PAGE_INIT_TIMEOUT = 10  # 页面初始化超时时间（秒）
PAGE_CLICK_TIMEOUT = 2  # 页面点击操作的延迟时间（秒）

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s [%(filename)s:%(lineno)d]",
)


# 异常处理装饰器
def exception_handler(func):
    """
    装饰器，用于捕获函数执行中的异常并记录日志。

    参数:
        func (function): 被装饰的函数。

    返回:
        function: 包装后的函数。
    """

    def wrapper(*err_args, **kwargs):
        try:
            return func(*err_args, **kwargs)
        except Exception as e:
            log_exception(e, f"执行 {func.__name__} 时发生错误")
            raise

    return wrapper


# 加载配置文件
def load_config(config_path="config.json"):
    """
    加载 JSON 格式的配置文件。

    参数:
        config_path (str): 配置文件路径，默认为 "config.json"。

    返回:
        dict: 配置文件内容。

    异常:
        如果文件不存在或格式错误，程序将终止运行。
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
        return None
    except FileNotFoundError:
        logging.error(f"配置文件未找到: {config_path}")
        sys.exit("配置文件缺失，程序终止运行！")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"配置文件格式错误: {e}")
        sys.exit("配置文件格式错误，程序终止运行！")
        return None


# 日志增强
def log_exception(e, context=""):
    """
    记录异常信息和堆栈信息。

    参数:
        e (Exception): 异常对象。
        context (str): 异常发生的上下文描述。
    """
    logging.error(f"{context} - 错误信息: {str(e)}")
    logging.error(traceback.format_exc())


# 依赖检查
def check_dependencies():
    """
    检查脚本运行所需的依赖项是否已安装。
    包括 Python 模块和 ChromeDriver。
    """
    dependencies = {
        "selenium": "pip install selenium"
    }

    for module, install_cmd in dependencies.items():
        try:
            __import__(module)
            logging.info(f"{module} 已安装")
        except ImportError:
            logging.error(f"{module} 未安装，请运行 `{install_cmd}`")
            sys.exit(1)

    # 检查 chromedriver 是否存在
    chromedriver_path = os.path.join(os.getcwd(), "chromedriver.exe")
    if not os.path.exists(chromedriver_path):
        logging.error(
            f"chromedriver.exe 未找到，请确保其位于脚本目录下: {chromedriver_path}"
        )
        sys.exit(1)

    logging.info("所有依赖项已满足")


# 解析命令行参数
def parse_args():
    """
    解析命令行参数。

    返回:
        argparse.Namespace: 包含解析后的参数。
    """
    parser = argparse.ArgumentParser(description="自动化测试脚本")
    parser.add_argument(
        "--config", type=str, default="config.json", help="配置文件路径"
    )
    return parser.parse_args()


# 计算文件 MD5
def calculate_md5(file_path):
    """
    计算文件的 MD5 值。

    参数:
        file_path (str): 文件路径。

    返回:
        str: 文件的 MD5 值，如果文件不存在则返回 None。
    """
    md5_hash = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except FileNotFoundError:
        logging.error(f"文件未找到: {file_path}")
        return None


# 提取 MD5
def extract_md5(output):
    """
    从字符串中提取 MD5 值。

    参数:
        output (str): 包含 MD5 值的字符串。

    返回:
        str: 提取到的 MD5 值，如果未找到则返回 None。
    """
    match = re.search(r"([a-fA-F\d]{32})", output)
    if match:
        return match.group(1)
    else:
        logging.error("未找到有效的 MD5 值")
        return None


# 主流程
def main_process():
    """
    主流程函数，执行文件上传、MD5 校验、删除等操作。
    """
    before_md5 = calculate_md5(boot_file)
    if not before_md5:
        logging.error("无法计算文件的 MD5 值，程序终止运行！")
        return

    logging.info(f"文件 {test_file} 的 MD5 值为: {before_md5}")

    for count in range(1, LOOP_CHECK_COUNT + 1):
        logging.info(f"第 {count} 次执行")

        # 初始化 Web 操作对象
        web = Web(server_ip, user_name, user_pwd, True)

        # 打开 Web 页面并上传软件
        web.open_web()
        web.web_upload_software(test_file)
        web.close_web()

        # logging.basicConfig() 只会在第一次调用时生效，后续再次调用不会改变已存在的日志配置
        # logging.getLogger().setLevel(logging.DEBUG)

        # 初始化 SSH 客户端并校验 MD5
        ssh_client = SSHClientWrapper(server_ip, user_name, user_pwd)

        md5_value = ssh_client.get_file_md5(test_file)
        if md5_value:
            logging.info(f"重启前 {test_file} 的 MD5 值为: {md5_value}")
            if md5_value != before_md5:
                logging.warning(f"重启前 {test_file} 的 MD5 前后不一致")
                if TERMINATE_ON_MD5_MISMATCH:
                    break
            else:
                logging.info(f"重启前 {test_file} 的 MD5 前后一致")

        ssh_client.reboot()
        logging.info(f"等待设备重启中...")
        time.sleep(60 * 4)
        logging.info(f"设备重启完成")

        md5_value = ssh_client.get_file_md5(test_file)
        if md5_value:
            logging.info(f"重启后 {test_file} 的 MD5 值为: {md5_value}")
            if md5_value != before_md5:
                logging.warning(f"重启后 {test_file} 的 MD5 前后不一致")
                if TERMINATE_ON_MD5_MISMATCH:
                    break
            else:
                logging.info(f"重启后 {test_file} 的 MD5 前后一致")

        # 删除软件并关闭 Web 页面
        web.open_web()
        web.web_delete_software(test_file, original_file)
        web.close_web()

        logging.info(f"等待设备重启2中...")
        time.sleep(60 * 4)
        logging.info(f"设备重启2完成")

        logging.info(f"第 {count} 次执行完成")
        time.sleep(5)


if __name__ == "__main__":
    # 检查依赖项
    check_dependencies()

    # 解析命令行参数
    args = parse_args()

    # 加载配置文件
    config = load_config(args.config)

    # 配置文件中的变量
    server_ip = config["server_ip"]  # Web 服务器 IP 地址
    user_name = config["user_name"]  # 登录用户名
    user_pwd = config["user_pwd"]  # 登录密码
    test_file = config["test_file"]  # 测试文件名
    DETAIL_PRINT = config["detail_print"]  # 是否打印详细信息
    TERMINATE_ON_MD5_MISMATCH = config[
        "terminate_on_md5_mismatch"
    ]  # MD5 校验失败是否终止脚本
    LOOP_CHECK_COUNT = config["loop_check_count"]  # 循环执行次数
    original_file = config["original_file"]  # 原始文件名

    # 计算测试文件的绝对路径
    boot_file = os.path.abspath(test_file)

    # 执行主流程
    main_process()
