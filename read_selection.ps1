# Reads the name of the element selected in Smode Compose, from the Parameters panel (UI Automation, read-only).
#
# Usage rule: keep ONE Parameters panel visible and NOT locked.
# The script does not check the lock state; it fails explicitly when the panel is missing or ambiguous
# (several panels are accepted only if they all show the same name).
#
# One-line JSON output:
#   success: {"ok":true,"name":"<element name>"}
#   failure: {"ok":false,"error":"<code>","message":"<explanation>"}   (exit code 2)
# Codes: smode_not_found | ui_not_readable | no_panel | multiple_panels | read_failed
#
# Run: powershell -NoProfile -ExecutionPolicy Bypass -File read_selection.ps1

function Fail($code, $msg) {
  [pscustomobject]@{ ok = $false; error = $code; message = $msg } | ConvertTo-Json -Compress
  exit 2
}

try {
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8   # element names with accents
  Add-Type @'
using System; using System.Runtime.InteropServices;
public class DpiAware { [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr c); }
'@
  [DpiAware]::SetProcessDpiAwarenessContext([IntPtr](-4)) | Out-Null
  Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes

  $proc = Get-Process Smode -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
  if (-not $proc) { Fail 'smode_not_found' "Smode is not running (or its window cannot be found)." }

  $root = [System.Windows.Automation.AutomationElement]::FromHandle($proc.MainWindowHandle)
  $all = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
  if ($all.Count -lt 100) { Fail 'ui_not_readable' "The Smode interface is not readable ($($all.Count) elements). Window minimized or hidden?" }

  $texts = @(); $combos = @()
  foreach ($e in $all) {
    $t = $e.Current.ControlType.ProgrammaticName
    $r = $e.Current.BoundingRectangle
    if ($t -eq 'ControlType.Text' -and $e.Current.Name -and $r.Height -ge 16) {
      $texts += [pscustomobject]@{ Name = $e.Current.Name; X = $r.X; Y = $r.Y; H = $r.Height; W = $r.Width }
    } elseif ($t -eq 'ControlType.ComboBox') {
      $combos += [pscustomobject]@{ X = $r.X; Y = $r.Y }
    }
  }

  # A panel title = non-numeric text, not ending with ':', with a width/height ratio of ~6.82
  # (300x44 or 150x22 depending on the UI scale), and no drop-down on its row
  # (this rules out values such as "100.0 %", durations, and the Viewport title which has a menu on its right).
  $numeric = '^[\d\s.,:;%+\-]+(\s*(deg|fps|ms|s|x))?$|^x\d'
  $titles = @($texts | Where-Object {
    $tx = $_
    ($tx.Name -notmatch $numeric) -and ($tx.Name -notmatch ':\s*$') -and ([math]::Abs($tx.W / $tx.H - 6.82) -lt 0.25) -and -not ($combos | Where-Object { [math]::Abs($_.Y - $tx.Y) -le ($tx.H * 0.3) -and $_.X -gt $tx.X -and ($_.X - $tx.X) -le ($tx.H * 12) })
  })

  if ($titles.Count -eq 0) {
    Fail 'no_panel' "No Parameters panel visible. Open a Parameters tab (not locked) and select an element."
  }
  # Several panels: no ambiguity if they all show the same name.
  $distinct = @($titles | ForEach-Object { $_.Name } | Select-Object -Unique)
  if ($distinct.Count -gt 1) {
    $names = $distinct -join ' | '
    Fail 'multiple_panels' "Several panels detected showing different elements ($names). Keep a single Parameters panel, not locked."
  }

  [pscustomobject]@{ ok = $true; name = $distinct[0] } | ConvertTo-Json -Compress
} catch {
  Fail 'read_failed' ("Read failed: " + $_.Exception.Message)
}
