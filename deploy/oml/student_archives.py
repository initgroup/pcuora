"""Date/sequence names and completed student-package discovery (Korean time)."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

KST = timezone(timedelta(hours=9))
PATTERN = re.compile(r'^oml-student-kit-(\d{8})-(\d{3,})\.zip$')


def archive_key(name):
    match = PATTERN.fullmatch(name)
    if not match:
        return None
    day, sequence = match.groups()
    try:
        datetime.strptime(day, '%Y%m%d')
    except ValueError:
        return None
    number = int(sequence)
    return (day, number) if number > 0 else None


def latest_student_archive(directory):
    directory = Path(directory)
    candidates = [path for path in directory.glob('oml-student-kit-*.zip')
                  if archive_key(path.name) and path.is_file() and not path.is_symlink()
                  and not path.with_name(path.name + '.reserve').exists()]
    return max(candidates, key=lambda path: archive_key(path.name), default=None)


@contextmanager
def reserve_student_archive(directory, *, now=None):
    """Reserve one name; concurrent builds cannot overwrite an earlier package."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    day = (now or datetime.now(KST)).astimezone(KST).strftime('%Y%m%d')
    while True:
        occupied = [archive_key(path.name.removesuffix('.reserve')) for path in directory.iterdir()]
        number = max((key[1] for key in occupied if key and key[0] == day), default=0) + 1
        output = directory / f'oml-student-kit-{day}-{number:03d}.zip'
        reservation = output.with_name(output.name + '.reserve')
        try:
            with reservation.open('x', encoding='ascii') as marker:
                marker.write('Student package build in progress.\n')
        except FileExistsError:
            continue
        if output.exists():
            reservation.unlink()
            continue
        break
    try:
        yield output
    finally:
        reservation.unlink(missing_ok=True)
