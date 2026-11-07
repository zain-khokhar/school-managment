"""
Verify every JS file in desktop_app/ui/js/ for:
1. Syntax validity (via node --check if available, plus regex AST check)
2. Every `import { a, b } from './path.js'` actually exists as an `export` in `./path.js`!
"""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
JS_DIR = ROOT / "desktop_app" / "ui" / "js"


def get_exports(js_path: Path) -> set[str]:
    text = js_path.read_text(encoding="utf-8")
    exports: set[str] = set()
    for m in re.finditer(r"export\s+(?:async\s+)?(?:function|const|let|var|class)\s+([A-Za-z0-9_$]+)", text):
        exports.add(m.group(1))
    for m in re.finditer(r"export\s*\{([^}]+)\}", text):
        for part in m.group(1).split(","):
            part = part.strip()
            if " as " in part:
                part = part.split(" as ")[-1].strip()
            if part:
                exports.add(part)
    return exports


def verify_all_js() -> int:
    errors: list[str] = []
    js_files = sorted(JS_DIR.rglob("*.js"))

    # Also check legacy app.js syntax
    all_to_check = [ROOT / "desktop_app" / "ui" / "app.js"] + js_files
    for jf in all_to_check:
        res = subprocess.run(["node", "--check", str(jf)], capture_output=True, text=True)
        if res.returncode != 0:
            errors.append(f"Syntax error in {jf.relative_to(ROOT)}:\n{res.stderr}")
        else:
            print(f"  [SYNTAX OK] {jf.relative_to(ROOT)}")

        # Check for malformed HTML tags inside JS template literals (e.g., `< table` or `</div >`)
        content = jf.read_text(encoding="utf-8")
        bad_open = re.findall(r"<\s+(?:div|table|tr|td|th|span|button|thead|tbody|ul|li|p|input|select|option|label)\b", content)
        bad_close = re.findall(r"</\s*[a-zA-Z0-9]+\s+>", content)
        if bad_open or bad_close:
            errors.append(f"Malformed HTML tag spacing in {jf.relative_to(ROOT)}: {bad_open + bad_close}")

    export_map = {jf.resolve(): get_exports(jf) for jf in js_files}

    for jf in js_files:
        text = jf.read_text(encoding="utf-8")
        for m in re.finditer(r"import\s*\{([^}]+)\}\s*from\s*['\"]([^'\"]+)['\"]", text):
            names_raw, rel_target = m.group(1), m.group(2)
            target_path = (jf.parent / rel_target).resolve()
            if not target_path.exists():
                errors.append(f"{jf.relative_to(ROOT)} imports non-existent file {rel_target}")
                continue
            target_exports = export_map.get(target_path, set())
            for item in names_raw.split(","):
                item = item.strip()
                if not item:
                    continue
                orig_name = item.split(" as ")[0].strip()
                if orig_name not in target_exports:
                    errors.append(
                        f"IMPORT ERROR in {jf.relative_to(ROOT)}: "
                        f"'{orig_name}' is NOT exported by {target_path.relative_to(ROOT)} "
                        f"(exports: {sorted(target_exports)})"
                    )

    if errors:
        print("\nJS VERIFICATION FAILED:")
        for e in errors:
            print("  -", e)
        return 1

    print("\nALL JS MODULES PASSED SYNTAX & STATIC IMPORT-EXPORT LINKAGE CHECK!")
    return 0


if __name__ == "__main__":
    sys.exit(verify_all_js())

