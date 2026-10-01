# ------------------------------------------ . ---------------------------------- 
# Filename : OrderBlockInTimeline.py          | Manual Launch mode only!         |
# Author   : Basile Rouault                   |  automatically order block       |
#                                             | inside a timeline acroding       |
#                                             | to the layer order               |
# Started  : 04/11/2022                       | only for top level layers        |
# ------------------------------------------- . --------------------------------- 

# Modified by Guillaume Henrion (GYOMH), 2026 : acts on a timeline chosen by name (Target), on the timeline
# of the script's parent, or on the scene/compo SELECTED in Smode (read_selection.ps1). Also handles clips that
# are not tied to a layer. The chaining logic is Basile's original idea.

BlockMargin: Oil.Seconds(0)
Target: Oil.String("")
Status: Oil.String("")

import subprocess, threading, json, ctypes, os, urllib.request

SCRIPT_LABEL = "Order Block In Timeline"
BRIDGE_URL = "http://127.0.0.1:8891"
script.label = SCRIPT_LABEL

def setStatus(text):
    print(text)
    try:
        script.Status = text
    except Exception as e:
        print(f"Status parameter not updated: {e}")

#---------------- CODE OIL (execute ici si Target, ou rappele via le pont avec la selection) ----------------#
OIL_DEFS = '''
def findLayersByName(root, name):
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

def timelineOwner(obj):
    for o in (obj, getattr(obj, "generator", None)):
        if o is None:
            continue
        try:
            tl = o.mainAnimation
            _ = o.layers
        except Exception:
            continue
        if tl is not None and tl.getOilClassName() == "TimelineCue":
            return o
    return None

def orderBlocks(owner, margin):
    timeline = owner.mainAnimation
    tracks = []
    for element, track in timeline.elementTracks.items():
        elt = element.get()
        if elt is None or len(track.blocks) == 0:
            continue
        tracks.append((elt, track.blocks[0]))
    ordered = []
    used = set()
    for layer in list(owner.layers):
        for i, (elt, block) in enumerate(tracks):
            if i not in used and (elt == layer or elt.isChildOf(layer)):
                ordered.append(block)
                used.add(i)
    rest = [(b.position.get(), b) for i, (e, b) in enumerate(tracks) if i not in used]
    rest.sort(key=lambda x: x[0])
    ordered += [b for _, b in rest]
    if len(ordered) < 2:
        return len(ordered), 0
    nxt = ordered[0].position.get() + ordered[0].length.get() + margin
    for block in ordered[1:]:
        block.position.set(nxt)
        nxt = nxt + block.length.get() + margin
    return len(ordered), len(ordered) - 1

def runOrder(root, name, margin):
    """Retourne le message de resultat."""
    matches = findLayersByName(root, name)
    if len(matches) > 1:
        return f"[ambiguous_name] {len(matches)} layers nommes '{name}'."
    if len(matches) == 1:
        owner = timelineOwner(matches[0])
        if owner is None:
            return f"[no_timeline] '{name}' n'a pas de timeline."
    else:
        # pas un layer : peut-etre le nom d une timeline elle-meme (ex. 'Main Timeline')
        owners = []
        def scan(el):
            o = timelineOwner(el)
            if o is not None and o.mainAnimation.getFriendlyName() == name:
                owners.append(o)
            try:
                kids = list(el.generator.layers) if getattr(el, "generator", None) is not None else list(el.layers)
            except Exception:
                kids = []
            for k in kids:
                scan(k)
        scan(root)
        if len(owners) == 0:
            return f"[not_a_layer] '{name}' n'est ni un layer ni une timeline."
        if len(owners) > 1:
            return f"[ambiguous_timeline] {len(owners)} timelines nommees '{name}' - selectionne la scene / compo (son layer) a la place."
        owner = owners[0]
    total, moved = orderBlocks(owner, margin)
    return f"'{name}' : {total} clip(s), {moved} deplace(s)."
'''
exec(OIL_DEFS)

#---------------- RAPPEL SUR LE FIL PRINCIPAL (execute par le pont) ----------------#
CALLBACK = OIL_DEFS + '''
try:
    _root = script.project.masterScene
except Exception:
    _root = script.rootElement
_name = %(name)r
_msg = %(err)r if _name is None else runOrder(_root, _name, %(margin)r)
print(_msg)
def _findTool(el, d=0):
    if d > 6:
        return None
    for attr in ("tools", "layers"):
        try:
            seq = list(getattr(el, attr))
        except Exception:
            continue
        for x in seq:
            try:
                if x.getOilClassName() == "PythonScriptTool" and str(x.label.get()).startswith(%(base)r):
                    return x
            except Exception:
                pass
            r = _findTool(x, d + 1)
            if r is not None:
                return r
    try:
        g = el.generator
        if g is not None:
            return _findTool(g, d + 1)
    except Exception:
        pass
    return None
_tool = _findTool(_root)
if _tool is not None:
    _tool.label = %(prefix)r + _msg
'''

#---------------- LECTURE DE LA SELECTION (fil separe, ne bloque pas Smode) ----------------#
def _documentsFolder():
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(0, 5, 0, 0, buf)  # CSIDL_PERSONAL = dossier Documents reel
    return buf.value

READER_PATH = os.path.join(_documentsFolder(), "Smode Files", "Tools", "read_selection.ps1")

def postToBridge(code):
    req = urllib.request.Request(BRIDGE_URL, data=json.dumps({"code": code}).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req, timeout=10).read()

def selectionWorker(margin):
    prefix = SCRIPT_LABEL + " - "
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", READER_PATH],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=25, creationflags=0x08000000)
        sel = json.loads(p.stdout.decode("utf-8-sig", errors="replace").strip())
    except Exception as ex:
        sel = {"ok": False, "error": "read_failed", "message": repr(ex)}
    try:
        if sel.get("ok"):
            postToBridge(CALLBACK % {"name": sel["name"], "err": "", "margin": margin, "base": SCRIPT_LABEL, "prefix": prefix})
        else:
            postToBridge(CALLBACK % {"name": None, "err": "[" + sel.get("error", "?") + "] " + sel.get("message", ""), "margin": margin, "base": SCRIPT_LABEL, "prefix": prefix})
    except Exception as ex:
        print("Bridge call failed:", repr(ex))

#-------------------------------------MAIN PROCESS-------------------------------------#
margin = script.BlockMargin.get()
targetName = script.Target.get().strip()

parentOwner = timelineOwner(script.parentElement) if targetName == "" else None

if targetName != "":
    try:
        showRoot = script.project.masterScene   # on ne cherche que dans le Show (pas pipeline / topologie)
    except Exception:
        showRoot = script.rootElement
    setStatus(runOrder(showRoot, targetName, margin))
elif parentOwner is not None:
    total, moved = orderBlocks(parentOwner, margin)
    setStatus(f"Timeline du parent : {total} clip(s), {moved} deplace(s).")
elif not os.path.isfile(READER_PATH):
    setStatus(f"[reader_missing] read_selection.ps1 introuvable. Copie-le dans : {READER_PATH}")
else:
    setStatus("Lecture de la selection (~1 s) - resultat dans le nom du script...")
    threading.Thread(target=selectionWorker, args=(margin,), daemon=True).start()
