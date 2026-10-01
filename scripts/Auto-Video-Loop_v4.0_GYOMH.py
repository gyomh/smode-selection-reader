# | |                                 | | | |                                 | | #
# |0|        AUTO VIDEO LOOP          |0| |0|_________________________________|0| #
# | |             V4.0                | | | |                                 | | #
# | |_________________________________| | | | - "Out" default value of 00:00  | | #
# | |    for SMODE 10.1 and onward    | | | |   correspond to video length    | | #
# |0|                                 |0| |0| - HAP Alpha videos will         |0| #
# | |          Instructions :         | | | |   automatically be processed    | | #
# | |                                 | | | |   with Alpha crossfade          | | #
# | |  1- Drag and drop a Video in    | | | | - If the video is either in     | | #
# |0|    "Video To Loop" parameter    |0| |0|   Prores or NotchLC  with Alpha |0| #
# | |  2- enter crossfade value       | | | |   use the "force Alpha" button  | | #
# | |  3- choose In and Out to crop   | | | | - Video export is in Beta       | | #
# | |  4- press Execute               | | | |   works ~1/4 of the time        | | #
# |0|_________________________________|0| |0|_________________________________|0| #
# | |      Vincent Le Moigne          | | | |            01/02/2025           | | #
#                                                                                 #
#    If you press the button 4 time 'video export' should work at some point :/   #
#_________________________________________________________________________________#

# Modified by Guillaume Henrion (GYOMH), 2026 : variant that acts on the element SELECTED in Smode
# (name read by read_selection.ps1) instead of the 'Video To Loop' drag and drop - see the instructions
# in the smode-selection-reader repository. The loop creation itself is Vincent's original code.

Crossfade: Oil.Seconds(1.)
AlphaCrossfade : Oil.Boolean(False)
In : Oil.Seconds()
Out : Oil.Seconds()
#ExportVideo : Oil.Boolean(False)
#ConvertExportToCompoFps : Oil.Boolean(False)
ReplaceByLoop: Oil.Boolean(False)
Status: Oil.String("")

import os
import time
from pathlib import Path

#-------------------------READ SELECTED ELEMENT (step 1 - Auto Video Loop 2)-----------------#
# Appelle read_selection.ps1 (Documents\Smode Files\Tools) dans un fil separe, renvoie le nom de l element
# affiche dans le panneau Parametres (un seul panneau non verrouille). Le layer correspondant est retrouve dans
# l arbre et doit etre un fichier video, sinon rien ne se passe. Les messages vont dans le parametre Status.

import subprocess, threading, json, ctypes, os

def _documentsFolder():
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(0, 5, 0, 0, buf)  # CSIDL_PERSONAL = dossier Documents reel
    return buf.value

READER_PATH = os.path.join(_documentsFolder(), "Smode Files", "Tools", "read_selection.ps1")

def readSelection(timeout=25):
    """Retourne {"ok": True, "name": ...} ou {"ok": False, "error": code, "message": ...}."""
    if not os.path.isfile(READER_PATH):
        return {"ok": False, "error": "reader_missing", "message": f"read_selection.ps1 introuvable. Copie-le dans : {READER_PATH}"}
    box = {}
    def work():
        try:
            p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", READER_PATH],
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,  # Smode n a pas de console : pas de handle herite
                               timeout=timeout, creationflags=0x08000000)  # sans fenetre
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
        return {"ok": False, "error": "timeout", "message": f"Lecture de la selection trop longue (> {timeout} s)."}
    if "exc" in box:
        return {"ok": False, "error": "read_failed", "message": box["exc"]}
    try:
        return json.loads(box["out"])
    except Exception:
        return {"ok": False, "error": "read_failed", "message": "Reponse illisible : " + (box.get("out") or box.get("err") or "vide")[:200]}


crossFade = script.Crossfade.get()
video = None   # resolu plus bas a partir de l element selectionne
videoIn = script.In.get()
videoOut = script.Out.get()
forceAlpha=script.AlphaCrossfade.get()
#exportLoop=script.ExportVideo.get()
#convertToProjectTimeBase = script.ConvertExportToCompoFps.get()
deleteInputVideo = script.ReplaceByLoop.get()

script.label = "Video Loop"
def findLayersByName(root, name):
    """Tous les layers (recursif) dont le nom affiche vaut `name`."""
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

warnings = []   # messages non bloquants, ajoutes au Status final

def setStatus(text):
    print(text)
    try:
        script.Status = text
    except Exception as e:
        print(f"Status parameter not updated: {e}")

