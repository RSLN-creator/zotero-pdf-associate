# -*- coding: utf-8 -*-
# Zotero PDF Associate 启动器（OS 双击 PDF 的接收入口）
# 链路: 资源管理器双击 -> 本启动器 -> POST http://127.0.0.1:23119/pdfassociate/open -> Zotero 内插件完成 打开/导入
# 插件未安装时自动回退到本地 API 导入（无哈希去重）；Zotero 未运行时自动拉起
# 配置: FIXED_COLLECTION 填分类名 = 固定导入位置；留空 = 按 PDF 所在文件夹名
import json, os, sys, time, hashlib, ctypes
import urllib.request, urllib.error, urllib.parse, subprocess

ZOTERO_EXE = os.environ.get("ZOTERO_EXE") or next(
    (p for p in [
        r"C:\Program Files\Zotero\zotero.exe",
        r"C:\Program Files (x86)\Zotero\zotero.exe",
    ] if os.path.isfile(p)),
    r"C:\Program Files\Zotero\zotero.exe"
)  # 自定义安装位置请改为实际路径，或设置环境变量 ZOTERO_EXE
ENDPOINT = "http://127.0.0.1:23119/pdfassociate/open"
HOST = "http://127.0.0.1:23119"
BASE = HOST + "/api/users/0"
APP_NAME = "zotero-pdf-import"
FIXED_COLLECTION = ""
KEYFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zotero-pdf-import.key")


def msg(text):
    ctypes.windll.user32.MessageBoxW(0, text, "Zotero PDF", 0x40)


def md5sum(path, chunk=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def post(url, payload, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def wait_zotero():
    for _ in range(60):
        try:
            urllib.request.urlopen(HOST + "/connector/ping", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


# ---------- 回退路径：插件未装时走本地 API 导入（沿用旧实现，密钥持久化复用） ----------
def http(method, url, data=None, headers=None, timeout=20):
    r = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.status, resp.read(), dict(resp.headers)


def authorize(sid):
    body = json.dumps({"appName": APP_NAME}).encode()
    st, data, _ = http("POST", HOST + "/api/local/authorize", body,
                       {"Content-Type": "application/json", "Zotero-Server-ID": sid}, timeout=90)
    return json.loads(data)["key"]


def load_key():
    try:
        with open(KEYFILE, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except Exception:
        return None


def save_key(k):
    try:
        with open(KEYFILE, "w", encoding="utf-8") as f:
            f.write(k)
    except Exception:
        pass


class Api:
    def __init__(self, sid):
        self.sid = sid
        self.key = load_key()
        if not self.key:
            self.key = authorize(sid)
            save_key(self.key)

    def req(self, method, path, data=None, headers=None, _retry=True):
        h = {"Zotero-Server-ID": self.sid, "Zotero-API-Key": self.key}
        h.update(headers or {})
        r = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 401 and _retry:
                self.key = authorize(self.sid)
                save_key(self.key)
                return self.req(method, path, data, headers, False)
            return e.code, e.read().decode("utf-8", "replace")


def fallback_import(pdf):
    api = Api(http("GET", HOST + "/api/")[2].get("Zotero-Server-ID"))
    coll_name = FIXED_COLLECTION or os.path.basename(os.path.dirname(os.path.abspath(pdf))) or "导入PDF"
    cols = json.loads(api.req("GET", "/collections?limit=100")[1])
    coll = next((c["key"] for c in cols if c["data"]["name"] == coll_name), None)
    if not coll:
        _, body = api.req("POST", "/collections", json.dumps([{"name": coll_name}]).encode(),
                          {"Content-Type": "application/json"})
        coll = json.loads(body)["success"]["0"]
    payload = [{"itemType": "attachment", "linkMode": "imported_file",
                "title": os.path.basename(pdf), "filename": os.path.basename(pdf),
                "contentType": "application/pdf", "collections": [coll]}]
    _, body = api.req("POST", "/items", json.dumps(payload).encode(), {"Content-Type": "application/json"})
    key = json.loads(body)["success"]["0"]
    with open(pdf, "rb") as f:
        data = f.read()
    form = urllib.parse.urlencode({"md5": hashlib.md5(data).hexdigest(),
                                   "mtime": int(os.path.getmtime(pdf) * 1000),
                                   "filename": os.path.basename(pdf), "filesize": len(data)}).encode()
    _, body = api.req("POST", f"/items/{key}/file", form,
                      {"Content-Type": "application/x-www-form-urlencoded", "If-None-Match": "*"})
    pre = json.loads(body)
    http("POST", pre["url"], data, {"Content-Type": "application/pdf", "Zotero-uploadKey": pre["uploadKey"]})
    form = urllib.parse.urlencode({"upload": pre["uploadKey"]}).encode()
    st, _b = api.req("POST", f"/items/{key}/file", form,
                     {"Content-Type": "application/x-www-form-urlencoded", "If-None-Match": "*"})
    if st != 204:
        raise RuntimeError(f"注册失败 HTTP {st}")
    return key


def main():
    if len(sys.argv) < 2:
        return
    pdf = sys.argv[1].strip('"')
    if not os.path.isfile(pdf):
        return
    try:
        with open(pdf, "rb") as f:
            head = f.read(5)
        if os.path.getsize(pdf) == 0 or head != b"%PDF-":
            msg("该文件为空或不是有效的PDF（可能下载不完整/损坏），已取消导入：\n" + pdf)
            return
        digest = md5sum(pdf)
    except OSError as e:
        msg(f"无法读取文件：{e}")
        return

    payload = {"path": os.path.abspath(pdf), "md5": digest}
    if FIXED_COLLECTION:
        payload["collection"] = FIXED_COLLECTION

    try:
        st, body = post(ENDPOINT, payload)
        tries = 0
        while st == 404 and tries < 8:  # Zotero 冷启动时端点可能晚于服务器就绪
            time.sleep(1)
            st, body = post(ENDPOINT, payload)
            tries += 1
        if st == 404:  # 插件未安装 → 回退本地 API
            try:
                http("GET", HOST + "/connector/ping", timeout=3)
            except Exception:
                subprocess.Popen([ZOTERO_EXE])
                if not wait_zotero():
                    raise RuntimeError("Zotero 启动超时")
            key = fallback_import(pdf)
            os.startfile(f"zotero://open-pdf/library/items/{key}")
        elif st != 200:
            msg(f"Zotero 处理失败（HTTP {st}）：\n{body[:500]}")
    except Exception as e:
        try:
            msg(f"Zotero PDF 打开失败：{e}\n\nPDF：{pdf}")
        except Exception:
            pass


if __name__ == "__main__":
    main()
