"""Geliştirme aracı: kaynak koddaki kullanıcıya görünen Türkçe metinleri _t() ile sarar.

  python installer/i18n_wrap.py --rapor  dosya.py ...   → neyin sarılacağını gösterir, dosyaya dokunmaz
  python installer/i18n_wrap.py --uygula dosya.py ...   → sarar ve gerekiyorsa içe aktarmayı ekler
  python installer/i18n_wrap.py --anahtarlar dosya.py ... → _t("...") içindeki tüm metinleri (çeviri anahtarları) JSON yazar

Kural: Türkçe harf içeren metinler ya da arayüz çağrılarına (setText, QLabel, QPushButton…) verilen metinler.
Belge dizgileri, karşılaştırmalar (x in "…", == "…") ve kod/biçim gerektiren çağrılar (re, open, setStyleSheet…) atlanır.
f-string'ler yer tutuculu kalıba çevrilir: f"{n} indirme" → _t("{0} indirme").format(n)
"""
import ast
import json
import re
import sys

TURKISH = re.compile(r"[çğıöşüÇĞİÖŞÜâîû…→·✔✖⬇⚠]")
UI_FUNCS = {
    "setText", "setWindowTitle", "setToolTip", "setPlaceholderText", "setSpecialValueText", "setSuffix",
    "addRow", "addTab", "addItem", "addAction", "addMenu", "addButton", "showMessage", "setHeaderLabel",
    "setHeaderLabels", "setHorizontalHeaderLabels", "QLabel", "QPushButton", "QCheckBox", "QGroupBox",
    "QAction", "QRadioButton", "QMessageBox", "question", "warning", "information", "critical", "about",
    "getText", "getOpenFileName", "getExistingDirectory", "getSaveFileName", "QTreeWidgetItem", "setTitle",
    "setStatusTip", "setFormat", "_act", "emit", "QToolBar",
}
SKIP_FUNCS = {
    "compile", "match", "search", "sub", "findall", "fullmatch", "split", "startswith", "endswith", "replace",
    "strip", "rstrip", "lstrip", "join", "open", "setStyleSheet", "setObjectName", "QColor", "QFont", "getattr",
    "setattr", "hasattr", "setProperty", "property", "get", "pop", "setdefault", "run", "Popen", "check_output",
    "QUrl", "fromLocalFile", "openUrl", "startfile", "loads", "dumps", "encode", "decode", "QIcon", "icon",
    "isinstance", "print", "makedirs", "exists", "isfile", "isdir", "join_path", "Path", "getenv",
    "_t", "format_exc", "mkstemp", "mkdtemp", "QSettings", "setApplicationName", "connect", "findChild",
}


def _call_name(node):
    f = node.func
    return f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")


def _docstring_ids(tree):
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body:
            first = n.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, (ast.Constant, ast.JoinedStr)):
                out.add(id(first.value))
    return out


def _parents(tree):
    par = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            par[id(c)] = n
    return par


def _text_of(node):
    if isinstance(node, ast.Constant):
        return node.value
    return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)


def _quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t") + '"'


def _rewrite(src, node):
    if isinstance(node, ast.Constant):
        return f"_t({_quote(node.value)})"
    parts, args = [], []
    for v in node.values:
        if isinstance(v, ast.Constant):
            parts.append(v.value.replace("{", "{{").replace("}", "}}"))
            continue
        spec = ""
        if v.format_spec is not None:
            if not all(isinstance(x, ast.Constant) for x in v.format_spec.values):
                return None  # iç içe ifade içeren biçim: elle
            spec = ":" + "".join(x.value for x in v.format_spec.values)
        conv = {115: "!s", 114: "!r", 97: "!a"}.get(v.conversion, "")
        parts.append("{" + str(len(args)) + conv + spec + "}")
        expr = ast.get_source_segment(src, v.value)
        if expr is None or "\n" in expr:
            return None
        args.append(expr)
    return f"_t({_quote(''.join(parts))}).format({', '.join(args)})"


