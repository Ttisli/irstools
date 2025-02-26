import sys
import re
import mysql.connector
import configparser
import logging
import json
import html  # 导入 html 模块
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit,
                             QScrollArea, QFrame, QMessageBox, QComboBox,
                             QGridLayout)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QIcon

# 配置日志记录
logging.basicConfig(
    filename='app.log',  # 日志文件名
    level=logging.DEBUG,  # 设置日志级别为 DEBUG，记录所有级别的日志信息
    format='%(asctime)s - %(levelname)s - %(message)s',  # 日志格式：时间 - 日志级别 - 日志信息
    filemode='a'  # 日志文件模式：追加模式，每次运行程序都在文件末尾添加日志
)


class DatabaseWorker(QThread):
    """
    数据库操作工作线程，用于在后台线程执行数据库操作，避免阻塞 UI 线程。
    """

    result_signal = pyqtSignal(str, list, list)  # 查询结果信号：表名，列名列表，数据列表
    error_signal = pyqtSignal(str)  # 错误信号：错误信息
    connection_signal = pyqtSignal(bool)  # 连接状态信号：连接成功/失败
    update_signal = pyqtSignal(str)  # 更新结果信号：更新信息
    columns_loaded_signal = pyqtSignal()  # 表字段加载完成信号

    def __init__(self, host, port, user, password, database):
        """
        初始化数据库连接信息。

        Args:
            host (str): 数据库主机名或 IP 地址。
            port (int): 数据库端口号。
            user (str): 数据库用户名。
            password (str): 数据库密码。
            database (str): 数据库名。
        """
        super().__init__()
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.input_text = ""
        self.conn = None  # 数据库连接对象，初始为 None
        self._table_columns = {}  # 存储表字段信息的字典，key 为表名，value 为字段列表
        # 预定义的条件列参数，用于限制更新操作的条件列范围，增强安全性
        self._table_conditions = {
            "ecsstatic": ["instanceId", "privateIpAddress", "eipAddress"],
            "rdsstatic": ["dBInstanceId", "ipAddress", "eipAddress"],
            "slbstatic": ["loadBalancerId", "slbIp", "eipAddress"],
            "ossstatic": ["instanceName"]
        }

    def run(self):
        """
        主运行逻辑：连接数据库并预加载表字段。
        在线程启动时自动执行，负责建立数据库连接并预加载表字段信息。
        """
        try:
            # 尝试连接数据库
            self.conn = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                connection_timeout=5  # 设置连接超时时间为 5 秒
            )
            self.connection_signal.emit(True)  # 连接成功，发送连接成功信号
            self.preload_table_columns()  # 预加载表字段

        except mysql.connector.Error as e:
            # 数据库连接失败，记录错误信息并发送错误信号
            logging.error(f"数据库连接失败: {e}")
            self.error_signal.emit(self.get_error_message(e))
            self.connection_signal.emit(False)  # 发送连接失败信号
        except Exception as e:
            # 其他异常，记录堆栈信息并发送错误信号
            logging.error(f"连接失败: {e}", exc_info=True)  # 记录堆栈信息
            self.error_signal.emit(f"连接失败: {e}")
            self.connection_signal.emit(False)

    def preload_table_columns(self):
        """
        预加载所有表的字段名，存储在 self._table_columns 字典中，用于后续查询和更新操作。
        """
        for table_name in ["ecsstatic", "rdsstatic", "slbstatic", "ossstatic"]:
            try:
                # 尝试重新连接数据库，防止连接断开
                if not self.conn.is_connected():
                    self.conn.reconnect(attempts=3, delay=1)
                cursor = self.conn.cursor()
                cursor.execute(f"SHOW COLUMNS FROM {table_name}")  # 执行 SQL 语句，获取表字段信息
                columns = [row[0] for row in cursor.fetchall()]  # 提取字段名
                self._table_columns[table_name] = columns  # 存储表字段信息
                cursor.close()
            except mysql.connector.Error as e:
                # 获取表字段失败，记录错误信息并发送错误信号
                self.error_signal.emit(f"获取表 {table_name} 字段失败: {e}")
                logging.error(f"获取表 {table_name} 字段失败: {e}")
        self.columns_loaded_signal.emit()  # 表字段加载完成，发送信号

    def execute_query(self, input_text):
        """
        执行查询操作，根据输入内容判断查询类型，并调用相应的查询函数。

        Args:
            input_text (str): 用户输入的查询内容。
        """
        try:
            # 尝试重新连接数据库，防止连接断开
            if not self.conn.is_connected():
                self.conn.reconnect(attempts=3, delay=1)

            # 根据输入内容判断查询类型
            if self.is_valid_ip(input_text):
                self.query_ip_tables(input_text)  # 查询 IP 相关表
            elif self.is_uuid(input_text) :  # 如果是 UUID,  同时查询 slb 和 ecs
                 self.query_ecs_table(input_text)
                 self.query_slb_table(input_text)
            elif  input_text.startswith("lb-"): #lb- 开头只查slb
                self.query_slb_table(input_text)  # 查询 SLB 表
            elif input_text.startswith("i-"): # i- 开头只查ecs
                self.query_ecs_table(input_text)  # 查询 ECS 表
            elif input_text.startswith(("pc-", "rm-")):
                self.query_rds_table(input_text)  # 查询 RDS 表
            else:
                self.query_oss_table(input_text)  # 查询 OSS 表
        except mysql.connector.Error as e:
            # 查询失败，记录错误信息并发送错误信号
            self.error_signal.emit(f"查询失败: {e}")
            logging.error(f"查询失败: {e}")
        except Exception as e:
            # 查询时发生未知错误，记录堆栈信息并发送错误信号
            self.error_signal.emit(f"查询时发生未知错误: {e}")
            logging.exception("查询时发生未知错误")  # 记录堆栈信息

    def query_ip_tables(self, ip):
        """
        查询 IP 相关表 (ecsstatic, rdsstatic, slbstatic)。

        Args:
            ip (str): 要查询的 IP 地址。
        """
        tables = {
            "ecsstatic": "eipAddress = %s OR privateIpAddress = %s",
            "rdsstatic": "ipAddress = %s OR eipAddress = %s",
            "slbstatic": "slbIp = %s OR eipAddress = %s"
        }
        self._query_tables([(table_name, condition, (ip, ip)) for table_name, condition in tables.items()])

    def query_slb_table(self, text):
        """
        查询 slbstatic 表，根据 loadBalancerId  (支持UUID 或 lb- 开头).

        Args:
            text (str): 要查询的 loadBalancerId.
        """
        tables = [("slbstatic", "loadBalancerId LIKE %s", (f"%{text}%",))]
        self._query_tables(tables)  # 使用通用方法

    def query_ecs_table(self, text):
         """
         查询 ECS 表 (ecsstatic)，根据 instanceId (支持UUID 或 i- 开头)。

         Args:
             text (str): 要查询的 instanceId。
         """
         tables = [("ecsstatic", "instanceId LIKE %s", (f"%{text}%",))]
         self._query_tables(tables)  # 使用通用方法

    def query_rds_table(self, text):
        """
        查询 RDS 表 (rdsstatic)，根据 dBInstanceId。

        Args:
            text (str): 要查询的 dBInstanceId。
        """
        self._query_tables([("rdsstatic", "dBInstanceId LIKE %s", (f"%{text}%",))])

    def query_oss_table(self, text):
        """
        查询 OSS 表 (ossstatic)，根据 instanceName。

        Args:
            text (str): 要查询的 instanceName。
        """
        self._query_tables([("ossstatic", "instanceName LIKE %s", (f"%{text}%",))])

    def _query_tables(self, tables):
        """
        通用查询方法，减少代码重复。

        Args:
            tables (list): 包含表名、查询条件和参数的列表。
        """
        for table_name, condition, params in tables:
            if table_name in self._table_columns:
                # 如果表字段信息已加载，则执行查询
                self.query_table(table_name, self._table_columns[table_name], condition, params)
            else:
                # 如果表字段信息未加载，则发送错误信号
                self.error_signal.emit(f"表 {table_name} 的字段信息未加载")

    def query_table(self, table_name, columns, condition, params):
        """
        执行具体表查询。

        Args:
            table_name (str): 表名。
            columns (list): 要查询的列名列表。
            condition (str): 查询条件。
            params (tuple): 查询参数。
        """
        try:
            cursor = self.conn.cursor()
            query = f"SELECT {', '.join(columns)} FROM {table_name} WHERE {condition}"  # 构建 SQL 查询语句

            # 记录查询信息到日志
            log_data = {"table_name": table_name, "query": query, "params": params}
            logging.debug(f"执行查询: {json.dumps(log_data, ensure_ascii=False)}")

            cursor.execute(query, params)  # 执行 SQL 语句
            results = cursor.fetchall()  # 获取查询结果

            if results:
                # 查询到数据，发送查询结果信号
                self.result_signal.emit(table_name, columns, results)
            else:
                # 未查询到数据，发送空结果信号
                self.result_signal.emit(table_name, [], [])

            cursor.close()
        except mysql.connector.Error as e:
            # 查询失败，记录错误信息并发送错误信号
            self.error_signal.emit(f"{table_name}表查询失败: {e}")
            logging.error(f"{table_name}表查询失败: {e}")
        except Exception as e:
            # 查询时发生未知错误，记录堆栈信息并发送错误信号
            self.error_signal.emit(f"查询 {table_name} 表时发生未知错误: {e}")
            logging.exception(f"查询 {table_name} 表时发生未知错误: {e}")

    def execute_update(self, table_name, update_column, update_value, conditions):
        """
        执行更新操作 (修改)。

        Args:
            table_name (str): 要更新的表名。
            update_column (str): 要更新的列名。
            update_value (str): 新的列值。
            conditions (dict): 更新条件，key 为列名，value 为列值。
        """
        try:
            # 尝试重新连接数据库，防止连接断开
            if not self.conn.is_connected():
                self.conn.reconnect(attempts=3, delay=1)

            cursor = self.conn.cursor()

            # 构建 WHERE 子句
            where_clauses = [f"{col} = %s" for col in conditions.keys()]
            where_clause = " AND ".join(where_clauses)
            query = f"UPDATE {table_name} SET {update_column} = %s WHERE {where_clause}"  # 构建 SQL 更新语句
            params = [update_value] + list(conditions.values())  # 构建 SQL 参数

            # 记录更新信息到日志
            log_data = {
                "table_name": table_name,
                "query": query,
                "params": params,
                "update_column": update_column,
                "update_value": update_value,
                "conditions": conditions
            }
            logging.debug(f"执行更新: {json.dumps(log_data, ensure_ascii=False)}")

            cursor.execute(query, tuple(params))  # 执行 SQL 语句
            self.conn.commit()  # 提交事务
            self.update_signal.emit(
                f"成功更新 {table_name} 表: {update_column} = {update_value} WHERE {where_clause} (条件: {conditions})")  # 发送更新结果信号
            cursor.close()

        except mysql.connector.Error as e:
            # 更新失败，记录错误信息并发送错误信号
            self.error_signal.emit(f"更新 {table_name} 表失败: {e}")
            logging.error(f"更新数据库失败: {e}")
        except Exception as e:
            # 更新时发生未知错误，记录堆栈信息并发送错误信号
            self.error_signal.emit(f"更新数据库时发生未知错误: {e}")
            logging.exception(f"更新数据库时发生未知错误: {e}")

    @staticmethod
    def is_valid_ip(ip):
        """
        检查字符串是否为有效的 IPv4 地址。

        Args:
            ip (str): 要检查的字符串。

        Returns:
            bool: 如果是有效的 IPv4 地址，则返回 True，否则返回 False。
        """
        pattern = re.compile(r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
        return bool(pattern.match(ip))

    @staticmethod
    def is_uuid(text):
        """
        检查字符串是否为有效的 UUID。

        Args:
            text (str): 要检查的字符串。

        Returns:
            bool: 如果是有效的 UUID，则返回 True，否则返回 False。
        """
        pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
        return bool(pattern.match(text))

    @staticmethod
    def get_error_message(err):
        """
        获取数据库错误信息。

        Args:
            err (mysql.connector.Error): 数据库错误对象。

        Returns:
            str: 错误信息。
        """
        error_messages = {
            2003: "无法连接到数据库服务器",
            1045: "身份验证失败",
            1049: "目标数据库不存在",
            2013: "连接超时",
            1054: "未知列"
        }
        return error_messages.get(err.errno, f"数据库错误: {err}")


class MainWindow(QWidget):
    """
    主界面类，负责 UI 显示和用户交互。
    """

    def __init__(self):
        """
        初始化主界面。
        """
        super().__init__()
        self.worker = None  # 数据库工作线程对象，初始为 None
        self.db_connected = False  # 数据库连接状态，初始为 False
        self.init_ui()  # 初始化 UI 界面
        self.load_config()  # 加载配置文件
        self.init_database()  # 初始化数据库连接
        # 添加图标
        if hasattr(sys, '_MEIPASS'):
            #  如果打包了，则从临时目录加载图标
            icon_path = os.path.join(sys._MEIPASS, 'smile.png')
        else:
            #  否则，从当前目录加载图标
            icon_path = 'con.png'

        self.setWindowIcon(QIcon(icon_path))

    def init_ui(self):
        """
        初始化界面。
        """
        self.setWindowTitle("IRS数据库工具 - by 章鱼")  # 设置窗口标题
        self.setFixedSize(700, 600)  # 设置窗口大小

        # 查询控件
        self.input_label = QLabel("请输入查询内容:")  # 查询输入框标签
        self.input_field = QLineEdit()  # 查询输入框
        self.input_field.setPlaceholderText("支持IP/UUID/实例ID/OSS名称/lb-/i-")  # 设置输入框提示信息
        self.query_btn = QPushButton("执行查询")  # 查询按钮
        self.result_area = QTextEdit()  # 查询结果显示区域
        self.status_bar = QLabel("正在初始化数据库连接...")  # 状态栏

        # 更新控件
        self.table_label = QLabel("选择表:")  # 表选择下拉框标签
        self.table_combo = QComboBox()  # 表选择下拉框
        self.table_combo.addItems(["ecsstatic", "rdsstatic", "slbstatic", "ossstatic"])  # 添加表名到下拉框

        self.update_column_label = QLabel("更新列:")  # 更新列下拉框标签
        self.update_column_combo = QComboBox()  # 更新列下拉框
        self.table_combo.currentIndexChanged.connect(self.update_update_columns)  # 绑定表选择事件

        self.update_value_label = QLabel("更新值:")  # 更新值输入框标签
        self.update_value_field = QLineEdit()  # 更新值输入框

        # 条件控件
        self.condition_column_label = QLabel("条件列:")  # 条件列下拉框标签
        self.condition_column_combo = QComboBox()  # 条件列下拉框
        self.table_combo.currentIndexChanged.connect(self.update_condition_columns)  # 绑定表选择事件

        self.condition_value_label = QLabel("条件值:")  # 条件值输入框标签
        self.condition_value_field = QLineEdit()  # 条件值输入框

        self.update_btn = QPushButton("执行更新")  # 更新按钮

        # 设置属性
        self.result_area.setReadOnly(True)  # 设置结果显示区域为只读
        self.query_btn.clicked.connect(self.execute_query)  # 绑定查询按钮点击事件
        self.input_field.returnPressed.connect(self.execute_query)  # 绑定输入框回车事件
        self.update_btn.clicked.connect(self.execute_update)  # 绑定更新按钮点击事件

        # 布局设置 (查询)
        query_layout = QHBoxLayout()
        query_layout.addWidget(self.input_label)
        query_layout.addWidget(self.input_field)
        query_layout.addWidget(self.query_btn)

        # 布局设置 (更新)
        update_layout = QGridLayout()
        update_layout.addWidget(self.table_label, 0, 0)
        update_layout.addWidget(self.table_combo, 0, 1)
        update_layout.addWidget(self.update_column_label, 1, 0)
        update_layout.addWidget(self.update_column_combo, 1, 1)
        update_layout.addWidget(self.update_value_label, 2, 0)
        update_layout.addWidget(self.update_value_field, 2, 1)
        update_layout.addWidget(self.condition_column_label, 3, 0)
        update_layout.addWidget(self.condition_column_combo, 3, 1)
        update_layout.addWidget(self.condition_value_label, 4, 0)
        update_layout.addWidget(self.condition_value_field, 4, 1)
        update_layout.addWidget(self.update_btn, 5, 0, 1, 2)  # 跨两列

        # 结果区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.result_area)

        # 状态栏
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.StyledPanel)
        status_layout = QHBoxLayout(status_frame)
        status_layout.addWidget(self.status_bar)

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.addLayout(query_layout)
        main_layout.addWidget(scroll_area)
        main_layout.addLayout(update_layout)
        main_layout.addWidget(status_frame)
        self.setLayout(main_layout)

        # 样式美化
        self.setStyleSheet("""
            QComboBox {
                padding: 6px;
                border: 1px solid #BDBDBD;
                border-radius: 4px;
            }
            QGridLayout {
               margin: 10px;
            }
        """)

    def update_update_columns(self, index):
        """
        根据所选表更新'更新列'下拉列表。

        Args:
            index (int): 所选表的索引。
        """
        table_name = self.table_combo.itemText(index)  # 获取所选表名
        self.update_column_combo.clear()  # 清空更新列下拉框
        if table_name in self.worker._table_columns:
            # 如果表字段信息已加载，则添加字段到下拉框
            self.update_column_combo.addItems(self.worker._table_columns[table_name])

    def update_condition_columns(self, index):
        """
        根据所选表更新'条件列'下拉列表。

        Args:
            index (int): 所选表的索引。
        """
        table_name = self.table_combo.itemText(index)  # 获取所选表名
        self.condition_column_combo.clear()  # 清空条件列下拉框
        # 仅添加预定义的条件列
        if table_name in self.worker._table_conditions:
            # 如果表有预定义的条件列，则添加到下拉框
            self.condition_column_combo.addItems(self.worker._table_conditions[table_name])

    def load_config(self):
        """
        加载配置文件。
        """
        self.config = configparser.ConfigParser()
        try:
            if not self.config.read('config.ini'):
                raise FileNotFoundError("配置文件不存在")
            if not self.config.has_section('DATABASE'):
                raise ValueError("缺少[DATABASE]配置节")

            self.db_config = {
                'host': self.config.get('DATABASE', 'host'),
                'port': self.config.get('DATABASE', 'port'),
                'user': self.config.get('DATABASE', 'user'),
                'password': self.config.get('DATABASE', 'password'),
                'database': self.config.get('DATABASE', 'database')
            }
        except Exception as e:
            QMessageBox.critical(self, "配置错误", f"配置文件错误: {e}")
            sys.exit(1)

    def init_database(self):
        """
        初始化数据库连接。
        """
        self.worker = DatabaseWorker(
            host=self.db_config['host'],
            port=self.db_config['port'],
            user=self.db_config['user'],
            password=self.db_config['password'],
            database=self.db_config['database']
        )  # 创建数据库工作线程
        self.worker.error_signal.connect(self.show_error)  # 绑定错误信号
        self.worker.connection_signal.connect(self.handle_connection)  # 绑定连接状态信号
        self.worker.result_signal.connect(self.handle_results)  # 绑定查询结果信号
        self.worker.update_signal.connect(self.handle_update_result)  # 绑定更新结果信号
        self.worker.columns_loaded_signal.connect(self.handle_columns_loaded)  # 绑定表字段加载完成信号
        self.worker.start()  # 启动数据库工作线程

    def execute_query(self):
        """
        执行查询。
        """
        if not self.db_connected:
            # 数据库未连接，显示警告信息
            QMessageBox.warning(self, "警告", "数据库连接未就绪")
            return

        input_text = self.input_field.text().strip()  # 获取输入内容并去除空格
        if not input_text:
            # 输入内容为空，显示警告信息
            QMessageBox.warning(self, "输入错误", "查询内容不能为空")
            return

        self.status_bar.setText("正在查询...")  # 设置状态栏信息
        self.query_btn.setEnabled(False)  # 禁用查询按钮
        self.result_area.clear()  # 清空结果显示区域
        self.worker.execute_query(input_text)  # 执行查询

    def execute_update(self):
        """
        执行更新 (修改)。
        """
        if not self.db_connected:
            # 数据库未连接，显示警告信息
            QMessageBox.warning(self, "警告", "数据库连接未就绪")
            return

        table_name = self.table_combo.currentText()  # 获取所选表名
        update_column = self.update_column_combo.currentText()  # 获取所选更新列名
        update_value = self.update_value_field.text().strip()  # 获取更新值

        # 获取所有条件
        conditions = {}
        # 获取条件列和条件值
        condition_column = self.condition_column_combo.currentText()
        condition_value = self.condition_value_field.text().strip()

        if condition_column and condition_value:
            # 验证条件列是否在允许的范围内
            if table_name in self.worker._table_conditions and condition_column in self.worker._table_conditions[table_name]:
                conditions[condition_column] = condition_value
            else:
                QMessageBox.warning(self, "输入错误", f"条件列 '{condition_column}' 不允许用于表 '{table_name}'")
                return

        if not update_value:
            # 更新值为空，显示警告信息
            QMessageBox.warning(self, "输入错误", "更新值不能为空")
            return

        if not conditions:
            # 没有条件，显示警告信息
            QMessageBox.warning(self, "输入错误", "请至少添加一个条件")
            return

        self.status_bar.setText("正在更新...")  # 设置状态栏信息
        self.update_btn.setEnabled(False)  # 禁用更新按钮
        self.worker.execute_update(table_name, update_column, update_value, conditions)  # 执行更新

    def handle_results(self, table_name, columns, data):
        """
        处理查询结果。

        Args:
            table_name (str): 表名。
            columns (list): 列名列表。
            data (list): 数据列表。
        """
        self.result_area.append(f"【{table_name}】")  # 添加表名到结果显示区域
        if columns and data:
            # 构建 HTML 表格
            html_table = "<table border='1' style='border-collapse: collapse; font-size: 14px;'>"

            # 添加数据行 (每列一列)
            for i, column in enumerate(columns):
                html_table += "<tr>"
                html_table += f"<th style='padding: 5px; min-width: 120px;'>{column}</th>"
                # 遍历每一行数据，取出当前列的值
                values = [html.escape(str(row[i])) for row in data]
                html_table += f"<td style='padding: 5px;'>{'<br>'.join(values)}</td>"
                html_table += "</tr>"

            html_table += "</table>"
            self.result_area.insertHtml(html_table)  # 插入 HTML 表格到结果显示区域
        else:
            self.result_area.append("未查询到数据")  # 未查询到数据

        self.status_bar.setText("查询完成")  # 设置状态栏信息
        self.query_btn.setEnabled(True)  # 启用查询按钮

    def handle_update_result(self, message):
        """
        处理更新结果。

        Args:
            message (str): 更新信息。
        """
        self.result_area.append(message)  # 添加更新信息到结果显示区域
        self.status_bar.setText("更新完成")  # 设置状态栏信息
        self.update_btn.setEnabled(True)  # 启用更新按钮

    def show_error(self, message):
        """
        显示错误信息。

        Args:
            message (str): 错误信息。
        """
        QMessageBox.critical(self, "错误", message)  # 显示错误信息框
        self.status_bar.setText("操作失败")  # 设置状态栏信息
        self.query_btn.setEnabled(True)  # 启用查询按钮
        self.update_btn.setEnabled(True)  # 启用更新按钮

    def handle_connection(self, success):
        """
        处理连接状态。

        Args:
            success (bool): 连接状态，True 表示连接成功，False 表示连接失败。
        """
        self.db_connected = success  # 设置数据库连接状态
        if success:
            self.status_bar.setText("就绪")  # 设置状态栏信息
            self.query_btn.setEnabled(True)  # 启用查询按钮
            self.update_btn.setEnabled(True)  # 启用更新按钮
        else:
            self.status_bar.setText("数据库连接失败")  # 设置状态栏信息
            self.query_btn.setEnabled(False)  # 禁用查询按钮
            self.update_btn.setEnabled(False)  # 禁用更新按钮

    def handle_columns_loaded(self):
        """
        字段加载完成后的处理。
        """
        self.update_update_columns(0)  # 更新更新列下拉框
        self.update_condition_columns(0)  # 更新条件列下拉框
        self.table_combo.currentIndexChanged.connect(self.update_condition_columns)  # 绑定表选择事件

    def closeEvent(self, event):
        """
        关闭事件。
        """
        if self.worker and self.worker.isRunning():
            self.worker.terminate()  # 停止数据库工作线程
        if hasattr(self.worker, 'conn') and self.worker.conn.is_connected():
            self.worker.conn.close()  # 关闭数据库连接
        logging.shutdown()  # 关闭 logging
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
