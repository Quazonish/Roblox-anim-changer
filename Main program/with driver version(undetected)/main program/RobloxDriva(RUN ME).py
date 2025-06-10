print('Loading libs...')
from ctypes import (
    Structure, c_void_p, c_size_t, byref, sizeof, create_string_buffer,
    windll, addressof, c_wchar_p, c_ulong, WinError, c_wchar
)
from ctypes.wintypes import HANDLE, DWORD, BOOL, LPCVOID, LPVOID
from struct import unpack_from, pack
from time import time, sleep
from threading import Thread
from gui import Ui_MainWindow
from PyQt5.QtWidgets import QApplication, QMainWindow
#from keyboard import on_release
from requests import get
from re import findall
class Requests(Structure):
    _fields_ = [
        ("process_id", HANDLE),
        ("target", c_void_p),
        ("buffer", c_void_p),
        ("size", c_size_t),
        ("return_size", c_size_t),
    ]

FILE_DEVICE_UNKNOWN = 0x22
FILE_SPECIAL_ACCESS = 0
METHOD_BUFFERED = 0

def CTL_CODE(DeviceType, Function, Method, Access):
    return (DeviceType << 16) | (Access << 14) | (Function << 2) | Method

attach_code = CTL_CODE(FILE_DEVICE_UNKNOWN, 0x696, METHOD_BUFFERED, FILE_SPECIAL_ACCESS)
read_code = CTL_CODE(FILE_DEVICE_UNKNOWN, 0x697, METHOD_BUFFERED, FILE_SPECIAL_ACCESS)
write_code = CTL_CODE(FILE_DEVICE_UNKNOWN, 0x698, METHOD_BUFFERED, FILE_SPECIAL_ACCESS)

kernel32 = windll.kernel32
CreateFileW = kernel32.CreateFileW
DeviceIoControl = kernel32.DeviceIoControl
CloseHandle = kernel32.CloseHandle

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80

device_handle = None
current_pid = None

def open_device():
    global device_handle
    if device_handle:
        return device_handle
    handle = CreateFileW(
        "\\\\.\\RobloxDriva",
        GENERIC_READ | GENERIC_WRITE,
        0,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None
    )
    if handle == HANDLE(-1).value:
        raise WinError()
    device_handle = handle
    return handle

def openProcess(pid: int) -> None:
    global current_pid
    handle = open_device()
    req = Requests()
    req.process_id = HANDLE(pid)
    current_pid = pid
    res, _ = ioctl(handle, attach_code, req)
    if res.return_size != 0:
        raise RuntimeError(f"Attach failed with code {res.return_size}")

def read(address: int, size: int) -> bytes:
    if device_handle is None or current_pid is None:
        raise RuntimeError("Process not opened. Call openProcess(pid) first.")
    read_buf = create_string_buffer(size)
    req = Requests()
    req.process_id = HANDLE(current_pid)
    req.target = c_void_p(address)
    req.buffer = c_void_p(addressof(read_buf))
    req.size = size
    req.return_size = 0
    res, _ = ioctl(device_handle, read_code, req)
    if res.return_size == 0:
        return b""
    return read_buf.raw[:res.return_size]

def write(address: int, data: bytes) -> int:
    if device_handle is None or current_pid is None:
        raise RuntimeError("Process not opened. Call openProcess(pid) first.")
    size = len(data)
    write_buf = create_string_buffer(data, size)
    req = Requests()
    req.process_id = HANDLE(current_pid)
    req.target = c_void_p(address)
    req.buffer = c_void_p(addressof(write_buf))
    req.size = size
    req.return_size = 0
    res, _ = ioctl(device_handle, write_code, req)
    return res.return_size

def ioctl(handle, control_code, request):
    in_buffer = byref(request)
    in_buffer_size = sizeof(request)
    out_buffer = Requests()
    out_buffer_size = sizeof(out_buffer)
    bytes_returned = DWORD(0)

    res = DeviceIoControl(
        handle,
        control_code,
        in_buffer,
        in_buffer_size,
        byref(out_buffer),
        out_buffer_size,
        byref(bytes_returned),
        None
    )
    if res == 0:
        raise WinError()
    return out_buffer, bytes_returned.value

