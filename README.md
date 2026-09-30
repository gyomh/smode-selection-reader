# Reading the selected element in Smode Compose (from a Script)

*[Version française](README.fr.md)*

A small helper that lets a **Smode Compose Script** find out which element is currently selected in the
interface, so your script can act on "whatever is selected" instead of asking the user to drag and drop it
into a parameter.

**Important: Smode Tech has not published an official API documentation, and this is not an officially
supported tool.** The Oil API does not expose the interface selection to scripts (nothing turned up when
scanning `engine`, `project` and `script`). This helper works around that by reading the name shown in the
Parameters panel through Windows UI Automation. It is experimental and was built by trial and error.

## How it works

Two pieces:

1. **`read_selection.ps1`** — a small PowerShell script (read-only, it never clicks or types). Smode is a JUCE
   application and exposes part of its interface to Windows UI Automation. The script finds the title of the
   Parameters panel (the name of the element it displays) and prints it as one line of JSON.

2. **`smode_read_selection.py`** — two Python functions to paste into your own Smode script:
   - `readSelection()` runs the PowerShell script in a separate thread (with a timeout) and returns the result;
   - `findLayersByName(root, name)` finds the layer(s) with that name in the project tree.

```
your Smode script --readSelection()--> powershell read_selection.ps1 --UI Automation--> Parameters panel title
        |
        +--findLayersByName(script.rootElement, name)--> the layer object, ready to use
```

## Install

1. Copy `read_selection.ps1` to `<your Documents folder>\Smode Files\Tools\read_selection.ps1`
   (create the `Tools` folder if needed). Every user of your script must do the same.
2. Paste the content of `smode_read_selection.py` near the top of your Smode script (after your Oil parameter
   declarations and before you use the selection).

The path is computed from the real Documents folder reported by Windows, so a redirected Documents folder
(OneDrive, for example) is fine.

## Use it in a script

```python
selection = readSelection()
if not selection["ok"]:
    print(selection["error"], selection["message"])     # tell the user what to fix
else:
    matches = findLayersByName(script.rootElement, selection["name"])
    if len(matches) == 1:
        layer = matches[0]
        # check its type yourself, e.g. layer.generator.getOilClassName() == 'VideoFileTextureGenerator'
```

Smode Scripts have no visible console for most users: writing the message into a text parameter
(`Status: Oil.String("")` then `script.Status = message`) is a convenient way to show it.

## What you get

Success: `{"ok": True, "name": "<element name>"}`. The helper returns **only the name**: it does not filter by
type, that is up to your script (the type shown in the panel depends on the sub-page currently displayed, so
it is not reliable to read it from the interface; look the layer up by name and read its type from Oil).

Failure: `{"ok": False, "error": <code>, "message": <text>}` with one of these codes:

| Code | Meaning |
|---|---|
| `reader_missing` | `read_selection.ps1` not found at the expected path |
| `timeout` | reading took longer than the timeout (25 s by default) |
| `read_failed` | unexpected error or unreadable answer |
| `smode_not_found` | Smode is not running |
| `ui_not_readable` | fewer than 100 interface elements visible (window minimized or hidden) |
| `no_panel` | no Parameters panel visible |
| `multiple_panels` | several panels show different elements (the names are listed in the message) |

## Rules and limits

- **Keep one Parameters panel visible and not locked.** A locked panel keeps showing an element that is not the
  selection, and the lock state cannot be read reliably. If several panels are open, the helper only accepts
  them when they all show the same name.
- **Launching your script:** the Execute button of the script's row in the *Elements* tree does not change the
  selection. The Execute button inside the script's own Parameters panel does (you have to select the script to
  show it), and you would then read the script's own name.
- **Name, not path.** Two layers with the same name cannot be told apart: handle that case in your script.
- **Speed:** a few seconds per call (about 3 to 4 s here), because the whole interface tree is walked.
- **Windows only**, with PowerShell 5.1 or later. The script must be started with `stdin=DEVNULL` from Smode
  (already done in `readSelection()`), otherwise `subprocess` fails with `OSError(9, 'The handle is invalid')`.
- **Tested:** Smode Compose 15.5 on Windows 11, English interface, one machine, Smode on the main display.
  Other interface languages, other UI scales and Smode on a secondary display are not verified.
- The Viewport title (which also shows an element name) is ignored on purpose; the detection relies on the shape
  of the panel title, so a future Smode interface change could break it.

## License

MIT — see [LICENSE](LICENSE).
