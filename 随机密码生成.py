import random
import tkinter as tk
import pickle
from tkinter import messagebox, Scrollbar, Listbox
from datetime import datetime
import os

# 获取当前电脑用户名
username = os.getlogin()

# 判断 OPMAK 文件夹是否存在，不存在则创建
opmak_folder = os.path.join(f'C:/Users/{username}/OPMAK')
if not os.path.exists(opmak_folder):
    os.makedirs(opmak_folder)

# 生成随机密码的函数
def generate_password():
    chars = ''
    if include_lowercase.get():
        chars += 'abcdefghijklmnopqrstuvwxyz'
    if include_uppercase.get():
        chars += 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    if include_digits.get():
        chars += '0123456789'
    if include_special_symbols.get():
        spec_symbols = special_symbols_entry.get().replace(':', '')
        chars += spec_symbols

    excluded = excluded_chars_entry.get()
    if excluded:
        chars = [char for char in chars if char not in excluded]

    length_str = length_entry.get()
    if not length_str.isdigit():
        result_text.delete(1.0, tk.END)
        result_text.insert(tk.END, "请填写数字作为密码长度。")
        return
    length = int(length_str)

    quantity_str = quantity_entry.get()
    if not quantity_str.isdigit():
        result_text.delete(1.0, tk.END)
        result_text.insert(tk.END, "请填写数字作为密码数量。")
        return
    quantity = int(quantity_str)

    passwords = [''.join(random.choice(chars) for _ in range(length)) for _ in range(quantity)]
    result_text.delete(1.0, tk.END)
    for password in passwords:
        result_text.insert(tk.END, password + '\n')

    if enable_history.get():
        now = datetime.now()
        with open(os.path.join(opmak_folder, 'password_history.dat'), 'a') as file:
            for password in passwords:
                file.write(f'{now.strftime("%Y-%m-%d %H:%M:%S")}: {password}\n')
        clear_history_if_needed()

# 保存设置的函数
def save_settings():
    settings = {}
    settings['include_lowercase'] = include_lowercase.get()
    settings['include_uppercase'] = include_uppercase.get()
    settings['include_digits'] = include_digits.get()
    settings['include_special_symbols'] = include_special_symbols.get()
    settings['special_symbols'] = special_symbols_entry.get()
    settings['excluded_chars'] = excluded_chars_entry.get()
    settings['length'] = length_entry.get()
    settings['quantity'] = quantity_entry.get()
    settings['enable_history'] = enable_history.get()

    with open(os.path.join(opmak_folder, 'config.dat'), 'wb') as file:
        pickle.dump(settings, file)

# 加载设置的函数
def load_settings():
    try:
        with open(os.path.join(opmak_folder, 'config.dat'), 'rb') as file:
            settings = pickle.load(file)
            include_lowercase.set(settings.get('include_lowercase', False))
            include_uppercase.set(settings.get('include_uppercase', False))
            include_digits.set(settings.get('include_digits', False))
            include_special_symbols.set(settings.get('include_special_symbols', False))
            special_symbols_entry.delete(0, tk.END)
            special_symbols_entry.insert(0, settings.get('special_symbols', ''))
            excluded_chars_entry.delete(0, tk.END)
            excluded_chars_entry.insert(0, settings.get('excluded_chars', ''))
            length_entry.delete(0, tk.END)
            length_entry.insert(0, settings.get('length', ''))
            quantity_entry.delete(0, tk.END)
            quantity_entry.insert(0, settings.get('quantity', ''))
            enable_history.set(settings.get('enable_history', False))
    except FileNotFoundError:
        pass

# 复制生成的密码到剪贴板的函数
def copy_result_passwords():
    password_text = result_text.get("1.0", "end-1c")
    password_text = password_text.rstrip('\n')
    root.clipboard_clear()
    root.clipboard_append(password_text)

