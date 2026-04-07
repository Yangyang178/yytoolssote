$env:PYTHONPATH = $PSScriptRoot + "\venv\Lib\site-packages"
Set-Location $PSScriptRoot
& $PSScriptRoot\venv\Scripts\python.exe "app.py"
