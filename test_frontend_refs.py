#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""前端引用检查：App.vue 里引用到的函数/变量是否都定义了

起因：我改 App.vue 时用「从 A 到 B 整段替换」，把夹在中间的 loadRecordList /
checkUpdate 等函数一起删掉了，结果 onMounted 抛 ReferenceError、加载遮罩永远
不关（界面一直转圈），而且没有任何报错提示 —— 这类错误纯靠肉眼很难发现。

这个脚本做两件便宜但有效的检查（不需要 node / 不需要构建）：
    1. 模板（template）里 @事件、:属性、{{ 表达式 }} 用到的名字，必须在 <script setup> 里定义；
    2. 脚本里以 foo( 形式调用的函数名，必须要么已定义、要么在已知的内置/全局白名单里。

运行：python test_frontend_refs.py
"""
import re
import sys
from pathlib import Path

APP_VUE = Path(__file__).resolve().parent / "frontend" / "src" / "App.vue"
COMPONENTS_DIR = Path(__file__).resolve().parent / "frontend" / "src" / "components"

# 允许出现在模板/脚本里、但不由本文件定义的名字
ALLOWED = {
    # JS 内置 / 全局
    "console", "JSON", "Object", "Array", "Number", "String", "Boolean", "Math", "Date",
    "Promise", "Set", "Map", "RegExp", "Error", "parseInt", "parseFloat", "isNaN",
    "encodeURIComponent", "decodeURIComponent", "setTimeout", "setInterval", "clearInterval",
    "clearTimeout", "requestAnimationFrame", "alert", "confirm", "prompt", "require",
    "if", "for", "while", "switch", "catch", "return", "typeof", "await", "new", "function",
    # 依赖与自动导入
    "ref", "computed", "watch", "reactive", "onMounted", "onUnmounted", "nextTick", "defineStore",
    "ElMessage", "ElMessageBox", "html2canvas", "axios", "useGachaRecordStore", "useSSRStore",
    # pywebview 注入
    "defineProps", "defineEmits", "resolve", "reject",
    "pywebview", "webview", "load_ssr_data", "get_record_list", "get_capture_status",
    "open_log_window", "render_log_view", "clear_capture", "get_ssr_data", "export_record",
    "import_record", "install_cert", "uninstall_cert", "check_cert_status", "get_gacha",
    "check_update", "start_update", "open_github", "copy_image_to_clipboard", "test_api",
    "open_log_folder", "create_temp_png_file", "write_chunk_to_file", "get_version_info",
}

SCRIPT_SYMBOL_RE = r"(?:const|let|var|function)\s+([A-Za-z_$][\w$]*)\s*[=(]"
CALL_RE = r"(?<![\w.$])([a-z][A-Za-z0-9_$]*)\s*\("

# 关键字 / 字面量，不算「调用」
KEYWORDS = {
    "if", "for", "while", "switch", "catch", "return", "typeof", "await", "async",
    "function", "new", "of", "in", "else", "do", "try", "delete", "void", "instanceof",
    "yield", "class", "const", "let", "var", "true", "false", "null", "undefined",
}

# 模板里的 v-for / 插槽变量（由 Vue 提供，不需要在本文件定义）
TEMPLATE_VARS_RE = (
    r'v-for="\s*\(?\s*([A-Za-z_$][\w$]*)\s*(?:,\s*([A-Za-z_$][\w$]*))?\s*\)?\s+(?:of|in)\s',
    r'v-slot:([A-Za-z_$][\w$]*)',
)


def check_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if "</template>" not in text or "<script" not in text:
        return []
    template, rest = text.split("</template>", 1)
    script = rest.split("</script>", 1)[0] if "</script>" in rest else rest

    defined = set(re.findall(SCRIPT_SYMBOL_RE, text))
    # 默认导入和命名导入同样是本模块中已定义的符号（包括 as 别名）。
    for name in re.findall(r'import\s+([A-Za-z_$][\w$]*)\s*(?:,\s*\{[^}]*\})?\s+from', script):
        defined.add(name)
    for names in re.findall(r'import\s*\{([^}]+)\}\s*from', script):
        for name in names.split(','):
            defined.add(name.strip().split(' as ')[-1].strip())
    for pattern in TEMPLATE_VARS_RE:
        for groups in re.findall(pattern, template):
            for name in (groups if isinstance(groups, tuple) else (groups,)):
                if name:
                    defined.add(name)
    problems = []

    # 1) 模板里用到的名字
    used = set()
    for pattern in (r'@[a-zA-Z]+="([A-Za-z_$][\w$]*)', r"@[a-zA-Z]+='([A-Za-z_$][\w$]*)",
                    r':[a-zA-Z\-]+="([A-Za-z_$][\w$]*)', r'v-if="([A-Za-z_$][\w$]*)',
                    r'v-model="([A-Za-z_$][\w$]*)', r"\{\{\s*([A-Za-z_$][\w$]*)"):
        used |= set(re.findall(pattern, template))
    for name in sorted(used - defined - ALLOWED - KEYWORDS):
        problems.append(f"模板引用了未定义的名字: {name}")

    # 2) 脚本里调用的函数（排除 obj.method() 与方法链）
    called = set(re.findall(CALL_RE, script))
    for name in sorted(called - defined - ALLOWED - KEYWORDS):
        problems.append(f"脚本调用了未定义的函数: {name}")

    return problems


def main() -> int:
    targets = [APP_VUE] + sorted(COMPONENTS_DIR.glob("*.vue"))
    failures = 0
    for path in targets:
        problems = check_file(path)
        if problems:
            failures += len(problems)
            print(f"[FAIL] {path.name}")
            for item in problems:
                print(f"       - {item}")
        else:
            print(f"[PASS] {path.name}")
    print("=" * 60)
    if failures:
        print(f"发现 {failures} 处未定义引用")
        return 1
    print("前端引用检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
