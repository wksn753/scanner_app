import requests

def scan_from_escl(url, output_file="scan.jpg"):
    """
    Scan from any eSCL/AirScan printer (HP, Canon, Epson, Brother)
    Example URL: http://192.168.1.100:8080/eSCL
    """
    if not url.endswith("/eSCL"):
        url = url.rstrip("/") + "/eSCL"

    scan_req = """<?xml version="1.0" encoding="UTF-8"?>
    <scan:ScanSettings xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03"
                       xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm">
      <pwg:Version>2.0</pwg:Version>
      <scan:Intent>Document</scan:Intent>
      <scan:InputSource>Platen</scan:InputSource>
      <pwg:ScanRegions>
        <pwg:ScanRegion>
          <pwg:Height>3508</pwg:Height>
          <pwg:Width>2480</pwg:Width>
          <pwg:XOffset>0</pwg:XOffset>
          <pwg:YOffset>0</pwg:YOffset>
        </pwg:ScanRegion>
      </pwg:ScanRegions>
      <pwg:InputAttributes>
        <pwg:MinimumSize>
          <pwg:Width>2480</pwg:Width>
          <pwg:Height>3508</pwg:Height>
        </pwg:MinimumSize>
      </pwg:InputAttributes>
      <scan:DocumentFormatExt>image/jpeg</scan:DocumentFormatExt>
      <scan:XResolution>300</scan:XResolution>
      <scan:YResolution>300</scan:YResolution>
      <scan:ColorMode>RGB24</scan:ColorMode>
    </scan:ScanSettings>"""

    try:
        # Start scan job
        headers = {"Content-Type": "application/xml"}
        r = requests.post(f"{url}/ScanJobs", data=scan_req, headers=headers, timeout=10)
        r.raise_for_status()
        job_url = r.headers["Location"]

        # Get image
        resp = requests.get(f"{job_url}/NextDocument", stream=True, timeout=30)
        resp.raise_for_status()

        with open(output_file, "wb") as f:
            for chunk in resp.iter_content(1024):
                f.write(chunk)

        print(f"eSCL scan saved: {output_file}")
        return output_file

    except Exception as e:
        raise RuntimeError(f"eSCL scan failed: {e}")