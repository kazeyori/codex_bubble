using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

namespace CodexBubbleInstaller
{
    internal static class InstallerBootstrapper
    {
        private const string DisplayName = "Codex \u989d\u5ea6\u60ac\u6d6e\u7403";

        [STAThread]
        private static int Main(string[] args)
        {
            bool quiet = HasArgument(args, "/quiet") || HasArgument(args, "-quiet");
            bool noLaunch = HasArgument(args, "/nolaunch") || HasArgument(args, "-nolaunch");
            string tempDir = Path.Combine(Path.GetTempPath(), "CodexBubbleSetup_" + Guid.NewGuid().ToString("N"));
            try
            {
                Directory.CreateDirectory(tempDir);
                ExtractResource("install.ps1", Path.Combine(tempDir, "install.ps1"));
                ExtractResource("codex-bubble-payload.zip", Path.Combine(tempDir, "codex-bubble-payload.zip"));

                string powershell = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.System),
                    @"WindowsPowerShell\v1.0\powershell.exe"
                );
                var startInfo = new ProcessStartInfo
                {
                    FileName = powershell,
                    Arguments = "-NoProfile -ExecutionPolicy Bypass -File \"" + Path.Combine(tempDir, "install.ps1") + "\"" +
                        (noLaunch ? " -NoLaunch" : "") +
                        (quiet ? " -Quiet" : ""),
                    WorkingDirectory = tempDir,
                    UseShellExecute = false,
                    CreateNoWindow = false
                };

                using (var process = Process.Start(startInfo))
                {
                    process.WaitForExit();
                    return process.ExitCode;
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "\u5b89\u88c5\u5931\u8d25\uff1a\n" + ex.Message,
                    DisplayName,
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return 1;
            }
            finally
            {
                try
                {
                    if (Directory.Exists(tempDir))
                    {
                        Directory.Delete(tempDir, true);
                    }
                }
                catch
                {
                }
            }
        }

        private static bool HasArgument(string[] args, string expected)
        {
            foreach (string arg in args)
            {
                if (string.Equals(arg, expected, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }
            return false;
        }

        private static void ExtractResource(string resourceName, string outputPath)
        {
            Assembly assembly = Assembly.GetExecutingAssembly();
            using (Stream input = assembly.GetManifestResourceStream(resourceName))
            {
                if (input == null)
                {
                    throw new InvalidOperationException("\u5b89\u88c5\u5668\u5185\u90e8\u8d44\u6e90\u7f3a\u5931\uff1a" + resourceName);
                }

                using (FileStream output = File.Create(outputPath))
                {
                    input.CopyTo(output);
                }
            }
        }
    }
}
