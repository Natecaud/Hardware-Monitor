import sys
import os
import subprocess
import platform
import wmi
import pythoncom

# Patch subprocess.Popen on Windows to hide console windows (for both psutil and GPUtil)
if platform.system() == "Windows":
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    # Save the original subprocess.Popen so we can use it without recursion
    original_popen = subprocess.Popen

    # Override subprocess.Popen globally
    subprocess.Popen = lambda *args, **kwargs: original_popen(
        *args,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW,
        **kwargs
    )
else:
    startupinfo = None

# Now import other modules after patching subprocess.Popen
import tkinter
from tkinter import ttk
import psutil
import threading
import queue
import GPUtil
import ctypes

# Suppress console output in the executable if frozen
if getattr(sys, 'frozen', False):
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

# Silence GPUtil debug output
GPUtil.__GPUtil__DEBUG = False
GPUtil.__GPUtil__SILENT = True

# Create a thread-safe queue for metric data
data_queue = queue.Queue()


def get_ohm_exe_path():
    """
    Returns the absolute path to the bundled OpenHardwareMonitor executable.
    When running as a bundled executable, the extra files are in the temporary folder
    specified by sys._MEIPASS.
    """
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    # Build the path relative to the base directory.
    return os.path.join(base_path, "openhardwaremonitor", "OpenHardwareMonitor.exe")


def launch_openhardwaremonitor():
    ohm_path = get_ohm_exe_path()
    try:
        # Use ShellExecuteW with the "runas" verb to request elevation.
        # The last parameter '2' indicates SW_SHOWMINIMIZED.
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", ohm_path, None, None, 2
        )
        if ret <= 32:
            print("Failed to launch OpenHardwareMonitor with elevation/minimized.")
    except Exception as e:
        print(f"Failed to launch OpenHardwareMonitor: {e}")


def get_cpu_temp():
    """Get CPU temperature using WMI with better sensor detection"""
    try:
        w = wmi.WMI(namespace="root\\OpenHardwareMonitor")
        sensors = w.Sensor()
        cpu_temps = []
        for sensor in sensors:
            if sensor.SensorType == "Temperature" and ("CPU" in sensor.Name or "Core" in sensor.Name):
                cpu_temps.append(sensor.Value)
        return max(cpu_temps) if cpu_temps else None
    except Exception as e:
        print(f"Temp error: {str(e)}")  # Only visible in console if not frozen
        return None


def get_gpu_temp():
    # Gets GPU temperatures using GPUtil
    try:
        gpus = GPUtil.getGPUs()
        return gpus[0].temperature if gpus else None
    except Exception:
        return None


def get_disk_usage():
    # Gets usage percentages for all physical drives
    disks = []
    for partition in psutil.disk_partitions():
        if "cdrom" in partition.opts or "removable" in partition.opts:
            continue

        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disks.append({
                "device": partition.device,
                "usage": usage.percent
            })
        except Exception:
            continue
    return disks


def measure_metrics():
    # Initialize COM for this thread
    pythoncom.CoInitialize()
    try:
        while True:
            cpu_usage = psutil.cpu_percent(interval=1)
            ram_usage = psutil.virtual_memory().percent
            gpu_usage = 0.0

            cpu_temp = get_cpu_temp()
            gpu_temp = get_gpu_temp()
            disks = get_disk_usage()

            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu_usage = gpus[0].load * 100
            except Exception:
                pass  # Ignore errors from GPU measurement

            # Put all data in queue
            data_queue.put({
                "cpu_usage": cpu_usage,
                "ram_usage": ram_usage,
                "gpu_usage": gpu_usage,
                "cpu_temp": cpu_temp,
                "gpu_temp": gpu_temp,
                "disks": disks
            })
    finally:
        pythoncom.CoUninitialize()