def close():
    global device_handle
    if device_handle:
        CloseHandle(device_handle)
        device_handle = None

class PROCESSENTRY32(Structure):
    _fields_ = [
        ("dwSize", DWORD),
        ("cntUsage", DWORD),
        ("th32ProcessID", DWORD),
        ("th32DefaultHeapID", c_void_p),
        ("th32ModuleID", DWORD),
        ("cntThreads", DWORD),
        ("th32ParentProcessID", DWORD),
        ("pcPriClassBase", c_ulong),
        ("dwFlags", DWORD),
        ("szExeFile", c_wchar * 260),
    ]

def get_pid_by_name(process_name: str) -> int | None:
    kernel32 = windll.kernel32
    TH32CS_SNAPPROCESS = 0x00000002

    CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
    Process32FirstW = kernel32.Process32FirstW
    Process32NextW = kernel32.Process32NextW
    CloseHandle = kernel32.CloseHandle

    snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == HANDLE(-1).value:
        raise WinError()

    entry = PROCESSENTRY32()
    entry.dwSize = sizeof(PROCESSENTRY32)

    found_pid = None
    success = Process32FirstW(snapshot, byref(entry))
    while success:
        if entry.szExeFile.lower() == process_name.lower():
            found_pid = entry.th32ProcessID
            break
        success = Process32NextW(snapshot, byref(entry))

    CloseHandle(snapshot)
    return found_pid

class MODULEENTRY32(Structure):
    _fields_ = [
        ('dwSize', DWORD),
        ('th32ModuleID', DWORD),
        ('th32ProcessID', DWORD),
        ('GlblcntUsage', DWORD),
        ('ProccntUsage', DWORD),
        ('modBaseAddr', c_void_p),
        ('modBaseSize', DWORD),
        ('hModule', HANDLE),
        ('szModule', c_wchar * 256),
        ('szExePath', c_wchar * 260),  
    ]

def get_module_base(pid: int) -> int | None:
    kernel32 = windll.kernel32
    TH32CS_SNAPMODULE = 0x00000008
    TH32CS_SNAPMODULE32 = 0x00000010

    CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
    Module32FirstW = kernel32.Module32FirstW
    Module32NextW = kernel32.Module32NextW
    CloseHandle = kernel32.CloseHandle

    snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snapshot == HANDLE(-1).value:
        raise WinError()

    module_entry = MODULEENTRY32()
    module_entry.dwSize = sizeof(MODULEENTRY32)

    success = Module32FirstW(snapshot, byref(module_entry))
    if not success:
        CloseHandle(snapshot)
        return None

    base_addr = module_entry.modBaseAddr

    CloseHandle(snapshot)
    return base_addr
def read_int8(address: int) -> int:
    return unpack_from("<Q", read(address, 8))[0]

def write_int8(address: int, value: int) -> int:
    return write(address, pack("<Q", value & 0xFF))

def read_int4(address: int) -> int:
    return int.from_bytes(read(address, 4), "little")

def write_int4(address: int, value: int) -> int:
    return write(address, value.to_bytes(4, 'little'))

def read_float(address: int) -> float:
    return unpack_from("<f", read(address, 4))[0]

def write_float(address: int, value: float) -> int:
    return write(address, pack("<f", value))

def h2d(hz: str, bit: int = 16) -> int:
    if type(hz) == int:
        return hz
    return int(hz, bit)

def DRP(Address: int, is64Bit: bool = None) -> int:
    Address = Address
    if type(Address) == str:
        Address = self.h2d(Address)
    return read_int8(Address)

def readString(address: int, length: int, encoding: str = "utf-8") -> str:
    data = read(address, length)
    return data.split(b"\x00", 1)[0].decode(encoding, errors="ignore")

def writeString(address: int, string: str, encoding: str = "utf-8"):
    write(address, string.encode(encoding, errors="ignore") + b'\x00')

