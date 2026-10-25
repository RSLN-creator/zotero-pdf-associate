# 注册 .pdf 关联到 Zotero PDF Associate（当前用户级，无需管理员）
# 用法: 右键"使用 PowerShell 运行"，或在 PowerShell 中执行  .\setup-association.ps1

$ErrorActionPreference = 'Stop'

# 1. 定位 pythonw.exe（启动器运行环境）
$pyw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pyw) {
    Write-Host "未找到 pythonw.exe。请先安装 Python（勾选 Add to PATH），或手动修改本脚本中的路径。"
    Write-Host "下载: https://www.python.org/downloads/"
    pause
    exit 1
}

# 2. 启动器路径（本脚本同目录下的 zotero-pdf-open.pyw）
$launcher = Join-Path $PSScriptRoot 'zotero-pdf-open.pyw'
if (-not (Test-Path $launcher)) {
    Write-Host "未找到启动器: $launcher"
    pause
    exit 1
}

# 3. 写注册表（HKCU，仅当前用户）
$cmd = "`"$pyw`" `"$launcher`" `"%1`""

New-Item -Path 'HKCU:\Software\Classes\Zotero.PDF' -Force | Out-Null
Set-ItemProperty -Path 'HKCU:\Software\Classes\Zotero.PDF' -Name '(default)' -Value 'Zotero PDF'

New-Item -Path 'HKCU:\Software\Classes\Zotero.PDF\DefaultIcon' -Force | Out-Null
Set-ItemProperty -Path 'HKCU:\Software\Classes\Zotero.PDF\DefaultIcon' -Name '(default)' -Value 'zotero.exe,0'

New-Item -Path 'HKCU:\Software\Classes\Zotero.PDF\shell\open\command' -Force | Out-Null
Set-ItemProperty -Path 'HKCU:\Software\Classes\Zotero.PDF\shell\open\command' -Name '(default)' -Value $cmd

New-Item -Path 'HKCU:\Software\Classes\.pdf\OpenWithProgids' -Force | Out-Null
New-ItemProperty -Path 'HKCU:\Software\Classes\.pdf\OpenWithProgids' -Name 'Zotero.PDF' -PropertyType String -Value '' -Force | Out-Null

# 无默认程序时的兜底（UserChoice 为空的系统）
Set-ItemProperty -Path 'HKCU:\Software\Classes\.pdf' -Name '(default)' -Value 'Zotero.PDF' -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "注册完成。现在："
Write-Host "  1. 右键任意 PDF -> 打开方式 -> 选择其他应用 -> Zotero PDF -> 始终"
Write-Host "     （这一步必须手动完成，Windows 只允许资源管理器写入默认程序）"
Write-Host "  2. 之后双击 PDF 即可在 Zotero 中无感打开/导入"
pause
