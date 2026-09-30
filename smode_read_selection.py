# Smode Compose - read the currently selected element from inside a Script.
#
# Paste this block at the top of your own Smode script (after your Oil parameter declarations).
# It needs read_selection.ps1 installed in:  <Documents>\Smode Files\Tools\read_selection.ps1
#
#   selection = readSelection()
#   if selection["ok"]:
#       layers = findLayersByName(script.rootElement, selection["name"])
#   else:
#       print(selection["error"], selection["message"])
#
# Good to know:
# - The name comes from the Parameters panel (read-only, through Windows UI Automation). Keep ONE Parameters
#   panel visible and not locked (several panels are fine if they all show the same name).
# - Run your script with the Execute button of its row in the Elements tree: it does not change the selection.
#   The Execute button inside the script's own Parameters panel does (you have to select the script first).
# - Smode has no console handle: the PowerShell process must be started with stdin=DEVNULL, otherwise
#   subprocess fails with OSError(9, 'The handle is invalid'). It also runs in a separate thread so that Smode's
#   main thread only waits with a timeout.

import subprocess, threading, json, ctypes, os

def _documentsFolder():
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(0, 5, 0, 0, buf)  # CSIDL_PERSONAL = the real Documents folder
    return buf.value

READER_PATH = os.path.join(_documentsFolder(), "Smode Files", "Tools", "read_selection.ps1")

def readSelection(timeout=25):
    """Returns {"ok": True, "name": ...} or {"ok": False, "error": code, "message": ...}.

    Error codes: reader_missing, timeout, read_failed (from this function) and
    smode_not_found, ui_not_readable, no_panel, multiple_panels, read_failed (from read_selection.ps1).
    """
    if not os.path.isfile(READER_PATH):
        return {"ok": False, "error": "reader_missing", "message": f"read_selection.ps1 not found. Copy it to: {READER_PATH}"}
    box = {}
    def work():
        try:
            p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", READER_PATH],
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=timeout, creationflags=0x08000000)  # CREATE_NO_WINDOW
            box["out"] = p.stdout.decode("utf-8-sig", errors="replace").strip()
            box["err"] = p.stderr.decode("utf-8", errors="replace").strip()
        except subprocess.TimeoutExpired:
            box["timeout"] = True
        except Exception as ex:
            box["exc"] = repr(ex)
    th = threading.Thread(target=work, daemon=True)
    th.start()
    th.join(timeout + 5)
    if th.is_alive() or box.get("timeout"):
        return {"ok": False, "error": "timeout", "message": f"Reading the selection took too long (> {timeout} s)."}
    if "exc" in box:
        return {"ok": False, "error": "read_failed", "message": box["exc"]}
    try:
        return json.loads(box["out"])
    except Exception:
        return {"ok": False, "error": "read_failed", "message": "Unreadable answer: " + (box.get("out") or box.get("err") or "empty")[:200]}


def findLayersByName(root, name):
    """All layers (recursive) whose display name is `name`. Use script.rootElement as `root`."""
    found = []
    def walk(element):
        if hasattr(element, "generator"):
            try:
                children = element.generator.layers
            except AttributeError:
                return
        elif hasattr(element, "layers"):
            children = element.layers
        else:
            return
        for child in children:
            if child.getFriendlyName() == name:
                found.append(child)
            walk(child)
    walk(root)
    return found