def ReadRobloxString(ExpectedAddress: int) -> str:
    StringCount = read_int4(ExpectedAddress + 0x10)
    if StringCount > 15:
        shit = DRP(ExpectedAddress)
        return readString(shit, StringCount)
    return readString(ExpectedAddress, StringCount)

def WriteRobloxString(ExpectedAddress: int, string: str): #Works only for long strings
    shit = DRP(ExpectedAddress)
    writeString(shit, str(string))
    write_int4(ExpectedAddress + 0x10, int(len(string)))

def GetClassName(Instance: int) -> str:
    ptr = read_int8(Instance + 0x18)
    ptr = read_int8(ptr + 0x8)
    fl = read_int8(ptr + 0x18)
    if fl == 0x1F:
        ptr = read_int8(ptr)
    return ReadRobloxString(ptr)

def GetNameAddress(Instance):
    ExpectedAddress = DRP(Instance + nameOffset, True)
    return ExpectedAddress

def GetName(Instance: int) -> str:
    ExpectedAddress = GetNameAddress(Instance)
    return ReadRobloxString(ExpectedAddress)

def GetChildren(Instance: int) -> str:
    ChildrenInstance = []
    InstanceAddress = Instance
    if not InstanceAddress:
        return False
    
    ChildrenStart = DRP(InstanceAddress + childrenOffset, True)
    if ChildrenStart == 0:
        return []
    ChildrenEnd = DRP(ChildrenStart + 8, True)
    OffsetAddressPerChild = 0x10
    CurrentChildAddress = DRP(ChildrenStart, True)
    for i in range(0, 9000):
        if CurrentChildAddress == ChildrenEnd:
            break
        ChildrenInstance.append(read_int8(CurrentChildAddress))
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

class MyApp(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

dataModel, wsAddr, camAddr, anims = [0] * 4

def init():
    global dataModel, wsAddr, camAddr
    pid = get_pid_by_name("RobloxPlayerBeta.exe")
    print(pid)
    openProcess(pid)
    baseAddr = get_module_base(pid)
    print(baseAddr)
    
    fakeDatamodel = read_int8(baseAddr + int(offsets['FakeDataModelPointer'], 16))
    print(f'Fake datamodel: {fakeDatamodel:x}')
    
    dataModel = read_int8(fakeDatamodel + int(offsets['FakeDataModelToDataModel'], 16))
    print(f'Real datamodel: {dataModel:x}')
    
    wsAddr = read_int8(dataModel + int(offsets['Workspace'], 16)) #FindFirstChildOfClass(dataModel, 'Workspace')
    print(f'Workspace: {wsAddr:x}')
    
    camAddr = read_int8(wsAddr + int(offsets['Camera'], 16)) #FindFirstChildOfClass(wsAddr, 'Camera')
    print(f'Camera: {camAddr:x}')
    
    print('Injected successfully\n-------------------------------')

def setNewAnims():
    global anims
    hum = read_int8(camAddr + int(offsets['CameraSubject'], 16))
    print(f'Humanoid: {hum:x}')
    char = read_int8(hum + int(offsets['Parent'], 16))
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
            ok = getAnim(animType)
            print(f'expAddr: {ok:x}')
            WriteRobloxString(ok+int(offsets['AnimationId'], 16), 'http://www.roblox.com/asset/?id='+trueAnim)
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

print('Loaded libs and stuff! Getting offsets...')
offsets = get('https://offsets.ntgetwritewatch.workers.dev/offsets.json').json()
print('Supported versions:')
print(offsets['RobloxVersion'])
print(offsets['ByfronVersion'])
print('Current latest roblox version:', get('https://weao.xyz/api/versions/current', headers={'User-Agent': 'WEAO-3PService'}).json()['Windows'])
print('Got some offsets! Init...')
nameOffset = int(offsets['Name'], 16)
childrenOffset = int(offsets['Children'], 16)

#on_release(reEnableEspKeyBind)

print('Inited! Creating GUI...')

app = QApplication([])
window = MyApp()
window.INJECT.clicked.connect(init)
window.SetPack.clicked.connect(applyAnimPack)
window.SetAnyAnim.clicked.connect(applyAnyAnim)
window.show()

app.exec_()
