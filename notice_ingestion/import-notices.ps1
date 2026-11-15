$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

Add-Type -AssemblyName System.Windows.Forms
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}

Write-Host 'Import saved notice HTML' -ForegroundColor Green
Write-Host 'Save the notice page as an HTML file in your browser, then select it.'
$choice = Read-Host 'Department (1 = Computer Engineering, 2 = Electrical Engineering)'
$department = switch ($choice) {
    '1' { 'computer' }
    '2' { 'electrical' }
    default { Write-Host 'Choose 1 or 2.' -ForegroundColor Yellow; exit 2 }
}

$dialog = [System.Windows.Forms.OpenFileDialog]::new()
$dialog.Title = 'Select saved notice HTML'
$dialog.Filter = 'HTML files (*.html;*.htm)|*.html;*.htm|All files (*.*)|*.*'
$dialog.Multiselect = $false
if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
    Write-Host 'File selection cancelled.'
    exit 0
}

$env:PYTHONPATH = Join-Path $projectRoot 'BE'
& $python -m notice_ingestion.main import --department $department --html $dialog.FileName
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Import failed. Check the HTML file and the parser error.' -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host ''
Write-Host 'Done. Any new posts are listed above.' -ForegroundColor Green
Read-Host 'Press Enter to close' | Out-Null
