import platform
import os
from backends import sane_backend, twain_backend
from backends.escl_backend import scan_from_escl

class ScannerManager:
    def __init__(self):
        self.os = platform.system().lower()
        self.is_render = os.getenv("RENDER") == "true"
        self.is_render = os.getenv("RENDER") == "true"

        if self.is_render:
        self.is_render = os.getenv("RENDER") == "true"
            print("Running on Render → using pure eSCL")
            self.backend = "escl"
        elif self.os in ["linux", "darwin"]:
            try:
                self.backend = sane_backend.SaneBackend()
                print("Using SANE backend")
            except Exception as e:
                print(f"SANE failed ({e}), falling back to eSCL")
                self.backend = "escl"
        elif self.os == "windows":
            self.backend = twain_backend.TwainBackend()
        else:
            self.backend = "escl"

    def list_scanners(self):
        if self.backend == "escl":
            return []  # Auto-discover via frontend
        return self.backend.list_scanners()

    def scan(self, scanner_id, output_file="scan.png"):
        if self.backend == "escl":
            raise RuntimeError("Use scan_network_escl() on Render")
        return self.backend.scan(scanner_id, output_file)

    def scan_network_escl(self, url, output_file="scan.jpg"):
        return scan_from_escl(url, output_file)