# 显示密码历史记录的函数
def show_history():
    global history_window
    if history_window is None or not history_window.winfo_exists():
        history_window = tk.Toplevel(root)
        history_window.title("密码历史记录")

        main_frame = tk.Frame(history_window)
        main_frame.pack(fill=tk.BOTH, expand=True)

        listbox_frame = tk.Frame(main_frame)
        listbox_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        with open(os.path.join(opmak_folder, 'password_history.dat'), 'r') as file:
            lines = file.readlines()
            sorted_lines = sorted(lines, key=lambda x: datetime.strptime(x.split(': ')[0].strip() if ':' in x else '1970-01-01 00:00:00', '%Y-%m-%d %H:%M:%S'), reverse=True)
            listbox = Listbox(listbox_frame, height=10, width=50)
            for line in sorted_lines:
                parts = line.strip().split(': ')
                if len(parts) == 2:
                    listbox.insert(tk.END, f'{parts[0]}: {parts[1]}')
            listbox.pack(fill=tk.BOTH, expand=True)
            scrollbar = Scrollbar(listbox_frame, orient="vertical", command=listbox.yview)
            listbox.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side="right", fill="y")

        search_frame = tk.Frame(main_frame)
        search_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        tk.Label(search_frame, text="输入关键词：").pack(side=tk.LEFT)
        search_entry = tk.Entry(search_frame)
        search_entry.pack(fill=tk.X, side=tk.LEFT, expand=True)
        search_button = tk.Button(search_frame, text="查找", command=lambda: perform_search(search_entry.get()))
        search_button.pack(side=tk.LEFT)

        button_frame = tk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        def perform_search(keyword):
            new_results = []
            for line in sorted_lines:
                parts = line.strip().split(': ')
                if len(parts) == 2:
                    date_str = parts[0]
                    password = parts[1]
                    if keyword.lower() in password.lower() or (datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S') if keyword.isdigit() and '-' in keyword else None):
                        new_results.append(line)
            listbox.delete(0, tk.END)
            for result in new_results:
                parts = result.strip().split(': ')
                if len(parts) == 2:
                    listbox.insert(tk.END, f'{parts[0]}: {parts[1]}')

        def copy_history_password(event):
            selected_index = listbox.curselection()
            if selected_index:
                selected_item = listbox.get(selected_index)
                password = selected_item.split(': ')[1]
                root.clipboard_clear()
                root.clipboard_append(password)
                copy_message_label = tk.Label(listbox_frame, text=f'{password}已复制：')
                copy_message_label.pack()
                history_window.after(2000, copy_message_label.destroy)

        listbox.bind("<Double-Button-1>", copy_history_password)

        clear_history_button = tk.Button(button_frame, text="清除历史记录", command=clear_history, bg='red', fg='white')
        clear_history_button.pack()

    else:
        history_window.lift()

# 检查并清理历史记录文件的函数
def clear_history_if_needed():
    try:
        with open(os.path.join(opmak_folder, 'password_history.dat'), 'r') as file:
            lines = file.readlines()
        if len(lines) > 1000:
            with open(os.path.join(opmak_folder, 'password_history.dat'), 'w') as file:
                remaining_lines = lines[-1000:]
                for line in remaining_lines:
                    file.write(line)
    except FileNotFoundError:
        pass

# 清除历史记录的函数
def clear_history():
    try:
        with open(os.path.join(opmak_folder, 'password_history.dat'), 'w') as file:
            pass
        messagebox.showinfo("提示", "历史记录已清除。")
        history_window.destroy()
        show_history()
    except FileNotFoundError:
        messagebox.showinfo("提示", "暂无历史记录可清除。")

root = tk.Tk()
root.title("随机密码生成器 - by 章鱼")

root.resizable(False, False)
root.geometry("500x430")

left_frame = tk.Frame(root)
left_frame.pack(side="left", padx=10)

right_frame = tk.Frame(root)
right_frame.pack(side="right", padx=10)

tk.Label(left_frame, text="所用字符").pack()
include_lowercase = tk.BooleanVar()
tk.Checkbutton(left_frame, text="小写字母(a-z)", variable=include_lowercase).pack()
include_uppercase = tk.BooleanVar()
tk.Checkbutton(left_frame, text="大写字母(A-Z)", variable=include_uppercase).pack()
include_digits = tk.BooleanVar()
tk.Checkbutton(left_frame, text="数字(0-9)", variable=include_digits).pack()
include_special_symbols = tk.BooleanVar()
tk.Label(left_frame, text="特殊符号：").pack()
special_symbols_entry = tk.Entry(left_frame)
special_symbols_entry.pack()
tk.Checkbutton(left_frame, text="自定义特殊符号", variable=include_special_symbols).pack()

tk.Label(left_frame, text="排除字符：").pack()
excluded_chars_entry = tk.Entry(left_frame)
excluded_chars_entry.pack()

tk.Label(left_frame, text="密码长度：").pack()
length_entry = tk.Entry(left_frame)
length_entry.pack()
tk.Label(left_frame, text="密码数量：").pack()
quantity_entry = tk.Entry(left_frame)
quantity_entry.pack()

enable_history = tk.BooleanVar()
tk.Checkbutton(left_frame, text="记录历史记录", variable=enable_history).pack()

tk.Button(left_frame, text="生成密码", command=generate_password).pack()
tk.Button(left_frame, text="保存设置", command=save_settings).pack()

result_text = tk.Text(right_frame, height=10, width=50)
result_text.pack()
tk.Button(right_frame, text="查看历史记录", command=show_history).pack()

copy_result_button = tk.Button(right_frame, text="复制生成的密码", command=copy_result_passwords)
copy_result_button.pack()

load_settings()

history_window = None

root.after(0, clear_history_if_needed)

root.mainloop()
