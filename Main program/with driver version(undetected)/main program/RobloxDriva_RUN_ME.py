print('Loading libs...')
from rbxMemory import *
from imgui_bundle import imgui, immapp, hello_imgui
from time import time, sleep
from threading import Thread
from requests import get
from re import findall

loopAnim = False
animPackId, animId = [''] * 2

dataModel, wsAddr, camAddr, anims = [0] * 4

def init():
    global dataModel, wsAddr, camAddr
    pid = get_pid_by_name("RobloxPlayerBeta.exe")
    if pid is None:
        print('You forgot to open roblox!')
        return
    setPid(pid)

    baseAddr = find_image_base() #get_module_base(pid)
    
    fakeDatamodel = read_int8(baseAddr + offsets['FakeDataModelPointer'])
    print(f'Fake datamodel: {fakeDatamodel:x}')
    
    dataModel = read_int8(fakeDatamodel + offsets['FakeDataModelToDataModel'])
    print(f'Real datamodel: {dataModel:x}')
    
    wsAddr = read_int8(dataModel + offsets['Workspace']) #FindFirstChildOfClass(dataModel, 'Workspace')
    print(f'Workspace: {wsAddr:x}')
    
    camAddr = read_int8(wsAddr + offsets['Camera']) #FindFirstChildOfClass(wsAddr, 'Camera')
    print(f'Camera: {camAddr:x}')
    
    print('Injected successfully\n-------------------------------')

def setNewAnims():
    global anims
    hum = read_int8(camAddr + offsets['CameraSubject'])
    print(f'Humanoid: {hum:x}')
    char = read_int8(hum + offsets['Parent'])
    print(f'Character: {char:x}')
    anims = FindFirstChild(char, 'Animate')
    print(f'Animate script: {anims:x}')

def getAnim(animName):
    animVal = FindFirstChild(anims, animName)
    print(f'Anim value: {animVal:x}')
    anim = FindFirstChildOfClass(animVal, 'Animation')
    print(f'Anim: {anim:x}')
    return anim

animTypes = ['run', 'walk', 'swim', 'idle', 'jump', 'fall', 'climb']
def getAnimNameFromName(name):
    name = name.lower()
    for animType in animTypes:
        if animType in name:
            return animType

def getTrueAnim(animRbmx):
    trueAnim = findall(r"http://www\.roblox\.com/asset/\?id=(\d+)\D", animRbmx)
    if len(trueAnim) > 0:
        return trueAnim[0]
    else:
        trueAnim = findall(r"rbxassetid://(\d+)\D", animRbmx)
        return trueAnim[0]

def setAnimPack():
    setNewAnims()
    animPackInfo = get('https://catalog.roblox.com/v1/bundles/details?bundleIds='+animPackId).json()[0]
    print('Animation pack name:', animPackInfo['name'])
    for anim in animPackInfo['items']:
        if anim['type'] == 'Asset':
            print('Animation name:', anim['name'])
            print('Animation id:', anim['id'])
            animRbmx = get('https://assetdelivery.roblox.com/v1/asset?id='+str(anim['id'])).text
            animType = getAnimNameFromName(animRbmx)
            print('Its', animType, 'animation')
            trueAnim = getTrueAnim(animRbmx)
            print('True anim id:', trueAnim)
            ok = getAnim(animType)
            print(f'expAddr: {ok:x}')
            WriteRobloxString(ok+offsets['AnimationId'], 'http://www.roblox.com/asset/?id='+trueAnim)
            print('Applied\n-------------------------------------------')
    print('COMPLETE!')

def setAnim():
    setNewAnims()
    if loopAnim:
        for i in GetChildren(FindFirstChild(anims, 'dance')):
            WriteRobloxString(i+offsets['AnimationId'], 'http://www.roblox.com/asset/?id='+animId)
        print('Applied! Chat /e dance to activate it. Jump/walk to disable it')
    else:
        WriteRobloxString(getAnim('wave')+offsets['AnimationId'], 'http://www.roblox.com/asset/?id='+animId)
        print('Applied! Chat /e wave to activate it')

print('Loaded libs and stuff! Getting offsets...')
offsets = get('https://offsets.ntgetwritewatch.workers.dev/offsets.json').json()

print('Converting strings to ints...')
for key, val in offsets.items():
    try:
        offsets[key] = int(val, 16)
    except ValueError:
        pass

print('Got some offsets! Init...')
setOffsets(offsets['Name'], offsets['Children'])

print('Inited! Creating GUI...')

def render_ui():
    global loopAnim, animPackId, animId

    if imgui.button("Inject"):
        init()

    _, animPackId = imgui.input_text("Anim pack ID##animPackId", animPackId, 1)
    _, animId = imgui.input_text("Animation ID##animId", animId, 1)

    if imgui.button("Set anim pack"):
        setAnimPack()
    imgui.same_line()

    if imgui.button("Set animation"):
        setAnim()
    imgui.same_line()

    _, loopAnim = imgui.checkbox("Loop", loopAnim)

open_device()

immapp.run(
    gui_function=render_ui,
    window_title="Roblox anim changer",
    window_size_auto=True,
    with_markdown=True,
    fps_idle=10
)
