import os, time
from pathlib import Path
from helpers import file_in_use, format_size

NEW_FILE_PROTECTION_SECONDS = 300

def clean_folder(folder, app, unlock=True):
    files = [Path(r)/f for r, _, fs in os.walk(folder) for f in fs]

    for i, path in enumerate(files):
        try:
            stat = path.stat()
            size = stat.st_size

            if time.time() - stat.st_mtime < NEW_FILE_PROTECTION_SECONDS:
                status = "Protected: Recently modified"
                app.protected_count += 1
            elif file_in_use(path):
                status = "Used by another program"
            else:
                try:
                    path.unlink()
                    app.last_cleaned += 1
                    app.last_size_mb += size/(1024**2)
                    status = "Deleted"
                except PermissionError:
                    app.protected_count += 1
                    status = "Needs Administrator Permission"

            app.root.after(0, lambda r=(path.name, format_size(size), status): app.add_rows_batch([r]))

        except:
            pass

    app.root.after(0, app.update_stats)

    if unlock:
        app.root.after(0, lambda: app.set_busy(False))