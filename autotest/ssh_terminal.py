import paramiko
import threading
import sys
import time

def ssh_interactive_shell(host, username, password):
    """
    通过 SSH 进入交互式 shell，支持 Tab 补全和 '?' 等通用功能。
    输入 'exit_shell' 退出循环并关闭连接。

    :param host: 远程设备的 IP 地址或主机名
    :param username: SSH 用户名
    :param password: SSH 密码
    """
    try:
        # 创建 SSH 客户端
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname=host, username=username, password=password)

        # 使用交互式 shell
        shell = ssh_client.invoke_shell()
        print("连接成功，进入交互式模式。输入 'exit_shell' 退出。")

        # 定义一个函数实时读取输出
        def read_output():
            while True:
                if shell.recv_ready():
                    output = shell.recv(65535).decode('utf-8')
                    sys.stdout.write(f"{output}")
                    sys.stdout.flush()

        # 启动一个线程实时读取设备返回的数据
        output_thread = threading.Thread(target=read_output, daemon=True)
        output_thread.start()

        # 主线程处理用户输入
        while True:
            command = input()  # 用户输入命令
            if command.lower() == "exit_shell":
                print("退出交互式 shell。")
                break
            shell.send(command + '\n')  # 发送命令到远程设备

        # 关闭连接
        ssh_client.close()

    except Exception as e:
        print(f"Exception occurred: {str(e)}")

# 示例调用
if __name__ == "__main__":
    host = "10.138.97.126"  # 替换为目标设备的 IP 地址
    username = "admin"  # 替换为 SSH 用户名
    password = "DPtech@123456"  # 替换为 SSH 密码

    ssh_interactive_shell(host, username, password)
