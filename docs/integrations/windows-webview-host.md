# Windows WebView Host Workflow

The Windows WebView host displays the browser overlay in a transparent,
topmost, click-through Windows desktop window. It points at the same URL served
by `listen.py --web-overlay`.

## Use This When

- You want the browser overlay above a borderless/windowed Rocket League window.
- OBS projection is not preserving transparency or z-order the way you need.
- You want global hotkeys for reload, click-through toggle, and exit.

Use an OBS Browser Source instead when the overlay only needs to appear in an
OBS scene.

## Requirements

- Windows 10/11.
- Rocket League in borderless or windowed mode. Exclusive fullscreen usually
  wins over desktop overlays.
- .NET 8 SDK to run from source, or .NET 8 Desktop Runtime for a published
  framework-dependent build.
- Microsoft Edge WebView2 Runtime.

## Start From Windows PowerShell

Start the listener and web overlay:

```powershell
py -3.12 listen.py --web-overlay --obs-dir .\obs-output
```

Start the host:

```powershell
.\integrations\windows-webview-host\Start-OverlayHost.ps1 -Url http://127.0.0.1:8765/ -Monitor 1
```

## Start From WSL

Run the listener in WSL:

```bash
.venv/bin/python listen.py --web-overlay --obs-dir ./obs-output
```

Launch the Windows host through Windows PowerShell:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w integrations/windows-webview-host/Start-OverlayHost.ps1)" -Url http://127.0.0.1:8765/ -Monitor 1
```

Do not install Linux `dotnet` in WSL for this host. The host is a Windows WPF
desktop app, so it needs the Windows .NET runtime and WebView2.

## Hotkeys

| Hotkey | Action |
| --- | --- |
| `Ctrl+Shift+F10` | Toggle click-through/interactive mode. |
| `Ctrl+Shift+F11` | Reload the WebView. |
| `Ctrl+Shift+F9` | Exit the host. |

## Useful Arguments

Choose a monitor and zoom:

```powershell
.\integrations\windows-webview-host\Start-OverlayHost.ps1 `
  -Url http://127.0.0.1:8765/ `
  -Monitor 2 `
  -Zoom 1.0
```

Use explicit bounds:

```powershell
.\integrations\windows-webview-host\Start-OverlayHost.ps1 `
  -Url http://127.0.0.1:8765/ `
  -X 0 -Y 0 -Width 2560 -Height 1440
```

Debug interactively:

```powershell
.\integrations\windows-webview-host\Start-OverlayHost.ps1 `
  -Url http://127.0.0.1:8765/ `
  -NoClickThrough `
  -ShowTaskbar `
  -DevTools
```

## Troubleshooting

Check the browser feed before debugging the host:

```bash
curl http://127.0.0.1:8765/state.json
```

From WSL, check from the Windows side:

```bash
powershell.exe -NoProfile -Command "(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/state.json).Content"
```

If Windows cannot reach the WSL listener on `127.0.0.1`, start the listener with
`--web-host 0.0.0.0`, get the WSL IP with `hostname -I`, then pass
`http://<wsl-ip>:8765/` to the host.

If the overlay is behind the game, confirm Rocket League is not using exclusive
fullscreen. If the window cannot be interacted with, use `Ctrl+Shift+F10` to
disable click-through or `Ctrl+Shift+F9` to exit.

The host's implementation README remains at
`integrations/windows-webview-host/README.md`.
