"""
===============================================================================
文件名称: auto_conn.py
文件功能: 使用 Telnet 进行串口操作，校验软件版本的 MD5 值。
作者: [zxf]
创建日期: 2025年5月12日
版本: 1.2
===============================================================================

功能描述:
1. 使用 Telnet 连接目标设备，执行一系列初始化命令。
2. 挂载目标设备的 /boot 目录，列出文件并校验指定文件的 MD5 值。
3. 提供日志记录功能，便于调试和问题排查。

依赖:
- Python 3.13 及以上
- Telnetlib3

注意事项:
1. 确保目标设备的 IP 和端口正确配置。
2. 确保目标设备支持 Telnet 协议并已启用。
3. 确保测试文件存在于目标设备的 /boot 目录中。

===============================================================================
"""

import asyncio
import logging
import re
import traceback
from typing import Optional

import telnetlib3


class SerialHandler:
    """
    使用 Telnet 进行串口操作的工具类
    """

    INIT_COMMANDS = ["q", "exit", "end", "co", "_", "_", "hzdp2015"]  # 初始化命令
    MOUNT_COMMAND = "mount /boot"  # 挂载 /boot 目录的命令
    CD_BOOT_COMMAND = "cd /boot"  # 切换到 /boot 目录的命令
    LS_COMMAND = "ls"  # 列出文件的命令

    def __init__(self, ip: str, port: int, log_level: int = logging.INFO):
        """
        初始化 SerialHandler 实例

        参数:
            ip (str): 目标设备的 IP 地址
            port (int): 目标设备的端口号
            log_level (int): 日志级别，默认为 logging.INFO
        """
        self.ip = ip
        self.port = port
        self.reader = None
        self.writer = None
        self._configure_logging(log_level)

    @staticmethod
    def _configure_logging(log_level: int):
        """
        配置日志

        参数:
            log_level (int): 日志调试等级
        """
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(levelname)s - %(message)s [%(filename)s:%(lineno)d]",
        )

    @staticmethod
    def exception_handler(func):
        """
        装饰器，用于捕获函数执行中的异常并记录日志

        参数:
            func (function): 被装饰的异步函数

        返回:
            function: 包装后的异步函数
        """
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                SerialHandler.log_exception(e, f"执行 {func.__name__} 时发生错误")
                raise

        return wrapper

    @staticmethod
    def log_exception(e: Exception, context: str = ""):
        """
        记录异常信息和堆栈

        参数:
            e (Exception): 异常对象
            context (str): 异常发生的上下文描述
        """
        logging.error(f"{context} - 错误信息: {str(e)}")
        logging.error(traceback.format_exc())

    async def _connect(self):
        """
        使用 telnetlib3 连接到目标设备

        异常:
            如果连接失败，将记录错误日志并抛出异常
        """
        try:
            self.reader, self.writer = await telnetlib3.open_connection(
                self.ip, self.port, connect_minwait=1.0, connect_maxwait=3.0
            )
            logging.info(f"成功连接到 {self.ip}:{self.port}")
        except Exception as e:
            logging.error(f"连接到 {self.ip}:{self.port} 失败: {e}")
            raise

    async def _close(self):
        """
        关闭 Telnet 连接
        """
        if self.writer:
            try:
                self.writer.close()
                logging.info("Telnet 连接已关闭")
            except Exception as e:
                logging.error(f"关闭 Telnet 连接时发生错误: {e}")

    @exception_handler
    async def _send_command(self, command: str, delay: float = 0.3):
        """
        发送命令到串口

        参数:
            command (str): 要发送的命令
            delay (float): 发送命令后的延迟时间（秒），默认为 0.3 秒
        """
        if self.writer is None:
            raise ConnectionError("Telnet 连接尚未建立，请先调用 connect 方法")
        self.writer.write(f"{command}\n")
        await asyncio.sleep(delay)
        logging.debug(f"发送命令: {command}")

    @exception_handler
    async def _read_until(self, expected: str, timeout: int = 10) -> str:
        """
        读取直到匹配到期望的字符串

        参数:
            expected (str): 期望的字符串
            timeout (int): 超时时间（秒），默认为 10 秒

        返回:
            str: 读取到的字符串
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
            return buf.decode("utf-8")
        except asyncio.TimeoutError:
            logging.error(f"读取 {expected} 超时")
            return ""

    async def _initialize_connection(self):
        """
        初始化连接，执行一系列预定义命令
        """
        for cmd in self.INIT_COMMANDS:
            await self._send_command(cmd)

    async def _execute_commands(self, commands: list[str]):
        """
        执行一组命令

        参数:
            commands (list[str]): 命令列表
        """
        for command in commands:
            await self._send_command(command)

    async def _read_and_log(self, expected: str, log_label: str) -> str:
        """
        读取数据并记录日志

        参数:
            expected (str): 期望的字符串
            log_label (str): 日志标签

        返回:
            str: 读取到的字符串
        """
        buf = await self._read_until(expected, timeout=10)
        logging.debug(
            f"{log_label}:\n"
            f"======{log_label}=======\n"
            f"{buf}\n"
            f"======{log_label}======="
        )
        return buf

    def _extract_md5(self, buf: str, test_file: str) -> Optional[str]:
        """
        从缓冲区中提取 MD5 值

        参数:
            buf (str): 缓冲区内容
            test_file (str): 测试文件名

        返回:
            Optional[str]: 提取到的 MD5 值或 None
        """
        match = re.search(r"([a-fA-F\d]{32})", buf)
        if match:
            md5_value = match.group(1)
            logging.info(f"文件 {test_file} 的 MD5 值为: {md5_value}")
            return md5_value
        else:
            logging.error("未找到有效的 MD5 值")
            return None

    async def _safe_close(self):
        """
        安全关闭连接
        """
        try:
            await self._close()
        except Exception as e:
            logging.error(f"关闭连接时发生错误: {e}")

    async def get_file_md5(self, test_file: str) -> Optional[str]:
        """
        校验软件版本的 MD5 值，返回 MD5 值

        参数:
            test_file (str): 测试文件名

        返回:
            Optional[str]: MD5 值或 None
        """
        try:
            await self._connect()

            # 初始化连接
            await self._initialize_connection()

            # 挂载目录并列出文件
            await self._execute_commands(
                [self.MOUNT_COMMAND, self.CD_BOOT_COMMAND, self.LS_COMMAND]
            )

            # 读取文件列表
            buf = await self._read_and_log(test_file, "设备返回内容A")

            # 发送 MD5 校验命令并读取结果
            await self._send_command(f"md5sum {test_file}", delay=10)
            buf = await self._read_and_log(test_file, "设备返回内容B")
            buf = await self._read_and_log(test_file, "设备返回内容C")

            # 提取 MD5 值
            return self._extract_md5(buf, test_file)
        except Exception as e:
            logging.error(f"校验过程中发生错误: {e}")
            return None
        finally:
            await self._safe_close()


# 主流程
async def main_process():
    """
    主流程，执行 MD5 校验
    """
    conn_ip = "10.138.110.183"
    conn_port = 10022
    test_file = "test.bin"

    serial_handler = SerialHandler(conn_ip, conn_port, log_level=logging.INFO)
    md5_value = await serial_handler.get_file_md5(test_file)
    if md5_value:
        print(f"获取到的 MD5 值: {md5_value}")
    else:
        print("获取 MD5 值失败")


if __name__ == "__main__":
    asyncio.run(main_process())