def update_gui(root, cpu_label, ram_label, gpu_label,
               cpu_temp_label, gpu_temp_label, disk_frame):
    try:
        # Get latest data
        data = data_queue.get_nowait()

        # Update existing labels with one decimal place formatting
        cpu_label.config(text=f"CPU Usage: {data['cpu_usage']:.1f}%")
        ram_label.config(text=f"RAM Usage: {data['ram_usage']:.1f}%")
        gpu_label.config(text=f"GPU Usage: {data['gpu_usage']:.1f}%")

        cpu_temp = data['cpu_temp'] or "N/A"
        gpu_temp = f"{data['gpu_temp']:.1f}" if data['gpu_temp'] else "N/A"
        cpu_temp_label.config(text=f"CPU Temp: {cpu_temp}°C")
        gpu_temp_label.config(text=f"GPU Temp: {gpu_temp}°C")

        for widget in disk_frame.winfo_children():
            widget.destroy()

        for i, disk in enumerate(data['disks']):
            ttk.Label(disk_frame,
                      text=f"{disk['device']}: {disk['usage']}%",
                      font=("System", 14),
                      style="CustomLabel.TLabel").grid(row=i, column=0, sticky="w", padx=20)

    except queue.Empty:
        pass

    root.after(200, update_gui, root, cpu_label, ram_label, gpu_label,
               cpu_temp_label, gpu_temp_label, disk_frame)


# Standard entry-point guard
if __name__ == '__main__':
    # Optionally, launch the bundled OpenHardwareMonitor executable.
    # This assumes you want to run OHM in the background to provide sensor data.
    launch_openhardwaremonitor()

    # GUI setup
    root = tkinter.Tk()
    root.title("Hardware Monitor")
    root.geometry("500x400")
    root.resizable(True, True)
    root.minsize(500, 400)
    root.maxsize(1000, 800)

    # Style and color setup
    root.configure(bg="black")
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TFrame", background="black")
    style.configure("CustomLabel.TLabel", foreground="#1fff00", background="black")

    main_frame = ttk.Frame(root)
    main_frame.grid(row=0, column=0, sticky="nsew")
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    # Configure grid layout
    main_frame.grid_columnconfigure(0, weight=1)
    main_frame.grid_columnconfigure(1, weight=1)
    for i in range(4):
        main_frame.grid_rowconfigure(i, weight=1)

    # Left Column (Usage)
    cpu_label = ttk.Label(main_frame, text="CPU Usage: 0%",
                          font=("System", 18), style="CustomLabel.TLabel")
    cpu_label.grid(row=0, column=0, pady=5, sticky="nsew")

    ram_label = ttk.Label(main_frame, text="RAM Usage: 0%",
                          font=("System", 18), style="CustomLabel.TLabel")
    ram_label.grid(row=1, column=0, pady=5, sticky="nsew")

    GPU_label = ttk.Label(main_frame, text="GPU Usage: 0%",
                          font=("System", 18), style="CustomLabel.TLabel")
    GPU_label.grid(row=2, column=0, pady=5, sticky="nsew")

    # Right Column (Temperatures)
    cpu_temp_label = ttk.Label(main_frame, text="CPU Temp: N/A°C",
                               font=("System", 18), style="CustomLabel.TLabel")
    cpu_temp_label.grid(row=0, column=1, pady=5, sticky="nsew")

    # Placeholder for RAM (no temperature)
    ttk.Label(main_frame, text="", style="CustomLabel.TLabel").grid(row=1, column=1)

    gpu_temp_label = ttk.Label(main_frame, text="GPU Temp: N/A°C",
                               font=("System", 18), style="CustomLabel.TLabel")
    gpu_temp_label.grid(row=2, column=1, pady=5, sticky="nsew")

    # Disk Usage Section
    disk_frame = ttk.Frame(main_frame)
    disk_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=10)
    disk_frame.grid_columnconfigure(0, weight=1)

    # Start measurement thread
    thread = threading.Thread(target=measure_metrics, daemon=True)
    thread.start()

    # Start GUI update loop with all required components
    update_gui(root, cpu_label, ram_label, GPU_label,
               cpu_temp_label, gpu_temp_label, disk_frame)

    root.mainloop()