selection = readSelection()
if not selection.get("ok"):
    setStatus("[" + selection.get("error", "?") + "] " + selection.get("message", ""))
else:
    selectedName = selection["name"]
    matches = findLayersByName(script.rootElement, selectedName)
    if len(matches) == 0:
        setStatus(f"[not_a_layer] '{selectedName}' is not a layer of this composition - nothing done.")
    elif len(matches) > 1:
        setStatus(f"[ambiguous_name] {len(matches)} layers are named '{selectedName}' - rename one of them.")
    elif matches[0].generator.getOilClassName() != 'VideoFileTextureGenerator':
        setStatus(f"[not_a_video] '{selectedName}' is not a video file - nothing done.")
    else:
        video = matches[0]
        setStatus(f"Looping '{selectedName}'...")

#-----------------------------IDENTIFY IF PROJECT OR STANDALONE COMPO-------------------------------------#
try:
    projectTimeBase=script.project.pipeline.parameters.timeBase
    projectP=script.project.pipeline.parameters.timeBase.p.get()
    projectQ=script.project.pipeline.parameters.timeBase.q.get()
    projectTimeBase=projectP/projectQ
    print (f"Project TimeBase : {str(projectTimeBase)[:5]}fps")
    isProject=True
except:
    isProject=False
    try:
        projectP=script.rootElement.mainAnimation.transport.timeBase.value.p.get()
        projectQ=script.rootElement.mainAnimation.transport.timeBase.value.q.get()
        projectTimeBase=projectP/projectQ
        print (f"Standalone compo timebase : {str(projectTimeBase)[:5]}fps")        
    except:
        print("Standalone Composition has no defined timebase, timeBase set to 50fps by default")
        projectP=50
        projectQ=1
        projectTimeBase=50.
    
#-- Set 'Out' value to video length if > length or = 0
try:
    if videoOut==0.0 or videoOut > video.generator.transport.length.get():
        videoOut=video.generator.transport.length.get()
        print(f"'Out' value not in range, set by default to video length : {str(video.generator.transport.length.get())[:5]} seconds")
        warnings.append(f"Out set to video length ({str(video.generator.transport.length.get())[:5]} s)")
except:
    pass
    
#------------------------------------ FIND WINDOWS PATH for FILE----------------------
def findPath(mediaPath, searchDirectory, maxDepth):
    mediaSmodeParts = Path(mediaPath).parts  
    for root, dirs, files in os.walk(searchDirectory):
        depth = root[len(searchDirectory):].count(os.sep)
        if depth > maxDepth:
            del dirs[:] 
            continue        
        if mediaSmodeParts[0] in dirs or mediaSmodeParts[0] in files:  # Early filtering with "root directory of smodePath"
            graal = Path(root) / mediaPath
            if graal.exists():
                return graal
    return None
    