def candidates(path):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    docs, par = _docstring_ids(tree), _parents(tree)
    found = []
    for n in ast.walk(tree):
        if not isinstance(n, (ast.Constant, ast.JoinedStr)) or id(n) in docs:
            continue
        if isinstance(n, ast.Constant) and not isinstance(n.value, str):
            continue
        p = par.get(id(n))
        if isinstance(p, ast.JoinedStr) or isinstance(p, ast.FormattedValue):
            continue  # f-string'in parçası
        text = _text_of(n)
        if not re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]", text):
            continue
        # bağlam: hangi çağrının argümanı / karşılaştırma mı
        ctx, q = None, n
        skip = False
        while q is not None and id(q) in par:
            pp = par[id(q)]
            if isinstance(pp, ast.Compare):
                skip = True
                break
            if isinstance(pp, ast.Call) and q is not pp.func:
                ctx = _call_name(pp)
                break
            if isinstance(pp, (ast.Assign, ast.Return, ast.Dict, ast.List, ast.Tuple, ast.IfExp, ast.BinOp,
                               ast.keyword, ast.AnnAssign, ast.AugAssign, ast.BoolOp, ast.Subscript)):
                q = pp
                continue
            break
        if skip or (ctx in SKIP_FUNCS):
            continue
        if re.fullmatch(r"[a-z0-9_.\-]+|Del|Esc|Ctrl\+.+|Shift\+.+|TurboDM|ffmpeg\.exe|ffmpeg|yt-dlp|OK", text):
            continue  # kod adı, simge adı, kısayol, özel ad: çevrilmez
        if TURKISH.search(text) or ctx in UI_FUNCS:
            found.append(n)
    return src, found


def apply(path, report_only):
    src, nodes = candidates(path)
    lines = src.splitlines(keepends=True)
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln))

    def pos(lineno, col):
        # col: UTF-8 bayt ofseti → karakter ofseti
        line = lines[lineno - 1]
        return offsets[lineno - 1] + len(line.encode("utf-8")[:col].decode("utf-8"))
    edits, manual = [], []
    # başka bir seçili metnin (ör. f-string ifadesi) içinde kalan metinler ayrıca sarılmaz
    spans = [(pos(n.lineno, n.col_offset), pos(n.end_lineno, n.end_col_offset)) for n in nodes]
    nodes = [n for n, (a0, b0) in zip(nodes, spans)
             if not any(a1 <= a0 and b0 <= b1 and (a1, b1) != (a0, b0) for a1, b1 in spans)]
    for n in nodes:
        new = _rewrite(src, n)
        a, b = pos(n.lineno, n.col_offset), pos(n.end_lineno, n.end_col_offset)
        if new is None:
            manual.append((n.lineno, src[a:b][:80]))
            continue
        edits.append((a, b, new, n.lineno))
    if report_only:
        for a, b, new, ln in sorted(edits):
            print(f"{path}:{ln}: {new[:110]}")
        for ln, s in manual:
            print(f"{path}:{ln}: ELLE: {s}")
        print(f"--- {path}: {len(edits)} sarılacak, {len(manual)} elle")
        return
    out = src
    for a, b, new, _ in sorted(edits, reverse=True):
        out = out[:a] + new + out[b:]
    if edits and "import _t" not in out:
        rel = "from .i18n import _t\n" if "turbodm" in path.replace("\\", "/").split("/")[-2:-1] else \
            "from turbodm.i18n import _t\n"
        m = list(re.finditer(r"^(?:from|import) [^\n]+\n(?:[ \t]+[^\n]*\n)*", out, re.M))
        idx = m[-1].end() if m else 0
        out = out[:idx] + rel + out[idx:]
    open(path, "w", encoding="utf-8").write(out)
    print(f"{path}: {len(edits)} sarıldı, {len(manual)} elle bakılacak")
    for ln, s in manual:
        print(f"   ELLE {ln}: {s}")


def keys(paths):
    out = {}
    for path in paths:
        tree = ast.parse(open(path, encoding="utf-8").read())
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call) and _call_name(n) == "_t" and n.args
                    and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
                out[n.args[0].value] = ""
    return out


if __name__ == "__main__":
    mode, files = sys.argv[1], sys.argv[2:]
    if mode == "--anahtarlar":
        json.dump(keys(files), sys.stdout, ensure_ascii=False, indent=1)
    else:
        for f in files:
            apply(f, mode == "--rapor")
