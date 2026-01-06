from ctypes import (
    Structure, c_void_p, c_ulonglong, c_int, c_bool,
    byref, sizeof, windll, create_string_buffer, addressof, POINTER,
    pointer, c_ulong, c_wchar
)
from ctypes.wintypes import HANDLE, DWORD
from struct import unpack_from, pack
from psutil import Process, HIGH_PRIORITY_CLASS
from os import getpid
Process(getpid()).nice(HIGH_PRIORITY_CLASS)

FILE_DEVICE_UNKNOWN = 0x22
METHOD_BUFFERED = 0
FILE_SPECIAL_ACCESS = 0

def CTL_CODE(DeviceType, Function, Method, Access):
    return (DeviceType << 16) | (Access << 14) | (Function << 2) | Method

code_rw = CTL_CODE(FILE_DEVICE_UNKNOWN, 0x1645, METHOD_BUFFERED, FILE_SPECIAL_ACCESS)
code_ba = CTL_CODE(FILE_DEVICE_UNKNOWN, 0x1646, METHOD_BUFFERED, FILE_SPECIAL_ACCESS)
code_get_guarded_region = CTL_CODE(FILE_DEVICE_UNKNOWN, 0x1647, METHOD_BUFFERED, FILE_SPECIAL_ACCESS)
code_security = 0x85b3b69

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

class RW(Structure):
    _fields_ = [
        ("security", c_int),
        ("process_id", c_int),
        ("address", c_ulonglong),
        ("buffer", c_ulonglong),
        ("size", c_ulonglong),
        ("write", c_bool),
    ]

class BA(Structure):
    _fields_ = [
        ("security", c_int),
        ("process_id", c_int),
        ("address", POINTER(c_ulonglong)),
    ]

class GA(Structure):
    _fields_ = [
        ("security", c_int),
        ("address", POINTER(c_ulonglong)),
    ]

kernel32 = windll.kernel32
CreateFileW = kernel32.CreateFileW
DeviceIoControl = kernel32.DeviceIoControl
CloseHandle = kernel32.CloseHandle

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3

driver_handle = None
process_id = 0

def setPid(pid: int):
    global process_id
    process_id = pid

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

def open_device() -> bool:
    global driver_handle
    if driver_handle:
        return True
    driver_handle = CreateFileW(
        r"\\.\paysoniscoolio",
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None
    )
    return driver_handle and driver_handle != HANDLE(-1).value

def ioctl_rw(address: int, buffer: bytes, size: int, is_write: bool) -> bytes | int:
    buf = create_string_buffer(buffer, size) if is_write else create_string_buffer(size)
    args = RW()
    args.security = code_security
    args.process_id = process_id
    args.address = address
    args.buffer = addressof(buf)
    args.size = size
    args.write = is_write

    if not DeviceIoControl(driver_handle, code_rw, byref(args), sizeof(args), None, 0, None, None):
        raise OSError("DeviceIoControl RW failed")

    return size if is_write else buf.raw

def read(address: int, size: int) -> bytes:
    return ioctl_rw(address, b'', size, False)

def write(address: int, data: bytes) -> int:
    return ioctl_rw(address, data, len(data), True)

def read_type(fmt: str, address: int) -> int | float:
    return unpack_from(fmt, read(address, sizeof_fmt(fmt)))[0]

def write_type(fmt: str, address: int, value) -> int:
    return write(address, pack(fmt, value))

def sizeof_fmt(fmt: str) -> int:
    from struct import calcsize
    return calcsize(fmt)

def read_int8(address: int) -> int:
    return read_type("<Q", address)

def write_int8(address: int, value: int) -> int:
    return write_type("<Q", address, value)

def read_int4(address: int) -> int:
    return read_type("<I", address)

def write_int4(address: int, value: int) -> int:
    return write_type("<I", address, value)

def read_float(address: int) -> float:
    return read_type("<f", address)

def write_float(address: int, value: float) -> int:
    return write_type("<f", address, value)

def write_bool(address: int, value: bool) -> int:
    return write(address, b'\xFF' if value else b'\x00')

def find_image_base() -> int:
    image_addr = c_ulonglong()
    args = BA()
    args.security = code_security
    args.process_id = process_id
    args.address = pointer(image_addr)

    if not DeviceIoControl(driver_handle, code_ba, byref(args), sizeof(args), None, 0, None, None):
        raise OSError("DeviceIoControl BA failed")

    return image_addr.value

def get_guarded_region() -> int:
    region_addr = c_ulonglong()
    args = GA()
    args.security = code_security
    args.address = byref(region_addr)

    if not DeviceIoControl(driver_handle, code_get_guarded_region, byref(args), sizeof(args), None, 0, None, None):
        raise OSError("DeviceIoControl GA failed")

    return region_addr.value

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

def GetChildren(Instance: int) -> list:
    ChildrenInstance = []
    InstanceAddress = Instance
    if not InstanceAddress:
        return []
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
    InstanceAddress = Instance
    if not InstanceAddress:
        return 0
    ChildrenStart = DRP(InstanceAddress + childrenOffset, True)
    if ChildrenStart == 0:
        return 0
    ChildrenEnd = DRP(ChildrenStart + 8, True)
    OffsetAddressPerChild = 0x10
    CurrentChildAddress = DRP(ChildrenStart, True)
    for i in range(0, 9000):
        if CurrentChildAddress == ChildrenEnd:
            break
        child = read_int8(CurrentChildAddress)
        try:
            if GetName(child) == ChildName:
                return child
        except OSError:
            pass
        CurrentChildAddress += OffsetAddressPerChild
    return 0

def FindFirstChildOfClass(Instance: int, ClassName: str) -> int:
    InstanceAddress = Instance
    if not InstanceAddress:
        return 0
    ChildrenStart = DRP(InstanceAddress + childrenOffset, True)
    if ChildrenStart == 0:
        return 0
    ChildrenEnd = DRP(ChildrenStart + 8, True)
    OffsetAddressPerChild = 0x10
    CurrentChildAddress = DRP(ChildrenStart, True)
    for i in range(0, 9000):
        if CurrentChildAddress == ChildrenEnd:
            break
        child = read_int8(CurrentChildAddress)
        try:
            if GetClassName(child) == ClassName:
                return child
        except OSError:
            pass
        CurrentChildAddress += OffsetAddressPerChild
    return 0

def DoForEveryChild(Instance: int, function):
    InstanceAddress = Instance
    if not InstanceAddress:
        return
    ChildrenStart = DRP(InstanceAddress + childrenOffset, True)
    if ChildrenStart == 0:
        return
    ChildrenEnd = DRP(ChildrenStart + 8, True)
    OffsetAddressPerChild = 0x10
    CurrentChildAddress = DRP(ChildrenStart, True)
    for i in range(0, 9000):
        if CurrentChildAddress == ChildrenEnd:
            break
        function(read_int8(CurrentChildAddress))
        CurrentChildAddress += OffsetAddressPerChild

def setOffsets(nameOffset2: int, childrenOffset2: int):
    global nameOffset, childrenOffset
    nameOffset, childrenOffset = nameOffset2, childrenOffset2
