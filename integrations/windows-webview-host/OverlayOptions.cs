using System.Globalization;
using System.Windows;

namespace RlStatsApiOverlay.Host;

public sealed record OverlayOptions(
    Uri Url,
    int MonitorIndex,
    Rect? Bounds,
    bool ClickThrough,
    bool Topmost,
    bool ShowInTaskbar,
    bool DevTools,
    double ZoomFactor)
{
    public static OverlayOptions Parse(string[] args)
    {
        var options = new Dictionary<string, string?>(StringComparer.OrdinalIgnoreCase);
        var flags = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        for (var index = 0; index < args.Length; index++)
        {
            var arg = args[index];
            if (!arg.StartsWith("--", StringComparison.Ordinal))
            {
                throw new ArgumentException($"Unexpected argument: {arg}");
            }

            var key = arg[2..];
            var equalsIndex = key.IndexOf('=', StringComparison.Ordinal);
            if (equalsIndex >= 0)
            {
                options[key[..equalsIndex]] = key[(equalsIndex + 1)..];
                continue;
            }

            if (IsFlag(key))
            {
                flags.Add(key);
                continue;
            }

            if (index + 1 >= args.Length)
            {
                throw new ArgumentException($"Missing value for --{key}");
            }
            options[key] = args[++index];
        }

        var urlText = GetOption(options, "url", "http://127.0.0.1:8765/");
        if (!Uri.TryCreate(urlText, UriKind.Absolute, out var url))
        {
            throw new ArgumentException($"Invalid --url value: {urlText}");
        }

        var bounds = ReadBounds(options);
        return new OverlayOptions(
            Url: url,
            MonitorIndex: ReadInt(options, "monitor", 1),
            Bounds: bounds,
            ClickThrough: !flags.Contains("no-click-through"),
            Topmost: !flags.Contains("not-topmost"),
            ShowInTaskbar: flags.Contains("show-taskbar"),
            DevTools: flags.Contains("devtools"),
            ZoomFactor: ReadDouble(options, "zoom", 1.0));
    }

    private static bool IsFlag(string key)
    {
        return key is "no-click-through" or "not-topmost" or "show-taskbar" or "devtools";
    }

    private static Rect? ReadBounds(Dictionary<string, string?> options)
    {
        var hasAny = options.ContainsKey("x")
            || options.ContainsKey("y")
            || options.ContainsKey("width")
            || options.ContainsKey("height");
        if (!hasAny)
        {
            return null;
        }

        var x = ReadDouble(options, "x", 0);
        var y = ReadDouble(options, "y", 0);
        var width = ReadDouble(options, "width", 1920);
        var height = ReadDouble(options, "height", 1080);
        if (width <= 0 || height <= 0)
        {
            throw new ArgumentException("--width and --height must be greater than zero");
        }
        return new Rect(x, y, width, height);
    }

    private static string GetOption(Dictionary<string, string?> options, string key, string fallback)
    {
        return options.TryGetValue(key, out var value) && !string.IsNullOrWhiteSpace(value) ? value : fallback;
    }

    private static int ReadInt(Dictionary<string, string?> options, string key, int fallback)
    {
        var value = GetOption(options, key, fallback.ToString(CultureInfo.InvariantCulture));
        if (!int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed))
        {
            throw new ArgumentException($"--{key} must be an integer");
        }
        return parsed;
    }

    private static double ReadDouble(Dictionary<string, string?> options, string key, double fallback)
    {
        var value = GetOption(options, key, fallback.ToString(CultureInfo.InvariantCulture));
        if (!double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var parsed))
        {
            throw new ArgumentException($"--{key} must be a number");
        }
        return parsed;
    }
}
