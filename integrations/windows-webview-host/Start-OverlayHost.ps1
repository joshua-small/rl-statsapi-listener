param(
    [string]$Url = "http://127.0.0.1:8765/",
    [int]$Monitor = 1,
    [double]$Zoom = 1.0,
    [switch]$NoClickThrough,
    [switch]$ShowTaskbar,
    [switch]$DevTools,
    [int]$X,
    [int]$Y,
    [int]$Width,
    [int]$Height
)

$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectPath = Join-Path $projectDir "RlStatsApiOverlay.Host.csproj"

if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    throw "Windows dotnet was not found. Install the .NET 8 SDK for Windows, then run this script again."
}

$sdkVersions = @(dotnet --list-sdks | ForEach-Object {
    $versionText = ($_ -split "\s+")[0]
    $version = $null
    if ([Version]::TryParse($versionText, [ref]$version)) {
        $version
    }
})

if (-not ($sdkVersions | Where-Object { $_.Major -ge 8 })) {
    throw "Windows .NET 8 SDK was not found. Current SDKs: $($sdkVersions -join ', '). Install the .NET 8 SDK for Windows, not Linux/WSL."
}

$appArgs = @(
    "--url", $Url,
    "--monitor", $Monitor,
    "--zoom", $Zoom
)

if ($NoClickThrough) {
    $appArgs += "--no-click-through"
}
if ($ShowTaskbar) {
    $appArgs += "--show-taskbar"
}
if ($DevTools) {
    $appArgs += "--devtools"
}

$hasBounds = $PSBoundParameters.ContainsKey("X") `
    -or $PSBoundParameters.ContainsKey("Y") `
    -or $PSBoundParameters.ContainsKey("Width") `
    -or $PSBoundParameters.ContainsKey("Height")

if ($hasBounds) {
    foreach ($requiredBound in @("X", "Y", "Width", "Height")) {
        if (-not $PSBoundParameters.ContainsKey($requiredBound)) {
            throw "Custom bounds require -X, -Y, -Width, and -Height."
        }
    }
    if ($Width -le 0 -or $Height -le 0) {
        throw "Custom bounds require positive -Width and -Height values."
    }

    $appArgs += @(
        "--x", $X,
        "--y", $Y,
        "--width", $Width,
        "--height", $Height
    )
}

dotnet run --project $projectPath -- @appArgs
