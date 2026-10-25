# Zotero PDF Associate

**双击任意 PDF，Zotero 无感接管：按内容哈希打开库内已有副本，或自动复制进"所在文件夹同名"的分类。**

> Double-click any PDF in your file manager: Zotero opens its existing library copy by content hash, or imports it seamlessly into a collection named after its folder.

## 功能特性

- **内容级去重（核心能力）**：按文件内容 MD5（`storageHash`）匹配库内附件，而不是按文件名或路径。把条目在 Zotero 里移动到任何分类、重命名、甚至在磁盘上换个位置存放，再次双击同一个 PDF 时**依然无感打开库里那份已被你整理过的副本**（含你的批注），绝不产生重复条目。
- **文件夹即分类**：库内没有时，自动复制进与 PDF 所在文件夹同名的分类（如 `D:\论文\缺陷检测\x.pdf` → 分类「缺陷检测」），分类不存在则自动创建。
- **损坏拒收**：0 字节或非 `%PDF` 头的文件直接拒收并提示，不再产生坏条目。
- **无感体验**：成功时零打扰（不弹窗、不抢焦点丢失）；Zotero 最小化到托盘也会自动还原并聚焦阅读器标签；Zotero 未运行时自动拉起并等待就绪。
- **全本地、零网络**：所有处理都在 127.0.0.1 完成，不上传任何数据。

## 工作原理

```
资源管理器双击 PDF
   │  (文件关联: pythonw 启动器)
   ▼
启动器 zotero-pdf-open.pyw
   │  校验文件头 → 流式计算 MD5 → POST {path, md5}
   ▼
Zotero 内插件端点  POST /pdfassociate/open   ← 插件注册在 Zotero 本地服务器上
   │  1. storageHash 查库 → 命中: Zotero.Reader.open(itemID) 直接打开
   │  2. 未命中: importFromFile 复制进存储 + 挂到文件夹同名分类
   ▼
阅读器打开（窗口自动还原聚焦）
```

**为什么需要启动器？** Zotero 平台限制：官方明确不支持通过命令行/文件关联把文件路径传入 Zotero（Zotero 论坛确认，命令行传参会被静默忽略）。本插件把处理逻辑放进 Zotero 内部，由一个极薄的 Python 启动器把文件路径经本地 HTTP 端点递进来，绕过该限制且无需任何 API 授权弹窗。

## 安装

1. **安装插件**：Zotero → 工具 → 插件 → 把 `zotero-pdf-associate-x.y.z.xpi` 拖进去（或从 Releases 下载）。
2. **安装启动器**：本仓库 `launcher/` 目录复制到任意固定位置，编辑 `zotero-pdf-open.pyw` 顶部：
   - `ZOTERO_EXE`：你的 zotero.exe 路径（支持环境变量 `ZOTERO_EXE` 覆盖）
   - `FIXED_COLLECTION`：留空 = 按文件夹名建分类；填分类名 = 固定导入位置
   - 需要 Python 3（仅标准库，无需 pip 装任何东西）
3. **注册文件关联**：PowerShell 运行 `launcher\setup-association.ps1`（当前用户级，无需管理员），
   然后右键任意 PDF → 打开方式 → 选择其他应用 → **Zotero PDF** → **始终**
   （最后这步 Windows 只允许资源管理器写入，必须手动点一次）。

完成后，双击任意 PDF 即可。

## 配置

| 配置 | 位置 | 说明 |
|---|---|---|
| 固定分类 / 文件夹模式 | 启动器 `FIXED_COLLECTION` | 留空按文件夹名；填名字则全部进该分类 |
| Zotero 路径 | 启动器 `ZOTERO_EXE` 或环境变量 `ZOTERO_EXE` | Zotero 未运行时自动拉起用 |

## 隐私与安全

- 插件端点仅监听 `127.0.0.1`，且 Zotero 服务器自带浏览器来源防护（非本机程序请求会被拒）。
- 启动器只读取你双击的那个 PDF，只与本机 Zotero 通信，无任何网络行为。
- 本插件不使用、不需要、也不修改本地 API 授权密钥。

## 性能

- 启动器流式计算 MD5（1MB 分块），内存占用恒定；命中时总耗时通常 < 500ms（含 Zotero 响应）。
- 去重查询走 SQLite 索引单条查询，与库大小无关。
- Zotero 运行中时启动器总开销约 0.1–0.3s（Python 解释器启动占大头，无窗口、无控制台）。

## English TL;DR

Double-click a PDF in Explorer → a tiny Python launcher computes its MD5 and POSTs it to an HTTP endpoint this plugin registers inside Zotero (port 23119, localhost only). The plugin opens the existing library copy matched by content hash — wherever you have organized it — or imports the file into a collection named after its folder. No duplicates, no dialogs, no network. This exists because Zotero officially ignores file paths passed on its command line.

## 常见问题

- **双击后没反应？** ① 确认插件已启用（工具 → 插件）；② 确认关联指向启动器（`setup-association.ps1`）；③ Zotero 首次冷启动需等几秒。
- **为什么不能做成纯插件、不要启动器？** Zotero 不把文件关联当作它的输入（见工作原理），这是平台限制，任何纯插件方案都绕不过。
- **会产生重复条目吗？** 不会。同一内容（MD5 相同）只入一次库；回收站里的不算数。
- **原文件删除了还能打开吗？** 能。导入时已复制进 Zotero 存储，原文件只是被引用的源头。

## License

MIT
