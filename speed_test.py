import time
import socket
import threading
import statistics

PING_HOST = "1.1.1.1"
PING_PORT = 80

TEST_HOST = "speed.cloudflare.com"
TEST_PORT = 80

PING_COUNT = 5
DOWNLOAD_BURSTS = 6
UPLOAD_BURSTS = 4
BUFFER_SIZE = 512 * 1024
DOWNLOAD_BYTES = 25000000
UPLOAD_BYTES = 8000000


def _safe_call_progress(cb, pct, msg=None):
    try:
        if cb:
            cb(pct, msg)
    except Exception:
        pass


def measure_ping():
    samples = []

    for _ in range(PING_COUNT):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)

            start = time.time()
            s.connect((PING_HOST, PING_PORT))
            elapsed = (time.time() - start) * 1000
            s.close()

            samples.append(elapsed)

        except Exception:
            continue

    if not samples:
        return None

    return round(statistics.median(samples))


def single_download_burst():
    total = 0

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(6)
        s.connect((TEST_HOST, TEST_PORT))

        request = (
            f"GET /__down?bytes={DOWNLOAD_BYTES} HTTP/1.1\r\n"
            f"Host: {TEST_HOST}\r\n"
            "Connection: close\r\n\r\n"
        )

        s.send(request.encode())

        start = time.time()

        while True:
            data = s.recv(BUFFER_SIZE)
            if not data:
                break

            total += len(data)

            if time.time() - start >= 4:
                break

        elapsed = max(time.time() - start, 1)
        s.close()

        return (total * 8) / elapsed / 1_000_000

    except Exception:
        return None


def single_upload_burst():
    payload = b"0" * UPLOAD_BYTES

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(6)
        s.connect((TEST_HOST, TEST_PORT))

        request = (
            "POST /__up HTTP/1.1\r\n"
            f"Host: {TEST_HOST}\r\n"
            f"Content-Length: {len(payload)}\r\n"
            "Connection: close\r\n\r\n"
        )

        s.send(request.encode())

        start = time.time()
        sent = 0

        while sent < len(payload):
            chunk = payload[sent : sent + BUFFER_SIZE]
            sent_now = s.send(chunk)
            if sent_now <= 0:
                break
            sent += sent_now

        elapsed = max(time.time() - start, 1)
        s.close()

        return (sent * 8) / elapsed / 1_000_000

    except Exception:
        return None


def measure_download(progress_cb=None):
    samples = []

    for i in range(DOWNLOAD_BURSTS):
        pct = 15 + int((i / DOWNLOAD_BURSTS) * 45)
        _safe_call_progress(progress_cb, pct, f"Download burst {i+1}/{DOWNLOAD_BURSTS}")

        speed = single_download_burst()
        if speed:
            samples.append(speed)

    if not samples:
        return None

    median_speed = statistics.median(samples)
    median_speed *= 0.96

    return round(median_speed, 2)


def measure_upload(progress_cb=None):
    samples = []

    for i in range(UPLOAD_BURSTS):
        pct = 65 + int((i / UPLOAD_BURSTS) * 30)
        _safe_call_progress(progress_cb, pct, f"Upload burst {i+1}/{UPLOAD_BURSTS}")

        speed = single_upload_burst()
        if speed:
            samples.append(speed)

    if not samples:
        return None

    median_speed = statistics.median(samples)
    median_speed *= 0.94

    return round(median_speed, 2)


def run_speed_test(progress_cb=None):
    result = {
        "ping": None,
        "download": None,
        "upload": None,
    }

    _safe_call_progress(progress_cb, 5, "Measuring latency...")
    result["ping"] = measure_ping()

    _safe_call_progress(progress_cb, 15, "Testing download...")
    result["download"] = measure_download(progress_cb)

    _safe_call_progress(progress_cb, 65, "Testing upload...")
    result["upload"] = measure_upload(progress_cb)

    _safe_call_progress(progress_cb, 100, "Done")

    return result


def run_speed_test_background(final_cb, progress_cb=None):
    def worker():
        res = run_speed_test(progress_cb)
        final_cb(res)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t
