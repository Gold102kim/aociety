using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows.Forms;

internal static class EchoVerseStarter
{
    [STAThread]
    private static void Main()
    {
        string root = AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
        string project = Path.Combine(root, "软件端");
        string buildEntry = Path.Combine(project, "dist", "index.html");
        string packageRoot = Path.Combine(project, "node_modules", ".pnpm");

        if (!Directory.Exists(project) || !File.Exists(buildEntry))
        {
            ShowError("没有找到完整的软件文件。请确认“EchoVerse启动器.exe”和“软件端”文件夹位于同一个目录。", root);
            return;
        }

        string electron = FindElectron(packageRoot);
        if (electron == null)
        {
            ShowError("没有找到 Electron 运行程序。请先在“软件端”目录中安装项目依赖。", project);
            return;
        }

        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = electron,
                Arguments = ".",
                WorkingDirectory = project,
                UseShellExecute = true
            });
        }
        catch (Exception exception)
        {
            ShowError("软件启动失败：" + exception.Message, project);
        }
    }

    private static string FindElectron(string packageRoot)
    {
        if (!Directory.Exists(packageRoot)) return null;

        foreach (string directory in Directory.GetDirectories(packageRoot, "electron@*").OrderByDescending(value => value))
        {
            string candidate = Path.Combine(directory, "node_modules", "electron", "dist", "electron.exe");
            if (File.Exists(candidate)) return candidate;
        }

        return null;
    }

    private static void ShowError(string message, string location)
    {
        MessageBox.Show(
            message + Environment.NewLine + Environment.NewLine + "检查位置：" + location,
            "EchoVerse 启动器",
            MessageBoxButtons.OK,
            MessageBoxIcon.Error
        );
    }
}
