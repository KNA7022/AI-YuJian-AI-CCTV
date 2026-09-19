# Resumable download of the PyTorch cu124 wheel.
# PyTorch's CDN supports range requests, so progress survives interruptions.
param(
    [string]$Url = "https://download-r2.pytorch.org/whl/cu124/torch-2.5.1%2Bcu124-cp311-cp311-win_amd64.whl",
    [string]$Destination = ".runtime\wheels\torch-2.5.1+cu124-cp311-cp311-win_amd64.whl",
    [int]$ChunkMB = 32,
    [int]$MaxRetries = 40
)
$ErrorActionPreference = "Stop"
$chunk = [int64]$ChunkMB * [int64]1MB

$dir = Split-Path -Parent $Destination
if ($dir -and !(Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

$head = [System.Net.HttpWebRequest]::Create($Url)
$head.Method = "HEAD"
$head.Timeout = 30000
$headResponse = $head.GetResponse()
$total = [int64]$headResponse.Headers["Content-Length"]
$headResponse.Close()
Write-Output "total size: $([math]::Round($total/1MB,1)) MB"

$attempt = 0
while ($true) {
    $have = 0
    if (Test-Path $Destination) { $have = (Get-Item $Destination).Length }
    if ($have -ge $total) { Write-Output "download complete: $have bytes"; break }
    if ($attempt -ge $MaxRetries) { Write-Output "FAILED after $attempt retries at $have bytes"; exit 1 }

    $end = $have + $chunk - 1
    if ($end -gt ($total - 1)) { $end = $total - 1 }
    try {
        $req = [System.Net.HttpWebRequest]::Create($Url)
        $req.AddRange($have, $end)
        $req.Timeout = 120000
        $req.ReadWriteTimeout = 120000
        $resp = $req.GetResponse()
        $stream = $resp.GetResponseStream()
        $fileStream = [System.IO.File]::Open($Destination, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write)
        $buffer = New-Object byte[] 1048576
        $written = 0
        while (($read = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $fileStream.Write($buffer, 0, $read)
            $written += $read
        }
        $fileStream.Close(); $stream.Close(); $resp.Close()
        $now = (Get-Item $Destination).Length
        $pct = [math]::Round($now * 100 / $total, 1)
        Write-Output ("chunk ok: +{0:N1} MB -> {1:N1}/{2:N1} MB ({3}%)" -f ($written/1MB), ($now/1MB), ($total/1MB), $pct)
        $attempt = 0
    }
    catch {
        $attempt++
        Write-Output ("chunk failed (attempt {0}/{1}): {2}" -f $attempt, $MaxRetries, $_.Exception.Message)
        Start-Sleep -Seconds 4
    }
}
Write-Output "DONE"
