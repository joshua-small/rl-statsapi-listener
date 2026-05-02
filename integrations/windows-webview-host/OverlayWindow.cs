using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Forms;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Threading;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.Wpf;
using Brushes = System.Windows.Media.Brushes;
using Color = System.Windows.Media.Color;
using MessageBox = System.Windows.MessageBox;
using Rectangle = System.Drawing.Rectangle;

namespace RlStatsApiOverlay.Host;

public sealed class OverlayWindow : Window
{
    private const int HotkeyToggleClickThrough = 1;
    private const int HotkeyReload = 2;
    private const int HotkeyExit = 3;
    private const uint VkF9 = 0x78;
    private const uint VkF10 = 0x79;
    private const uint VkF11 = 0x7A;

    private readonly OverlayOptions _options;
    private readonly WebView2CompositionControl _webView;
    private readonly Border _statusShell;
    private readonly TextBlock _statusText;
    private readonly DispatcherTimer _statusTimer;

    private HwndSource? _source;
    private nint _hwnd;
    private bool _clickThrough;

    public OverlayWindow(OverlayOptions options)
    {
        _options = options;
        _clickThrough = options.ClickThrough;

        AllowsTransparency = true;
        Background = Brushes.Transparent;
        ShowActivated = false;
        ShowInTaskbar = options.ShowInTaskbar;
        Topmost = options.Topmost;
        WindowStartupLocation = WindowStartupLocation.Manual;
        WindowStyle = WindowStyle.None;
        ResizeMode = ResizeMode.NoResize;
        Title = "RL StatsAPI Overlay";

        _webView = new WebView2CompositionControl
        {
            DefaultBackgroundColor = System.Drawing.Color.Transparent,
            HorizontalAlignment = System.Windows.HorizontalAlignment.Stretch,
            VerticalAlignment = VerticalAlignment.Stretch,
        };

        _statusText = new TextBlock
        {
            Foreground = Brushes.White,
            FontSize = 14,
            FontWeight = FontWeights.SemiBold,
            TextWrapping = TextWrapping.NoWrap,
        };
        _statusShell = new Border
        {
            Background = new SolidColorBrush(Color.FromArgb(210, 8, 14, 22)),
            BorderBrush = new SolidColorBrush(Color.FromArgb(90, 255, 255, 255)),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(12, 8, 12, 8),
            HorizontalAlignment = System.Windows.HorizontalAlignment.Left,
            VerticalAlignment = VerticalAlignment.Top,
            Margin = new Thickness(16),
            Visibility = Visibility.Collapsed,
            Child = _statusText,
        };

        var root = new Grid { Background = Brushes.Transparent };
        root.Children.Add(_webView);
        root.Children.Add(_statusShell);
        Content = root;

        _statusTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1.6) };
        _statusTimer.Tick += (_, _) =>
        {
            _statusTimer.Stop();
            _statusShell.Visibility = Visibility.Collapsed;
        };

        SourceInitialized += OnSourceInitialized;
        Loaded += OnLoaded;
        Closed += OnClosed;
    }

    protected override void OnActivated(EventArgs e)
    {
        base.OnActivated(e);
        if (_clickThrough)
        {
            ApplyNativeStyles();
        }
    }

    private async void OnLoaded(object sender, RoutedEventArgs e)
    {
        try
        {
            var environment = await CreateWebViewEnvironment();
            await _webView.EnsureCoreWebView2Async(environment);
            ConfigureWebView();
            _webView.CoreWebView2.Navigate(_options.Url.ToString());
            ShowStatus(_clickThrough ? "Click-through overlay active" : "Interactive overlay mode");
        }
        catch (Exception exc)
        {
            MessageBox.Show(
                exc.Message,
                "Could not start WebView2 overlay",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
            Close();
        }
    }

    private void OnSourceInitialized(object? sender, EventArgs e)
    {
        _hwnd = new WindowInteropHelper(this).Handle;
        _source = HwndSource.FromHwnd(_hwnd);
        _source?.AddHook(WndProc);

        ApplyBounds();
        ApplyNativeStyles();
        RegisterHotkeys();
    }

    private void OnClosed(object? sender, EventArgs e)
    {
        if (_hwnd != nint.Zero)
        {
            NativeMethods.UnregisterHotKey(_hwnd, HotkeyToggleClickThrough);
            NativeMethods.UnregisterHotKey(_hwnd, HotkeyReload);
            NativeMethods.UnregisterHotKey(_hwnd, HotkeyExit);
        }

        _source?.RemoveHook(WndProc);
        _webView.Dispose();
    }

    private static async Task<CoreWebView2Environment> CreateWebViewEnvironment()
    {
        var userDataFolder = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "RLStatsApiOverlay",
            "WebView2");
        Directory.CreateDirectory(userDataFolder);
        return await CoreWebView2Environment.CreateAsync(browserExecutableFolder: null, userDataFolder: userDataFolder);
    }

    private void ConfigureWebView()
    {
        _webView.DefaultBackgroundColor = System.Drawing.Color.Transparent;
        _webView.ZoomFactor = _options.ZoomFactor;

        var settings = _webView.CoreWebView2.Settings;
        settings.AreDefaultContextMenusEnabled = _options.DevTools;
        settings.AreDevToolsEnabled = _options.DevTools;
        settings.AreBrowserAcceleratorKeysEnabled = _options.DevTools;
        settings.IsStatusBarEnabled = false;
        settings.IsZoomControlEnabled = _options.DevTools;

        _webView.CoreWebView2.NavigationCompleted += (_, args) =>
        {
            if (!args.IsSuccess)
            {
                ShowStatus($"Navigation failed: {args.WebErrorStatus}");
            }
        };
    }

    private void ApplyBounds()
    {
        var bounds = _options.Bounds is { } customBounds
            ? new Rectangle(
                (int)Math.Round(customBounds.X),
                (int)Math.Round(customBounds.Y),
                (int)Math.Round(customBounds.Width),
                (int)Math.Round(customBounds.Height))
            : SelectMonitorBounds();

        Left = bounds.Left;
        Top = bounds.Top;
        Width = bounds.Width;
        Height = bounds.Height;

        NativeMethods.SetWindowPos(
            _hwnd,
            _options.Topmost ? NativeMethods.HwndTopmost : NativeMethods.HwndNotopmost,
            bounds.Left,
            bounds.Top,
            bounds.Width,
            bounds.Height,
            NativeMethods.SwpNoactivate | NativeMethods.SwpShowwindow | NativeMethods.SwpFramechanged);
    }

    private Rectangle SelectMonitorBounds()
    {
        var screens = Screen.AllScreens;
        if (screens.Length == 0)
        {
            return new Rectangle(0, 0, 1920, 1080);
        }

        var index = Math.Clamp(_options.MonitorIndex, 1, screens.Length) - 1;
        return screens[index].Bounds;
    }

    private void ApplyNativeStyles()
    {
        if (_hwnd == nint.Zero)
        {
            return;
        }

        var style = NativeMethods.GetWindowLongPtr(_hwnd, NativeMethods.GwlExStyle).ToInt64();
        style |= NativeMethods.WsExLayered | NativeMethods.WsExToolwindow | NativeMethods.WsExNoactivate;
        if (_options.Topmost)
        {
            style |= NativeMethods.WsExTopmost;
        }
        else
        {
            style &= ~NativeMethods.WsExTopmost;
        }

        if (_clickThrough)
        {
            style |= NativeMethods.WsExTransparent;
        }
        else
        {
            style &= ~NativeMethods.WsExTransparent;
        }

        NativeMethods.SetWindowLongPtr(_hwnd, NativeMethods.GwlExStyle, new nint(style));
        NativeMethods.SetWindowPos(
            _hwnd,
            _options.Topmost ? NativeMethods.HwndTopmost : NativeMethods.HwndNotopmost,
            0,
            0,
            0,
            0,
            NativeMethods.SwpNomove
                | NativeMethods.SwpNosize
                | NativeMethods.SwpNoactivate
                | NativeMethods.SwpFramechanged
                | NativeMethods.SwpShowwindow);
    }

    private void RegisterHotkeys()
    {
        var modifiers = NativeMethods.ModControl | NativeMethods.ModShift;
        NativeMethods.RegisterHotKey(_hwnd, HotkeyToggleClickThrough, modifiers, VkF10);
        NativeMethods.RegisterHotKey(_hwnd, HotkeyReload, modifiers, VkF11);
        NativeMethods.RegisterHotKey(_hwnd, HotkeyExit, modifiers, VkF9);
    }

    private nint WndProc(nint hwnd, int msg, nint wParam, nint lParam, ref bool handled)
    {
        if (msg == NativeMethods.WmHotkey)
        {
            handled = true;
            HandleHotkey(wParam.ToInt32());
            return nint.Zero;
        }

        if (msg == NativeMethods.WmMouseActivate && _clickThrough)
        {
            handled = true;
            return new nint(NativeMethods.MaNoActivate);
        }

        if (msg == NativeMethods.WmNchittest && _clickThrough)
        {
            handled = true;
            return new nint(NativeMethods.HtTransparent);
        }

        return nint.Zero;
    }

    private void HandleHotkey(int hotkeyId)
    {
        switch (hotkeyId)
        {
            case HotkeyToggleClickThrough:
                _clickThrough = !_clickThrough;
                ApplyNativeStyles();
                ShowStatus(_clickThrough ? "Click-through overlay active" : "Interactive overlay mode");
                break;
            case HotkeyReload:
                _webView.CoreWebView2?.Reload();
                ShowStatus("Overlay reloaded");
                break;
            case HotkeyExit:
                Close();
                break;
        }
    }

    private void ShowStatus(string text)
    {
        _statusText.Text = text;
        _statusShell.Visibility = Visibility.Visible;
        _statusTimer.Stop();
        _statusTimer.Start();
    }
}
