namespace RlStatsApiOverlay.Host;

public static class Program
{
    [STAThread]
    public static int Main(string[] args)
    {
        OverlayOptions options;
        try
        {
            options = OverlayOptions.Parse(args);
        }
        catch (ArgumentException exc)
        {
            System.Windows.MessageBox.Show(
                exc.Message,
                "RL StatsAPI Overlay Host",
                System.Windows.MessageBoxButton.OK,
                System.Windows.MessageBoxImage.Error);
            return 2;
        }

        // Avoid a white WebView flash before CoreWebView2 applies its transparent background.
        Environment.SetEnvironmentVariable("WEBVIEW2_DEFAULT_BACKGROUND_COLOR", "00FFFFFF");

        var app = new App(options);
        app.Run();
        return 0;
    }
}
