/* Zotero PDF Associate
 * 双击任意 PDF（由启动器转发到本端点）：
 *   1. 按内容哈希(MD5)查找库内已有副本 → 直接打开（无论它被整理到哪个分类、原文件是否还在原位）
 *   2. 库内没有 → 复制进"所在文件夹同名"的分类并打开
 *   3. 空文件 / 非 PDF 拒收
 */
var unregisterEndpoint = null;

function logError(e) {
    try { Zotero.logError(e); } catch (x) { /* noop */ }
}

function install(data, reason) {}

async function startup({ id, version }, reason) {
    await Zotero.initializationPromise;
    await Zotero.uiReadyPromise;

    const ROUTE = '/pdfassociate/open';

    Zotero.Server.Endpoints[ROUTE] = class {
        supportedMethods = ['POST'];
        supportedDataTypes = ['application/json'];

        async init(requestData) {
            try {
                const payload = requestData.data || {};
                const path = payload.path;
                const md5 = payload.md5 || null;
                const fixedCollection = payload.collection || null;

                if (!path || typeof path !== 'string') {
                    return [400, 'text/plain', 'path required'];
                }
                if (!(await IOUtils.exists(path))) {
                    return [404, 'text/plain', 'file not found: ' + path];
                }
                const stat = await IOUtils.stat(path);
                if (stat.size === 0) {
                    return [415, 'text/plain', 'empty file (可能下载不完整)'];
                }
                const head = new TextDecoder().decode(await IOUtils.read(path, { maxBytes: 5 }));
                if (head !== '%PDF-') {
                    return [415, 'text/plain', 'not a PDF'];
                }

                let item = md5 ? await findByMd5(md5) : null;
                if (item) {
                    // 库内记录存在但存储文件丢失时重新导入
                    const p = await item.getFilePathAsync();
                    if (!p || !(await IOUtils.exists(p))) item = null;
                }
                let imported = false;
                if (!item) {
                    item = await importToCollection(path, fixedCollection);
                    imported = true;
                }

                await Zotero.Reader.open(item.id);
                const wins = (typeof Zotero.getMainWindows === 'function' && Zotero.getMainWindows()) || [];
                const win = wins[0] || (typeof Zotero.getMainWindow === 'function' && Zotero.getMainWindow());
                if (win) {
                    try { if (win.restore) win.restore(); win.focus(); } catch (e) { logError(e); }
                }
                return [200, 'text/plain', imported ? 'IMPORTED' : 'OPENED'];
            } catch (e) {
                logError(e);
                return [500, 'text/plain', (e && e.message) || String(e)];
            }
        }
    };

    unregisterEndpoint = function () {
        delete Zotero.Server.Endpoints[ROUTE];
    };
}

// storageHash 即附件内容 MD5（导入时写入）；linkMode 0 = imported_file；排除回收站
async function findByMd5(md5) {
    const itemID = await Zotero.DB.valueQueryAsync(
        'SELECT ia.itemID FROM itemAttachments ia '
        + 'LEFT JOIN deletedItems di ON di.itemID = ia.itemID '
        + 'WHERE ia.linkMode = 0 AND ia.storageHash = ? AND di.itemID IS NULL '
        + 'ORDER BY ia.itemID DESC LIMIT 1',
        [md5]
    );
    if (!itemID) return null;
    return Zotero.Items.get(parseInt(itemID, 10)) || null;
}

async function importToCollection(path, fixedCollection) {
    const libraryID = Zotero.Libraries.userLibraryID;
    const parts = path.split(/[\\/]/).filter(Boolean);
    const folderName = fixedCollection || parts[parts.length - 2] || '导入PDF';

    let collection = Zotero.Collections.getByLibrary(libraryID)
        .find(c => c.name === folderName);
    if (!collection) {
        collection = new Zotero.Collection();
        collection.libraryID = libraryID;
        collection.name = folderName;
        await collection.saveTx();
    }

    const item = await Zotero.Attachments.importFromFile({
        file: path,
        libraryID,
        contentType: 'application/pdf'
    });
    item.addToCollection(collection.id);
    await item.saveTx();
    return item;
}

function shutdown({ id }, reason) {
    if (unregisterEndpoint) unregisterEndpoint();
    unregisterEndpoint = null;
}

function uninstall(data, reason) {}
