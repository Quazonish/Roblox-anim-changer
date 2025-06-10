print('Loading libs...')
from pymem import Pymem
from pymem.process import is_64_bit, list_processes
from ctypes import windll
from psutil import pid_exists
from time import time, sleep
from threading import Thread
from requests import get
from re import findall
from gui import Ui_MainWindow
from PyQt5.QtWidgets import QApplication, QMainWindow
print('Loaded libs! Getting offsets...')
offsets = get('https://offsets.ntgetwritewatch.workers.dev/offsets.json').json()
print('Supported versions:')
print(offsets['RobloxVersion'])
print(offsets['ByfronVersion'])
print('Current latest roblox version:', get('https://weao.xyz/api/versions/current', headers={'User-Agent': 'WEAO-3PService'}).json()['Windows'])
print('Got some offsets! Init...')
baseAddr = 0

class MyApp(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

class hyper:
    def __init__(self, ProgramName=None):
        self.ProgramName = ProgramName
        self.Pymem = Pymem()
        self.Addresses = {}
        self.Handle = None
        self.is64bit = False
        self.ProcessID = -1
        self.PID = self.ProcessID
        access_rights = 0x1038
        if type(ProgramName) == str:
            self.Pymem = Pymem(ProgramName)
            self.Handle = windll.kernel32.OpenProcess(access_rights, False, self.Pymem.process_id)
            self.is64bit = not is_64_bit(self.Handle)
            self.ProcessID = self.Pymem.process_id
            self.PID = self.ProcessID
        elif type(ProgramName) == int:
            self.Pymem.open_process_from_id(ProgramName)
            self.Handle = windll.kernel32.OpenProcess(access_rights, False, ProgramName)
            self.is64bit = not is_64_bit(self.Handle)
            self.ProcessID = self.Pymem.process_id
            self.PID = self.ProcessID

    def h2d(self, hz: str, bit: int = 16) -> int:
        if type(hz) == int:
            return hz
        return int(hz, bit)

    def DRP(self, Address: int, is64Bit: bool = None) -> int:
        Address = Address
        if type(Address) == str:
            Address = self.h2d(Address)
        return int.from_bytes(self.Pymem.read_bytes(Address, 8), "little")

    def getRawProcesses(self):
        toreturn = []
        for i in list_processes():
            toreturn.append(
                [
                    i.cntThreads,
                    i.cntUsage,
                    i.dwFlags,
                    i.dwSize,
                    i.pcPriClassBase,
                    i.szExeFile,
                    i.th32DefaultHeapID,
                    i.th32ModuleID,
                    i.th32ParentProcessID,
                    i.th32ProcessID,
                ]
            )
        return toreturn

    def SimpleGetProcesses(self):
        toreturn = []
        for i in self.getRawProcesses():
            toreturn.append({"Name": i[5].decode(), "Threads": i[0], "ProcessId": i[9]})
        return toreturn

    def YieldForProgram(self, programName):
        global baseAddr
        ProcessesList = self.SimpleGetProcesses()
        for i in ProcessesList:
            if i["Name"] == programName:
                self.Pymem.open_process_from_id(i["ProcessId"])
                self.ProgramName = programName
                access_rights = 0x1038
                self.Handle = windll.kernel32.OpenProcess(access_rights, False, i["ProcessId"])
                self.is64bit = not is_64_bit(self.Handle)
                self.ProcessID = self.Pymem.process_id
                self.PID = self.ProcessID
                print('Roblox PID:', self.ProcessID)
                for module in hyper.Pymem.list_modules():
                    if module.name == "RobloxPlayerBeta.exe":
                        baseAddr = module.lpBaseOfDll
                print(f'Roblox base addr: {baseAddr:x}')
                return True
        return False

    def isProcessDead(self):
        return not pid_exists(self.ProcessID)

hyper = hyper()
nameOffset = int(offsets['Name'], 16)
childrenOffset = int(offsets['Children'], 16)
hyper.YieldForProgram("RobloxPlayerBeta.exe")
def reOpenRoblox():
    while True:
        if hyper.isProcessDead():
            try:
                while not hyper.YieldForProgram("RobloxPlayerBeta.exe"):
                    pass
            except:
                pass
        sleep(0.1)
Thread(target=reOpenRoblox, daemon=True).start()

def ReadRobloxString(ExpectedAddress: int) -> str:
    StringCount = hyper.Pymem.read_int(ExpectedAddress + 0x10)
    if StringCount > 15:
        shit = hyper.DRP(ExpectedAddress)
        return hyper.Pymem.read_string(shit, StringCount)
    return hyper.Pymem.read_string(ExpectedAddress, StringCount)

def WriteRobloxString(ExpectedAddress: int, string: str): #Only for long
    shit = hyper.DRP(ExpectedAddress)
    hyper.Pymem.write_string(shit, str(string))
    hyper.Pymem.write_int(ExpectedAddress + 0x10, int(len(string)))

def GetClassName(Instance: int) -> str:
    ptr = hyper.Pymem.read_longlong(Instance + 0x18)
    ptr = hyper.Pymem.read_longlong(ptr + 0x8)
    fl = hyper.Pymem.read_longlong(ptr + 0x18)
    if fl == 0x1F:
        ptr = hyper.Pymem.read_longlong(ptr)
    return ReadRobloxString(ptr)

def GetNameAddress(Instance):
    ExpectedAddress = hyper.DRP(Instance + nameOffset, True)
    return ExpectedAddress

def GetName(Instance: int) -> str:
    ExpectedAddress = GetNameAddress(Instance)
    return ReadRobloxString(ExpectedAddress)

def GetChildren(Instance: int) -> str:
    ChildrenInstance = []
    InstanceAddress = Instance
    if not InstanceAddress:
        return False
    ChildrenStart = hyper.DRP(InstanceAddress + childrenOffset, True)
    if ChildrenStart == 0:
        return []
    ChildrenEnd = hyper.DRP(ChildrenStart + 8, True)
    OffsetAddressPerChild = 0x10
    CurrentChildAddress = hyper.DRP(ChildrenStart, True)
    for i in range(0, 9000):
        if CurrentChildAddress == ChildrenEnd:
            break
        ChildrenInstance.append(hyper.Pymem.read_longlong(CurrentChildAddress))
        CurrentChildAddress += OffsetAddressPerChild
    return ChildrenInstance

def FindFirstChild(Instance: int, ChildName: str) -> int:
    ChildrenOfInstance = GetChildren(Instance)
    for i in ChildrenOfInstance:
        if GetName(i) == ChildName:
            return i

def FindFirstChildOfClass(Instance: int, ClassName: str) -> int:
    ChildrenOfInstance = GetChildren(Instance)
    for i in ChildrenOfInstance:
        try:
            if GetClassName(i) == ClassName:
                return i
        except:
            pass

dataModel, wsAddr, camAddr, anims = [0] * 4

def init():
    global dataModel, wsAddr, camAddr
    visEngine = hyper.Pymem.read_longlong(baseAddr + int(offsets['VisualEnginePointer'], 16))
    print(f'Visual engine: {visEngine:x}')
    
    fakeDatamodel = hyper.Pymem.read_longlong(visEngine + int(offsets['VisualEngineToDataModel1'], 16))
    print(f'Fake datamodel: {fakeDatamodel:x}')
    
    dataModel = hyper.Pymem.read_longlong(fakeDatamodel + int(offsets['VisualEngineToDataModel2'], 16))
    print(f'Real datamodel: {dataModel:x}')
    
    wsAddr = hyper.Pymem.read_longlong(dataModel + int(offsets['Workspace'], 16)) #FindFirstChildOfClass(dataModel, 'Workspace')
    print(f'Workspace: {wsAddr:x}')
    
    camAddr = hyper.Pymem.read_longlong(wsAddr + int(offsets['Camera'], 16)) #FindFirstChildOfClass(wsAddr, 'Camera')
    print(f'Camera: {camAddr:x}')
    
    print('Injected successfully\n-------------------------------')

def setNewAnims():
    global anims
    hum = hyper.Pymem.read_longlong(camAddr + int(offsets['CameraSubject'], 16))
    print(f'Humanoid: {hum:x}')
    char = hyper.Pymem.read_longlong(hum + int(offsets['Parent'], 16))
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

def applyAnimPack():
    animPackId = window.AnimPackId.text()
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
            WriteRobloxString(getAnim(animType)+int(offsets['AnimationId'], 16), 'http://www.roblox.com/asset/?id='+trueAnim)
            print('Applied\n-------------------------------------------')
    print('COMPLETE!')

def applyAnyAnim():
    setNewAnims()
    if window.Loop.isChecked():
        for i in GetChildren(FindFirstChild(anims, 'dance')):
            WriteRobloxString(i+int(offsets['AnimationId'], 16), 'http://www.roblox.com/asset/?id='+window.AnyAnimId.text())
        print('Applied! Chat /e dance to activate it. Jump/walk to disable it')
    else:
        WriteRobloxString(getAnim('wave')+int(offsets['AnimationId'], 16), 'http://www.roblox.com/asset/?id='+window.AnyAnimId.text())
        print('Applied! Chat /e wave to activate it')

print('Inited! Creating GUI...')

app = QApplication([])
window = MyApp()
window.INJECT.clicked.connect(init)
window.SetPack.clicked.connect(applyAnimPack)
window.SetAnyAnim.clicked.connect(applyAnyAnim)
window.show()

app.exec_()
