import requests

def scan_from_escl(url, output_file="scan.jpg"):
    """
    url example: http://192.168.1.100:8080/eSCL
    """
    # Start scan job
    scan_req = """
    <scan:ScanSettings xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03">
      <scan:InputSource>Platen</scan:InputSource>
      <scan:DocumentFormat>image/jpeg</scan:DocumentFormat>
      <scan:Resolution>
        <scan:XResolution>300</scan:XResolution>
        <scan:YResolution>300</scan:YResolution>
      </scan:Resolution>
    </scan:ScanSettings>
    """
    headers = {"Content-Type": "application/xml"}
    r = requests.post(f"{url}/ScanJobs", data=scan_req, headers=headers)
    job_url = r.headers["Location"]

    # Fetch scanned image
    resp = requests.get(f"{job_url}/NextDocument", stream=True)
    with open(output_file, "wb") as f:
        for chunk in resp.iter_content(1024):
            f.write(chunk)
    return output_file
