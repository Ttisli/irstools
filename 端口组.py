import sys
import os
import base64
import json
import requests
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QPushButton, QFileDialog, QLabel, QDialog,
                             QFormLayout, QLineEdit, QComboBox, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage

# -------------------- 配置类 --------------------
class Config:
    def __init__(self):
        self.api_provider = "openai"  # 默认API提供商
        self.api_key = ""
        self.proxy = ""
        self.openai_api_base = "https://api.openai.com/v1" # OpenAI API Base URL，可以配置
        self.gemini_api_key = "" # Gemini API Key
        self.deepseek_api_key = "" # Deepseek API Key

    def save_config(self, filename="config.json"):
        config_data = {
            "api_provider": self.api_provider,
            "api_key": self.api_key,
            "proxy": self.proxy,
            "openai_api_base": self.openai_api_base,
            "gemini_api_key": self.gemini_api_key,
            "deepseek_api_key": self.deepseek_api_key,
        }
        with open(filename, 'w') as f:
            json.dump(config_data, f, indent=4)

    def load_config(self, filename="config.json"):
        try:
            with open(filename, 'r') as f:
                config_data = json.load(f)
                self.api_provider = config_data.get("api_provider", "openai")
                self.api_key = config_data.get("api_key", "")
                self.proxy = config_data.get("proxy", "")
                self.openai_api_base = config_data.get("openai_api_base", "https://api.openai.com/v1")
                self.gemini_api_key = config_data.get("gemini_api_key", "")
                self.deepseek_api_key = config_data.get("deepseek_api_key", "")
        except FileNotFoundError:
            pass  # 使用默认配置

# 全局配置实例
config = Config()
config.load_config()

# -------------------- 设置对话框 --------------------
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")

        self.api_provider_combo = QComboBox()
        self.api_provider_combo.addItems(["openai", "deepseek-r1", "gemini-2.0"])
        self.api_provider_combo.setCurrentText(config.api_provider)

        self.api_key_edit = QLineEdit(config.api_key)
        self.proxy_edit = QLineEdit(config.proxy)
        self.openai_api_base_edit = QLineEdit(config.openai_api_base)
        self.gemini_api_key_edit = QLineEdit(config.gemini_api_key)
        self.deepseek_api_key_edit = QLineEdit(config.deepseek_api_key)

        layout = QFormLayout()
        layout.addRow("API Provider:", self.api_provider_combo)
        layout.addRow("OpenAI API Base:", self.openai_api_base_edit)  # 新增 OpenAI API Base 输入框
        layout.addRow("API Key:", self.api_key_edit)
        layout.addRow("Gemini API Key:", self.gemini_api_key_edit)
        layout.addRow("Deepseek API Key:", self.deepseek_api_key_edit)
        layout.addRow("Proxy:", self.proxy_edit)

        self.buttons = QHBoxLayout()
        self.save_button = QPushButton("保存")
        self.cancel_button = QPushButton("取消")
        self.buttons.addWidget(self.save_button)
        self.buttons.addWidget(self.cancel_button)

        layout.addRow(self.buttons)

        self.setLayout(layout)

        self.save_button.clicked.connect(self.save_settings)
        self.cancel_button.clicked.connect(self.reject)

    def save_settings(self):
        config.api_provider = self.api_provider_combo.currentText()
        config.api_key = self.api_key_edit.text()
        config.proxy = self.proxy_edit.text()
        config.openai_api_base = self.openai_api_base_edit.text() # 保存 OpenAI API Base
        config.gemini_api_key = self.gemini_api_key_edit.text()
        config.deepseek_api_key = self.deepseek_api_key_edit.text()
        config.save_config() # 保存到文件
        self.accept()


