$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $Python)) {
    $Python = "pythonw"
}

if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = "$Root\src"
} else {
    $env:PYTHONPATH = "$Root\src;$env:PYTHONPATH"
}

foreach ($Key in @("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")) {
    $Value = [Environment]::GetEnvironmentVariable($Key)
    if ($Value -and ($Value -like "*127.0.0.1:9*" -or $Value -like "*localhost:9*")) {
        Remove-Item "Env:$Key" -ErrorAction SilentlyContinue
    }
}
if (-not $env:NO_PROXY) {
    $env:NO_PROXY = "127.0.0.1,localhost"
}

& $Python desktop_app.py
