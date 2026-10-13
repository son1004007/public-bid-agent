#requires -Version 5.1
<# 로컬 PC 하루 한 번 공식 공고 7일 중첩 갱신 작업 등록. 현재 Windows 사용자 DPAPI 키 사용. #>
[CmdletBinding()]
param([ValidatePattern('^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')][string]$At='09:00',[ValidateSet('Install','Remove','Status')][string]$Action='Install')
$ErrorActionPreference='Stop'
$name='PublicBidAgent-OfficialCollection'
if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'Windows 전용' }
$existing=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$owner=$identity.Name
if ($existing) {
 $taskUser=[string]$existing.Principal.UserId
 try {
  $taskSid=if ($taskUser -eq $identity.User.Value) { $taskUser } else {
   ([Security.Principal.NTAccount]::new($taskUser)).Translate([Security.Principal.SecurityIdentifier]).Value
  }
 } catch { throw '예약 작업 실행 계정을 식별할 수 없습니다' }
 if ($taskSid -ne $identity.User.Value) { throw '동일 이름의 다른 사용자 예약 작업이 이미 존재합니다' }
 if ($existing.Actions.Count -ne 1 -or -not ($existing.Actions[0].Arguments -like '*scheduled_collection.py*')) {
  throw '동일 이름의 다른 용도 예약 작업을 변경할 수 없습니다'
 }
}
if ($Action -eq 'Status') {
 if (-not $existing) { Write-Output 'STATUS=NOT_REGISTERED'; exit 0 }
 $info=Get-ScheduledTaskInfo -TaskName $name
 Write-Output ('STATUS='+$existing.State)
 Write-Output ('LAST_RESULT='+$info.LastTaskResult)
 Write-Output ('LAST_RUN='+$info.LastRunTime.ToString('s'))
 Write-Output ('NEXT_RUN='+$info.NextRunTime.ToString('s'))
 exit 0
}
if ($Action -eq 'Install' -and $existing) { throw '이미 등록된 예약 작업이 있습니다. 먼저 -Action Status로 확인하세요' }
if ($Action -eq 'Remove') {
 if ($existing) { Unregister-ScheduledTask -TaskName $name -Confirm:$false }
 Write-Output 'STATUS=REMOVED'; exit 0
}
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$base=Join-Path $env:LOCALAPPDATA 'PublicBidAgent\Lab'
$py=Join-Path $base '.venv\Scripts\python.exe'
$script=Join-Path $repo 'local_app\scheduled_collection.py'
$data=Join-Path $base 'user-json'
foreach ($path in @($py,$script,$data)) { if (-not (Test-Path $path)) { throw ('예약 수집 입력 누락: '+$path) } }
$account=$owner
foreach ($checked in @($repo,$py,$script,$data)) {
 $cursor=Get-Item -LiteralPath $checked -Force
 while ($cursor) {
  if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw ('재분석 경로를 거부합니다: '+$cursor.FullName) }
  $cursor=$cursor.Parent
 }
}
$argsText='-B "'+$script+'" --data-dir "'+$data+'" --days 7 --apply'
$taskAction=New-ScheduledTaskAction -Execute $py -Argument $argsText -WorkingDirectory $repo
$start=[datetime]::ParseExact($At,'HH:mm',[Globalization.CultureInfo]::InvariantCulture)
$trigger=New-ScheduledTaskTrigger -Daily -At $start
$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 60) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal=New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $name -Action $taskAction -Trigger $trigger -Settings $settings -Principal $principal -Description 'G2B 7-day official sync; private DPAPI, preserves decisions and RFP.' | Out-Null
Write-Output 'STATUS=REGISTERED'
Write-Output ('SCHEDULE=DAILY '+$At)
Write-Output ('RUN_AS='+$account)
Write-Output ('DATA_DIR='+$data)