#-------------------------------------CREATE LOOP COMPO AND TIMELINE-------------------------------------#
def createCompo(video):
    global loopLength
    
    label = video.getFriendlyName()
    length = video.generator.transport.length.get()
    timeBase = video.generator.transport.timeBase.value
    resolutionX = video.generator.resolution.width.get()
    resolutionY = video.generator.resolution.height.get()
    timeBaseP = video.generator.transport.timeBase.value.p.get()
    timeBaseQ = video.generator.transport.timeBase.value.q.get()
    codec=video.generator.streamer.video.information.codec
    colorSpace = video.generator.streamer.video.information.pixelFormat.colorSpace
    gammaValue=video.generator.gammaValue.value
    gam=" "
    if gammaValue==2.2:
        gam="sRGB"
    if gammaValue==1.0:
        gam="Linear"
    videoTimeBase=timeBaseP/timeBaseQ
    videoFramesRemainder = round(abs(length % 1)*videoTimeBase)
    projectFramesRemainder = round(videoFramesRemainder*projectTimeBase/videoTimeBase -0.5)
    videoInterval=videoOut-videoIn
   
    print(f"\n------VIDEO-INFO----------------")
    print(f"Label      : {label}")
    print(f"Length     : {str(length).split('.')[0]}sec {projectFramesRemainder}frames - ({str(length)[:5]}) ")
    print(f"Timebase   : {str(videoTimeBase)[:5]}fps - ({timeBase})")
    print(f"Resolution : {resolutionX}x{resolutionY}")
    print(f"Codec      : {codec} - ({colorSpace})")
    print(f"Gamma Value: {gammaValue} - {gam}")
    
    # Create and define timeline based on video length / time base / crossfade 
    timeline = Oil.createObject("TimelineCue") 
    if videoIn !=0.0 or videoOut != 0.0: 
        length=videoOut-videoIn
        print(f"Interval   : {str(videoInterval)[:5]} secondes")
    else:
        pass
    loopLength = length - crossFade - cropTime
    timeline.transport.length = length - crossFade - cropTime
    timeline.parameters.looping.set(True)
    timeline.parameters.launchMode.set(1)
    timeline.transport.timeBase.enabled = True
    timeline.transport.timeBase.value.p.set(timeBaseP)
    timeline.transport.timeBase.value.q.set(timeBaseQ)
    
    getattr(timeline.parameters, 'in').enabled = True
    getattr(timeline.parameters, 'in').value = cropTime
        
    # Create and define composition based on video resolution
    compo = Oil.createObject("TextureLayer")
    singleRenderer = Oil.createObject("SingleTextureRenderer")
    groupRenderer = Oil.createObject("GroupTextureRenderer")

    compoGen = Oil.createObject("Compo")
    compoGen.mainAnimation = timeline
    compoGen.rasterizer.resolution.preset.set(False)
    compoGen.rasterizer.resolution.width = resolutionX
    compoGen.rasterizer.resolution.height = resolutionY
    compoGen.rasterizer.quality.automatic = False
    compoGen.rasterizer.quality.gammaValue = gammaValue
    compo.generator = compoGen
    compoLabel=f"{label} LOOP {str(videoTimeBase)[:5]}fps"
    compo.label = compoLabel
    compo.colorLabel=video.colorLabel
    blendingMode =  ' '
    
    #-- If Main renderer is a Single Renderer
    if video.renderer.getOilClassName() == 'SingleTextureRenderer':
        blendingMode =  video.renderer.blendingMode
        print(f"Renderer   : Single Renderer - {blendingMode}")
        try:
            compo.renderer.target = video.renderer.target
        except AttributeError as e:
            print(f"Argument error: {e}")    
        compo.renderer.placement = video.renderer.placement.clone()
        compo.renderer.blendingMode = video.renderer.blendingMode

    #-- If Main renderer is a Group (multiple renderers)
    elif video.renderer.getOilClassName() == 'GroupTextureRenderer':
        print("Renderer   : Group Renderer")        
        groupRenderer.placement = video.renderer.placement.clone()
        compo.renderer = groupRenderer    
    
        #-- get childs of video Group Renderer values to reassign to compo
        print(f"-------------------------------")
        n = 0
        print(f"Renderers to copy:")
        for e in video.renderer.renderers:            
            print(f"{n}-{e.getFriendlyName()}")
            compo.renderer.renderers.append(e.clone())
            n = n + 1

    print(f"-------------------------------")
    
    #------------------ DELETE OLD COMPO LOOP IF EXIST !!!----------------------
    for e in video.parentElement.layers:
        if e.getFriendlyName() == compoLabel:
            print(f"\n{compoLabel} already exists - Replacing old compo !!!")
            warnings.append("previous loop replaced")
            video.parentElement.layers.remove(e)
    
    # Check if video framerate and project timebase divide each other to an integer
    if not (projectTimeBase % videoTimeBase == 0 or videoTimeBase % projectTimeBase == 0):
        print(f"\n------! FRAMERATE MISMATCH !------- \nYour project is in {str(projectTimeBase)[:5]}fps and your video is in {str(videoTimeBase)[:5]}fps")
        print(f"Attention my grosse louloute, Stuttering may Occur !!!")
        warnings.append(f"framerate mismatch (project {str(projectTimeBase)[:5]} fps / video {str(videoTimeBase)[:5]} fps), stuttering may occur")

    # ------------------------CREATE COMPO LOOP !!! (finally)-------------------

    for i in range(0,len(video.parentElement.layers)):
        if video.parentElement.layers[i].getFriendlyName()==label:
            n=i+1
            break
    video.parentElement.layers.insert(n,compo)
    
   
    # Clone (to avoid UID conflict) source video into composition
    compo.generator.layers.append(video.clone())
    compo.generator.layers.append(video.clone()) 
    
    # Duplicate source video into composition with label and full Renderer
    for n, layer in enumerate(compoGen.layers, start=1):
        layer.label = f"{label}_{n}"    
    video1 = compo.generator.layers[f"{label}_1"]
    video2 = compo.generator.layers[f"{label}_2"]   
    video1.renderer=Oil.createObject("SingleTextureRenderer")
    video2.renderer=Oil.createObject("SingleTextureRenderer")
    video1.generator.transport.player=None
    video2.generator.transport.player=None
    video1.generator.frameBlending.set(False)
    video2.generator.frameBlending.set(False)
    
    blockLength = length - crossFade
    videoInterval = videoOut-videoIn-crossFade
    
    # Create and configure block1 - Single block of first row
    timeline.transport.position.set(0)        
    track, block1 = timeline.createBlock(video1)
    block1.footage.position.automateTransport = True
    
    # Create and configure block2 - First block of second row
    track, block2 = timeline.createBlock(video2)
    block2.footage.position.automateTransport = True
    block2.footage.intensity.fadeOut.enabled = True 
    
    # Create and configure block22 that is here only to already load the video in the beginning of the next loop
    timeline.transport.position.set(crossFade+cropTime)
    track, block22 = timeline.createBlock(video2)
    block22.footage.position.automateTransport = True 
    block22.position=crossFade+cropTime+0.00001
    block22.footage.intensity.maximum=0.

    # Rules for In and Out values
    if videoIn !=0.0:   
        block1.footage.position.automateTransport = True
        getattr(block1.footage.position, 'in').value = videoIn
        getattr(block2.footage.position, 'in').value = videoOut-crossFade-cropTime
        getattr(block2.footage.position, 'out').value = videoOut
        getattr(block22.footage.position, 'in').value = videoOut-videoInterval+cropTime
        getattr(block22.footage.position, 'out').value = videoOut-crossFade
    else:
        block2.length.set(crossFade)
        getattr(block2.footage.position, 'in').value = blockLength-cropTime
        getattr(block2.footage.position, 'out').value = length    
        getattr(block22.footage.position, 'in').value = crossFade+cropTime
        getattr(block22.footage.position, 'out').value = length-crossFade  
            
    if videoOut != 0.0:
        block1.footage.position.automateTransport = True
        getattr(block1.footage.position, 'out').value = videoOut-crossFade
    
    # Check alpha with codec name (only for Hap Alpha) as notch LC or Prores 4444 are encoded in rgba colorSpace by default
    if "alpha" in str(codec).casefold() or forceAlpha==True :
        block1.footage.intensity.fadeIn.enabled = True 
        block1.footage.intensity.fadeIn.value.length = crossFade*0.5
        block2.footage.intensity.fadeOut.value.length = crossFade*0.5        
        print(f"Video with Alpha, crossfade set to {str(crossFade*.5)[:5]} seconds on each block to avoid transparent crossfade")
    else:
        block2.footage.intensity.fadeOut.value.length = crossFade   
        
    #-- Delete source video from the element tree if 'Replace Video by Loop Compo' checked in parameters editor
    if deleteInputVideo:
        video.parentElement.layers.remove(video)
    
    video.activation.set(0)
    timeline.transport.play.trig()
    
    return loopLength
    
