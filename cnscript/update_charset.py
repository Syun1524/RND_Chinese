import os
import glob

def main():
    charset_file = 'charset.utf8'
    
    # 1. 读取现有的 charset.utf8 文件内容到集合中
    # 如果文件不存在，则创建一个空集合
    existing_chars = set()
    if os.path.exists(charset_file):
        with open(charset_file, 'r', encoding='utf-8') as f:
            content = f.read()
            existing_chars = set(content)
        print(f"已加载现有字符集，包含 {len(existing_chars)} 个字符。")
    else:
        print("未找到 charset.utf8 文件，将创建新文件。")

    # 2. 查找当前目录下所有的 .txt 文件
    txt_files = glob.glob('*.txt')
    
    if not txt_files:
        print("当前目录下没有找到 .txt 文件。")
        return

    print(f"发现 {len(txt_files)} 个 txt 文件，开始比对...")

    # 用于存储不在现有字符集中的新字符
    new_chars_set = set()

    # 3. 遍历所有 txt 文件
    for file_path in txt_files:
        # 跳过 charset.utf8 本身（以防它被错误地重命名或逻辑混淆，虽然扩展名不同）
        if file_path == charset_file:
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                for char in content:
                    if char not in existing_chars:
                        new_chars_set.add(char)
        except UnicodeDecodeError:
            print(f"警告：文件 {file_path} 编码不是 UTF-8，已跳过。")
        except Exception as e:
            print(f"读取文件 {file_path} 时出错：{e}")

    # 4. 如果有新字符，则追加写入
    if new_chars_set:
        # 为了保持某种顺序（可选），这里转为列表排序，或者直接写入
        # 这里直接转换为字符串，不排序以保持发现顺序或随机顺序均可
        # 如果希望字符有序，可以使用: new_chars = sorted(new_chars_set)
        new_chars = ''.join(new_chars_set)
        
        with open(charset_file, 'a', encoding='utf-8') as f:
            f.write(new_chars)
        
        print(f"比对完成！发现 {len(new_chars_set)} 个新字符，已追加到 {charset_file} 末尾。")
    else:
        print("比对完成。未发现新字符，charset.utf8 未发生更改。")

if __name__ == '__main__':
    main()