namespace RlStatsApiOverlay.Host;

public sealed class App : System.Windows.Application
{
    private readonly OverlayOptions _options;

    public App(OverlayOptions options)
    {
        _options = options;
        ShutdownMode = System.Windows.ShutdownMode.OnMainWindowClose;
    }

    protected override void OnStartup(System.Windows.StartupEventArgs e)
    {
        base.OnStartup(e);
        MainWindow = new OverlayWindow(_options);
        MainWindow.Show();
    }
}
