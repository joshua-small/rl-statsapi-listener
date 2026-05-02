using System.Runtime.InteropServices;

namespace RlStatsApiOverlay.Host;

internal static class NativeMethods
{
    public const int GwlExStyle = -20;
    public const int HtTransparent = -1;
    public const int MaNoActivate = 3;
    public const int WmHotkey = 0x0312;
    public const int WmMouseActivate = 0x0021;
    public const int WmNchittest = 0x0084;

    public const uint ModControl = 0x0002;
    public const uint ModShift = 0x0004;
    public const uint SwpNosize = 0x0001;
    public const uint SwpNomove = 0x0002;
    public const uint SwpNozorder = 0x0004;
    public const uint SwpNoactivate = 0x0010;
    public const uint SwpFramechanged = 0x0020;
    public const uint SwpShowwindow = 0x0040;

    public const long WsExTopmost = 0x00000008L;
    public const long WsExTransparent = 0x00000020L;
    public const long WsExToolwindow = 0x00000080L;
    public const long WsExLayered = 0x00080000L;
    public const long WsExNoactivate = 0x08000000L;

    public static readonly nint HwndTopmost = new(-1);
    public static readonly nint HwndNotopmost = new(-2);

    [DllImport("user32.dll", EntryPoint = "GetWindowLongPtrW", SetLastError = true)]
    public static extern nint GetWindowLongPtr(nint hwnd, int index);

    [DllImport("user32.dll", EntryPoint = "SetWindowLongPtrW", SetLastError = true)]
    public static extern nint SetWindowLongPtr(nint hwnd, int index, nint value);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool SetWindowPos(
        nint hwnd,
        nint hwndInsertAfter,
        int x,
        int y,
        int cx,
        int cy,
        uint flags);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool RegisterHotKey(nint hwnd, int id, uint fsModifiers, uint vk);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool UnregisterHotKey(nint hwnd, int id);
}
