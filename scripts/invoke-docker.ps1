# Deprecated: use .\fortress.ps1 <command>
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$PyArgs)
$cmd = if ($PyArgs.Count -ge 2 -and $PyArgs[0] -eq '-c') {
    @("shell", "-c", "python $($PyArgs[1])")
} else {
    @("shell", "-c", "python $($PyArgs -join ' ')")
}
& "$PSScriptRoot\..\fortress.ps1" @cmd
