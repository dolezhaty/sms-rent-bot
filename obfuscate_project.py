import os
import marshal
import base64

def obfuscate_file(src_path, dest_path):
    if not os.path.exists(src_path):
        return
    
    # Читаем исходный код
    with open(src_path, 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Вместо marshal (который зависит от версии Python), используем base64 от исходного кода
    # Это обеспечит работу на любой версии Python (3.11, 3.12 и т.д.)
    encoded_source = base64.b64encode(source.encode('utf-8')).decode('ascii')
    
    # Создаем обертку
    wrapper = f"""import base64, os, sys, traceback
# --- [DEBUG] Saints Sms Bot Protection Layer ---
try:
    _s = base64.b64decode('{encoded_source}').decode('utf-8')
    _g = globals()
    _g['__file__'] = os.path.abspath(__file__)
    exec(_s, _g)
except Exception:
    print(f"--- [ERROR] Critical failure in {{os.path.basename(__file__)}} ---")
    traceback.print_exc()
    input("Press Enter to exit...")
"""
    
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write(wrapper)

def process_all():
    deploy_dir = 'deploy'
    # Список файлов в корне
    root_files = ["main.py", "admin_server.py", "loader.py", "database.py", "database_models.py"]
    
    for f in root_files:
        print(f"Obfuscating {f}...")
        obfuscate_file(f, os.path.join(deploy_dir, f))
    
    # Список папок для обработки
    folders = ["src", "bin", "handlers"]
    for folder in folders:
        for root, dirs, files in os.walk(folder):
            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, os.path.curdir)
                dest_path = os.path.join(deploy_dir, rel_path)
                
                if file.endswith('.py'):
                    print(f"Obfuscating {rel_path}...")
                    obfuscate_file(src_path, dest_path)
                elif file.endswith('.json'):
                    print(f"Copying {rel_path}...")
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    import shutil
                    shutil.copy2(src_path, dest_path)

if __name__ == "__main__":
    process_all()
