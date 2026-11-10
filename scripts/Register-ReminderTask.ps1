param([string]$TaskName = 'AssetCairn Reminders')

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'Create the project .venv and install requirements.txt first.' }
$UtcTomorrow = [DateTime]::UtcNow.Date.AddDays(1).AddHours(8)
$LocalRunTime = [TimeZoneInfo]::ConvertTimeFromUtc($UtcTomorrow, [TimeZoneInfo]::Local)
$Action = New-ScheduledTaskAction -Execute $Python -Argument 'manage.py send_reminders' -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At $LocalRunTime
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)
$Principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force | Out-Null
Write-Output "Registered '$TaskName' at $($LocalRunTime.ToString('HH:mm')) local time (08:00 UTC at registration)."
Write-Output 'This task runs while your Windows account is signed in. Re-register after daylight-saving changes.'