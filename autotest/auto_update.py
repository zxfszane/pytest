"""
===============================================================================
文件名称: auto_update.py
文件功能: 自动化测试脚本，用于通过 Web 界面上传、删除软件版本，并通过串口校验 MD5 值。
作者: [zxf]
创建日期: 2025年5月12日
版本: 1.1
===============================================================================

功能描述:
1. web页面上传版本, 后台校验上传的版本MD5值是否和上传前一致。
2. web端使用selenium自动化操作, 上传和删除软件版本。
3. 后台使用telnet连接串口, 挂载/boot后校验版本 MD5值。

依赖:
- Python 3.13以上
- Selenium
- Telnetlib3
- ChromeDriver (需与 Chrome 浏览器版本匹配)

! 注意事项:
! 确保目标设备和测试环境的网络连接正常。
! 确保 ChromeDriver 已正确安装并配置在脚本所在目录。
===============================================================================
"""

import sys
import time
import os
import json
import logging
import hashlib
import traceback
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as seec
import re
import argparse
import telnetlib3
import asyncio

# 固定的全局变量
COMMANDS = ["q", "exit", "end", "co", "_", "_", "hzdp2015"]  # 串口初始化命令
MOUNT_DIR = "/boot"  # 挂载目录
MD5SUM_CMD = "md5sum"  # MD5 校验命令
READ_TIMEOUT = 10  # 串口读取超时时间（秒）
UPLOAD_TIMEOUT = 500  # 文件上传超时时间（秒）
PAGE_INIT_TIMEOUT = 10  # 页面初始化超时时间（秒）
PAGE_CLICK_TIMEOUT = 2  # 页面点击操作的延迟时间（秒）
CONN_SEND_CMD_TIMEOUT = 0.3  # 串口发送命令后的延迟时间（秒）

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s [%(filename)s:%(lineno)d]",
)


# 异常处理装饰器
def exception_handler(func):
    def wrapper(*err_args, **kwargs):
        try:
            return func(*err_args, **kwargs)
        except Exception as e:
            log_exception(e, f"执行 {func.__name__} 时发生错误")
            raise

    return wrapper


# 加载配置文件
def load_config(config_path="config.json"):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"配置文件未找到: {config_path}")
        sys.exit("配置文件缺失，程序终止运行！")
    except json.JSONDecodeError as e:
        logging.error(f"配置文件格式错误: {e}")
        sys.exit("配置文件格式错误，程序终止运行！")


# 日志增强
def log_exception(e, context=""):
    logging.error(f"{context} - 错误信息: {str(e)}")
    logging.error(traceback.format_exc())


# 获取当前时间
def get_now_time():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


