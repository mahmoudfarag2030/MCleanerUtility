import time
import psutil
import winreg
import os
from pathlib import Path

try:
    import win32pdh
    PDH_AVAILABLE = True
except Exception:
    win32pdh, PDH_AVAILABLE = None, False

try:
    import win32com.client
    WMI_AVAILABLE = True
except Exception:
    win32com, WMI_AVAILABLE = None, False


# =========================================================
# UNINSTALL REGISTRY SCAN
# =========================================================
def scan_uninstall(keyword):
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    found = []

    for hive, path in roots:
        try:
            key = winreg.OpenKey(hive, path)

            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    sub = winreg.OpenKey(key, winreg.EnumKey(key, i))
                    dn, _ = winreg.QueryValueEx(sub, "DisplayName")

                    if keyword.lower() in dn.lower():
                        found.append(dn)

                except Exception:
                    pass

        except Exception:
            pass

    return found


# =========================================================
# CPU SPEED
# =========================================================
class CpuSpeedReader:
    def __init__(self):
        self.pdh_query = None
        self.pdh_counter = None
        self.max_mhz = None

        if WMI_AVAILABLE:
            try:
                for cpu in win32com.client.GetObject("winmgmts:").InstancesOf("Win32_Processor"):
                    self.max_mhz = float(getattr(cpu, "MaxClockSpeed", 0))
                    break
            except Exception:
                pass

        if PDH_AVAILABLE:
            try:
                self.pdh_query = win32pdh.OpenQuery()
                self.pdh_counter = win32pdh.AddCounter(
                    self.pdh_query,
                    r"\Processor Information(_Total)\% Processor Performance"
                )

                win32pdh.CollectQueryData(self.pdh_query)
                time.sleep(0.05)

            except Exception:
                self.pdh_query = None
                self.pdh_counter = None

    def read(self):
        try:
            if self.pdh_query and self.pdh_counter:
                win32pdh.CollectQueryData(self.pdh_query)

                _, val = win32pdh.GetFormattedCounterValue(
                    self.pdh_counter,
                    win32pdh.PDH_FMT_DOUBLE
                )

                return ((float(val) / 100) * self.max_mhz) / 1000 if self.max_mhz else 0

        except Exception:
            pass

        try:
            freqs = psutil.cpu_freq(percpu=True)
            vals = [f.current for f in freqs if f and f.current]

            return sum(vals) / len(vals) / 1000 if vals else 0

        except Exception:
            return 0


# =========================================================
# FILE CHECK
# =========================================================
def file_exists(path):
    try:
        return Path(path).exists()
    except Exception:
        return False


# =========================================================
# MAIN TOOL CHECK
# =========================================================
def check_basic_tools():
    sys32 = Path(os.getenv("SystemRoot", r"C:\Windows")) / "System32"
    wow64 = Path(os.getenv("SystemRoot", r"C:\Windows")) / "SysWOW64"

    results = []

    # ---------------- Visual C++ ----------------
    vc_versions = [
        "Visual C++ 2015",
        "Visual C++ 2013",
        "Visual C++ 2012",
        "Visual C++ 2010",
        "Visual C++ 2008",
        "Visual C++ 2005"
    ]

    for version in vc_versions:
        x64 = any("x64" in x for x in scan_uninstall(version))
        x86 = any("x86" in x for x in scan_uninstall(version))

        results.append((f"{version} x64", "Installed" if x64 else "Missing", ""))
        results.append((f"{version} x86", "Installed" if x86 else "Missing", ""))

    # ---------------- DirectX ----------------
    dx_files = [
        ("DirectX Legacy DX9", sys32 / "d3dx9_43.dll"),
        ("DirectX Legacy DX10", sys32 / "d3dx10_43.dll"),
        ("DirectX Legacy DX11", sys32 / "d3dx11_43.dll"),
        ("XInput 1.3", sys32 / "xinput1_3.dll")
    ]

    for name, file in dx_files:
        results.append((name, "Installed" if file_exists(file) else "Missing", ""))

    # ---------------- .NET ----------------
    dotnet_checks = [
        ("NET Framework 4.8", scan_uninstall(".NET Framework 4.8")),
        ("NET Desktop Runtime 8", scan_uninstall(".NET Runtime 8")),
        ("NET Desktop Runtime 10", scan_uninstall(".NET Runtime 10")),
        ("NET Framework 3.5", scan_uninstall(".NET Framework 3.5")),
    ]

    for name, found in dotnet_checks:
        results.append((name, "Installed" if found else "Missing", ""))

    # ---------------- XNA ----------------
    results.append((
        "XNA Framework 4.0",
        "Installed" if scan_uninstall("XNA Framework Redistributable 4.0") else "Missing",
        ""
    ))

    results.append((
        "XNA Framework 3.1",
        "Installed" if scan_uninstall("XNA Framework Redistributable 3.1") else "Missing",
        ""
    ))

    # ---------------- OpenAL ----------------
    results.append((
        "OpenAL",
        "Installed" if file_exists(sys32 / "OpenAL32.dll") else "Missing",
        ""
    ))

    # ---------------- Java ----------------
    results.append((
        "Java Runtime 8",
        "Installed" if scan_uninstall("Java") else "Missing",
        ""
    ))

    # ---------------- Gaming Platforms ----------------
    results.append((
        "Steam",
        "Installed" if scan_uninstall("Steam") else "Missing",
        ""
    ))

    results.append((
        "Epic Games",
        "Installed" if scan_uninstall("Epic") else "Missing",
        ""
    ))

    results.append((
        "NVIDIA PhysX",
        "Installed" if scan_uninstall("PhysX") else "Missing",
        ""
    ))

    # ---------------- Vulkan ----------------
    results.append((
        "Vulkan Runtime",
        "Installed" if file_exists(sys32 / "vulkan-1.dll") else "Missing",
        ""
    ))

    return results