# -------------------- API 调用线程 --------------------
class ApiCallThread(QThread):
    message_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, prompt, image_path=None):
        super().__init__()
        self.prompt = prompt
        self.image_path = image_path

    def run(self):
        try:
            if config.api_provider == "openai":
                response = self.call_openai_api(self.prompt, self.image_path)
            elif config.api_provider == "deepseek-r1":
                response = self.call_deepseek_api(self.prompt, self.image_path)
            elif config.api_provider == "gemini-2.0":
                response = self.call_gemini_api(self.prompt, self.image_path)
            else:
                self.error_occurred.emit("不支持的API提供商")
                return

            self.message_received.emit(response)

        except Exception as e:
            self.error_occurred.emit(f"API 调用出错: {str(e)}")

    def call_openai_api(self, prompt, image_path=None):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}"
        }

        data = {
            "model": "gpt-4-vision-preview",  # Or your desired model
            "messages": [
                {
                    "role": "user",
                    "content": []
                }
            ],
            "max_tokens": 300
        }

        if image_path:
            with open(image_path, "rb") as image_file:
                img_base64 = base64.b64encode(image_file.read()).decode('utf-8')

            image_content = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_base64}"
                }
            }
            data["messages"][0]["content"].append(image_content)


        text_content = {
            "type": "text",
            "text": prompt
        }

        data["messages"][0]["content"].append(text_content)


        proxies = {}
        if config.proxy:
            proxies = {"http": config.proxy, "https": config.proxy}

        try:
            response = requests.post(f"{config.openai_api_base}/chat/completions", headers=headers, json=data, proxies=proxies)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            return response.json()['choices'][0]['message']['content']
        except requests.exceptions.RequestException as e:
            raise Exception(f"OpenAI API 请求失败: {e}")


    def call_deepseek_api(self, prompt, image_path=None):
        #  Deepseek API 的调用逻辑，需要根据 Deepseek 的 API 文档来实现
        api_url = "YOUR_DEEPSEEK_API_ENDPOINT"  # 替换为实际的 Deepseek API 端点
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.deepseek_api_key}"
        }

        data = {
            "model": "deepseek-vl",
            "messages": [
                {
                    "role": "user",
                    "content": []
                }
            ],
            "max_tokens": 300
        }

        if image_path:
            with open(image_path, "rb") as image_file:
                img_base64 = base64.b64encode(image_file.read()).decode('utf-8')

            image_content = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_base64}"
                }
            }
            data["messages"][0]["content"].append(image_content)

        text_content = {
            "type": "text",
            "text": prompt
        }

        data["messages"][0]["content"].append(text_content)


        proxies = {}
        if config.proxy:
            proxies = {"http": config.proxy, "https": config.proxy}


        try:
            response = requests.post(api_url, headers=headers, json=data, proxies=proxies)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'] # 根据实际的返回格式调整
        except requests.exceptions.RequestException as e:
            raise Exception(f"Deepseek API 请求失败: {e}")

    def call_gemini_api(self, prompt, image_path=None):
        # Gemini API 的调用逻辑，需要根据 Gemini 的 API 文档来实现
         api_url = "https://7b5krb21xg.apifox.cn"  # 替换为实际的 Gemini API 端点
         headers = {
            "Content-Type": "application/json",
            "Content-Type": "application/json",
        }
         params = {
            "key": config.gemini_api_key
        }

         data = {
            "contents": [{
                "parts": []
            }]
         }

         if image_path:
             with open(image_path, "rb") as image_file:
                 img_base64 = base64.b64encode(image_file.read()).decode('utf-8')

             image_content = {
                 "inline_data": {
                     "mime_type": "image/jpeg",
                     "data": img_base64
                 }
             }
             data["contents"][0]["parts"].append(image_content)


         text_content = {
             "text": prompt
         }
         data["contents"][0]["parts"].append(text_content)

         proxies = {}
         if config.proxy:
             proxies = {"http": config.proxy, "https": config.proxy}

         try:
            response = requests.post(api_url, headers=headers, json=data, params=params, proxies=proxies)
            response.raise_for_status()
            return response.json()['candidates'][0]['content']['parts'][0]['text']  # 根据实际的返回格式调整
         except requests.exceptions.RequestException as e:
             raise Exception(f"Gemini API 请求失败: {e}")


# -------------------- 主窗口 --------------------
class ChatWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI 聊天")

        self.config = config  # 引入配置

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)

        self.input_box = QTextEdit()
        self.image_label = QLabel()  # 用于显示上传的图片
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_path = None

        self.upload_button = QPushButton("上传图片")
        self.send_button = QPushButton("发送")
        self.settings_button = QPushButton("设置")

        # 布局
        hbox = QHBoxLayout()
        hbox.addWidget(self.upload_button)
        hbox.addWidget(self.send_button)
        hbox.addWidget(self.settings_button)

        vbox = QVBoxLayout()
        vbox.addWidget(self.chat_display)
        vbox.addWidget(self.image_label) # 添加图片显示
        vbox.addWidget(self.input_box)
        vbox.addLayout(hbox)

        self.setLayout(vbox)

        # 信号与槽
        self.send_button.clicked.connect(self.send_message)
        self.upload_button.clicked.connect(self.upload_image)
        self.settings_button.clicked.connect(self.open_settings)

    def display_image(self, image_path):
        """显示图片在 QLabel 中"""
        pixmap = QPixmap(image_path)
        # 缩放图片以适应 QLabel 的大小
        scaled_pixmap = pixmap.scaled(self.image_label.width(), self.image_label.height(), Qt.KeepAspectRatio)
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.adjustSize() # 根据图片大小调整Label
        self.image_path = image_path # 保存图片路径

    def upload_image(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "选择图片", "", "Images (*.png *.jpg *.jpeg)")
        if file_path:
            self.display_image(file_path)  # 显示图片

    def send_message(self):
        prompt = self.input_box.toPlainText()
        self.chat_display.append(f"用户: {prompt}")
        self.input_box.clear()

        # 创建 API 调用线程
        self.api_thread = ApiCallThread(prompt, self.image_path)  # 传递图片路径
        self.api_thread.message_received.connect(self.display_message)
        self.api_thread.error_occurred.connect(self.display_error)
        self.api_thread.start()


    def display_message(self, message):
        self.chat_display.append(f"AI: {message}")

    def display_error(self, error):
        QMessageBox.critical(self, "错误", error)
        self.chat_display.append(f"错误: {error}")

    def open_settings(self):
        settings_dialog = SettingsDialog(self)
        if settings_dialog.exec_() == QDialog.Accepted:
            #  刷新配置，重新加载API key
            self.config.load_config() # 重新加载配置
            QMessageBox.information(self, "提示", "设置已保存，请重新启动程序以使所有更改生效。")



if __name__ == '__main__':
    app = QApplication(sys.argv)
    chat_window = ChatWindow()
    chat_window.resize(800, 600) # 初始窗口大小
    chat_window.show()
    sys.exit(app.exec_())