#-------------------------------------VIDEO EXPORT (beta)-------------------------------------#

def exportVideoLoopCompo(video, loopLength):
    global looplength
    
    print("-")
    #-- Delete previous task to configure parameters of task [1] after it is append()
    for i in range(1,len(engine.tasks.group.tasks)):
        engine.tasks.group.tasks[i].state.set(2)
    
    #-- Define export path (by default in the same folder as the standalone composition)
    compo=script.rootElement
    compoLabel = f"{video.getFriendlyName()}_Loop"
    
    depthLimit=3
    mediaPath = str(video.generator.file.path)
    fileName = Path(mediaPath).name
    
    for drive in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        rootPath = f"{drive}:/"
        if Path(rootPath).exists():
            fullPath = findPath(mediaPath, rootPath, maxDepth=depthLimit)
            if fullPath:
                #print(f"Full path : {fullPath}")
                break
    else:
        fullPath= compo.document.nativeFile.get()
        print(f"Error: depth limit ({depthLimit}) should be increased, export folder set to Compo Folder")
     
    videoFolderPath=str(fullPath).replace(fileName,"Exported_Loops")
    
    #-- Create tasks and task settings
    exportTask = Oil.createObject("CompoVideoExportTask")
    exportSettings=Oil.createObject("VideoExportUserSettings")
    
    #-- setup export settings like you would in video export windows to adjust to loop length
    exportSettings.fileExporter.videoExporter.resolution.height=compo.rasterizer.resolution.height
    exportSettings.fileExporter.videoExporter.resolution.width =compo.rasterizer.resolution.width
    exportSettings.outputDirectory.set(videoFolderPath)
    exportSettings.end.set(loopLength)
    print(f"\nExporting {exportSettings.fileName} in : ")
    print(f"{exportSettings.outputDirectory}\n-length      : {exportSettings.end}")
    
    #-- Configure export timebase based on COMPO
    if convertToProjectTimeBase == True :
        P=compo.mainAnimation.transport.timeBase.value.p
        Q=compo.mainAnimation.transport.timeBase.value.q
        T=P.get()/Q.get()
        exportSettings.timeBase.p=P
        exportSettings.timeBase.q=Q
        exportFps=f"{str(T)[:5]} fps (Compo Timebase)"
    #-- Configure export timebase based on VIDEO
    elif convertToProjectTimeBase == False :
        P=video.generator.transport.timeBase.value.p
        Q=video.generator.transport.timeBase.value.q
        T=P.get()/Q.get()
        exportSettings.timeBase.p=P
        exportSettings.timeBase.q=Q
        exportFps=f"{str(T)[:5]} fps (Video Timebase)"
    exportTask.name = f"{compoLabel}_{str(T)[:5]}fps" 
    exportSettings.fileName=f"{compoLabel}_{str(T)[:5]}fps" 
    
    print(f"-resolution  : {exportSettings.fileExporter.videoExporter.resolution}")
    print(f"-exported at : {exportFps} ")
    
    #-- Assign settings to tasks and duplicate composition in another thread before ewport
    exportTask.parameters.settings = exportSettings
    exportTask.parameters.documentToClone.set(compo.document)
    
    #-- Append task into some wizardry that seem to improve video export success !!???
    n=0
    while n < 1:   
        engine.tasks.group.tasks.append(exportTask)
        engine.tasks.group.paused=True
        engine.tasks.group.tasks[1].paused=True
        engine.tasks.group.tasks[1].paused=False
        engine.tasks.group.paused=False
        n=n+1
