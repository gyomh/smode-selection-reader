# Reads the name of the element selected in Smode, from the Parameters panel (UI Automation, read-only).
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
# Speed: the title position is cached in %LOCALAPPDATA%\SmodeSelection\panel_pos.json and re-read directly
# (AutomationElement.FromPoint, ~0.5 s). A full scan (~4+ s) only happens when the cached position no longer
# shows a valid title (layout changed); it then refreshes the cache. Delete the file to force a full scan.
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
  Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, WindowsBase

  $proc = Get-Process Smode -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
  if (-not $proc) { Fail 'smode_not_found' "Smode is not running (or its window cannot be found)." }

  $cacheDir  = Join-Path $env:LOCALAPPDATA 'SmodeSelection'
  $cacheFile = Join-Path $cacheDir 'panel_pos.json'
  $numeric = '^[\d\s.,:;%+\-]+(\s*(deg|fps|ms|s|x))?$|^x\d'

  # Fast path: re-read the title at its cached position, accept it only if it still looks like a panel title.
  if (Test-Path $cacheFile) {
    try {
      $pos = Get-Content $cacheFile -Raw | ConvertFrom-Json
      $pt = New-Object System.Windows.Point(($pos.X + $pos.W / 2), ($pos.Y + $pos.H / 2))
      $el = [System.Windows.Automation.AutomationElement]::FromPoint($pt)
      if ($el -and $el.Current.ProcessId -eq $proc.Id) {
        # FromPoint returns an unnamed container sitting on the title; the Text itself is a nearby sibling
        # (checking a few siblings costs milliseconds, enumerating all children would cost seconds).
        $txt = $null
        if ($el.Current.ControlType.ProgrammaticName -eq 'ControlType.Text') { $txt = $el }
        else {
          $walker = [System.Windows.Automation.TreeWalker]::RawViewWalker
          foreach ($dir in 'Next', 'Prev') {
            $cur = $el
            for ($i = 0; $i -lt 4 -and -not $txt; $i++) {
              $cur = if ($dir -eq 'Next') { $walker.GetNextSibling($cur) } else { $walker.GetPreviousSibling($cur) }
              if (-not $cur) { break }
              if ($cur.Current.ControlType.ProgrammaticName -eq 'ControlType.Text') {
                $cr = $cur.Current.BoundingRectangle
                if ([math]::Abs($cr.X - $pos.X) -le 2 -and [math]::Abs($cr.Y - $pos.Y) -le 2) { $txt = $cur }
              }
            }
          }
        }
        if ($txt) {
          $r = $txt.Current.BoundingRectangle; $nm = $txt.Current.Name
          if ($nm -and $r.Height -ge 16 -and ($nm -notmatch $numeric) -and ($nm -notmatch ':\s*$') -and ([math]::Abs($r.Width / $r.Height - 6.82) -lt 0.25)) {
            [pscustomobject]@{ ok = $true; name = $nm } | ConvertTo-Json -Compress
            exit 0
          }
        }
      }
    } catch {}
  }

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

  try {
    $first = $titles | Select-Object -First 1
    if (-not (Test-Path $cacheDir)) { New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null }
    [pscustomobject]@{ X = $first.X; Y = $first.Y; W = $first.W; H = $first.H } | ConvertTo-Json -Compress | Set-Content -Path $cacheFile -Encoding UTF8
  } catch {}
  [pscustomobject]@{ ok = $true; name = $distinct[0] } | ConvertTo-Json -Compress
} catch {
  Fail 'read_failed' ("Read failed: " + $_.Exception.Message)
}
