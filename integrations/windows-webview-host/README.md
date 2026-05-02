# Windows WebView Overlay Host

A small Windows-only host for the browser overlay served by `listen.py --web-overlay`.

It opens the local overlay URL in WebView2, makes the native window transparent, topmost, no-activate, and click-through, then uses global hotkeys for control.

## Requirements

- Windows 10/11.
- Rocket League running in borderless/windowed mode. True exclusive fullscreen usually wins over normal desktop overlays.
- .NET 8 SDK to run from source, or .NET 8 Desktop Runtime for a published framework-dependent build.
- Microsoft Edge WebView2 Runtime. It is normally already installed with Edge on modern Windows.

## Start The Overlay

If you are in a Windows PowerShell terminal, start the listener and web overlay:

```powershell
py -3.12 listen.py --web-overlay --obs-dir .\obs-output
```

Then start the host:

```powershell
.\integrations\windows-webview-host\Start-OverlayHost.ps1 -Url http://127.0.0.1:8765/ -Monitor 1
```

If VS Code is opened through WSL, keep the listener in the WSL terminal:

```bash
.venv/bin/python listen.py --web-overlay --obs-dir ./obs-output
```

Then launch the Windows host from a second WSL terminal by calling Windows PowerShell:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w integrations/windows-webview-host/Start-OverlayHost.ps1)" -Url http://127.0.0.1:8765/ -Monitor 1
```

The host starts click-through by default.

Do not install Linux `dotnet` in WSL for this host. The transparent window is a Windows desktop app, so it needs the Windows .NET 8 SDK/runtime and Windows WebView2 Runtime.

## Check The Feed

Before debugging the host, check that the browser overlay feed is reachable.

From WSL:

```bash
curl http://127.0.0.1:8765/state.json
```

From the Windows side:

```bash
powershell.exe -NoProfile -Command "(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/state.json).Content"
```

The result should be JSON. If it is a `500` or connection error, restart the listener and fix the feed before relaunching the host.

## Hotkeys

- `Ctrl+Shift+F10`: toggle click-through/interactive mode.
- `Ctrl+Shift+F11`: reload the WebView.
- `Ctrl+Shift+F9`: exit the host.

These are registered as global hotkeys so they still work while Rocket League has focus.

## Useful Arguments

```powershell
.\integrations\windows-webview-host\Start-OverlayHost.ps1 `
  -Url http://127.0.0.1:8765/ `
  -Monitor 2 `
  -Zoom 1.0
```

Custom pixel bounds:

```powershell
.\integrations\windows-webview-host\Start-OverlayHost.ps1 `
  -Url http://127.0.0.1:8765/ `
  -X 0 -Y 0 -Width 2560 -Height 1440
```

Debug mode:

```powershell
.\integrations\windows-webview-host\Start-OverlayHost.ps1 `
  -Url http://127.0.0.1:8765/ `
  -NoClickThrough `
  -ShowTaskbar `
  -DevTools
```

## Publish An EXE

Build from WSL:

```bash
powershell.exe -NoProfile -Command "dotnet build \"$(wslpath -w integrations/windows-webview-host/RlStatsApiOverlay.Host.csproj)\""
```

Framework-dependent build:

```powershell
dotnet publish integrations\windows-webview-host -c Release -r win-x64 --self-contained false
```

Run the published host:

```powershell
.\integrations\windows-webview-host\bin\Release\net8.0-windows10.0.19041.0\win-x64\publish\RlStatsApiOverlay.Host.exe --url http://127.0.0.1:8765/
```

## Troubleshooting

- If the overlay is blank, open `http://127.0.0.1:8765/` in Edge first. Fix the listener/web overlay before debugging the host.
- If you are using WSL and Edge cannot reach `127.0.0.1:8765`, start the listener with `--web-host 0.0.0.0`, get the WSL IP with `hostname -I`, then pass `-Url http://<wsl-ip>:8765/` to the host.
- If `Start-OverlayHost.ps1` says Windows `dotnet` is missing, install the .NET 8 SDK for Windows. Installing `dotnet` inside WSL will not let WSL run a WPF overlay window.
- If you cannot close or interact with the window, press `Ctrl+Shift+F9` to exit or `Ctrl+Shift+F10` to disable click-through.
- If the overlay is behind the game, confirm Rocket League is borderless/windowed rather than exclusive fullscreen.
- If WebView2 fails to initialize, install or repair the Evergreen WebView2 Runtime.
- If layout scale feels wrong, try `--zoom 0.9` or a custom `--width`/`--height` matching the game window.
