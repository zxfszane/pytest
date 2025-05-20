"""
===============================================================================
文件名称: auto_web.py
文件功能: 自动化测试脚本，用于通过 Web 界面上传、删除软件版本。
作者: [zxf]
创建日期: 2025年5月12日
版本: 1.2
===============================================================================

功能描述:
1. 使用 Selenium 自动化操作 Web 页面，完成软件版本的上传和删除操作。
2. 支持通过 HTTPS 或 HTTP 协议访问 Web 界面。
3. 提供详细的日志记录功能，便于调试和问题排查。

依赖:
- Python 3.13 及以上
- Selenium
- ChromeDriver (需与 Chrome 浏览器版本匹配)

注意事项:
1. 确保目标设备的 Web 服务已启动，并正确配置 IP 地址和端口。
2. 确保 ChromeDriver 已正确安装并配置在脚本所在目录。
3. 确保测试文件路径正确，且文件存在。

===============================================================================
"""

import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select


class Web:
    """
    Web 界面操作类，封装了 Selenium 的常用操作。
    """

    def __init__(self, host_ip, username, user_password, use_https=True, log_level=logging.INFO):
        """
        初始化 Web 类并登录

        参数:
            host_ip (str): 服务器 IP 地址
            username (str): 登录用户名
            user_password (str): 登录密码
            bin_file (str): 测试文件路径
            use_https (bool): 是否使用 HTTPS 协议，默认为 True
            log_level (int): 日志调试等级，默认为 INFO
        """
        self.server_ip = host_ip
        self.user_name = username
        self.user_pwd = user_password
        self.use_https = use_https
        self.driver = None
        self._configure_logging(log_level)

    @staticmethod
    def _configure_logging(log_level):
        """
        配置日志

        参数:
            log_level (int): 日志调试等级
        """
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(levelname)s - %(message)s [%(filename)s:%(lineno)d]",
        )

    def open_web(self):
        """
        初始化 Chrome WebDriver 并登录
        """
        # 初始化 WebDriver
        file_path = os.path.join(os.getcwd(), "chromedriver.exe")
        options = webdriver.ChromeOptions()
        options.add_argument("--ignore-certificate-errors")  # 忽略证书错误
        service = Service(executable_path=file_path)
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.maximize_window()
        self.driver.implicitly_wait(10)

        # 登录操作
        protocol = "https" if self.use_https else "http"
        self.driver.get(f"{protocol}://{self.server_ip}/html/login.html")
        time.sleep(2)
        self.driver.execute_script(
            f"""
            javascript:(function(){{
            password.value='{self.user_pwd}';
            username.value='{self.user_name}';
            document.getElementById('code').setAttribute('maxlength',6);
            document.getElementById('code').value='umcccc';
            CheckForm();
            $('#loginForm').attr('action','/func/web_main/login').submit();
            }})()
            """
        )
        time.sleep(3)
        logging.info("登录成功")

    def close_web(self):
        """
        关闭 WebDriver
        """
        if self.driver:
            self.driver.quit()
            logging.info("WebDriver 已关闭")

    def _click_element(self, by, identifier, delay=2):
        """
        通用点击方法，根据定位方式和标识符点击元素

        参数:
            by (selenium.webdriver.common.by.By): 定位方式 (如 By.ID, By.XPATH)
            identifier (str): 元素标识符
            delay (int): 点击后等待的时间，默认 2 秒
        返回:
            None
        异常:
            捕获并记录查找或点击元素时的异常
        """
        try:
            element = self.driver.find_element(by, identifier)
            element.click()
            time.sleep(delay)
        except Exception as e:
            logging.error(f"点击元素失败: {identifier}, 错误信息: {e}")

    def _switch_to_iframe(self, iframe_id):
        """
        切换到指定 iframe

        参数:
            iframe_id (str): iframe 的 ID
        返回:
            None
        """
        try:
            self.driver.switch_to.frame(iframe_id)
            time.sleep(1)
        except Exception as e:
            logging.error(f"切换到 iframe '{iframe_id}' 失败: {e}")

    def _handle_alert(self, timeout=10):
        """
        等待并处理弹窗，根据内容决定接受或取消

        参数:
            timeout (int): 等待弹窗的超时时间，默认 10 秒
        返回:
            None
        """
        try:
            WebDriverWait(self.driver, timeout).until(EC.alert_is_present())
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
        except Exception as e:
            logging.error(f"处理弹窗失败: {e}")

    def navigate_to_menu(self, menu_ids):
        """
        通用菜单导航方法，按顺序点击菜单

        参数:
            menu_ids (list[str]): 菜单 ID 列表，按顺序点击
        返回:
            None
        """
        for menu_id in menu_ids:
            self._click_element(By.ID, menu_id)

    def web_upload_software(self, file_name, upload_type=2):
        """
        上传软件版本

        参数:
            file_name (str): 待上传的软件文件名
            upload_type (int): 上传类型（1: downapp, 2: change_version_button, 3: download_reboot_button）
        返回:
            None
        """
        self.navigate_to_menu(
            [
                "menu_M_System_Managment",
                "menu_T_Version_Management",
                "menu_T_Soft_Version_Update",
            ]
        )
        self._switch_to_iframe("HiddenSubWin")
        file_path = os.path.join(os.getcwd(), file_name)
        try:
            upload_input = self.driver.find_element(By.ID, "soft_file_downloadId")
            logging.info(f"上传文件路径：{file_path}")
            upload_input.send_keys(file_path)
            time.sleep(1)

            logging.info("开始上传...")
            if upload_type == 1:
                self._click_element(By.ID, "downapp")
            elif upload_type == 2:
                self._click_element(By.ID, "change_version_button")
            elif upload_type == 3:
                self._click_element(By.ID, "download_reboot_button")

            self._handle_alert(500)
            logging.info("上传完成")
        except Exception as e:
            logging.error(f"上传失败: {e}")

    def web_delete_software(self, file_name, original_file=""):
        """
        删除软件版本

        参数:
            file_name (str): 需要删除的软件文件名
            original_file (str): 需要设置为下次启动的版本（可选）
        返回:
            None
        """
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

        # 如果需要设置下次启动版本
        if original_file:
            try:
                nextboot = self.driver.find_element(By.ID, "select_id")
                select = Select(nextboot)
                select.select_by_value(original_file)
                logging.info(f"选中下拉选项 '{original_file}'，下次启动版本...")
                nextboot.click()

                self._click_element(By.ID, "SUBMIT_BTN")
                time.sleep(3)
                logging.info("设置成功！")
            except Exception as e:
                logging.error(f"设置下次启动版本失败: {e}")

        # 删除指定软件版本
        try:
            row_xpath = f"//table[@id='SoftVersionList']/tbody/tr[@value='{file_name}']"
            delete_button_xpath = (
                f"{row_xpath}/td[4]//span[contains(@class, 'gop GOP_DEL')]"
            )
            delete_button = self.driver.find_element(By.XPATH, delete_button_xpath)
            logging.info(f"找到文件 '{file_name}' ，准备删除...")
            delete_button.click()

            self._click_element(By.ID, "SUBMIT_BTN")
            time.sleep(3)
            logging.info("删除成功！")
        except Exception as e:
            logging.error(f"删除失败: {e}")

        self.driver.refresh()
        self.driver.switch_to.default_content()


# 主流程入口
if __name__ == "__main__":
    # 示例配置参数
    server_ip = "10.138.97.126"  # Web 服务器 IP 地址
    user_name = "admin"          # 登录用户名
    user_pwd = "DPtech@123456"   # 登录密码
    test_file = "test.bin"       # 测试文件名
    original_file = "LSWCTC5662-DEBUG-H9C8.0.96R3T1.bin"  # 原始文件名

    # 初始化 Web 类并登录
    web = Web(server_ip, user_name, user_pwd, use_https=True, log_level=logging.INFO)

    try:
        web.open_web()
        # 上传软件版本（如需测试上传，取消下行注释）
        web.web_upload_software(test_file)
        time.sleep(5)  # 等待上传完成

        # 删除软件版本
        web.web_delete_software(test_file, original_file)
    finally:
        # 关闭 WebDriver
        web.close_web()
