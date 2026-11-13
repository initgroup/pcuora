"""Package a learner's completed source and reports. Does not submit to any server."""
import argparse
import re
from html.parser import HTMLParser
from pathlib import Path
import zipfile
from source_files import ROOT, inventory, manifest
from distribution_guard import validate_files


def build(root, student_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]{4,20}', student_id):
        raise ValueError('Invalid student ID for filename.')
    files = inventory(root, audience='student')
    reports = [name for name in files if name.lower() in
               ('submission/report.pdf', 'submission/report.html', 'submission/report.txt')]
    if len(reports) != 1:
        raise ValueError('Complete one report: submission/report.pdf, report.html or report.txt.')
    report_name = reports[0]
    data = files[report_name]
    if Path(report_name).suffix.lower() == '.pdf':
        if not data.startswith(b'%PDF-'):
            raise ValueError('The PDF report does not have a valid PDF header.')
    else:
        text = data.decode('utf-8-sig')
        if not text.strip() or '[[작성]]' in text:
            raise ValueError('Complete the report with your own content before packaging.')
        if report_name.lower().endswith('.html'):
            class ReportText(HTMLParser):
                def __init__(self): super().__init__(); self.text = []
                def handle_data(self, value): self.text.append(value)
            parser = ReportText(); parser.feed(text); text = ' '.join(parser.text)
        if not re.search(r'학번\s*[:：]\s*' + re.escape(student_id) + r'(?![\w-])', text):
            raise ValueError('Student ID must match the report field: [student ID label]: value')
    validate_files(files, root)
    name = 'COM22417_2026H2_' + student_id
    packed = {name + '/' + ('report/' + path.removeprefix('submission/') if path.startswith('submission/') else 'source/' + path): raw
              for path, raw in files.items()}
    output = root / 'downloads' / (name + '.zip')
    output.parent.mkdir(exist_ok=True)
    temporary = output.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path, raw in packed.items(): archive.writestr(path, raw)
        archive.writestr(name + '/MANIFEST.sha256.json', manifest(packed))
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip(): raise ValueError('Archive integrity check failed.')
    temporary.replace(output)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--student-id', required=True)
    args = parser.parse_args()
    try:
        print('Created: ' + str(build(ROOT, args.student_id)))
        print('Review the ZIP, then upload it to the submission destination announced in class.')
    except ValueError as error:
        raise SystemExit(str(error)) from None