# 依赖检查
def check_dependencies():
    """
    检查脚本运行所需的依赖项是否已安装
    """
    dependencies = {
        "selenium": "pip install selenium",
        "telnetlib3": "pip install telnetlib3",
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
    parser = argparse.ArgumentParser(description="自动化测试脚本")
    parser.add_argument(
        "--config", type=str, default="config.json", help="配置文件路径"
    )
    return parser.parse_args()


# 页面点击操作
class Web:
    """
    Web 界面操作类，封装了 Selenium 的常用操作。
    """

    def __init__(self):
        self.driver = None

    @exception_handler
    def _initialize_driver(self):
        """
        初始化 Chrome WebDriver
        """
        file_path = os.getcwd() + os.sep + "chromedriver.exe"
        options = webdriver.ChromeOptions()
        options.add_argument("--ignore-certificate-errors")  # 忽略证书错误
        service = Service(executable_path=file_path)
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.maximize_window()
        self.driver.implicitly_wait(PAGE_INIT_TIMEOUT)

    @exception_handler
    def _click_element(self, by, identifier, delay=PAGE_CLICK_TIMEOUT):
        """
        通用点击方法，根据定位方式和标识符点击元素
        """
        element = self.driver.find_element(by, identifier)
        element.click()
        time.sleep(delay)

    @exception_handler
    def _switch_to_iframe(self, iframe_id):
        """
        切换到指定 iframe
        """
        self.driver.switch_to.frame(iframe_id)
        time.sleep(1)

    @exception_handler
    def _handle_alert(self, timeout=UPLOAD_TIMEOUT):
        """
        等待并处理弹窗，根据内容决定接受或取消
        """
        WebDriverWait(self.driver, timeout).until(seec.alert_is_present())
        alert = self.driver.switch_to.alert
        alert_text = alert.text
        logging.info(f"弹窗内容：{alert_text}")

        # 根据弹窗内容决定操作
        if any(keyword in alert_text for keyword in ["成功", "完成", "completed"]):
            logging.info("接受弹窗")
            alert.accept()
        else:
            logging.warning("取消弹窗")
            alert.dismiss()

    def navigate_to_menu(self, menu_ids):
        """
        通用菜单导航方法
        """
        for menu_id in menu_ids:
            self._click_element(By.ID, menu_id)

    def web_main(self):
        """
        打开登录页面并登录
        """
        self._initialize_driver()
        self.driver.get(f"https://{server_ip}/html/login.html")
        time.sleep(2)
        self.driver.execute_script(
            f"""
            javascript:(function(){{
            password.value='{user_pwd}';
            username.value='{user_name}';
            document.getElementById('code').setAttribute('maxlength',6);
            document.getElementById('code').value='umcccc';
            CheckForm();
            $('#loginForm').attr('action','/func/web_main/login').submit();
            }})()
            """
        )
        time.sleep(3)
        return self.driver

    def web_upload_software(self):
        """
        上传软件版本
        """
        self.navigate_to_menu(
            [
                "menu_M_System_Managment",
                "menu_T_Version_Management",
                "menu_T_Soft_Version_Update",
            ]
        )
        self._switch_to_iframe("HiddenSubWin")

        try:
            upload_input = self.driver.find_element(By.ID, "soft_file_downloadId")
            logging.info(f"上传文件路径：{boot_file}")
            upload_input.send_keys(boot_file)
            time.sleep(1)

            logging.info(f"开始上传....{get_now_time()}")
            self._click_element(By.ID, "downapp")
            self._handle_alert()
            logging.info(f"上传完成....{get_now_time()}")
        except Exception as e:
            log_exception(e, "上传失败")

    def web_delete_software(self):
        """
        删除软件版本
        """
        logging.info(f"现在是....{get_now_time()}")
        self.driver.refresh()
        time.sleep(2)

        self.navigate_to_menu(
            [
                "menu_M_System_Managment",
                "menu_T_Version_Management",
                "menu_T_Soft_Version_Update",
            ]
        )
        self._switch_to_iframe("HiddenSubWin")

        try:
            row_xpath = f"//table[@id='SoftVersionList']/tbody/tr[@value='{test_file}']"
            delete_button_xpath = (
                f"{row_xpath}/td[4]//span[contains(@class, 'gop GOP_DEL')]"
            )
            delete_button = self.driver.find_element(By.XPATH, delete_button_xpath)
            logging.info(f"找到文件 '{test_file}' ，准备删除...")
            delete_button.click()

            self._click_element(By.ID, "SUBMIT_BTN")
            time.sleep(3)
            logging.info("删除成功！")
        except Exception as e:
            log_exception(e, "删除失败")

        self.driver.refresh()
        self.driver.switch_to.default_content()


# 串口操作类
class SerialHandler:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.reader = None
        self.writer = None

    async def connect(self):
        """
        使用 telnetlib3 连接到目标设备
        """
        self.reader, self.writer = await telnetlib3.open_connection(
            self.ip, self.port, connect_minwait=1.0, connect_maxwait=3.0
        )

    @exception_handler
    async def send_command(self, command, delay=CONN_SEND_CMD_TIMEOUT):
        """
        发送命令到串口
        """
        if self.writer is None:
            raise ConnectionError("Telnet 连接尚未建立，请先调用 connect 方法")
        self.writer.write(f"{command}\n")
        await asyncio.sleep(delay)
        logging.debug(f"发送命令: {command}")

    @exception_handler
    async def read_until(self, expected, timeout=READ_TIMEOUT):
        """
        读取直到匹配到期望的字符串
        """
        if self.reader is None:
            raise ConnectionError("Telnet 连接尚未建立，请先调用 connect 方法")
        try:
            expected_bytes = (
                expected.encode("utf-8") if isinstance(expected, str) else expected
            )
            buf = await asyncio.wait_for(
                self.reader.readuntil(expected_bytes), timeout=timeout
            )
            logging.debug(f"读取到的数据: {buf}")
            return buf.decode("utf-8")  # 解码为字符串返回
        except asyncio.TimeoutError:
            logging.error(f"读取 {expected} 超时")
            return ""

    async def close(self):
        """
        关闭 Telnet 连接
        """
        if self.writer:
            self.writer.close()  # 直接关闭连接
            logging.info("Telnet 连接已关闭")


# 计算文件 MD5
def calculate_md5(file_path):
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
    match = re.search(r"([a-fA-F\d]{32})", output)
    if match:
        return match.group(1)
    else:
        logging.error("未找到有效的 MD5 值")
        return None


# 校验软件版本的 MD5 值
async def conn_validate_soft_process(serial_handler, before_md5):
    try:
        # 执行初始化命令
        for cmd in COMMANDS:
            await serial_handler.send_command(cmd)

        # 挂载目录并列出文件
        await serial_handler.send_command("", 3)
        await serial_handler.send_command(f"mount {MOUNT_DIR}")
        await serial_handler.send_command(f"cd {MOUNT_DIR}")
        await serial_handler.send_command("ls")

        # 读取文件列表
        buf = await serial_handler.read_until(f"{test_file}", timeout=READ_TIMEOUT)
        if DETAIL_PRINT:
            logging.debug(f"设备返回内容1: {buf}")

        # 发送 MD5 校验命令
        await serial_handler.send_command(f"{MD5SUM_CMD} {test_file}", delay=READ_TIMEOUT)

        # 读取 MD5 命令
        buf = await serial_handler.read_until(f"{test_file}", timeout=READ_TIMEOUT)
        if DETAIL_PRINT:
            logging.debug(f"设备返回内容2: {buf}")

        # 读取 MD5 校验结果
        buf = await serial_handler.read_until(f"{test_file}", timeout=READ_TIMEOUT)
        if DETAIL_PRINT:
            logging.debug(f"设备返回内容3: {buf}")

        # 提取 MD5 值
        after_md5 = extract_md5(buf)
        if after_md5 is None:
            logging.error("MD5 获取失败，跳过校验")
            return True

        # 打印详细信息
        if DETAIL_PRINT:
            logging.info(f"MD5 校验结果: {buf}")
        logging.info(f"计算后的MD5值  : {after_md5}")

        # 比较 MD5 值
        if after_md5 != before_md5:
            logging.error(
                f"========================================================================\n"
                f"{test_file} MD5 校验失败！\n"
                f"上传前: {before_md5}\n"
                f"上传后: {after_md5}\n"
                f"========================================================================\n"
            )
            if TERMINATE_ON_MD5_MISMATCH:
                raise SystemExit("MD5 校验失败，脚本终止运行！")
            else:
                return False
        else:
            logging.info(f"MD5上传前后一致: {before_md5}")
        return True

    except Exception as e:
        log_exception(e, "校验过程中发生错误")
        return False


# 主流程
async def main_process():
    before_md5 = calculate_md5(boot_file)
    if not before_md5:
        logging.error("无法计算文件的 MD5 值，程序终止运行！")
        return

    logging.info(f"文件 {test_file} 的 MD5 值为: {before_md5}")

    web = Web()
    web.web_main()

    serial_handler = SerialHandler(conn_ip, conn_port)
    await serial_handler.connect()

    for count in range(1, LOOP_CHECK_COUNT + 1):
        logging.info(f"{get_now_time()}  第 {count} 次执行")

        web.web_upload_software()

        try:
            if not await conn_validate_soft_process(serial_handler, before_md5):
                logging.warning("MD5 校验失败，但脚本继续运行（根据配置）。")
                if TERMINATE_ON_MD5_MISMATCH:
                    break
        except SystemExit as e:
            logging.error(str(e))
            break

        web.web_delete_software()
        logging.info(f"第 {count} 次执行完成")
        await asyncio.sleep(5)

    await serial_handler.close()


if __name__ == "__main__":
    check_dependencies()
    args = parse_args()
    config = load_config(args.config)

    # 配置文件中的变量
    server_ip = config["server_ip"]  # Web 服务器 IP 地址
    user_name = config["user_name"]  # 登录用户名
    user_pwd = config["user_pwd"]  # 登录密码
    conn_ip = config["conn_ip"]  # 串口连接的 IP 地址
    conn_port = config["conn_port"]  # 串口连接的端口号
    test_file = config["test_file"]  # 测试文件名
    DETAIL_PRINT = config["detail_print"]  # 是否打印详细信息
    TERMINATE_ON_MD5_MISMATCH = config[
        "terminate_on_md5_mismatch"
    ]  # MD5 校验失败是否终止脚本
    LOOP_CHECK_COUNT = config["loop_check_count"]  # 循环执行次数

    # 计算测试文件的绝对路径
    boot_file = os.path.abspath(test_file)

    asyncio.run(main_process())
