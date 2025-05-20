"""
===============================================================================
文件名称: auto_ssh.py
文件功能: 使用 SSH 连接远程设备，执行命令并获取文件的 MD5 值。
作者: [zxf]
创建日期: 2025年5月12日
版本: 1.2
===============================================================================

功能描述:
1. 使用 Paramiko 库通过 SSH 连接远程设备。
2. 执行一系列命令，包括挂载目录、切换目录和计算文件的 MD5 值。
3. 提供日志记录功能，便于调试和问题排查。

依赖:
- Python 3.13 及以上
- Paramiko

注意事项:
1. 确保目标设备的 SSH 服务已启动，并正确配置 IP 地址和端口。
2. 确保提供的用户名和密码具有执行相关命令的权限。
3. 确保目标文件存在于远程设备的指定目录中。

===============================================================================
"""

import time
import paramiko
import re
import logging


class SSHClientWrapper:
    """
    SSH 客户端包装类，用于通过 SSH 执行命令并获取文件的 MD5 值。
    """

    def __init__(self, host, username, password, log_level=logging.INFO, default_delay=1):
        """
        初始化 SSH 客户端包装类。

        参数:
            host (str): 远程设备的 IP 地址或主机名
            username (str): SSH 用户名
            password (str): SSH 密码
            log_level (int): 日志调试等级（默认 INFO）
            default_delay (int): 默认命令延迟时间（秒）
        """
        self.host = host
        self.username = username
        self.password = password
        self.default_delay = default_delay
        self.log_level = log_level
        self.ssh_client = None
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

    def _connect(self):
        """
        建立 SSH 连接（内部方法）。

        异常:
            如果连接失败，将记录错误日志并抛出异常。
        """
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(hostname=self.host, username=self.username, password=self.password)
            logging.info("SSH 连接成功。")
        except paramiko.AuthenticationException:
            logging.error("认证失败，请检查用户名或密码。")
            raise
        except paramiko.SSHException as ssh_error:
            logging.error(f"SSH 连接错误: {str(ssh_error)}")
            raise
        except Exception as e:
            logging.error(f"发生异常: {str(e)}")
            raise

    def _disconnect(self):
        """
        关闭 SSH 连接（内部方法）。
        """
        if self.ssh_client:
            self.ssh_client.close()
            logging.info("SSH 连接已关闭。")

    def reboot(self):
        try:
            # 建立连接
            self._connect()

            # 使用交互式 shell
            shell = self.ssh_client.invoke_shell()
            logging.debug("进入交互式模式。")
            time.sleep(5)

            # 检查初始输出
            if shell.recv_ready():
                output = shell.recv(65535).decode('utf-8')
                logging.debug(output)

            # 定义命令和延迟时间
            commands_with_delays = [
                ("reboot", 1),
                ("Y", 1),
                ("Y", 1)
            ]

            for cmd, delay in commands_with_delays:
                logging.info(f"发送命令: {cmd}")
                shell.send(cmd + '\n')
                time.sleep(delay)

                # 检查命令输出
                if shell.recv_ready():
                    output = shell.recv(65535).decode('utf-8')
                    logging.info(output)

        except Exception as e:
            logging.error(f"发生异常: {str(e)}")
            return None

        finally:
            # 确保断开连接
            self._disconnect()

    def get_file_md5(self, file_name):
        """
        获取远程文件的 MD5 值。

        参数:
            file_name (str): 需要计算 MD5 的远程文件名

        返回:
            str: 文件的 MD5 值（32位十六进制字符串），未获取到则返回 None
        """
        try:
            # 建立 SSH 连接
            self._connect()

            # 获取交互式 shell
            shell = self.ssh_client.invoke_shell()
            logging.debug("进入交互式 shell 模式。")
            time.sleep(2)  # 等待 shell 初始化

            # 读取初始欢迎信息
            if shell.recv_ready():
                output = shell.recv(65535).decode('utf-8')
                logging.debug(f"初始输出: {output}")

            # 需要依次执行的命令及等待时间（秒）
            commands_with_delays = [
                ("ssh 127.0.0.1 22000", 1),   # 跳转到目标端口
                ("conplat", 1),               # 登录平台
                ("yy4lsz1h", 1),              # 输入密码
                ("su", 1),                    # 切换到 root
                ("yy4lsz1h", 1),              # 输入 root 密码
                ("mount /boot", 1),           # 挂载 /boot
                ("cd /boot", 1),              # 进入 /boot 目录
                (f"md5sum {file_name}", 6)    # 计算文件 MD5
            ]

            md5info = ""
            for cmd, delay in commands_with_delays:
                logging.info(f"发送命令: {cmd}")
                shell.send(cmd + '\n')
                time.sleep(delay)
                # 读取命令输出
                output = ""
                while shell.recv_ready():
                    output += shell.recv(65535).decode('utf-8')
                    time.sleep(0.2)
                if output:
                    logging.info(f"命令输出: {output}")
                if "md5sum" in cmd:
                    md5info = output  # 保存 md5sum 的输出

            # 退出登录，确保安全退出
            for cmd in ["exit", "exit"]:
                logging.info(f"发送命令: {cmd}")
                shell.send(cmd + '\n')
                time.sleep(1)
                output = ""
                while shell.recv_ready():
                    output += shell.recv(65535).decode('utf-8')
                    time.sleep(0.2)
                if output:
                    logging.info(f"退出输出: {output}")

            # 正则提取 MD5 值
            md5_match = re.search(r'\b[0-9a-fA-F]{32}\b', md5info)
            if md5_match:
                md5_value = md5_match.group(0)
                logging.info(f"提取到的文件 MD5: {md5_value}")
                return md5_value
            else:
                logging.warning("未能提取到有效的 MD5 信息。")
                return None

        except Exception as e:
            logging.error(f"获取 MD5 过程中发生异常: {str(e)}")
            return None

        finally:
            # 关闭 SSH 连接
            self._disconnect()


# 示例调用
if __name__ == "__main__":
    host = "10.138.97.126"  # 替换为目标设备的 IP 地址
    username = "admin"  # 替换为 SSH 用户名
    password = "DPtech@123456"  # 替换为 SSH 密码
    file_name = "lswctc.bin"  # 替换为目标文件名

    # 创建 SSH 客户端实例，启用详细日志
    ssh_client = SSHClientWrapper(host, username, password, logging.DEBUG)
    md5_value = ssh_client.get_file_md5(file_name)
    if md5_value:
        print(f"文件 {file_name} 的 MD5 值为: {md5_value}")
    else:
        print("未能获取文件的 MD5 值。")

    ssh_client.reboot()

    time.sleep(500)

    print("结束了!")