#-------------------------------------MAIN PROCESS-------------------------------------#
    
#-- launch script main function if video is linked in parameters and crossfade stands in acceptable values
if video and video.generator.getOilClassName() == 'VideoFileTextureGenerator':
    #-- Set cropTime to 1 frame to avoid Smode Shite
    timeBaseP = video.generator.transport.timeBase.value.p.get()
    timeBaseQ = video.generator.transport.timeBase.value.q.get()
    videoInterval=videoOut-videoIn
    cropTime = 1./timeBaseP*timeBaseQ

    #-- Get video lenght to prevent out of range crossfade     
    max_val = float(1.)
    crossFadeK = float(crossFade)
    lengthV = float(video.generator.transport.length.get())
    lengthK = float(video.generator.transport.length.get()) * .5 -cropTime
    if videoIn!=0.0 or videoOut!=0.0:
        lengthK=videoInterval*0.5 -cropTime
        lengthV=videoInterval
    videoTimeBase=timeBaseP/timeBaseQ
    videoFramesRemainder = round(abs(lengthK % 1)*videoTimeBase )
    projectFramesRemainder = round(videoFramesRemainder*projectTimeBase/videoTimeBase ) -1
    defaultFramesRemainder = round(videoFramesRemainder*50./videoTimeBase -cropTime) -1
    
    if videoIn > videoOut :
            print ("\n-----------!!IN and OUT ERROR!!-----------")
            print (f"  IN ({str(videoIn)[:4]}sec) is superior to OUT ({str(videoOut)[:5]}sec) \n ")
            warnings.append(f"IN ({str(videoIn)[:4]} s) is superior to OUT ({str(videoOut)[:5]} s)")
    
    if crossFade > lengthK :
        print("\n------------!!CROSSFADE ERROR!!-----------")
        print(f"            Video loop length : {str(lengthV)[:5]}")
        print(f"          Crossfade is set to : {str(crossFade)[:5]}")
        print(f"Crossfade must be inferior to : {str(lengthK)[:5]}")
        print(f"{"-"*42}")
        if isProject == True:
            print(f"At your project Timebase ({str(projectTimeBase)[:5]} fps) ~ {str(lengthK).split('.')[0]} sec | {projectFramesRemainder} frames")
        if isProject == False:
            print(f" At default timebase (50 fps) ~ {str(lengthK).split('.')[0]} sec | {defaultFramesRemainder} frames")    
        setStatus(f"[crossfade_error] Crossfade ({str(crossFade)[:5]} s) must be inferior to {str(lengthK)[:5]} s (video loop length {str(lengthV)[:5]} s) - nothing done.")
    else:
        createCompo(video)
        setStatus(f"Loop created for '{selectedName}'" + (" | " + " | ".join(warnings) if warnings else ""))

elif selection.get("ok") and video is None:
    pass   # deja explique dans Status (not_a_layer / ambiguous_name / not_a_video)